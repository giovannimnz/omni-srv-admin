# Edge Auth — Cloudflare Access + Apache Basic Auth (Phase 16 / M005)

**Status:** ready (Phase 16 PLAN executed 2026-06-17 — Access not yet enabled in Cloudflare account; see "Current State" below)

**Scope:** `portainer.atius.com.br` and `docker.atius.com.br`.

**Goal:** replace the Apache Basic Auth prompt with Cloudflare Access
SSO (email one-time PIN), while keeping Basic Auth as a documented
fallback in case Cloudflare Access is unavailable.

---

## Current State (2026-06-17)

- Both `portainer.atius.com.br/` and `docker.atius.com.br/` return
  `401 Unauthorized` with a `WWW-Authenticate: Basic realm="ATIUS Admin"`
  challenge served by Apache2.
- Cloudflare Access is **not** enabled on the account yet. The
  Cloudflare API answers
  `access.api.error.not_enabled: Access is not enabled. Visit the
  Access dashboard at https://dash.cloudflare.com/ and click the
  'Enable Access' button.` for any `/access/*` endpoint.
- No service token has been issued yet (none possible until Access is
  enabled in the dashboard).
- `omni-cli` already has a Cloudflare-Access-aware client module
  (`cli/omni/edge.py`) that auto-falls-back to Basic Auth.

## Why Cloudflare Access

- Free tier covers up to 50 users (we have 1 admin today).
- SSO via email one-time PIN — no credential fatigue.
- Centralized audit log in the Cloudflare dashboard.
- Service token lets cron jobs and `omni-cli` call the admin edge
  without interactive SSO.

## Constraints / Risks

- **Account tier:** free — 50 users max. Documented in 16-PLAN.md
  Risks. If team grows past 50, plan to upgrade.
- **Access outage = total admin edge loss.** Mitigation: Apache Basic
  Auth stays enabled and the `omni edge check` command shows
  `auth=none` clearly when neither is configured.
- **Service token rotation:** annually per Cloudflare dashboard.
  Procedure in §"Service token rotation" below.
- **Anti-bot / Turnstile:** Cloudflare browser automation is blocked.
  All Access operations happen via the API or via the operator's
  authenticated dashboard session — never via `browser_navigate` /
  Playwright.

---

## Cutover procedure (Cloudflare Access ON, Basic Auth OFF)

Pre-conditions: Access enabled in the Cloudflare dashboard (UI step
"Enable Access" — cannot be done from the API), a service token
generated, and the token file present on SRV-1.

1. **Verify Access is enabled and reachable from the API:**
   ```bash
   curl -sS "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps" \
     -H "X-Auth-Email: $CF_AUTH_EMAIL" \
     -H "X-Auth-Key: $CF_GLOBAL_API_KEY" | python3 -m json.tool
   ```
   Expect HTTP 200 and `result: [...]` (or `result: null` when no
   apps exist yet — the error `access.api.error.not_enabled` must be
   gone).

2. **Create the self-hosted Access application** with the two
   domains:
   ```bash
   curl -sS "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps" \
     -H "X-Auth-Email: $CF_AUTH_EMAIL" \
     -H "X-Auth-Key: $CF_GLOBAL_API_KEY" \
     -H "Content-Type: application/json" \
     -X POST \
     -d '{
       "name": "Atius Admin Edge",
       "type": "self_hosted",
       "domain": "portainer.atius.com.br,docker.atius.com.br",
       "session_duration": "24h",
       "allowed_idps": [],
       "auto_redirect_to_identity": false
     }' | tee /tmp/access-app.json
   ```
   Copy the `id` from the response — you will need it for the policy.

3. **Create the Allow policy** (email allowlist):
   ```bash
   APP_ID=$(jq -r .result.id /tmp/access-app.json)
   curl -sS "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps/$APP_ID/policies" \
     -H "X-Auth-Email: $CF_AUTH_EMAIL" \
     -H "X-Auth-Key: $CF_GLOBAL_API_KEY" \
     -H "Content-Type: application/json" \
     -X POST \
     -d '{
       "name": "Allow Giovanni",
       "decision": "allow",
       "include": [
         { "email": { "email": "giovannimunizds@hotmail.com" } }
       ],
       "require": [],
       "exclude": []
     }' | tee /tmp/access-policy.json
   ```

4. **Enable the One-time PIN identity provider** (default in
   dashboard; verify via API):
   ```bash
   curl -sS "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/identity_providers" \
     -H "X-Auth-Email: $CF_AUTH_EMAIL" \
     -H "X-Auth-Key: $CF_GLOBAL_API_KEY" | python3 -m json.tool
   ```
   Confirm the `onetimepin` IdP is present and active.

5. **Issue the service token** in the dashboard
   (Access → Service Auth → Generate token → Name
   `omni-cli-automation`, Duration 1 year). Copy the `Client ID` and
   `Client Secret`. Persist to disk:
   ```bash
   python3 -c "
   from omni.edge import write_cf_service_token
   p = write_cf_service_token('<CF_CLIENT_ID>', '<CF_CLIENT_SECRET>')
   print('wrote', p)
   "
   ```
   File lives at `~/.hermes/secrets/cloudflare-service-token.json`,
   mode `0600`. It is **not** committed to the repo
   (`.gitignore` rejects it).

