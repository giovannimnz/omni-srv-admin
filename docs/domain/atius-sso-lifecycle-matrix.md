# Atius SSO - Canonical Lifecycle Matrix

## Status and ownership

- Contract owner: `omni-srv-admin/docs/domain/`
- Machine source:
  `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json`
- Skill acceptance:
  `/home/ubuntu/.codex/skills/atius-sso/references/lifecycle-acceptance.md`
- Runtime status: **planned until 10-04/10-05 evidence**
- Phase 11 boundary: the allowlisted AdGuard root is eligible for central
  handoff, but the AdGuard facade is not approved until Phase 11 implements and
  validates its app-local contract.

This file is the single owner-side lifecycle contract. The manual index,
operations manual, platform manual, and application playbook reference it
instead of redefining route or logout semantics.

## Normative capsule

- Canonical human app URL: `https://<app>.atius.com.br/login`.
- `/login` stays visible through an internal rewrite or minimal proxy serving
  the ATS shell.
- `/sso` is internal or controlled compatibility. Public redirection from
  `/login` into `/sso` is prohibited.
- Compatibility bootstrap validates a same-origin target, stores it
  transiently, and lands on clean `/login`; `return_to` does not persist in the
  app URL.
- Destination is `valid`, `missing`, or `rejected`; only `valid` contains a
  URL. Missing, expired, and rejected state is neutral, never implicit Trade.
- Central logout is POST-only `/api/sso/logout` with the real browser
  `Origin`, `Content-Type: application/json`, and a session-bound one-time
  `X-CSRF-Token`.
- GET, missing/wrong Origin, wrong content type, missing/invalid/replayed CSRF
  fail closed before session, cookie, or destination mutation.
- App-local logout owns one exact operation and never exposes a general ATS API
  proxy.
- Central completion is always `https://sso.atius.com.br/login`; application
  context is separate validated short-lived state.

## Exact neutral state

| Field | Exact value |
|---|---|
| Heading | `Sessão Atius ativa` |
| Body | `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.` |
| Label | `Destino seguro` |
| Value | `Nenhum destino selecionado` |
| URL | `https://sso.atius.com.br/login` |
| Application controls | absent |

Neutral state must not render `Entrar novamente`, `Voltar para`, an application
link, or any substitute application navigation control. `Encerrar sessão` may
remain as the explicit non-application action.

## Five-stage lifecycle

| Stage | Visible public URL | Context class | Required result |
|---|---|---|---|
| Entry | `https://<app>.atius.com.br/login` | validated same-origin bootstrap | clean `/login`, no visible `return_to` |
| Login | `https://<app>.atius.com.br/login` | validated login state | session returns to the same exact app target |
| Logout complete | `https://sso.atius.com.br/login` | one-time post-logout state | same validated target or exact neutral tuple |
| Re-entry | `https://sso.atius.com.br/login` | same validated post-logout state | `Entrar novamente` preserves the target |
| Return | validated application URL | consumed post-logout state | `Voltar para` reaches the target and consumes state |

Cookie classes stay separate:

| Class | Required attributes |
|---|---|
| Login bootstrap | host-only, HttpOnly, Secure, SameSite=Lax, short-lived |
| OIDC transaction | host-only, HttpOnly, Secure, SameSite=Lax, short-lived, separate from destination |
| Post-logout | host-only, HttpOnly, Secure, SameSite=Lax, short-lived, one-time |

## Exact surfaces and ownership

| Owner | Surface | Contract |
|---|---|---|
| App/gateway | `/login` | visible human URL; internal rewrite/minimal proxy |
| App/gateway | `/sso` | controlled compatibility bootstrap; never canonical UI |
| App/gateway | local session endpoint | server-side `auth-token` validation through `/v1/auth/me` |
| App/gateway | local logout | exact POST facade; incoming browser Origin must match app origin |
| ATS | return policy | exact scheme/host/default-port/bounded-path/encoding allowlist |
| ATS | `/api/sso/logout` | POST/Origin/JSON/one-time-CSRF enforcement |
| ATS | `/login` completion | fixed central URL and exact valid/neutral rendering |
| Keycloak | OIDC identity/end-session | identity only; fixed registered central completion |
| App backend proxy | private credential | server-side only; never exposed to browser |

## Apache/internal proxy template

The app vhost keeps `/login` visible. It must not emit a public redirect to
`/sso`.

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

The concrete vhost may use an application gateway instead of direct
`ProxyPassMatch`, but the result is identical: `/login` stays in the browser,
only the required ATS shell/assets/auth endpoints are proxied, and forwarded
headers are fixed to the exact app host.

