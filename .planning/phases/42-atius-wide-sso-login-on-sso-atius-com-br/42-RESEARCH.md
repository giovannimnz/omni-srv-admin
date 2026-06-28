# Phase 42: Atius-wide SSO Login on sso.atius.com.br - Research

**Researched:** 2026-06-28  
**Domain:** Web SSO, OIDC Authorization Code Flow, Keycloak/FreeIPA, ATS JWT-cookie coexistence, Apache/Cloudflare edge  
**Confidence:** HIGH for local code/runtime facts; MEDIUM for external framework guidance because Context7 exposed Keycloak 26.5.2 docs while the local baseline is Keycloak 26.6.3. [VERIFIED: `.planning/phases/36-keycloak-sso-and-coexistence/36-01-SUMMARY.md` + Context7 `/keycloak/keycloak/26.5.2`]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

<!-- DATA_A7F3KQ91_START -->
## Implementation Decisions

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
<!-- DATA_A7F3KQ91_END -->

### the agent's Discretion

No `## the agent's Discretion` section exists in `42-CONTEXT.md`. The `## Specific Ideas` section is copied verbatim as planning guidance. [VERIFIED: `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-CONTEXT.md`]

<!-- DATA_B2L8MR04_START -->
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
<!-- DATA_B2L8MR04_END -->

### Deferred Ideas (OUT OF SCOPE)

<!-- DATA_C9P6ZT15_START -->
## Deferred Ideas

- Migrating every non-ATS Atius app in one cutover is deferred. Phase 42 should
  produce the Atius-wide login foundation and at most one reference migration
  path through ATS.
- Cross-domain Horistic `.horistic.com` SSO is deferred unless the plan finds a
  low-risk federation-only contract. `.atius.com.br` is the immediate domain.
- Windows/Mac domain login remains out of scope; this is web SSO.
- Creating or rotating secrets is execution scope, not planning scope.
<!-- DATA_C9P6ZT15_END -->
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SSO-01 | Operador tem `sso.atius.com.br` definido como subdominio canonico de login da Atius, com contrato de DNS/Apache/Cloudflare/TLS e rollback antes de qualquer publicacao live. | No enabled or available Apache vhost for `sso.atius.com.br` exists today, while `auth.atius.com.br` and ATS app vhosts are enabled; plan must create a gated edge contract and rollback. [VERIFIED: `/etc/apache2/sites-enabled` read-only inventory + `/etc/apache2/sites-available` check] |
| SSO-02 | Keycloak existente em `auth.atius.com.br` vira provedor OIDC controlado para login Atius-wide sem quebrar o SSO/JWT legado durante a migracao. | Phase 36 verified Keycloak 26.6.3 on `127.0.0.1:8180`, realm `atius`, FreeIPA federation, Apache proxy at `auth.atius.com.br`, and unchanged legacy Apache/JWT surfaces. [VERIFIED: `.planning/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md`] |
| SSO-03 | ATS usa o novo fluxo SSO como primeira aplicacao de referencia, preservando `auth-token`, RBAC (`is_admin`, `can_access_*`) e rotas protegidas ate a compatibilidade ser provada. | ATS backend currently issues/verifies `auth-token`, refreshes it, and enforces RBAC from the `"user"` table; frontend middleware is only a UX guard. [VERIFIED: `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` + `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/middleware/permissions.js` + `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`] |
| SSO-04 | `sso.atius.com.br` suporta redirect seguro de volta para app hosts Atius sem open redirect. | OWASP recommends avoiding user-controlled redirect URLs or validating them against a trusted allowlist; current ATS uses `redirect=` query params in login paths, so Phase 42 needs explicit host/path validation tests. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html] |
| SSO-05 | Logout global limpa sessao Keycloak e cookies legados `.atius.com.br`, com smoke test cross-subdomain e rollback documentado. | ATS already double-clears `auth-token` with `.atius.com.br` domain and no-domain variants; Keycloak adds RP-initiated logout through the OIDC end-session endpoint. [VERIFIED: ATS logout route + Context7 `/keycloak/keycloak/26.5.2`] |
| SSO-06 | Tokens, client secrets, session secrets e credenciais de smoke ficam fora de Git, `.planning`, Obsidian, logs e shell history. | Phase 36 documents root-only Keycloak env paths, and current ATS runtime tests contain hardcoded fallback smoke credentials that must be removed before reuse; this research intentionally does not copy secret values. [VERIFIED: `docs/domain/keycloak-freeipa-coexistence.md` + ATS test inspection] |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- Use PT-BR with Giovanni unless requested otherwise; keep standard tool terms in English. [VERIFIED: prompt-provided AGENTS.md instructions]
- Be direct and operational: commands, paths, evidence, blockers, next steps. [VERIFIED: prompt-provided AGENTS.md instructions]
- Document non-trivial infrastructure/incident/architecture work in `~/GitHub/obsidian-vault/ideaverse` when execution changes future operations. [VERIFIED: prompt-provided AGENTS.md instructions]
- Create or verify a backup before destructive or hard-to-reverse actions. [VERIFIED: prompt-provided AGENTS.md instructions]
- In repos with `.planning/config.json` and `graphify.enabled: true`, run Graphify status/query before planning or broad codebase work; current graph was fresh and not commit-stale during this research. [VERIFIED: prompt-provided AGENTS.md instructions + `gsd-tools graphify status`]
- Use GBrain for local operational memory before non-trivial work; query returned no SSO-specific prior entry, so this research relies on phase artifacts, code, vault notes, and docs. [VERIFIED: prompt-provided AGENTS.md instructions + `gbrain query`]
- Do not overwrite, revert, or clean dirty worktrees; ATS has extensive pre-existing dirty/untracked work and Phase 42 planning must avoid resets/cleanup. [VERIFIED: prompt-provided AGENTS.md instructions + `git -C /home/ubuntu/GitHub/Atius-Capital/ats status --short`]
- Do not copy secrets into docs, diffs, logs, or planning files; this is binding for Keycloak client secrets, JWT secrets, test passwords, bearer tokens, and smoke credentials. [VERIFIED: prompt-provided AGENTS.md instructions]
- Local project identity: repo `omni-srv-admin`, display name `Omni Srv Admin`, domain `atius.com.br`, host `10.1.1.1`. [VERIFIED: `./AGENTS.md`]

## Summary

Phase 42 should be planned as a controlled authentication migration, not a direct authorization rewrite. The best planning target is `sso.atius.com.br` as an Atius login facade that delegates authentication to the existing `auth.atius.com.br` Keycloak realm and then bridges back into the ATS legacy `auth-token` session until OIDC-native authorization is separately proven. This recommendation follows the locked requirement to preserve ATS `auth-token`, refresh/logout, and DB-backed RBAC. [VERIFIED: `42-CONTEXT.md` + ATS auth/RBAC files]

