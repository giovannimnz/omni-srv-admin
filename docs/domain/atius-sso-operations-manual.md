# Atius SSO - Operations Manual

## Purpose and status

Executable owner procedure for `understand | mount | include | validate |
operate | remove`.

Canonical matrix:

- `docs/domain/atius-sso-lifecycle-matrix.md`

Runtime status: **planned until 10-04/10-05 evidence**. Do not infer deployment
from these instructions.

## Contract capsule

- App-local `/login` is the canonical human URL and stays visible through
  internal rewrite/minimal proxy.
- `/sso` is internal or controlled compatibility; never redirect the public
  `/login` route into `/sso`.
- A bootstrap query is transient, same-origin, and removed before the clean
  public URL.
- Destination state is `valid | missing | rejected` across entry, login,
  logout-complete, re-entry, and return; missing/rejected is neutral.
- Central logout is POST-only `/api/sso/logout` with real browser `Origin`,
  `Content-Type: application/json`, and session-bound one-time
  `X-CSRF-Token`.
- GET, wrong/missing Origin, wrong content type, missing/invalid/replayed CSRF
  fail closed before mutation.
- Local logout exposes one exact operation, not a general ATS API proxy.
- Central completion remains `https://sso.atius.com.br/login`.

Exact neutral state:

- heading `Sessão Atius ativa`
- body `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- label/value `Destino seguro` / `Nenhum destino selecionado`
- URL `https://sso.atius.com.br/login`
- no application controls

## Mount/include procedure

1. Define exact public host, protected paths, public exceptions, and owner.
2. Classify the app as ATS-native, own-backend, or internal-resource proxy.
3. Define local authorization and the private backend/credential identifier.
4. Capture hashes, a recoverable backup, and runtime before-state.
5. Update the exact central policy in
   `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts`.
6. Implement:
   - canonical `/login` internal facade;
   - controlled `/sso` bootstrap landing on clean `/login`;
   - fixed forwarded host/proto/port and exact CORS;
   - server-side session validation through `/v1/auth/me`;
   - private backend proxy with server-side credential;
   - exact local POST logout forwarding the real incoming Origin and
     one-time CSRF operation only.
7. Run the matrix in `docs/domain/atius-sso-lifecycle-matrix.md`.
8. Prove rollback and reapply before promotion.
9. Update owner docs; schedule Obsidian/GBrain/Graphify closeout after runtime
   and browser proof.

## Minimal reverse-proxy pattern

Keep `/login` visible:

```apache
ProxyPreserveHost On
ProxyPassMatch "^/login$" "http://127.0.0.1:3015/sso/login"
ProxyPassReverse "/login" "http://127.0.0.1:3015/sso/login"

<LocationMatch "^/login$">
    RequestHeader set X-Forwarded-Host "<app>.atius.com.br"
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
</LocationMatch>
```

The gateway validates legacy `/sso` context and redirects only to clean
`/login`; an unconditional Apache compatibility redirect is insufficient.
Proxy only the shell, immutable assets, and exact auth/session/refresh/logout
operations. Never proxy ATS APIs generally.

## Validate

Run the deterministic contract:

```bash
node scripts/validate-atius-sso-lifecycle-contract.mjs \
  --contract /home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json \
  --report /path/to/private/report.json
```

Run ATS unit/integration tests under the CPU governor, then headless browser
validation from fresh `valid`, `missing`, and `rejected` contexts. Prove:

1. anonymous entry reaches clean app `/login`;
2. address bar stays on `/login`;
3. login returns to the same validated target;
4. POST logout uses browser-generated Origin, JSON, and one-time CSRF;
5. logout-complete shows the same destination or exact neutral tuple;
6. `Entrar novamente` and `Voltar para` use the same target;
7. destination and logout negatives fail closed;
8. app/backend secrets never reach browser or evidence;
9. rollback/reapply returns the same hashes and behavior.

Do not put an allowed Origin header into JavaScript or copy/paste positive
`curl` examples. The browser supplies it. Negative tests may deliberately send
an invalid Origin to prove rejection.

## Remove

1. Inventory allowlist, `/login`, controlled `/sso`, session, logout, proxy,
   runtime, and docs; create backup.
2. Remove the exact central host/path.
3. Remove or adapt local facade, middleware, session, logout, and private proxy.
4. Prove no remaining dependency on `auth-token`, `/v1/auth/me`, central
   login/logout, or ATS-authenticated proxy.
5. Run survivor positives plus removed-app negatives through the full
   lifecycle.
6. For rollback, restore the owned backup, rerun contract/lifecycle/headless
   checks, and verify hashes/readback.

## AdGuard boundary

`https://adguard.atius.com.br/` is an allowlisted root destination for central
handoff. That does not approve the Phase 11 app-local facade, Apache/gateway
apply, or live AdGuard lifecycle.

## Evidence and secrets

Evidence may record timestamps, hosts, commands, status, hashes, backup paths,
Vault profile/path/field names, and sanitized URLs. It must not contain
passwords, cookie/token/CSRF values, client secrets, or Vault values.

Canonical identifiers:

- Vault profile `browser-login`
- Vault path `kv/atius/browser-login/access-keys`
- fields `username`, `password`, `totp_secret`
- GBrain slug `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`
- Phase 42:
  `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`

## Change record template

```markdown
## SSO change - <app>

- Type:
- Exact host/paths:
- Public exceptions:
- Owner:
- Before hashes/backup:
- Central policy:
- Local `/login` facade:
- Controlled `/sso` behavior:
- Session/logout/private proxy:
- Lifecycle positives/negatives:
- Headless evidence:
- Rollback/reapply:
- Runtime status:
- Knowledge readback:
```
