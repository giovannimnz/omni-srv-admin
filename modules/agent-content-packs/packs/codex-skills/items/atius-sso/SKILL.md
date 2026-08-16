---
name: atius-sso
description: Understand, mount, include, validate, operate, or remove Atius SSO integrations while preserving the canonical login and destination lifecycle.
---

# Atius SSO

Use this single skill for cross-system Atius SSO work. Do not create a competing
SSO skill.

## Read first

Always read:

- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-manual-index.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-operations-manual.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-wide-sso.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-application-playbook.md`
- `/home/ubuntu/GitHub/omni-srv-admin/docs/domain/atius-sso-lifecycle-matrix.md`
- `/home/ubuntu/GitHub/obsidian-vault/AiSecondBrain/30-RECURSOS/atius/SSO-Atius-Guia-Canonico.md`
- `/home/ubuntu/GitHub/omni-srv-admin/.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`

For an app-specific job, also read its local SSO document if one exists.

Then read:

- `references/source-of-truth.md`
- `references/lifecycle-acceptance.md`

## Normative contract

- The canonical human URL is `https://<app>.atius.com.br/login`.
- `/login` uses an internal rewrite or a minimal proxy so the browser keeps
  `/login` visible while the internal ATS shell is served.
- `/sso` is internal or a controlled compatibility surface. Never publish an
  external redirect from `/login` to `/sso`.
- A legacy `/sso` request may bootstrap a validated same-origin destination,
  but must land on a clean `/login`; the public app URL must not retain
  `return_to`.
- Destination state is explicit: `valid`, `missing`, or `rejected`. Only
  `valid` contains an application URL. Missing, expired, or rejected context is
  neutral and never implies `trade.atius.com.br`.
- The visible `Destino seguro` value for a valid application is the bare
  hostname only (`URL.hostname`). Never show scheme, port, trailing slash,
  path, query, or fragment in that field. Example:
  `https://ssh.atius.com.br/compute` renders as `ssh.atius.com.br`. Keep the
  complete validated URL unchanged for allowlist enforcement, redirects,
  logout, re-entry, and return. Direct central neutral state remains
  `Nenhum destino selecionado`.
- The validated lifecycle spans entry, login, logout-complete, re-entry, and
  return.
- The central host/path allowlist is authoritative. Validate scheme, exact host,
  default HTTPS port, bounded path, encoding, suffix confusion, userinfo, and
  protocol-relative input.
- Canonical central logout is `POST https://sso.atius.com.br/api/sso/logout`
  with the real browser `Origin`, `Content-Type: application/json`, and a
  session-bound one-time `X-CSRF-Token`.
- Logout rejects `GET`, missing or wrong Origin, wrong content type, missing or
  invalid CSRF, and CSRF replay before mutation. Examples must never forge
  `Origin`.
- An app-local logout facade owns one exact operation only. It may proxy the
  exact central logout endpoint and must never expose the general ATS API.
- The central completion URL is `https://sso.atius.com.br/login`; application
  context is carried separately in validated short-lived state.

Direct central `/login` with no valid destination has this exact neutral state:

- heading: `Sessão Atius ativa`
- body: `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- label: `Destino seguro`
- value: `Nenhum destino selecionado`
- URL: `https://sso.atius.com.br/login`
- no `Entrar novamente`, `Voltar para`, application link, or substitute
  application control

The shared session cookie is `auth-token`. Session validation remains
`GET https://api.atius.com.br/v1/auth/me`. HashiCorp Vault is the only secret
source of truth.

## Job types

Choose exactly one:

- `understand`
- `mount`
- `include`
- `validate`
- `operate`
- `remove`

`mount` means a new integration from zero. `include` means adding an app to an
existing central contract. `operate` covers owner-side runtime work after the
governed release gates.

## Mount or include

1. Classify the app:
   - ATS-native host;
   - app with its own backend;
   - proxy for an internal resource.
2. Define the exact public host, protected paths, and explicit public
   exceptions.
3. Define the internal backend and the name of the server-side credential.
4. Update the central return policy in
   `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`.
5. Implement the exact app-local surface:
   - canonical `/login` backed by internal rewrite/minimal proxy;
   - controlled legacy `/sso` handling that lands cleanly on `/login`;
   - fixed forwarded host/proto/port and exact ATS CORS origin;
   - same-origin transient bootstrap with no persistent public query;
   - local middleware/gate;
   - local session-validation endpoint;
   - authenticated server-side proxy for any private backend;
   - exact/minimal local logout facade using POST/Origin/JSON/one-time CSRF.
6. Run the complete lifecycle matrix in
   `references/lifecycle-acceptance.md`.
7. Record repo documentation and the canonical owner references. Obsidian and
   GBrain synchronization occurs only in the governed knowledge closeout.