The Phase 36 Keycloak baseline is usable but intentionally additive: Keycloak 26.6.3 is active on `atius-srv-1`, listens privately on `127.0.0.1:8180`, is exposed through Apache as `auth.atius.com.br`, and has a working `atius` realm with FreeIPA LDAP federation and OIDC smoke evidence. Phase 42 should not replace that with password grant; use OIDC Authorization Code Flow for browser login and reserve direct access/password grant for controlled diagnostics only. [VERIFIED: `36-01-SUMMARY.md` + `36-VERIFICATION.md`] [CITED: Context7 `/keycloak/keycloak/26.5.2`]

The main planner risk is edge/session fragility: `sso.atius.com.br` does not exist in Apache today, ATS middleware derives host behavior from forwarded/host headers, current ATS app vhosts are inconsistent about explicit `X-Forwarded-Host`, and historical incidents show cookie domain, Secure/SameSite, PM2 env, and build cache mistakes can make SSO appear partially working while silently failing cross-subdomain. [VERIFIED: Apache read-only inventory + `.planning/codebase/CONCERNS.md` + vault notes]

**Primary recommendation:** Plan a `sso.atius.com.br` login facade with strict redirect allowlist, OIDC Authorization Code callback, ATS local-session bridge, and two-phase rollout: first local `--resolve`/test-only, then gated Apache/Cloudflare/Keycloak live apply with rollback. [VERIFIED: requirements + local code + Context7 Keycloak docs]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Canonical login UX and redirect allowlist | Frontend Server / SSO facade | Browser / ATS frontend | `sso.atius.com.br` must validate redirect targets server-side before any browser redirect; browser UI must not decide trust. [VERIFIED: `42-CONTEXT.md` + OWASP redirect guidance] |
| OIDC authentication | Identity Provider / Keycloak | Apache reverse proxy | Keycloak owns user authentication, token issuance, discovery, refresh, and end-session endpoints; Apache must preserve issuer/redirect correctness through proxy headers. [VERIFIED: Phase 36 docs + Context7 Keycloak reverse-proxy docs] |
| ATS local session bridge | API / Backend | Frontend Server | Existing ATS JWT cookie is issued and verified by backend routes; callback bridge should mint or validate only after Keycloak code exchange succeeds. [VERIFIED: ATS `routes/auth`, `routes/token`] |
| ATS authorization and trading safeguards | API / Backend + Database | Browser / Client UX | Existing backend reads `"user"` permissions (`is_admin`, `can_access_*`) and must remain authoritative until claim mapping is explicitly verified. [VERIFIED: ATS `middleware/permissions.js`] |
| Cross-subdomain route protection | Browser / Client middleware | API / Backend | Next middleware redirects unauthenticated users and protects UX, but backend still enforces auth/RBAC. [VERIFIED: ATS `frontend/src/middleware.ts` + `permissions.js`] |
| Global logout | SSO facade / Frontend Server | Keycloak + ATS API | Logout must orchestrate Keycloak RP-initiated logout and legacy cookie clearing for `.atius.com.br` plus no-domain stale cookies. [VERIFIED: ATS logout handlers + Context7 Keycloak logout docs] |
| Edge/TLS/proxy contract | CDN / Static Edge + Apache | Keycloak / ATS services | `sso.atius.com.br` requires DNS/Cloudflare/TLS/vhost/header contract before live publication; current vhost is absent. [VERIFIED: Apache inventory + Phase 42 requirement SSO-01] |
| Secret handling | OS / Secret store | CI/test runner env | Existing Keycloak env files are root-only paths, and SSO-06 forbids secrets in Git/planning/logs/history. [VERIFIED: `docs/domain/keycloak-freeipa-coexistence.md` + `42-CONTEXT.md`] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Keycloak | 26.6.3 local baseline | OIDC provider, browser SSO session, token endpoint, logout endpoint, FreeIPA federation | Already installed and verified in Phase 36; do not introduce another IdP. [VERIFIED: `36-01-SUMMARY.md`] |
| Apache HTTP Server | 2.4.58 (Ubuntu) | TLS termination, reverse proxy, `X-Forwarded-*`, local `--resolve` smoke target | Existing production edge on SRV-1; modules `headers`, `proxy_http`, `rewrite`, and `ssl` are loaded. [VERIFIED: `apache2ctl -v` + `apache2ctl -M`] |
| ATS Next.js frontend | 14.2.29 lockfile | Middleware, login UI, route handlers, logout cookie emission | Existing app surface for `trade`, `painel`, `dashboard`, `backtest`, `strategy`, `admin`; no upgrade recommended. [VERIFIED: ATS `frontend/package-lock.json`] |
| ATS Fastify API | 5.7.1 lockfile | `/v1/auth/me`, `/auth/refresh`, `/auth/logout`, token/session bridge endpoints | Existing backend session/RBAC enforcement tier. [VERIFIED: ATS `package-lock.json`] |
| `@fastify/cookie` | 11.0.2 lockfile | Parse, set, and clear `auth-token` cookies | Existing cookie layer; docs require matching path/domain on deletion. [VERIFIED: ATS `package-lock.json` + Context7 `/fastify/fastify-cookie`] |
| `jsonwebtoken` | 9.0.3 lockfile | Legacy ATS JWT sign/verify | Existing legacy token format; preserve for migration compatibility, do not expand as new SSO authority. [VERIFIED: ATS `package-lock.json` + ATS auth code] |
| `jose` | 6.1.3 lockfile | JWT verification in Next middleware / future JWKS verification | Already used in ATS middleware; suitable for edge-side token checks when needed. [VERIFIED: ATS `frontend/package-lock.json` + `frontend/src/middleware.ts`] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| Jest | 30.2.0 lockfile | Backend unit/runtime contract tests | Use for redirect allowlist, OIDC callback bridge, auth-token preservation, RBAC regressions. [VERIFIED: ATS `package-lock.json` + `jest.backend.config.js`] |
| Playwright | 1.58.2 lockfile | Browser cross-subdomain SSO/logout smoke | Use after local/staging edge is available; run one worker because cookies share `.atius.com.br`. [VERIFIED: ATS `package-lock.json` + `playwright.config.js` + existing SSO specs] |
| curl | 8.5.0 | Local `--resolve` smoke and Set-Cookie inspection | Use before any public DNS/Cloudflare change. [VERIFIED: `curl --version`] |
| OpenSSL | 3.0.13 | TLS/certificate inspection | Use for `sso.atius.com.br` certificate and origin checks. [VERIFIED: `openssl version`] |
| PM2 | 7.0.1 | ATS process runtime | Use read-only status before cutover and gated restart only during execution. [VERIFIED: `pm2 --version` + ATS health vault note] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SSO facade delegating to `auth.atius.com.br` | Directly alias/front Keycloak as `sso.atius.com.br` | Direct Keycloak fronting is simpler but cannot by itself issue ATS `auth-token`, enforce app redirect allowlist, or clear stale ATS cookies; it risks breaking SSO-03 and SSO-05. [VERIFIED: `42-CONTEXT.md` + ATS auth/logout code] |
| Bridge OIDC callback to ATS local JWT | Teach ATS middleware/API to validate Keycloak tokens directly | Native validation reduces legacy JWT reliance later, but first cutover must still query ATS DB for RBAC and preserve existing cookie/session behavior. [VERIFIED: ATS RBAC code + `42-CONTEXT.md`] |
| App-local `/login` on every ATS subdomain | Centralized `sso.atius.com.br/login` | Existing app-local login works today; centralized login is required by SSO-01 and needs redirect hardening to avoid open redirect. [VERIFIED: `42-CONTEXT.md` + ATS middleware] |

