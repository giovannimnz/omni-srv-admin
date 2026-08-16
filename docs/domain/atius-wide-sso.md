# Atius-wide SSO at `sso.atius.com.br`

## Purpose and status

Platform/host manual for ATS, Keycloak/OIDC, Apache/Cloudflare/TLS, runtime
release, rollback, and central login/logout ownership.

Canonical reusable contract:

- `docs/domain/atius-sso-lifecycle-matrix.md`

Runtime status: **live for the 2026-07-30 host-local SSO recovery scope**:
`grafana.atius.com.br`, `portainer.atius.com.br`, `docker.atius.com.br`,
`vpn.atius.com.br`, and `adguard.atius.com.br` passed two browser login/logout
cycles each. Evidence:
`docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/`.

## Contract capsule

- Apps expose canonical human `/login` backed by internal rewrite/minimal
  proxy; the address bar stays on `/login`.
- `/sso` is compatibility only: query-free entry returns `308 /login`; a
  legacy allowlisted `return_to` is captured once in the transient cookie and
  returns `307 /login`. It is never a human canonical route.
- `return_to` never remains in the browser-facing login URL. A validated deep
  link is carried in a host-only, HttpOnly, Secure, SameSite=Lax cookie with a
  ten-minute TTL and consumed once by `/login`.
- Validated destination survives entry, login, logout-complete, re-entry, and
  return. State is `valid | missing | rejected`; neutral state never defaults
  to Trade.
- Central logout is POST-only `/api/sso/logout` with real browser `Origin`,
  `Content-Type: application/json`, and session-bound one-time
  `X-CSRF-Token`; all negative cases fail closed before mutation.
- App-local logout exposes one exact/minimal operation and never proxies the
  general ATS API.
- Completion URI is fixed at `https://sso.atius.com.br/login`.

| Site | Human URL | Default destination |
|---|---|---|
| SSH | `https://ssh.atius.com.br/login` | `https://ssh.atius.com.br/compute` |
| RDP | `https://rdp.atius.com.br/login` | `https://rdp.atius.com.br/giovanni-w11-pc` |
| OCI | `https://oci.atius.com.br/login` | `https://oci.atius.com.br/` |
| Grafana | `https://grafana.atius.com.br/login` | `https://grafana.atius.com.br/` |
| Portainer | `https://portainer.atius.com.br/login` | `https://portainer.atius.com.br/` |
| Docker | `https://docker.atius.com.br/login` | `https://docker.atius.com.br/` |
| VPN | `https://vpn.atius.com.br/login` | `https://vpn.atius.com.br/` |
| AdGuard | `https://adguard.atius.com.br/login` | `https://adguard.atius.com.br/` |
| Remote MT5 | `https://remote.atius.com.br/login` | `https://remote.atius.com.br/mt5/1/` |
| Talk | `https://talk.atius.com.br/login` | `https://talk.atius.com.br/` |
| Admin Talk | `https://admin.talk.atius.com.br/login` | `https://admin.talk.atius.com.br/` |

Any new human-facing `/sso?return_to=...` or persistent
`/login?return_to=...` URL is outside the contract.

Exact neutral state:

- `Sessão Atius ativa`
- `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- `Destino seguro`
- `Nenhum destino selecionado`
- central `/login`
- no application controls

## Responsibility map

```text
app /login (visible)
  -> internal ATS login shell
  -> ATS exact destination policy
  -> auth-token on .atius.com.br
  -> app validates /v1/auth/me
  -> app authorizes/proxies private backend
  -> app exact POST logout facade
  -> ATS POST/Origin/JSON/one-time-CSRF logout
  -> fixed central /login completion
  -> same validated destination or exact neutral state
```

- `sso.atius.com.br`: central login/logout policy and completion UI.
- `auth.atius.com.br`: optional OIDC identity/end-session owner.
- `api.atius.com.br`: ATS session authority.
- app/gateway: visible `/login`, controlled `/sso`, local authorization,
  session facade, exact logout, and private proxy.

## Central ATS and Keycloak

- Central login: `https://sso.atius.com.br/login`
- Session cookie: `auth-token`
- Session validation: `GET https://api.atius.com.br/v1/auth/me`
- OIDC issuer: `https://auth.atius.com.br/realms/atius`
- OIDC callback: `https://sso.atius.com.br/api/sso/callback`
- Fixed registered completion: `https://sso.atius.com.br/login`

Application destination is separate from OIDC transaction/completion state.
Keycloak remains identity-only; ATS database/RBAC remains authoritative.

The live release gate in 10-04 must read back `SSO_OIDC_LOGOUT_ENABLED`,
`SSO_OIDC_POST_LOGOUT_REDIRECT_URI`, PM2 artifact identity, and the registered
Keycloak completion without logging secret material. Both OIDC-off and OIDC-on
branches must pass the same destination semantics.

## Central logout

Accepted operation:

- method POST;
- exact path `/api/sso/logout`;
- browser-generated Origin in the exact central allowlist;
- JSON content type;
- session-bound one-time CSRF header;
- authenticated session;
- fixed completion URL.

Rejected before mutation:

- GET;
- missing/wrong Origin;
- wrong content type;
- missing/invalid/replayed CSRF.

Do not authorize from forwarded Origin and do not place a synthetic allowed
Origin in examples. The route clears both auth cookie variants only after its
request boundary passes.

## App facade template

The platform contract requires internal proxying:

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

The app gateway validates controlled `/sso` bootstrap and lands on clean
`/login`. The facade proxies only required shell/assets/exact auth operations,
not the ATS frontend/API generally.

## Publication sequence

1. Capture exact source/runtime hashes and before-state.
2. Verify recoverable backups for ATS build, PM2, Apache, Cloudflare/DNS/TLS,
   and Keycloak registration.
3. Run the lifecycle contract, ATS tests, secret scan, and candidate smokes
   under the CPU governor.
4. Run headless `valid | missing | rejected` lifecycle checks with sanitized
   mode-`0600` evidence.
5. Prove rollback before cutover.
6. Apply only after the governed 10-04 release gate.
7. Read back runtime identity and rerun full lifecycle.
8. Roll back/reapply and rerun the same checks.
9. Plan 10-05 owns final headless/visual/knowledge/Graphify closeout.

## Rollback

- Restore only owned ATS/PM2/Apache/Keycloak/edge artifacts from recorded
  backups.
- Revert Cloudflare/DNS/TLS to the captured before-state when changed.
- Rerun exact contract, entry/login/logout-complete/re-entry/return, negatives,
  and secret scan.
- Compare expected/current hashes and runtime identity.
- Never treat source restoration alone as runtime rollback.

## AdGuard/Phase 11 boundary

The central allowlist may accept `https://adguard.atius.com.br/`. This proves
only that ATS can hand off to the root. It does not approve the Phase 11
app-local `/login`, controlled `/sso`, Apache/gateway, logout facade, or live
browser lifecycle.

## Evidence, history, and secrets

Canonical history:

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-PATTERNS.md`

GBrain readback:

- `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`

HashiCorp Vault is authoritative. Only profile/path/field identifiers may enter
docs or evidence; never values.