The 2026-07-31 sealed recovery scope approved the live AdGuard app-local
facade for that scope. Future AdGuard feature expansion still needs its own
lifecycle evidence; a central allowlist entry alone is not approval.

## Validate

Validation is lifecycle-wide. A first redirect is never approval. A single login is also not approval for app-local SSO: for each public app host, run at least two consecutive browser cycles (anonymous access -> `/login` -> authenticated app -> logout -> `/login` -> relogin) and prove the visible origin never changes to `sso.atius.com.br` during the human app flow. The logout step must click the real visible app control; direct navigation to `/logout` does not prove the product UX. The authenticated screenshot must wait for an app-specific ready marker and reject loading/error states. For data dashboards, inspect every visible panel: `Sem dados`, `No data`, persistent loading, datasource errors, or query errors are FAIL even when other panels have data. A bounded E2E time window is allowed only when it renders real datasource series; never manufacture metric samples.

For browser-based remote desktops, the SSO shell and logout control do not prove readiness. Require a non-blank framebuffer in the visible noVNC region, using stable desktop landmarks or a pixel-diversity/non-black gate with timeout. A black canvas is FAIL. Avoid version-specific canvas selectors unless the live noVNC DOM proves them; a viewport-region gate is more portable.

When an app can complete same-origin authentication while Playwright is filling the login form, an input-detached error is not automatically failure or success. Accept it only after the browser is on the exact app origin outside `/login` and the app-specific authenticated ready marker passes. Origin change, staying on `/login`, or missing readiness remains FAIL.

If the user provides a visual/login model such as `ssh.atius.com.br/login`, functional PASS is still incomplete until screenshot evidence is visually compared against that model and each app-local `/login` passes the required brand/layout elements.

Session-validation adapters must not fan out `GET /v1/auth/me` per asset/request. Use a short positive cache and coalesce concurrent checks per token/origin. Preserve semantics: `401/403` means invalid/forbidden; `429`, `5xx`, timeout, or transport failure means temporary auth unavailability and must never be rendered as bad credentials. Do not weaken or raise the central rate limit to mask adapter amplification.

URL-standard traps validated on 2026-07-31:

- Do not treat a one-shot `atius_sso_login_return_to` cookie as persistent browser state. In the legacy `/sso?return_to=...` path, the HTTP response must set a short-lived `Secure; HttpOnly; SameSite=Lax; Max-Age=600` carrier, but the final browser-visible `/login` render should consume it and leave no persistent `return_to` cookie. Browser gates should verify clean final URL and no persistent cookie; use HTTP/header probes to prove the transient carrier.
- Do not put `ProxyPassReverseCookiePath / /<app>/` at broad vhost scope when the same vhost proxies the ATS `/login` facade. It rewrites the SSO carrier cookie path and can prevent `/login` from receiving it. Scope cookie-path rewriting to the protected app location only, e.g. `<Location /mt5/> ProxyPassReverseCookiePath / /mt5/ </Location>`.

Next.js middleware runs in the Edge runtime by default. Do not import server-only SDK code that uses `node:crypto`, `fs`, DB clients, or Node-only APIs into middleware. Use an edge-compatible adapter path (`crypto.subtle`, `fetch`, type-only imports from core) and keep Node/server SDKs behind route handlers or server components. Gate with both middleware bundle/typecheck and `next build` before declaring the Next adapter ready.

Required automated and headless coverage:

Before running the harness, always choose an exclusive evidence directory. Supported precedence is `--evidence-dir`, positional output directory, `E2E_OUTPUT_DIR`, then the legacy default. Never let an ad-hoc subset write into a historical/default evidence pack. If that happens, preserve a checksummed backup, identify the canonical owner, and remove only the contaminated untracked default.

Any temporary `next start`/rollback smoke must use a non-production port and be reconciled at closeout. Before stopping a late process, compare PID, cwd, cgroup, listener, PM2/systemd ownership, Apache `ProxyPass`, and the production unit. A process with deleted rollback cwd, no supervisor owner, and no Apache reference is an orphan smoke; stop only that PID gracefully, prove its port released, then rerun the affected app lifecycle and visual review. Never infer production ownership from a matching UI or `Ready` line alone.

1. anonymous entry;
2. canonical `/login` stays visible;
3. successful authentication reaches the same validated destination;
4. central POST logout reaches the fixed completion URL;
5. logout-complete displays the same validated destination;
6. `Entrar novamente` reuses that destination;
7. `Voltar para` returns to that destination;
8. missing and rejected destination states render the exact neutral tuple;
9. GET, wrong-Origin, wrong-content-type, missing/invalid/replayed-CSRF logout
   requests fail closed without mutation;