**Installation:**

```bash
# No package install is recommended for Phase 42 research/planning.
# Use existing ATS lockfile versions; do not upgrade Next.js or Playwright in this phase.
```

**Version verification:** `npm view` on 2026-06-28 returned latest versions `next@16.2.9`, `fastify@5.8.5`, `@fastify/cookie@11.0.2`, `jsonwebtoken@9.0.3`, `jose@6.2.3`, `jest@30.4.2`, `@playwright/test@1.61.1`; ATS lockfiles currently pin older compatible versions for Next, Fastify, Jest, Playwright, and `jose`. [VERIFIED: npm registry + ATS lockfiles]

## Package Legitimacy Audit

No external package installation is recommended. Existing package names were discovered from ATS `package.json`/lockfiles, then checked with the GSD package-legitimacy seam and npm registry. [VERIFIED: ATS package files + npm registry + `package-legitimacy check`]

| Package | Registry | Age / Signal | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|--------------|-----------|-------------|---------|-------------|
| `next` | npm | latest published 2026-06-09; seam flags latest as too-new | ~40M/week | `github.com/vercel/next.js` | SUS for latest | Keep existing `14.2.29`; do not upgrade without `checkpoint:human-verify`. [VERIFIED: npm registry + package-legitimacy] |
| `fastify` | npm | established | ~8.7M/week | `github.com/fastify/fastify` | OK | Approved existing dependency. [VERIFIED: npm registry + package-legitimacy] |
| `@fastify/cookie` | npm | established | ~1.4M/week | `github.com/fastify/fastify-cookie` | OK | Approved existing dependency. [VERIFIED: npm registry + package-legitimacy] |
| `jsonwebtoken` | npm | established | ~49M/week | `github.com/auth0/node-jsonwebtoken` | OK | Approved existing dependency for legacy compatibility only. [VERIFIED: npm registry + package-legitimacy] |
| `jose` | npm | established | ~88M/week | `github.com/panva/jose` | OK | Approved existing dependency. [VERIFIED: npm registry + package-legitimacy] |
| `jest` | npm | established | ~44M/week | `github.com/jestjs/jest` | OK | Approved existing test dependency. [VERIFIED: npm registry + package-legitimacy] |
| `@playwright/test` | npm | latest published 2026-06-23; seam flags latest as too-new | ~41M/week | `github.com/microsoft/playwright` | SUS for latest | Keep existing `1.58.2`; do not upgrade without `checkpoint:human-verify`. [VERIFIED: npm registry + package-legitimacy] |

**Packages removed due to [SLOP] verdict:** none. [VERIFIED: package-legitimacy]  
**Packages flagged as suspicious [SUS]:** `next` latest and `@playwright/test` latest only; planner should not install/upgrade them in Phase 42 unless a human checkpoint approves. [VERIFIED: package-legitimacy]

## Architecture Patterns

### System Architecture Diagram

```text
Unauthenticated app request
  -> trade/painel/dashboard/backtest/strategy/admin.atius.com.br
  -> Apache vhost preserves Host and sets required X-Forwarded-* contract
  -> ATS Next middleware sees missing auth-token
  -> redirect to https://sso.atius.com.br/login?return_to=<allowlisted target>
  -> SSO facade validates return_to host/path against config
     -> invalid target: 400/403, no redirect
     -> valid target: start OIDC Authorization Code Flow
  -> browser redirects to Keycloak at auth.atius.com.br/realms/atius/protocol/openid-connect/auth
  -> Keycloak authenticates against FreeIPA-backed realm
  -> browser returns to sso.atius.com.br/callback?code=...&state=...
  -> SSO facade validates state and exchanges code at Keycloak token endpoint
  -> SSO facade maps Keycloak subject/email to ATS user
     -> no ATS user / inactive user: deny without issuing auth-token
     -> valid ATS user: ATS backend/session bridge issues legacy auth-token cookie for .atius.com.br
  -> browser redirects to original allowlisted app target
  -> ATS backend enforces RBAC from database on protected API routes
```

This flow keeps Keycloak as identity provider and ATS backend as authorization authority. [VERIFIED: Phase 36 docs + ATS backend code + Context7 Keycloak OIDC docs]

### Recommended Project Structure

```text
/home/ubuntu/GitHub/Atius-Capital/ats/
├── frontend/src/app/sso/                 # optional route group if SSO facade is hosted in existing Next app [ASSUMED]
├── frontend/src/app/api/sso/             # callback/logout helpers if using Next route handlers [ASSUMED]
├── frontend/src/lib/sso/                 # redirect allowlist, state cookie helpers, OIDC client wrapper [ASSUMED]
├── backend/server/routes/auth/           # legacy auth-token bridge, refresh, logout compatibility [VERIFIED: codebase]
├── backend/server/middleware/            # authoritative RBAC remains here [VERIFIED: codebase]
└── tests/
    ├── backend/auth/                     # redirect/callback/session/RBAC contract tests [VERIFIED: test tree]
    └── frontend/e2e/                     # cross-subdomain login/logout browser smoke [VERIFIED: test tree]

/home/ubuntu/GitHub/omni-srv-admin/
├── docs/domain/                          # Keycloak/SSO runbook updates [VERIFIED: repo]
└── .planning/phases/42-.../              # GSD planning artifacts [VERIFIED: repo]
```

### Pattern 1: SSO Facade, Not Keycloak Alias

