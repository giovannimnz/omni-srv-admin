# Atius SSO - Manual Index

## Purpose and status

This is the routing index for understanding, mounting, including, validating,
operating, and removing Atius SSO integrations.

Canonical reusable contract:

- `docs/domain/atius-sso-lifecycle-matrix.md`

Runtime status: **live and visually sealed for the 2026-07-31 fleet scope**.
The 12 public hosts passed `24/24` complete browser cycles and visual review
`12/12`. Evidence:
`docs/evidence/atius-sso/2026-07-31-full-fleet-final-strict-20260731-202636/`.
Plans `10-04` and `10-05` have runtime promotion and final browser/visual
evidence; older pending language is historical only.

## Contract capsule

- Canonical human app URL: `https://<app>.atius.com.br/login`.
- `/login` stays visible through internal rewrite/minimal proxy.
- `/sso` is internal or controlled compatibility; public redirection from
  `/login` into `/sso` is forbidden.
- Destination lifecycle is `valid | missing | rejected` through entry, login,
  logout-complete, re-entry, and return.
- Missing/rejected state is neutral and never implies Trade.
- Central logout is POST-only `/api/sso/logout` with real browser `Origin`,
  `Content-Type: application/json`, and session-bound one-time
  `X-CSRF-Token`; negatives fail closed before mutation.
- App-local logout is one exact/minimal operation, never a general ATS API
  proxy.
- Backup, lifecycle tests, rollback, reapply, and readback are mandatory.

Exact neutral state is:

- `Sessão Atius ativa`
- `Você entrou com sucesso. Nenhum aplicativo de destino foi informado. Você pode fechar esta aba.`
- `Destino seguro`
- `Nenhum destino selecionado`
- URL `https://sso.atius.com.br/login`
- no application controls

## Reading routes

### Understand the architecture

- `docs/domain/atius-sso-learnings.md`
- `docs/domain/atius-wide-sso.md`
- `docs/domain/atius-sso-lifecycle-matrix.md`

### Mount or publish the central host

- `docs/domain/atius-wide-sso.md`
- `docs/domain/atius-sso-lifecycle-matrix.md`

This covers ATS, Keycloak/OIDC, Apache, Cloudflare, TLS, release gates, and
rollback.

### Include or remove an application

- `docs/domain/atius-sso-operations-manual.md`
- `docs/domain/atius-sso-application-playbook.md`
- `docs/domain/atius-sso-lifecycle-matrix.md`

### Validate

Approval requires the full entry/login/logout-complete/re-entry/return matrix,
positive and negative destination/logout checks, exact neutral copy, sanitized
headless evidence, and rollback/readback. A first redirect is not acceptance.

## Ownership

| Owner | Responsibility |
|---|---|
| ATS | central allowlist, login/logout policy, neutral completion |
| App/gateway | visible `/login`, controlled `/sso`, session, exact logout, local authorization |
| `omni-srv-admin` | owner manuals and lifecycle matrix |
| `atius-sso` skill | executable agent procedure |
| Obsidian/GBrain | governed knowledge mirror after runtime proof |

`adguard.atius.com.br` now has its app-local facade validated for the recovery
scope above; future AdGuard feature expansion still needs its own lifecycle
evidence.

## Actual planning evidence

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-LEARNINGS.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-PATTERNS.md`

## Skill and knowledge readback

- Skill: `/home/ubuntu/.codex/skills/atius-sso/SKILL.md`
- Obsidian:
  `/home/ubuntu/GitHub/obsidian-vault/AiSecondBrain/30-RECURSOS/atius/SSO-Atius-Guia-Canonico.md`
- GBrain:
  `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico`

Do not create a second SSO skill or duplicate knowledge page.

## Secret rule

HashiCorp Vault is authoritative. Manuals and evidence may contain only profile,
path, and field identifiers, never values.