6. **Validate the cutover:**
   ```bash
   omni edge status           # service_token_present: true, octal 0o600
   omni edge auth --prefer service-token
   omni edge check --edge-name portainer --prefer service-token   # expect 200
   omni edge check --edge-name docker   --prefer service-token   # expect 200
   curl -sI https://portainer.atius.com.br/   # expect 302 to CF Access login
   curl -sI https://docker.atius.com.br/      # expect 302 to CF Access login
   ```

7. **Remove Apache Basic Auth** (only after the 200 + 302 above):
   - Edit `/etc/apache2/sites-enabled/portainer.atius.com.br-le-ssl.conf`
     and the equivalent `docker.atius.com.br-le-ssl.conf` vhost and
     drop the `<Location />` / `AuthType Basic` block.
   - `sudo apache2ctl configtest && sudo systemctl reload apache2`.
   - Re-run step 6; expect `http: 200` (or 302) and no
     `WWW-Authenticate: Basic` header.

8. **Update the cutover gate doc** — `.planning/STATE.md` "M005
   Follow-ups" section moves Cloudflare Access from
   `follow-up before broad Portainer sharing` to
   `✅ Cloudflare Access live — email allowlist; service token
   working; Basic Auth removed`.

---

## Rollback procedure (Access OFF, Basic Auth back ON)

Use this if Access is misbehaving (lockout, false-positive block,
outage) and you need admin access back **right now**.

1. **Operator dashboard:** Cloudflare → Account → Access → Applications
   → `Atius Admin Edge` → toggle `Application is enabled` off.
   Service tokens are also temporarily revoked via the same toggle
   for the application. (It is a per-app switch — the org still has
   Access enabled, but the policy stops evaluating.)

2. **Bring Basic Auth back online** (only needed if it was already
   removed in cutover step 7):
   ```bash
   sudo a2enconf atius-admin-edge-basic-auth   # if a conf was dropped
   sudo systemctl reload apache2
   curl -sI -u "$OMNI_ADMIN_EDGE_BASIC_USER:$OMNI_ADMIN_EDGE_BASIC_PASS" \
        https://portainer.atius.com.br/        # expect 200
   ```

3. **Cron job smoke** — if the service token is still needed for
   automation but the app is disabled, the `omni edge auth` will
   resolve to `label=cf-service-token` but `omni edge check` will
   return a 302 (CF Access is no longer gating but the application
   is down). Re-enable the application in the dashboard.

4. **Post-incident** — file a `60-LOGS/2026-MM-DD-cloudflare-access-incident.md`
   note with: timestamp, cause, mitigation, follow-up actions, and
   rollback duration.

---

## Service token rotation (annual)

1. Generate a new token in the Cloudflare dashboard (Access → Service
   Auth → Generate token). Note: tokens cannot be issued from the
   API — they require a human in the dashboard.
2. Persist it (overwrites the existing file, with `.bak` backup):
   ```bash
   python3 -c "
   from omni.edge import rotate_cf_service_token
   p = rotate_cf_service_token('<NEW_CF_CLIENT_ID>', '<NEW_CF_CLIENT_SECRET>')
   print('rotated', p)
   "
   ```
3. Revoke the old token in the dashboard.
4. Update any operator runbook that referenced the old
   `CF_CLIENT_ID` literal (typically none — the file path is the
   contract).
5. Smoke: `omni edge check --edge-name portainer --prefer service-token`
   → 200.

---

## Validation matrix

| Check | Pre-cutover (now) | Post-cutover target | Post-rollback |
|---|---|---|---|
| `curl -sI https://portainer.atius.com.br/` (no creds) | 401 Basic challenge | 302 → CF Access login | 401 Basic challenge |
| `omni edge check --edge-name portainer` (no creds) | 401 (or 403 with mock token) | 302 | 401 |
| `omni edge check --edge-name portainer --prefer service-token` (no Access) | 403 | 200 | 403 |
| `omni edge check --edge-name portainer --prefer service-token` (Access live) | n/a | 200 | n/a |
| `omni edge check --edge-name portainer --prefer basic` (Basic creds set) | 200 | 200 (still allowed) | 200 |
| Direct origin (10.1.1.1:9444 via VPN) | 200 (Basic Auth) | 200 (Basic Auth) | 200 (Basic Auth) |

The "Direct origin" line is the manual proof that Basic Auth is the
underlying authentication and that Cloudflare Access is just an SSO
shim on top — without Access, the admin edge is still functional from
the VPN.

---

## Files in this cutover

| File | Purpose |
|---|---|
| `cli/omni/edge.py` | Cloudflare-Access-aware HTTP client (service token + Basic Auth fallback) |
| `docs/operations/edge-auth.md` | This runbook |
| `~/.hermes/secrets/cloudflare-service-token.json` | Service token (mode 0600, not in git) |
| `.planning/phases/16-m005-cloudflare-access/16-PLAN.md` | Phase 16 plan |
| `.planning/phases/16-m005-cloudflare-access/16-SUMMARY.md` | Phase 16 execution summary |

---

## References

- Cloudflare Access docs: <https://developers.cloudflare.com/cloudflare-one/policies/access/>
- Cloudflare API: <https://developers.cloudflare.com/api/operations/access-applications-list-applications>
- Phase 16 plan: `.planning/phases/16-m005-cloudflare-access/16-PLAN.md`
- Phase 13 live bootstrap (where the Basic Auth was set up):
  `.planning/phases/13-k3s-ha-portainer-oci/13-LIVE-BOOTSTRAP-2026-06-14.md`