**What:** `sso.atius.com.br` should own login UX, redirect validation, callback handoff, and global logout while delegating actual authentication to `auth.atius.com.br` Keycloak. [VERIFIED: `42-CONTEXT.md`]  
**When to use:** Use this for Phase 42 because ATS must keep legacy `auth-token` and DB-backed RBAC until migration is proven. [VERIFIED: ATS auth/RBAC code]  
**Example:**

```typescript
// Source: Context7 /keycloak/keycloak/26.5.2 + ATS auth-token bridge requirement
// Pseudocode only; do not hardcode secrets or client credentials.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const returnTo = validateAtiusReturnTo(url.searchParams.get("return_to"));
  const state = await createServerSideState({ returnTo });

  return redirectToKeycloakAuthorizationEndpoint({
    realm: "atius",
    clientId: process.env.ATIUS_SSO_CLIENT_ID,
    redirectUri: "https://sso.atius.com.br/callback",
    state,
    scope: "openid email profile"
  });
}
```

### Pattern 2: Strict Redirect Allowlist

**What:** Parse `return_to` with `new URL`, require `https`, require exact host from config, and require path prefix from config; reject protocol-relative, unknown host, userinfo, non-HTTPS, and open-ended URLs. [CITED: OWASP Unvalidated Redirects Cheat Sheet]  
**When to use:** Every `redirect`, `return_to`, `next`, and `post_logout_redirect_uri` path in `sso.atius.com.br`, Swagger/docs login, and ATS login compatibility. [VERIFIED: ATS middleware/API redirect usage]  
**Example:**

```typescript
// Source: OWASP Unvalidated Redirects Cheat Sheet + Next.js URL/redirect docs via Context7.
const RETURN_TARGETS = new Map<string, string[]>([
  ["trade.atius.com.br", ["/", "/painel", "/sinal"]],
  ["painel.atius.com.br", ["/"]],
  ["dashboard.atius.com.br", ["/"]],
  ["backtest.atius.com.br", ["/"]],
  ["strategy.atius.com.br", ["/"]],
  ["admin.atius.com.br", ["/"]]
]);

export function validateAtiusReturnTo(raw: string | null): URL {
  if (!raw) return new URL("https://trade.atius.com.br/");
  const parsed = new URL(raw, "https://sso.atius.com.br");

  if (parsed.protocol !== "https:") throw new Error("invalid_redirect_protocol");
  if (parsed.username || parsed.password) throw new Error("invalid_redirect_userinfo");
  const allowedPaths = RETURN_TARGETS.get(parsed.hostname);
  if (!allowedPaths) throw new Error("invalid_redirect_host");
  if (!allowedPaths.some((prefix) => parsed.pathname === prefix || parsed.pathname.startsWith(`${prefix}/`))) {
    throw new Error("invalid_redirect_path");
  }
  return parsed;
}
```

### Pattern 3: Dual Logout Orchestration

**What:** Logout must clear ATS cookies and the Keycloak browser SSO session. ATS already appends multiple `Set-Cookie` headers to clear `.atius.com.br` and no-domain variants; keep that behavior and add Keycloak RP-initiated logout. [VERIFIED: ATS `frontend/src/app/api/auth/logout/route.ts` + Context7 Keycloak logout docs]  
**When to use:** `sso.atius.com.br/logout` and compatibility logout from ATS app menu. [VERIFIED: ATS auth context logout flow]  
**Example:**

```typescript
// Source: ATS logout route + Fastify cookie docs + Keycloak RP-initiated logout docs.
export async function POST() {
  await fetch("http://localhost:8015/v1/auth/logout", { method: "POST" }).catch(() => null);

  const response = NextResponse.redirect(
    "https://auth.atius.com.br/realms/atius/protocol/openid-connect/logout" +
      "?post_logout_redirect_uri=https%3A%2F%2Fsso.atius.com.br%2Flogged-out"
  );

  response.headers.append(
    "Set-Cookie",
    "auth-token=; Path=/; Domain=.atius.com.br; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
  );
  response.headers.append(
    "Set-Cookie",
    "auth-token=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
  );
  return response;
}
```

### Anti-Patterns to Avoid

- **Direct password grant as user-facing login:** password grant passed Phase 36 smoke but browser login should use Authorization Code Flow. [VERIFIED: Phase 36 smoke + Context7 Keycloak docs]
- **Freeform `redirect=` propagation:** existing app URLs use redirect params; Phase 42 must not forward them without allowlist validation. [VERIFIED: ATS middleware/API code + OWASP]
- **Moving RBAC into frontend or Keycloak claims in the first cutover:** current trading permissions are database-backed and enforced by ATS backend; claim mapping is deferred until verified. [VERIFIED: `42-CONTEXT.md` + ATS `permissions.js`]
- **Assuming Apache headers are uniform:** `ProxyPreserveHost On` is present, but explicit `X-Forwarded-Host` is not consistently set across ATS vhosts; make the header contract explicit. [VERIFIED: `/etc/apache2/sites-enabled/*atius*.conf` read-only inventory]
- **Reusing live tests with hardcoded credential fallbacks:** current runtime SSO/RBAC tests include fallback credentials in code; remove fallbacks before any Phase 42 live smoke. [VERIFIED: ATS runtime test inspection]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser SSO protocol | Custom login/token protocol | Keycloak OIDC Authorization Code Flow | Discovery, token exchange, refresh, logout, session handling, and issuer consistency are already provided. [CITED: Context7 `/keycloak/keycloak/26.5.2`] |
| Token signature/JWKS validation | Custom JWT decoder | `jose` / Keycloak JWKS / existing `jsonwebtoken` only for legacy ATS JWT | Prior SSO incident showed custom cookie/token decoding caused incompatibility; use library-backed formats. [VERIFIED: vault `2026-06-02-phase7-sso-success.md` + ATS deps] |
| Cookie deletion | Manual single cookie clear | Existing Next/Fastify cookie APIs plus multiple `Set-Cookie` headers for domain/no-domain | Cookie deletion requires matching path/domain; current ATS double-clear handles stale cookies. [VERIFIED: ATS logout code + Context7 Fastify cookie docs] |
| Redirect validation | Regex-only or denylist redirect filtering | Server-side exact allowlist of scheme, host, and path | OWASP recommends allowlist validation for user-influenced redirect targets. [CITED: OWASP Unvalidated Redirects Cheat Sheet] |
| Authorization model | Keycloak claim-only permission migration in Phase 42 | ATS DB-backed RBAC until role/claim mapping is proven | Trading access flags live in ATS database and backend middleware. [VERIFIED: ATS `permissions.js`] |
| Edge publication | Direct DNS/vhost live edits | Backup, staged Apache config, `apache2ctl configtest`, local `curl --resolve`, then gated reload | SSO-01 requires rollback before publication, and current `sso` vhost is absent. [VERIFIED: `42-CONTEXT.md` + Apache inventory] |