Legacy `/sso` handling belongs to the app gateway:

1. parse optional bootstrap destination;
2. accept only same-origin HTTPS/default-port/bounded-path input;
3. store normalized state in a short-lived host-only HttpOnly cookie;
4. redirect to clean `/login`;
5. clear state and fail neutral/closed on rejection.

Do not use an unconditional Apache redirect that bypasses validation.

## Exact app-local API surface

Each integration declares concrete local names, but exposes no more than:

- canonical `GET /login` facade;
- controlled compatibility `GET /sso`;
- exact login/session/refresh endpoints required by the ATS shell;
- one local session read endpoint;
- one local POST logout facade;
- app-specific authenticated backend proxy paths.

The facade must not proxy `/api/*`, `/v1/*`, or the ATS frontend generally.

Browser logout example:

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

The browser supplies `Origin`; JavaScript and gateway examples never synthesize
or overwrite it. The local facade validates the incoming exact app Origin and
passes the authenticated operation through the one allowed upstream path.

## Destination positive matrix

| ID | Input | Expected |
|---|---|---|
| trade-root-explicit | `https://trade.atius.com.br/` | valid only when explicitly supplied |
| ssh-bounded-prefix | `https://ssh.atius.com.br/compute/giovanni-w11-pc` | valid exact bounded path |
| adguard-root | `https://adguard.atius.com.br/` | valid central handoff; no Phase 11 facade claim |
| missing | no input | neutral |
| rejected | invalid input | neutral/fail-closed |

## Mandatory negative matrix

Destination rejects:

- host suffix confusion;
- userinfo;
- protocol-relative URL;
- non-HTTPS scheme;
- non-default port;
- disallowed path;
- malformed URL;
- single/double encoded traversal;
- cross-origin local bootstrap.

Logout rejects before mutation:

- GET;
- missing Origin;
- wrong Origin;
- wrong content type;
- missing CSRF token;
- invalid CSRF token;
- reused CSRF token.

Documentation audit rejects:

- `/sso` prescribed as the human canonical route;
- public redirect from `/login` into `/sso`;
- implicit Trade fallback;
- mutating GET logout;
- forged allowed Origin examples;
- first-redirect-only approval;
- general ATS API proxy;
- stale short GBrain slug;
- secret-like values.

## Required validation

Run the documentation contract:

```bash
node /home/ubuntu/GitHub/omni-srv-admin/scripts/validate-atius-sso-lifecycle-contract.mjs \
  --contract /home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/fixtures/sso-lifecycle-contract.json \
  --report /path/to/private/10-03-doc-audit.json
```

Run the existing ATS lifecycle suite under the host CPU guardrail. Browser
approval must be headless, start from fresh contexts, retain sanitized evidence,
and cover:

1. entry;
2. login;
3. destination after login;
4. logout-complete;
5. re-entry;
6. return;
7. missing and rejected neutral states;
8. logout and destination negatives;
9. exact `Destino seguro`;
10. public URL without persistent bootstrap query.

A redirect-only smoke is insufficient.

## Onboarding and removal

Onboarding:

1. define exact host, allowed paths, public exceptions, local authorization,
   backend, and server-side credential identifier;
2. capture target hashes and a recoverable backup;
3. update central policy;
4. implement the exact local surface;
5. run every positive and negative lifecycle check;
6. prove rollback and reapply;
7. record owner/readback evidence without secret values.

Removal:

1. back up and inventory allowlist/facade/session/logout/proxy dependencies;
2. remove the central host/path;
3. remove or adapt `/login`, controlled `/sso`, session, logout, and private
   proxy surfaces;
4. prove no dependency remains on `auth-token`, `/v1/auth/me`, central
   login/logout, or ATS-authenticated private proxy;
5. prove survivor apps pass and the removed app fails the exact checks;
6. restore from backup and rerun the complete matrix when rollback is needed.

## Secret and knowledge rules

HashiCorp Vault is authoritative. Documentation may name only:

- profile `browser-login`;
- path `kv/atius/browser-login/access-keys`;
- fields `username`, `password`, `totp_secret`.

Never record values.

Canonical GBrain readback:

```bash
/home/ubuntu/.local/bin/gbrain get \
  aisecondbrain/30-recursos/atius/sso-atius-guia-canonico
```

Actual historical workstream paths:

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-PATTERNS.md`

Do not create a duplicate GBrain page to preserve a non-resolving short slug.
