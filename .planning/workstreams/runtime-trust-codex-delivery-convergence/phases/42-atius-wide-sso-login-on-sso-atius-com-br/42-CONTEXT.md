# Phase 42: Atius-wide SSO Login on sso.atius.com.br - Context

**Gathered:** 2026-06-28
**Status:** Ready for research
**Source:** User-directed Phase 42 scope plus ATS/Phase 36 inspection

<domain>
## Phase Boundary

Create an Atius-wide login entrypoint at `sso.atius.com.br`.

This phase plans the identity migration path. It does not directly mutate live
DNS, Apache, Cloudflare, Keycloak clients, ATS production code, PM2, or secrets
during planning. The executable implementation phase must be gated and
rollbackable.

ATS is the reference application because it already has working multi-subdomain
SSO via `.atius.com.br` cookies. The goal is to turn the current app-local
login model into a centralized Atius login model without losing the existing
RBAC and trading safeguards.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** `sso.atius.com.br` is the canonical user-facing login host for Atius-wide SSO.
- **D-02:** The Phase 36 Keycloak instance remains the OIDC provider baseline through `auth.atius.com.br`.
- **D-03:** ATS is the first migration target and must keep legacy `auth-token`, refresh, logout, and backend RBAC compatibility until OIDC is proven.
- **D-04:** Phase 42 centralizes authentication first; ATS DB permissions remain authoritative for authorization.
- **D-05:** Redirects from `sso.atius.com.br` must use an allowlist and reject freeform, protocol-relative, and unknown-host targets.
- **D-06:** Logout must clear Keycloak browser SSO plus `.atius.com.br` and no-domain ATS `auth-token` cookies.
- **D-07:** Apache/Cloudflare forwarded-header behavior must be explicit, tested, and rollbackable.
- **D-08:** No Keycloak secret, JWT secret, session secret, test password, bearer token, cookie value, or smoke credential may be written to artifacts.

### D-01 | Canonical login host
`sso.atius.com.br` is the canonical user-facing login host for Atius-wide SSO.
It should own the login UX, redirect validation, callback handoff, and global
logout entrypoint.

### D-02 | Existing Keycloak provider
The Keycloak instance validated in Phase 36 remains the OIDC provider baseline.
`auth.atius.com.br` is the current Keycloak/OIDC surface; Phase 42 must decide
whether `sso.atius.com.br` fronts Keycloak directly or acts as a login facade
that delegates to `auth.atius.com.br`.

### D-03 | ATS-first compatibility
ATS is the first migration target. Its current `auth-token` cookie, refresh,
logout, and backend RBAC enforcement must continue working until the OIDC path
is proven end-to-end.

### D-04 | Authentication before authorization migration
Phase 42 centralizes authentication first. ATS authorization remains enforced by
existing backend state (`is_admin`, `can_access_backtest`,
`can_access_dashboard`, `can_access_automation`, `can_access_trade`,
`can_access_lc`) until role/claim mapping is explicitly verified.

### D-05 | No open redirects
Redirects from `sso.atius.com.br` must be allowlisted for known Atius app hosts
and paths. Freeform redirect targets, protocol-relative URLs, and unknown hosts
must be rejected.

### D-06 | Logout must be global and compatible
Logout must clear both the Keycloak browser SSO session and the legacy
`.atius.com.br` `auth-token` cookie, including stale no-domain cookies where
the current ATS logout flow already handles legacy cleanup.

### D-07 | Edge/header fragility must be addressed
The current ATS middleware depends on Apache `x-forwarded-host`. Phase 42 must
make this dependency explicit in Apache/Cloudflare contracts and tests so SSO
does not silently break when proxy headers change.

### D-08 | Secrets stay out of artifacts
No Keycloak client secret, JWT secret, session secret, test password, bearer
token, or smoke credential may be written to Git, `.planning`, Obsidian, logs,
or shell history.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Keycloak/FreeIPA baseline
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-CONTEXT.md` — Phase 36 decisions, especially additive Keycloak and legacy SSO preservation.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md` — Keycloak 26.6.3, `127.0.0.1:8180`, realm `atius`, FreeIPA federation, `phase36-smoke`.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md` — current OIDC and FreeIPA federation evidence.
- `docs/domain/keycloak-freeipa-coexistence.md` — runbook/baseline for the deployed Keycloak/FreeIPA path.

### ATS current SSO implementation
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts` — subdomain routing, protected route redirects, `auth-token` cookie checks and `x-forwarded-host` dependency.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/contexts/auth-context.tsx` — frontend session hydration and logout behavior.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` — `/auth/me`, `/auth/refresh`, `/auth/logout`, cookie options and global logout cleanup.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/token/index.js` — current login token issuance and `.atius.com.br` cookie creation.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/users/index.js` — alternate login path still issuing `auth-token`.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/middleware/permissions.js` — backend auth/RBAC enforcement contract.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/api.js` — Swagger/docs SSO guard and forwarded origin handling.
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` — current runtime SSO endpoint coverage.

### Known risks and historical notes
- `.planning/codebase/CONCERNS.md` — "SSO Middleware Depends on Apache Forwarded Headers" and certificate/vhost risks.
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/61-Incidents/2026-06-02-phase7-sso-success.md` — prior router SSO lesson: shared session secret and cookie decoder compatibility matter.
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/horistic-login-sso-audit-2026-05-29.md` — prior lesson: cookie `Domain`, `Secure`, `SameSite`, and production env must be verified via `Set-Cookie`.
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/20-PROJETOS/atius/2026-06-15-ats-project-health-review.md` — current ATS runtime health, PM2 and test baseline.

### Up-to-date framework docs consulted during planning
- Context7 `/keycloak/keycloak` — Keycloak OIDC endpoints, authorization code flow, RP-initiated logout, protocol mapper concepts.
- Context7 `/vercel/next.js` — Next.js middleware/proxy cookie and redirect APIs.

</canonical_refs>

<specifics>
## Specific Ideas

- Add a DNS/Apache/Cloudflare contract for `sso.atius.com.br` but apply it only
  during execution with `apache2ctl configtest`, local `--resolve` smoke, and
  rollback.
- Prefer OIDC Authorization Code Flow for browser login; do not base the new
  user-facing flow on password grant.
- Preserve the ATS `auth-token` cookie during the first migration by either:
  1. issuing a local ATS session after OIDC callback validation, or
  2. teaching ATS backend middleware to validate Keycloak-issued tokens while
     keeping RBAC lookup in the ATS database.
- Keep backend authorization checks authoritative. Frontend middleware remains
  UX/routing guard, not the final security boundary.
- Add allowlisted redirect targets for current Atius app hosts:
  `trade.atius.com.br`, `painel.atius.com.br`, `dashboard.atius.com.br`,
  `backtest.atius.com.br`, `strategy.atius.com.br`, `admin.atius.com.br`,
  plus future app hosts only by explicit config.
- Include a no-open-redirect test matrix and cookie inspection matrix in the
  plan.

</specifics>

<deferred>
## Deferred Ideas

- Migrating every non-ATS Atius app in one cutover is deferred. Phase 42 should
  produce the Atius-wide login foundation and at most one reference migration
  path through ATS.
- Cross-domain Horistic `.horistic.com` SSO is deferred unless the plan finds a
  low-risk federation-only contract. `.atius.com.br` is the immediate domain.
- Windows/Mac domain login remains out of scope; this is web SSO.
- Creating or rotating secrets is execution scope, not planning scope.

</deferred>

---

*Phase: 42-atius-wide-sso-login-on-sso-atius-com-br*
*Context gathered: 2026-06-28*