**Key insight:** This phase is hard because it crosses identity provider, reverse proxy, browser cookies, ATS session code, and trading authorization. Custom glue should be limited to allowlisted redirects and session bridging; protocol, cookie, and RBAC primitives should stay in standard libraries/existing code. [VERIFIED: local code + external docs]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | ATS stores user activation and permissions in the `"user"` table; Keycloak realm `atius` imports FreeIPA users through LDAP federation; browsers may hold existing `.atius.com.br` and no-domain `auth-token` cookies. [VERIFIED: ATS SQL queries in auth/RBAC + Phase 36 docs] | Plan an identity mapping check from Keycloak subject/email/username to ATS user IDs; do not migrate RBAC until mapping is verified. Add browser cookie cleanup tests for domain and no-domain variants. |
| Live service config | Apache has enabled `auth.atius.com.br` and ATS app vhosts; no enabled or available `sso.atius.com.br` vhost exists; Cloudflare DNS/TLS state was not changed or queried through an authenticated API in this research. [VERIFIED: `/etc/apache2/sites-enabled` + `/etc/apache2/sites-available`] [ASSUMED] | Planner must add a live edge inventory task before apply: Cloudflare record/proxy state, Apache vhost backup, certificate coverage, `apache2ctl configtest`, local `--resolve` smoke, and rollback. |
| OS-registered state | `keycloak.service` is active, starts `/opt/keycloak/bin/kc.sh start --optimized`, and reads `/etc/keycloak/keycloak.env`; `apache2` is active; ports `8180`, `8015`, `3015`, `80`, and `443` are listening. [VERIFIED: `systemctl cat/show/is-active` + `ss -ltn`] | Do not restart services in planning. Execution plan must snapshot service state and include gated restart/reload steps only after local smoke passes. |
| Secrets/env vars | Keycloak env, FreeIPA bind env, and recovery admin env are root-only paths; ATS requires `JWT_SECRET`; current runtime tests include hardcoded fallback smoke credentials. [VERIFIED: `docs/domain/keycloak-freeipa-coexistence.md` + ATS `api.js` + test inspection] | Add Wave 0 secret hygiene task: remove fallback credentials, require env-only smoke credentials, avoid shell history, and never copy client/JWT/test secrets into artifacts. |
| Build artifacts | ATS frontend `.next` exists, PM2 process env can cache stale `NODE_ENV`, and historical SSO failures came from old Next build and PM2 env not applying on restart. [VERIFIED: vault `horistic-login-sso-audit-2026-05-29.md` + ATS package/build files] | Plan gated rebuild/restart only during execution; verify Set-Cookie attributes via `curl -D -` and Playwright after restart. |

**Nothing found in category:** No `sso.atius.com.br` Apache artifact exists locally to migrate in place; it must be added as new edge config during execution. [VERIFIED: `/etc/apache2/sites-enabled` + `/etc/apache2/sites-available`]

## Common Pitfalls

### Pitfall 1: Treating `sso.atius.com.br` as Only a Keycloak Alias
**What goes wrong:** Login reaches Keycloak but ATS never receives a compatible `auth-token`, so existing apps still redirect to `/login` or backend APIs return 401. [VERIFIED: ATS middleware/auth code]  
**Why it happens:** Keycloak authenticates the browser, but ATS currently authorizes and hydrates sessions from a local JWT cookie and database user ID. [VERIFIED: ATS `routes/auth` + `permissions.js`]  
**How to avoid:** Build an OIDC callback-to-ATS-session bridge first. [VERIFIED: `42-CONTEXT.md`]  
**Warning signs:** Keycloak session exists but `/v1/auth/me` returns unauthenticated. [VERIFIED: ATS `/auth/me` behavior]

### Pitfall 2: Open Redirect Through `redirect` / `return_to`
**What goes wrong:** A trusted `sso.atius.com.br` URL can bounce users or OAuth codes to an attacker-controlled domain. [CITED: OWASP Unvalidated Redirects Cheat Sheet]  
**Why it happens:** Login flows naturally carry return destinations, and current ATS has redirect query params. [VERIFIED: ATS middleware/API code]  
**How to avoid:** Use exact allowlist by scheme, host, and path; reject unknown hosts, protocol-relative URLs, userinfo, non-HTTPS, and encoded host bypasses. [CITED: OWASP Unvalidated Redirects Cheat Sheet]  
**Warning signs:** Tests accept `https://evil.example`, `//evil.example`, `https://trade.atius.com.br.evil.example`, or `%2f%2fevil.example`. [VERIFIED: security research synthesis]

### Pitfall 3: Proxy Header Drift
**What goes wrong:** Middleware sees the wrong host and routes/protects the wrong app, causing silent SSO failures or bypass-like UX. [VERIFIED: `.planning/codebase/CONCERNS.md`]  
**Why it happens:** ATS middleware prefers `x-forwarded-host`; Apache vhosts are not uniform in explicitly setting that header. [VERIFIED: ATS middleware + Apache inventory]  
**How to avoid:** Standardize `ProxyPreserveHost`, `X-Forwarded-Host`, `X-Forwarded-Proto`, and `X-Forwarded-Port` contracts for `sso`, ATS app vhosts, and Keycloak. [CITED: Context7 Keycloak reverse-proxy docs]  
**Warning signs:** Local direct port tests pass but domain tests loop or redirect to the wrong subdomain. [VERIFIED: historical concerns + ATS vhost patterns]

### Pitfall 4: Cookie Domain / Secure / SameSite Mismatch
**What goes wrong:** Login succeeds on one subdomain but SSO fails on others. [VERIFIED: vault `horistic-login-sso-audit-2026-05-29.md`]  
**Why it happens:** Production cookie domain is conditional on `NODE_ENV === 'production'`; PM2 env changes may not apply with simple restart. [VERIFIED: ATS auth code + vault note]  
**How to avoid:** Verify `Set-Cookie` with `curl -D -` and Playwright; include `.atius.com.br`, `Secure`, `HttpOnly`, and `SameSite=Lax`. [VERIFIED: ATS cookie code + vault note]  
**Warning signs:** Cookie is host-only, lacks `Secure`, or disappears after cross-subdomain navigation. [VERIFIED: vault note]

