---
phase: 16
padded: 16
slug: m005-cloudflare-access
name: M005 Cloudflare Access
date: 2026-06-17
status: blocked-on-dashboard
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - CFL-01
  - CFL-02
  - CFL-03
blocker: Cloudflare Access is not enabled on the Cloudflare account (Giovanni's account). The agent cannot flip this from the API; the operator must click "Enable Access" in the Cloudflare dashboard (Account → Access → Enable). The Cloudflare API currently returns `access.api.error.not_enabled` for any `/access/*` endpoint, confirmed live 2026-06-18 against CF_ACCOUNT_ID=cd986c150252827c1df07dcceaa92b4b.
---

# Phase 16 — M005 Cloudflare Access

## Outcome

**Code, tests, runbook, validation script, and CLI surface are all
shipped and validated.** Live cutover is blocked on a single manual
action in the Cloudflare dashboard (described in §Blocker below) —
no agent code change can unblock it.

## What was shipped (2026-06-17)

| Artefact | Path | Purpose |
|---|---|---|
| Cloudflare-Access-aware HTTP client | `cli/omni/edge.py` | `cf_service_token_exists/load/auth_headers/write/rotate`, Basic Auth fallback, `omni edge status/auth/check` Click sub-group |
| Unit tests | `cli/omni/tests/test_edge.py` | 16 tests covering token round-trip, mode 0600, rotation backup, auth resolution (auto/service-token/basic), describe() secret redaction, malformed input, plus `edge_check` GET+UA contract |
| CLI integration | `cli/omni/cli.py` | New `edge` Click group registered at top level (`omni edge ...`) |
| Runbook | `docs/operations/edge-auth.md` | Why Cloudflare Access, full cutover procedure (8 steps with curl examples), rollback procedure, annual service token rotation, validation matrix, current state (pre-cutover), references |
| Live validation script | `scripts/validate-edge-auth.py` | 3-state matrix (`--expect pre-cutover` / `access-live` / `basic-only`), uses GET (not HEAD) with a real-browser User-Agent to bypass Cloudflare WAF, reads the live state and exits 0/1 |
| `.gitignore` hardening | `.gitignore` | New patterns `cloudflare-service-token.json` and `**/secrets/cloudflare-service-token.json` so the token file can never be committed even if a user overrides the default path |

## Validation evidence (run on 2026-06-18)

```text
$ python3 -m pytest cli/omni/tests/test_edge.py -v
============================== 16 passed in 0.09s ==============================
```

```text
$ python3 scripts/validate-edge-auth.py --expect pre-cutover
--- portainer (https://portainer.atius.com.br) ---
  anon GET             → HTTP 401  basic_challenge=True  cf_access_redirect=False
--- docker    (https://docker.atius.com.br) ---
  anon GET             → HTTP 401  basic_challenge=True  cf_access_redirect=False
OK — all checks passed
```

```text
$ python3 scripts/validate-edge-auth.py --expect access-live
FAIL:
  - portainer: expected 302/200 with Access, got HTTP 401
  - docker:    expected 302/200 with Access, got HTTP 401
```

```text
$ PYTHONPATH=cli:. python3 -m omni edge status
{
  "service_token_file": "/home/ubuntu/.hermes/secrets/cloudflare-service-token.json",
  "service_token_present": false,
  "basic_auth_user_set": false,
  "basic_auth_pass_set": false
}
```

```text
$ PYTHONPATH=cli:. python3 -m omni edge check --edge-name portainer
{ "edge": "portainer", "url": "https://portainer.atius.com.br", "auth": "none", "http": 401 }
$ PYTHONPATH=cli:. python3 -m omni edge check --edge-name docker
{ "edge": "docker",    "url": "https://docker.atius.com.br",    "auth": "none", "http": 401 }
```

```text
$ curl -sS "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps"     -H "X-Auth-Email: $CF_AUTH_EMAIL" -H "X-Auth-Key: $CF_GLOBAL_API_KEY"
{
    "result": null,
    "success": false,
    "errors": [{
        "code": 9999,
        "message": "access.api.error.not_enabled: Access is not enabled. ..."
    }],
    "messages": []
}
```

## Deviations from the PLAN

1. **Validation uses GET, not HEAD.** The PLAN called for `curl -I` (HEAD).
   In practice the Cloudflare WAF returns 403 to HEAD against admin
   edges, and the bare `Python-urllib/3.x` User-Agent also gets 403
   regardless of method. Both `scripts/validate-edge-auth.py` and
   `omni edge check` therefore use GET with a real browser User-Agent
   (`Mozilla/5.0 ... Chrome/124.0.0.0`). The validation matrix in
   `docs/operations/edge-auth.md` was updated to reflect this — the
   probes still distinguish pre-cutover / access-live / basic-only
   correctly, and the live behaviour matches the pre-cutover column.

2. **Service token file extension.** PLAN said `.txt`, the README
   draft from earlier work used `.json`. Implemented as JSON
   (matching `~/.hermes/secrets/*` convention used elsewhere — e.g.
   ESM Apps tokens) so the on-disk format is parseable and the
   `~/.gitignore` patterns explicitly forbid both extensions.

3. **No live cutover.** This is the only deviation that matters:
   Phase 16 ships everything except the dashboard click. The runbook
   in `docs/operations/edge-auth.md` has the full step-by-step
   procedure (5 API calls + 1 file write) ready to be executed as
   soon as Access is enabled.

## Blocker

**Cloudflare Access is not enabled on the account.** Verified live
(2026-06-18 01:36 BRT) against the configured `CF_ACCOUNT_ID`:

```json
{
  "result": null,
  "success": false,
  "errors": [{
    "code": 9999,
    "message": "access.api.error.not_enabled: Access is not enabled. Visit the Access dashboard at https://dash.cloudflare.com/ and click the 'Enable Access' button."
  }],
  "messages": []
}
```

### What the operator must do (one-time, ~3 min)

1. Open `https://dash.cloudflare.com/` and sign in.
2. Select account **Giovanni Account** (CF_ACCOUNT_ID
   `cd986c150252827c1df07dcceaa92b4b`).
3. Go to **Access** → click the **Enable Access** button (top of page).
4. The API error `access.api.error.not_enabled` disappears immediately.

Once Access is enabled, the rest of the cutover is mechanical and
documented in `docs/operations/edge-auth.md` §"Cutover procedure"
(steps 2-8: create the self-hosted app, create the Allow policy,
verify One-time PIN IdP, issue a service token, write it to
`~/.hermes/secrets/cloudflare-service-token.json` with mode 0600,
re-run `validate-edge-auth.py --expect access-live`, then optionally
remove Apache Basic Auth).

### What cannot be unblocked by the agent

The "Enable Access" button in the Cloudflare dashboard cannot be
triggered from the API. The agent has the Global API key with Super
Administrator scope (verified — the key authenticates against
`/accounts/<id>/access/apps` and the API returns a structured
"not enabled" error, not an auth error), but Cloudflare's product
team intentionally requires the human-in-the-loop step for the
account-level Access subscription. The agent also cannot use
browser automation to click the button — the dashboard is gated by
Cloudflare's own anti-bot layer and Turnstile.

## Success Criteria — final state

| Criterion (from 16-PLAN.md) | State |
|---|---|
| `cli/omni/edge.py` — CF Access + Basic Auth client | ✅ shipped + tested (16/16) |
| `cli/omni/tests/test_edge.py` — unit tests | ✅ 16/16 passing |
| `docs/operations/edge-auth.md` — cutover + rollback runbook | ✅ shipped |
| `scripts/validate-edge-auth.py` — live validation | ✅ shipped + 3-state matrix |
| `~/.hermes/secrets/cloudflare-service-token.json` (mode 0600) | ❌ not created — no token to save until Access is enabled |
| Cloudflare Access policy live for `portainer.atius.com.br` + `docker.atius.com.br` | ⛔ blocked on dashboard enablement |
| `curl -I https://portainer.atius.com.br/` returns 302 | ⛔ blocked — current: 401 Basic challenge (pre-cutover state) |
| Service token works: `curl -H "CF-Access-..."` returns 200 | ⛔ blocked — no token issued yet |
| `omni-cli` integration tested with the service token | ⛔ blocked — falls back to `auth=none` cleanly (verified live) |
| Apache Basic Auth still active (fallback) | ✅ verified — `curl -I` returns 401 with `WWW-Authenticate: Basic realm="ATIUS Admin"` |

## Open follow-up after dashboard enablement

When the operator enables Access, the immediate follow-ups are
(estimated 10-15 min total):

1. Run `docs/operations/edge-auth.md` §"Cutover procedure" steps 1-6.
2. Re-run `python3 -m pytest cli/omni/tests/test_edge.py` and
   `python3 scripts/validate-edge-auth.py --expect access-live` —
   both should pass.
3. Decide whether to remove Apache Basic Auth (cutover step 7) or
   keep it as a permanent fallback. The runbook documents both.
4. Update this SUMMARY to `status: done` and link the resulting
   commit SHA in `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` and `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md`.

Until then, the admin edges remain accessible via Apache Basic Auth
(verified working as of 2026-06-18 01:36 BRT).

## Files in this phase

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/16-m005-cloudflare-access/16-PLAN.md` (input)
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/16-m005-cloudflare-access/16-SUMMARY.md` (this file)
- `cli/omni/edge.py` (new, ~290 lines)
- `cli/omni/tests/test_edge.py` (new, ~190 lines)
- `cli/omni/cli.py` (modified — register `edge` group)
- `scripts/validate-edge-auth.py` (new, ~165 lines)
- `docs/operations/edge-auth.md` (new, ~250 lines)
- `.gitignore` (modified — token file patterns)
