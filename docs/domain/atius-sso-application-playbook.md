# Atius SSO - Application Playbook

## Purpose and status

Canonical application-side playbook for mounting, including, validating,
operating, and removing an Atius SSO app.

Canonical matrix:

- `docs/domain/atius-sso-lifecycle-matrix.md`

Runtime status: **live and visually sealed for the 2026-07-31 fleet scope**.
The 12 public hosts passed `24/24` complete browser cycles and visual review
`12/12`. Evidence:
`docs/evidence/atius-sso/2026-07-31-full-fleet-final-strict-20260731-202636/`.
Plans `10-04` and `10-05` have runtime promotion and final browser/visual
evidence; older pending language is historical only.

## Contract capsule

- Human entry is app-local `/login`; internal rewrite/minimal proxy keeps it
  visible.
- `/sso` is compatibility only: query-free entry returns `308 /login`; a
  legacy allowlisted `return_to` is captured once and returns `307 /login`.
  Never redirect public `/login` into `/sso`.
- A legacy deep link is allowlisted, stored in a host-only, HttpOnly, Secure,
  SameSite=Lax cookie for at most ten minutes, consumed once, and removed from
  the clean public URL.
- Human URLs containing persistent `return_to` are prohibited.
- Destination is `valid | missing | rejected` through entry, login,
  logout-complete, re-entry, and return. Missing/rejected is neutral, not Trade.
- Central logout is POST-only `/api/sso/logout` with the real browser
  `Origin`, `Content-Type: application/json`, and a session-bound one-time
  `X-CSRF-Token`.
- GET, wrong/missing Origin, wrong content type, missing/invalid/replayed CSRF
  fail closed before mutation.
- Local logout owns one exact/minimal operation and never publishes a general
  ATS API proxy.
- The visible `Destino seguro` value is the destination's bare hostname only.
  Do not expose scheme, port, slash, path, query, or fragment in that field.
  Keep the complete validated URL for redirects and authorization; display
  normalization must not weaken destination validation.

Exact neutral state:

- heading `Sessão Atius ativa`
- body `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- `Destino seguro` / `Nenhum destino selecionado`
- URL `https://sso.atius.com.br/login`
- no application controls

## Integration types

1. ATS-native host.
2. Web app with its own backend.
3. Proxy for an internal resource.

For any type, ATS owns central authentication/redirect/logout policy. The app
owns its visible login facade, local authorization, exact session/logout
surface, public exceptions, and private backend proxy.

## Include an app

1. Define the exact HTTPS host and allowed root/bounded paths.
2. Enumerate protected paths and explicit public exceptions.
3. Define local authorization and private backend/credential identifiers.
4. Capture target hashes, runtime before-state, and recoverable backup.
5. Update
   `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`.
6. Implement:
   - visible `/login` backed by internal ATS shell proxy;
   - controlled `/sso` compatibility bootstrap;
   - exact forwarded host/proto/port and CORS origin;
   - host-only transient context with clean public URL;
   - server-side session validation using `/v1/auth/me`;
   - authenticated local proxy for private backend;
   - exact local POST logout preserving the incoming browser Origin and
     one-time CSRF semantics.
7. Run the complete lifecycle matrix.
8. Prove rollback/reapply and hash/runtime readback.
9. Update owner docs; wait for governed knowledge closeout.

Do not expose backend credentials in browser code, cookies, logs, traces, or
reports.

## Minimal app facade

```text
GET /login
  -> internal rewrite/minimal proxy to ATS login shell

GET /sso
  -> validate optional same-origin bootstrap
  -> store short-lived HttpOnly context
  -> redirect to clean /login

GET /auth/session
  -> server-side validation of auth-token through /v1/auth/me

POST /auth/logout
  -> enforce exact incoming app Origin + JSON + one-time CSRF
  -> call only central POST /api/sso/logout
```

Shell assets and auth/session/refresh operations must be explicitly listed.
Never proxy an ATS API prefix generally.

Browser JavaScript does not set `Origin`; the browser supplies it:

```js
await fetch('/auth/logout', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken,
  },
  body: '{}',
})
```

## Validate

Run the owner audit:

```bash
node /home/ubuntu/GitHub/omni-srv-admin/scripts/validate-atius-sso-lifecycle-contract.mjs \
  --contract /home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json \
  --report /path/to/private/report.json
```

Under the CPU governor, run central policy/route tests and headless browser
checks from fresh `valid`, `missing`, and `rejected` contexts. Approval proves:

1. clean visible app `/login`;
2. no persistent `return_to`;
3. exact destination after login;
4. POST logout boundary;
5. exact destination or neutral logout completion;
6. re-entry and return;
7. exact `Destino seguro`;
8. destination/logout negatives;
9. no secret values;
10. rollback and reapply.

A first redirect or allowlist-only result is not approval.

## Remove an app

1. Back up central policy, local facade/session/logout/proxy, runtime, and docs.
2. Remove exact host/path from central policy.
3. Remove or adapt `/login`, controlled `/sso`, session, logout, middleware,
   local authorization, and private proxy.
4. Prove no dependency remains on `auth-token`, `/v1/auth/me`, central
   login/logout, or ATS-authenticated private proxy.
5. Run survivor positives and removed-app negatives through the full lifecycle.
6. Restore backup and rerun the complete contract when rollback is required.
7. Record hashes/readback without secret values.

## AdGuard boundary

The allowlisted `https://adguard.atius.com.br/` root is a valid central handoff
target. It is not evidence that the Phase 11 AdGuard app facade, logout, or
browser lifecycle is implemented or approved.

## Secret and knowledge identifiers

HashiCorp Vault only:

- profile `browser-login`
- path `kv/atius/browser-login/access-keys`
- fields `username`, `password`, `totp_secret`

Never record values.

Canonical readback:

- GBrain `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`
- Phase 42
  `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