### Pitfall 5: Logout Clears Only One Session Layer
**What goes wrong:** User logs out from ATS but remains signed into Keycloak, or Keycloak logout leaves legacy `auth-token` alive. [VERIFIED: ATS logout code + Context7 Keycloak logout docs]  
**Why it happens:** Browser has multiple session layers after migration: Keycloak SSO session and ATS cookie. [VERIFIED: architecture synthesis]  
**How to avoid:** `sso.atius.com.br/logout` must clear ATS cookie variants and call Keycloak RP-initiated logout with an allowlisted post-logout redirect. [VERIFIED: ATS logout route + Context7 Keycloak docs]  
**Warning signs:** After logout, navigating to another ATS subdomain silently re-authenticates without intended state. [VERIFIED: SSO test design]

### Pitfall 6: Secret Leakage in Tests and Docs
**What goes wrong:** Test credentials or client/JWT secrets leak into Git, `.planning`, Obsidian, logs, or shell history. [VERIFIED: `42-CONTEXT.md`]  
**Why it happens:** Current ATS runtime tests have fallback credentials in source code. [VERIFIED: ATS runtime test inspection]  
**How to avoid:** Make live tests fail closed when env vars are absent; read secrets from approved secret store or operator-provided environment only. [VERIFIED: SSO-06]  
**Warning signs:** Test files include default email/password values or docs include raw bearer/JWT/client secrets. [VERIFIED: test inspection]

## Code Examples

Verified patterns from official/local sources:

### Keycloak OIDC Endpoints

```text
# Source: Context7 /keycloak/keycloak/26.5.2
Discovery:
  https://auth.atius.com.br/realms/atius/.well-known/openid-configuration

Authorization:
  https://auth.atius.com.br/realms/atius/protocol/openid-connect/auth

Token exchange / refresh:
  https://auth.atius.com.br/realms/atius/protocol/openid-connect/token

UserInfo:
  https://auth.atius.com.br/realms/atius/protocol/openid-connect/userinfo

RP-initiated logout:
  https://auth.atius.com.br/realms/atius/protocol/openid-connect/logout
```

Do not include client secrets in commands, docs, or planning files. [VERIFIED: SSO-06 + Phase 36 root-only secret note]

### Apache Local Smoke Shape

```bash
# Source: Phase 36 smoke pattern + Phase 42 SSO-01 requirement.
# Use placeholders only; do not include credentials.
apache2ctl configtest
curl --resolve sso.atius.com.br:443:127.0.0.1 \
  -I https://sso.atius.com.br/login
curl --resolve auth.atius.com.br:443:127.0.0.1 \
  -sS https://auth.atius.com.br/realms/atius/.well-known/openid-configuration \
  | jq '.issuer,.authorization_endpoint,.token_endpoint,.end_session_endpoint'
```

### Cookie Inspection

```bash
# Source: ATS current cookie implementation + vault cookie-domain lesson.
# Supply credentials only through env/secret store; never inline them.
curl -sS -D - -o /dev/null \
  -H 'Content-Type: application/json' \
  --data @/path/to/root-only-login-payload.json \
  https://api.atius.com.br/v1/token/generate \
  | rg -i '^set-cookie: auth-token='
```

Expected attributes for production legacy cookie: `Domain=.atius.com.br`, `Path=/`, `HttpOnly`, `Secure`, `SameSite=Lax`. [VERIFIED: ATS auth/token routes]

## State of the Art

| Old Approach | Current Approach | When Changed / Verified | Impact |
|--------------|------------------|--------------------------|--------|
| Direct password grant smoke | Browser Authorization Code Flow for user login | Keycloak docs current for 26.x; Phase 36 password grant was only smoke evidence. [VERIFIED: Phase 36 + Context7] | Planner should not design user-facing login around password grant. |
| App-local login on each ATS subdomain | Canonical `sso.atius.com.br` login facade | Locked in Phase 42 context on 2026-06-28. [VERIFIED: `42-CONTEXT.md`] | Existing `/login` remains compatibility path during migration. |
| Single ATS cookie logout | Dual logout: ATS cookie variants + Keycloak browser SSO session | Required by SSO-05 and Keycloak RP logout docs. [VERIFIED: SSO-05 + Context7] | Logout tests must span Keycloak and ATS cookies. |
| Implicit proxy/host behavior | Explicit Apache/Cloudflare/Keycloak forwarded-header contract | Required by D-07 and Keycloak reverse-proxy docs. [VERIFIED: `42-CONTEXT.md` + Context7] | `X-Forwarded-*` drift becomes a testable contract. |

