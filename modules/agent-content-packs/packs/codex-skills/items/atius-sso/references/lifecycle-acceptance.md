# Atius SSO - Lifecycle Acceptance

This matrix is mandatory for onboarding, validation, rollback, and removal.
A first redirect is not approval.

## Frozen contract

- Canonical human route: app-local `/login`.
- Routing strategy: internal rewrite or minimal proxy; `/login` remains visible.
- Compatibility route: `/sso` is internal/controlled and lands cleanly on
  `/login`; never publish an external redirect from `/login` to `/sso`.
- Destination states: `valid`, `missing`, `rejected`.
- Central completion URL: `https://sso.atius.com.br/login`.
- Central logout: `POST /api/sso/logout`.
- Required browser request metadata: real browser `Origin`,
  `Content-Type: application/json`, session-bound one-time `X-CSRF-Token`.
- App-local logout ownership: one exact/minimal operation; no general ATS API
  proxy.
- Runtime status: live and visually sealed for the 2026-07-31 fleet scope;
  new app integrations or feature expansions still require their own release
  and browser evidence.

Exact neutral tuple:

| Field | Required value |
|---|---|
| Heading | `Sessão Atius ativa` |
| Body | `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.` |
| Label | `Destino seguro` |
| Value | `Nenhum destino selecionado` |
| URL | `https://sso.atius.com.br/login` |
| Application controls | absent |

The neutral state has no `Entrar novamente`, `Voltar para`, application link,
or substitute application navigation control.

## Lifecycle matrix

| Stage | Public URL | Destination source | Required result |
|---|---|---|---|
| Entry | `https://<app>.atius.com.br/login` | validated transient same-origin bootstrap | clean `/login`; no visible `return_to` |
| Login | `https://<app>.atius.com.br/login` | validated login context | authentication returns to the same exact target |
| Logout complete | `https://sso.atius.com.br/login` | validated one-time post-logout context | same safe destination or exact neutral tuple |
| Re-entry | `https://sso.atius.com.br/login` | same validated post-logout context | `Entrar novamente` preserves the target |
| Return | validated application URL | same validated post-logout context | `Voltar para` reaches that target and consumes context |

For `missing` and `rejected`, logout-complete and re-entry remain neutral and
must never synthesize `trade.atius.com.br`.

## Required positive checks

- Explicit Trade root works only when supplied and allowlisted.
- Bounded SSH prefix works only for its exact allowlisted path.
- AdGuard app-local facade is accepted for the sealed 2026-07-31 recovery
  scope; future AdGuard feature expansion still needs its own lifecycle
  evidence.
- `/login` stays visible while the internal ATS shell is served.
- Legacy `/sso` bootstrap lands on clean `/login`.
- Valid destination survives entry, authentication, logout-complete,
  `Entrar novamente`, and `Voltar para`.
- App-local logout proxies only the exact central POST operation.
- Backup, rollback, reapply, and readback restore the same contract.

## Required negative checks

Destination policy rejects or neutralizes:

- host suffix confusion;
- userinfo;
- protocol-relative URL;
- non-HTTPS scheme;
- non-default port;
- disallowed path;
- malformed URL;
- single/double encoded traversal;
- cross-origin app-local bootstrap.

Logout fails closed before mutation for:

- GET;
- missing Origin;
- wrong Origin;
- forged Origin example or forwarded-origin substitution;
- wrong content type;
- missing CSRF token;
- invalid CSRF token;
- reused CSRF token.

Documentation/runtime audit rejects:

- `/sso` as the human canonical route;
- external redirection from `/login` into the compatibility namespace;
- implicit Trade fallback;
- mutating GET logout;
- general ATS API proxy;
- first-redirect-only approval;
- stale short GBrain slug;
- any secret-like value.

## Headless and visual proof

Use a fresh headless browser context for `valid`, `missing`, and `rejected`.
Retain sanitized mode-`0600` evidence proving:

- address bar and lack of persistent `return_to`;
- exact `Destino seguro`;
- post-login destination;
- logout-complete destination or exact neutral tuple;
- re-entry;
- return;
- all negative requests;
- no secret values in trace, screenshot manifest, report, or command line.

## Rollback

Before mutation:

1. capture exact target hashes and owner repo;
2. create a recoverable backup without secret values;
3. record runtime before-state and affected surface IDs.

Rollback:

1. restore only the owned files/runtime artifact;
2. rerun the central machine contract and the documentation audit;
3. rerun entry/login/logout-complete/re-entry/return positives and negatives;
4. verify the full GBrain slug
   `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico` and Graphify
   readback in the governed closeout;
5. do not claim runtime promotion for a new or changed scope without fresh release/browser evidence equivalent to the materialized 10-04/10-05 gates.

## Removal

Removal is complete only when:

- host/path leaves the central allowlist;
- app-local `/login`, controlled `/sso`, session, logout, and proxy surfaces
  are removed or explicitly adapted;
- the app no longer depends on `auth-token`, `/v1/auth/me`, central login or
  logout, or an ATS-authenticated server-side proxy;
- survivor apps still pass the lifecycle;
- the removed app fails the central and app-local destination checks;
- rollback can restore the prior contract and pass the full matrix.

## Secret identifiers

HashiCorp Vault is the only source. Evidence may name only:

- profile `browser-login`
- path `kv/atius/browser-login/access-keys`
- fields `username`, `password`, `totp_secret`

Never store values.