10. cross-origin, suffix, userinfo, protocol-relative, port, path, and encoding
    destination inputs fail closed;
11. browser automation is headless and retains sanitized evidence;
12. rollback and reapply readbacks pass.

Check the machine contract:

```bash
node /home/ubuntu/GitHub/omni-srv-admin/scripts/validate-atius-sso-lifecycle-contract.mjs \
  --contract /home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json \
  --report /path/to/private/report.json
```

Do not call a new integration, expansion, or migration complete while its own
runtime/browser promotion evidence is absent. Phase 10 plans 10-04 and 10-05 are
materialized for the sealed 2026-07-31 fleet scope; future scopes need fresh
evidence.

## Remove

1. Capture the current allowlist, facade, session, logout, docs, and runtime
   readback plus a recoverable backup.
2. Remove the exact host/path from the central allowlist.
3. Remove or adapt app-local `/login`, legacy `/sso`, middleware, session,
   logout, and authenticated proxy surfaces.
4. Prove the app no longer depends on `auth-token`, `/v1/auth/me`, the central
   login/logout endpoints, or an ATS-authenticated server-side proxy.
5. Run positive survivors and negative removed-app cases across the complete
   lifecycle.
6. Roll back by restoring the backed-up policy/facade, rerunning the exact
   contract audit, and proving readback. Do not improvise a parallel login.
7. Update owner documentation; schedule Obsidian/GBrain/Graphify closeout
   through the owning phase.

## Understand

Report:

- which app host owns the visible `/login`;
- which central host owns login/logout policy;
- which host owns IdP/OIDC;
- which service validates the ATS session;
- which exact app targets are allowlisted;
- how the five-stage destination lifecycle behaves;
- how POST/Origin/JSON/one-time-CSRF logout behaves;
- where secrets come from;
- which rollback/readback gates remain.

Do not invent architecture beyond code, machine contract, owner manuals, and
runtime evidence.

## Authorization control plane boundary

A central authorization control plane is planned in
`/home/ubuntu/GitHub/atius-sso/.planning/phases/01-authorization-control-plane/`.
Treat it as architecture/planning until implementation, governed rollout, and
fresh browser/runtime evidence are complete.

Locked planning boundary:

- admin UI: `https://sso.atius.com.br/admin/permissions`;
- Keycloak remains identity/OIDC only;
- `/v1/auth/me` remains the compatible session-validation endpoint;
- fine authorization uses a separate `/v1/authz/*` boundary;
- backend/gateway PEPs are authoritative; hidden UI is not enforcement;
- app/resource/action catalogs come from versioned application manifests;
- canonical actions are `view`, `read`, `write`, `execute`, `approve`, and
  `manage`;
- default deny, explicit deny over allow, fail closed on decision-path failure;
- current live evidence remains host-local lifecycle evidence with
  `centralOidcFlow=false`; do not claim the planned authorization plane is live;
- live rollout and final fleet acceptance require the explicit human gates in
  plans `01-09` and `01-10`.

Authorization security proof must also cover:

- cross-process revocation through a monotonic policy/user/session epoch; local
  cache invalidation hooks alone do not prove the <=5s SLO;
- established-channel revocation for WebSocket/SSE, noVNC/RDP, VPN peers, and
  Docker/API sockets before claiming protocol/data-plane enforcement;
- PostgreSQL role separation: migration/DDL owner, runtime resolver/auth-server
  roles without direct policy/grant/audit DML, and a dedicated append-only audit
  writer behind an allowlisted function;
- operational break-glass independent of normal policy availability: sealed
  loopback/local CLI, two humans plus MFA, minimal short-lived scope,
  `BREAK_GLASS_APPROVED_UNTIL`, and a permission-restricted hash-chained local
  spool when central audit is unavailable. Replay/readback to central audit is
  mandatory before closure;
- privileged OIDC negative cases: missing prelink, duplicate/unverified/changed
  email, subject/link conflict, callback replay, and state/nonce mismatch.

## Secret and evidence rules

- Never print or persist passwords, cookies, tokens, client secrets, CSRF
  values, or Vault values.
- Record only Vault identifiers:
  - profile: `browser-login`
  - path: `kv/atius/browser-login/access-keys`
  - fields: `username`, `password`, `totp_secret`
- Evidence directories are private and reports are mode `0600`.
- Browser evidence stores sanitized origin/path, cookie attributes, and
  pass/fail results only.
- GBrain readback uses the existing full slug
  `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`; do not create a
  duplicate short record.

## Output

Return:

1. job type;
2. current canonical contract;
3. files changed;
4. complete lifecycle validation evidence;
5. backup and rollback/readback evidence;
6. residual risks or blockers, especially pending 10-04/10-05 or Phase 11.