**Deprecated/outdated:**
- User-facing password grant login: use only for controlled diagnostics, not canonical web SSO. [VERIFIED: Context7 Keycloak OIDC docs]
- Hardcoded live smoke credentials in tests: remove before Phase 42 validation. [VERIFIED: ATS test inspection]
- Cookie decoder or token parser built from guessed formats: prior router SSO incident showed this breaks real sessions. [VERIFIED: vault `2026-06-02-phase7-sso-success.md`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The SSO facade can be hosted inside the existing ATS Next.js app without adding dependencies. [ASSUMED] | Recommended Project Structure | If false, planner must create a separate small service and deployment path. |
| A2 | External Cloudflare DNS/proxy state for `sso.atius.com.br` is not already configured. [ASSUMED] | Runtime State Inventory | If false, execution rollback must include existing DNS/proxy state rather than treating it as new. |
| A3 | Keycloak 26.5.2 Context7 docs are materially applicable to the local Keycloak 26.6.3 OIDC/reverse-proxy behavior. [ASSUMED] | Standard Stack / Patterns | If false, planner must re-check exact 26.6.3 release docs before implementation. |
| A4 | ATS can map Keycloak user identity to an ATS user via email/username without collisions. [ASSUMED] | Runtime State Inventory | If false, implementation needs an explicit linking table or manual migration. |

## Open Questions

1. **Where should the SSO facade live?**  
   What we know: ATS already has Next route handlers and cookie/logout code. [VERIFIED: ATS frontend code]  
   What's unclear: Whether `sso.atius.com.br` should proxy to the existing ATS Next process or a separate minimal service. [ASSUMED]  
   Recommendation: Plan Wave 0 decision after checking vhost/process blast radius; default to existing ATS Next only if routing stays isolated.

2. **What is the final Keycloak client model?**  
   What we know: Phase 36 used `phase36-smoke` for smoke and no app migration. [VERIFIED: Phase 36 docs]  
   What's unclear: Client ID, confidential/public type, redirect URIs, web origins, and post-logout URIs for `sso.atius.com.br`. [VERIFIED: no Keycloak admin export read in this research]  
   Recommendation: Planner must add a no-secrets Keycloak client inventory/export step and a gated admin apply step.

3. **How will ATS users link to Keycloak users?**  
   What we know: ATS auth/RBAC uses local user IDs and active flags. [VERIFIED: ATS auth/RBAC code]  
   What's unclear: Whether FreeIPA/Keycloak usernames/emails uniquely match ATS users. [ASSUMED]  
   Recommendation: Plan read-only DB and Keycloak user mapping audit before issuing ATS cookies from OIDC callbacks.

4. **How will Cloudflare state be applied?**  
   What we know: `cloudflared`, `cfcli`, and `wrangler` were not available on this host, and no live Cloudflare mutation was performed. [VERIFIED: command availability audit]  
   What's unclear: Whether Cloudflare DNS/API access is via dashboard, another tool, or existing inventory. [ASSUMED]  
   Recommendation: Planner must include a manual/API checkpoint for DNS/proxy/TLS with before/after screenshots or API export.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Node.js | ATS frontend/backend tests and route handlers | yes | v24.13.1 | Use existing PM2 runtime; avoid runtime upgrade in this phase. [VERIFIED: `node --version`] |
| npm | ATS test/build commands | yes | 11.8.0 | Use lockfiles; no installs recommended. [VERIFIED: `npm --version`] |
| Apache | Edge/vhost/TLS/proxy contract | yes | 2.4.58 (Ubuntu) | None for live edge; configtest before reload. [VERIFIED: `apache2ctl -v`] |
| Apache modules | Proxy/header/rewrite/TLS | yes | `headers`, `proxy`, `proxy_http`, `proxy_wstunnel`, `rewrite`, `ssl` loaded | None. [VERIFIED: `apache2ctl -M`] |
| Keycloak service | OIDC provider | yes | service active; local baseline 26.6.3 | No alternate IdP; rollback is legacy ATS login. [VERIFIED: `systemctl is-active keycloak` + Phase 36 docs] |
| Keycloak listener | OIDC local backend | yes | `127.0.0.1:8180` listening | Do not expose direct port publicly. [VERIFIED: `ss -ltn`] |
| ATS API | Legacy auth/RBAC | yes | port `8015` listening | Rollback uses existing `/v1/token/generate` and `auth-token`. [VERIFIED: `ss -ltn`] |
| ATS frontend | Existing app hosts | yes | port `3015` listening | Rollback uses current app-local login. [VERIFIED: `ss -ltn`] |
| curl | Smoke tests | yes | 8.5.0 | Use browser/Playwright for cases curl cannot cover. [VERIFIED: `curl --version`] |
| OpenSSL | TLS checks | yes | 3.0.13 | Browser TLS inspection. [VERIFIED: `openssl version`] |
| PM2 | ATS runtime management | yes | 7.0.1 | Gated restart only; avoid in research. [VERIFIED: `pm2 --version`] |
| Cloudflare CLI | DNS/proxy automation | no | none found for `cloudflared`, `cfcli`, `wrangler` | Manual dashboard/API checkpoint or install only after package/tool legitimacy review. [VERIFIED: command availability audit] |
| Java default CLI | Keycloak admin/runtime checks | partial | default `java` is 17.0.19; Phase 36 says Keycloak runtime uses Java 21 | Verify service-specific Java env before changing Keycloak. [VERIFIED: `java -version` + Phase 36 summary] |

**Missing dependencies with no fallback:**
- Authenticated Cloudflare automation is not available locally; planner must add a manual/API checkpoint before any live DNS/proxy change. [VERIFIED: command availability audit]

**Missing dependencies with fallback:**
- Cloudflare CLI can be replaced by dashboard/API export plus human checkpoint for this phase. [ASSUMED]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Jest 30.2.0 for backend/unit/runtime; Playwright 1.58.2 for browser E2E. [VERIFIED: ATS lockfiles] |
| Config file | `/home/ubuntu/GitHub/Atius-Capital/ats/jest.backend.config.js`, `jest.backend.runtime.config.js`, `playwright.config.js`. [VERIFIED: file reads] |
| Quick run command | `cd /home/ubuntu/GitHub/Atius-Capital/ats && npx jest --config jest.backend.config.js tests/backend/auth/test_sso_redirect_allowlist.test.js --runInBand` [ASSUMED: new test file] |
| Full suite command | `cd /home/ubuntu/GitHub/Atius-Capital/ats && npm run test:backend:ci && npx playwright test tests/frontend/e2e/test_sso_regression.spec.ts --project=chromium --workers=1` [VERIFIED: scripts/config + existing SSO spec] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SSO-01 | `sso.atius.com.br` vhost/TLS/proxy contract passes local configtest and `--resolve` smoke before live publication | smoke/manual-gated | `apache2ctl configtest && curl --resolve sso.atius.com.br:443:127.0.0.1 -I https://sso.atius.com.br/login` | no, Wave 0 script needed. [VERIFIED: no sso vhost] |
| SSO-02 | Keycloak discovery and auth-code endpoints reachable through `auth.atius.com.br`; legacy ATS login still works | integration | `curl --resolve auth.atius.com.br:443:127.0.0.1 -sS https://auth.atius.com.br/realms/atius/.well-known/openid-configuration` plus ATS auth runtime test | partial: Phase 36 verification exists; Phase 42 regression missing. [VERIFIED: Phase 36 docs] |
| SSO-03 | OIDC callback bridge issues/preserves ATS `auth-token` and backend RBAC still blocks/permits as before | unit + runtime | `npx jest --config jest.backend.config.js tests/backend/auth/test_sso_oidc_bridge.test.js --runInBand` | no, Wave 0. [ASSUMED] |
| SSO-04 | Redirect allowlist rejects external, protocol-relative, subdomain-confusion, non-HTTPS, and unknown path targets | unit | `npx jest --config jest.backend.config.js tests/backend/auth/test_sso_redirect_allowlist.test.js --runInBand` | no, Wave 0. [ASSUMED] |
| SSO-05 | Logout clears Keycloak session path and `.atius.com.br`/no-domain `auth-token` cookies across app hosts | e2e + header smoke | `npx playwright test tests/frontend/e2e/test_sso_global_logout.spec.ts --project=chromium --workers=1` | no dedicated global Keycloak+ATS logout test; ATS logout tests exist. [VERIFIED: existing test tree] |
| SSO-06 | No secrets in source/planning/log-producing tests; live tests require env credentials and fail closed when absent | static/unit | `rg -n "SSO_TEST_PASSWORD|ADMIN_TEST_PASSWORD|client_secret|JWT_SECRET=.*[^<]" tests backend frontend .planning` with secret-safe patterns | partial; current runtime tests need cleanup. [VERIFIED: test inspection] |

### Sampling Rate

- **Per task commit:** Run focused Jest unit for the touched auth/redirect module plus `npm --prefix frontend run build` if middleware/route handlers change. [VERIFIED: ATS scripts]
- **Per wave merge:** Run backend auth/RBAC tests and Playwright SSO regression with one worker. [VERIFIED: ATS scripts + Playwright config]
- **Phase gate:** Local `--resolve` smoke for `sso` and `auth`, no-open-redirect matrix green, cookie inspection green, global logout green, legacy ATS login rollback green. [VERIFIED: requirements + research synthesis]

### Wave 0 Gaps

- [ ] `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js` - covers SSO-04. [ASSUMED]
- [ ] `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_oidc_bridge.test.js` - covers SSO-02/SSO-03 without live secrets. [ASSUMED]
- [ ] `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_global_logout.spec.ts` - covers SSO-05. [ASSUMED]
- [ ] `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` - remove hardcoded fallback credentials before live reuse. [VERIFIED: test inspection]
- [ ] Apache/edge smoke script under `omni-srv-admin/scripts/` or phase artifact - covers SSO-01 with `apache2ctl configtest`, `curl --resolve`, and rollback checklist. [ASSUMED]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement: false`. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

OWASP ASVS is a standard for testing web application security controls, and the current OWASP page identifies ASVS 5.0.0 as latest stable; this table keeps the GSD template's V2-V6 labels for planner compatibility. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Keycloak OIDC Authorization Code Flow; ATS password login remains rollback/legacy only. [VERIFIED: Phase 36 + Context7 Keycloak] |
| V3 Session Management | yes | Keycloak browser SSO session plus ATS `auth-token` cookie with `HttpOnly`, `Secure`, `SameSite=Lax`, domain cleanup, refresh, and logout. [VERIFIED: ATS auth/logout code] |
| V4 Access Control | yes | ATS backend RBAC from `"user"` table remains authoritative; frontend middleware is UX guard only. [VERIFIED: ATS `permissions.js` + `middleware.ts`] |
| V5 Input Validation | yes | Redirect allowlist using parsed URL scheme/host/path; reject unknown or malformed redirect targets. [CITED: OWASP Unvalidated Redirects Cheat Sheet] |
| V6 Cryptography | yes | Do not hand-roll token crypto; use Keycloak/JWKS, `jose`, and existing `jsonwebtoken` for legacy JWT only. [VERIFIED: dependencies + prior SSO incident note] |

### Known Threat Patterns for Keycloak + ATS + Apache SSO

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Open redirect leaks auth code or sends user to phishing domain | Spoofing / Information Disclosure | Strict allowlist for `return_to`, `redirect`, and `post_logout_redirect_uri`; unit tests for bypass payloads. [CITED: OWASP Unvalidated Redirects Cheat Sheet] |
| Proxy header spoofing or drift causes wrong issuer/host handling | Spoofing / Tampering | Apache must set and overwrite `X-Forwarded-*`; Keycloak must use correct `--proxy-headers` mode. [CITED: Context7 Keycloak reverse-proxy docs] |
| Session fixation/stale cookies after migration | Elevation of Privilege | Clear both `.atius.com.br` and no-domain cookies and verify Set-Cookie attributes after logout. [VERIFIED: ATS logout route + Fastify cookie docs] |
| Authorization bypass by trusting Keycloak claims too early | Elevation of Privilege | Keep ATS backend DB permission checks until claim mapping has tests and UAT. [VERIFIED: `42-CONTEXT.md` + ATS RBAC code] |
| Secret exposure in tests/logs/planning | Information Disclosure | Remove default credentials from runtime tests; use env/secret store and redact command output. [VERIFIED: SSO-06 + test inspection] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-CONTEXT.md` - locked decisions, scope, deferred ideas. [VERIFIED: codebase grep/read]
- `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` - SSO-01..SSO-06 and Phase 42 success criteria. [VERIFIED: codebase grep/read]
- `.planning/phases/36-keycloak-sso-and-coexistence/36-CONTEXT.md`, `36-01-SUMMARY.md`, `36-VERIFICATION.md` - Keycloak/FreeIPA/OIDC baseline. [VERIFIED: codebase read]
- `docs/domain/keycloak-freeipa-coexistence.md` - final Keycloak state and root-only secret paths. [VERIFIED: codebase read]
- ATS auth/session/RBAC files under `/home/ubuntu/GitHub/Atius-Capital/ats/` - current cookie, logout, refresh, middleware, and RBAC contracts. [VERIFIED: file reads]
- `/etc/apache2/sites-enabled/*.atius*.conf`, `systemctl`, `ss`, `apache2ctl` read-only checks - current edge and service inventory. [VERIFIED: local runtime read-only commands]
- Vault notes `2026-06-02-phase7-sso-success.md`, `horistic-login-sso-audit-2026-05-29.md`, `2026-06-15-ats-project-health-review.md` - historical cookie/session/build/runtime lessons. [VERIFIED: local vault reads]

### Secondary (MEDIUM confidence)

- Context7 `/keycloak/keycloak/26.5.2` - OIDC endpoints, Authorization Code Flow, RP-initiated logout, reverse proxy header guidance. [CITED: Context7]
- Context7 `/vercel/next.js/v14.3.0-canary.87` - middleware cookies, route-handler cookies, redirects. [CITED: Context7]
- Context7 `/fastify/fastify-cookie` - `setCookie`, `clearCookie`, and matching domain/path deletion behavior. [CITED: Context7]
- OWASP Unvalidated Redirects and Forwards Cheat Sheet - redirect allowlist and validation guidance. [CITED: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html]
- OWASP ASVS project page - ASVS purpose and current-version note. [CITED: https://owasp.org/www-project-application-security-verification-standard/]

### Tertiary (LOW confidence)

- Assumptions A1-A4 in the Assumptions Log require planner/user confirmation or execution-time inventory. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for local versions and runtime availability; MEDIUM for exact Keycloak 26.6.3 external-doc parity because Context7 returned 26.5.2 docs. [VERIFIED: lockfiles/runtime + Context7]
- Architecture: HIGH for tier boundaries because they are dictated by current ATS/Keycloak responsibilities. [VERIFIED: local code + Phase 36/42 docs]
- Pitfalls: HIGH for local cookie/proxy/test risks; MEDIUM for external open-redirect/ASVS taxonomy. [VERIFIED: local files + OWASP]

**Research date:** 2026-06-28  
**Valid until:** 2026-07-05 for external docs/package latest checks; local code/runtime inventory should be refreshed immediately before planning execution because ATS and Apache state are live and dirty. [VERIFIED: npm modified dates + git status + runtime checks]
