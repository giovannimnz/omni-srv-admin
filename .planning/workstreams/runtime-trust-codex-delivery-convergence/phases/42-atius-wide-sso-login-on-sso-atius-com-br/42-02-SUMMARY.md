---
phase: 42-atius-wide-sso-login-on-sso-atius-com-br
plan: 42-02
subsystem: auth
tags: [sso, oidc, keycloak, nextjs, fastify, ats]
requires:
  - phase: 36-keycloak-sso-and-coexistence
    provides: Keycloak realm `atius` at `auth.atius.com.br` and the legacy ATS JWT-cookie baseline
  - phase: 42-01
    provides: Redirect allowlist, mocked OIDC bridge, and logout contract tests for Wave 0
provides:
  - ATS-hosted SSO facade on `sso.atius.com.br` with server-side `return_to` normalization
  - Backend OIDC callback bridge that exchanges the auth code and reissues the legacy `auth-token`
  - Canonical middleware/logout wiring that sends protected production hosts through `sso.atius.com.br`
affects: [42-03, ats-auth, ats-frontend, keycloak-edge]
tech-stack:
  added: []
  patterns: [allowlisted return_to normalization, transient PKCE/nonce cookies, OIDC-to-legacy-cookie bridge]
key-files:
  created:
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/state.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/oidc.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/sso/login/page.tsx
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/login/route.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/callback/route.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/logout/route.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/sso.js
  modified:
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts
    - /home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/contexts/auth-context.tsx
    - /home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js
key-decisions:
  - "The ATS frontend now fronts `sso.atius.com.br` and delegates browser auth to Keycloak through Authorization Code Flow instead of reviving password-grant UX."
  - "The backend bridge reissues only the existing `auth-token`; Keycloak remains identity-only while ATS DB flags stay authoritative for RBAC."
  - "Protected production hosts now treat `sso.atius.com.br/login` as canonical, while localhost keeps the preexisting local-login fallback."
patterns-established:
  - "Return target safety is centralized in one Next utility and reused by the page, middleware, login route, callback route, and logout route."
  - "OIDC callback handling is split cleanly: Next validates transient browser state, Fastify exchanges the code and maps the ATS user, and only `auth-token` crosses back to the browser."
requirements-advanced: [SSO-01, SSO-02, SSO-03, SSO-04, SSO-05]
coverage:
  - id: D1
    description: ATS exposes the `sso.atius.com.br` facade with allowlisted `return_to`, PKCE/nonce cookies, and redacted login/callback handling.
    requirement: SSO-01
    verification:
      - kind: unit
        ref: tests/backend/auth/test_sso_redirect_allowlist.test.js#Phase 42 redirect allowlist contract
        status: pass
      - kind: other
        ref: cd /home/ubuntu/GitHub/Atius-Capital/ats/frontend && npm run build
        status: pass
    human_judgment: false
  - id: D2
    description: ATS backend exchanges the OIDC code server-side, maps exactly one active ATS user, and issues only the legacy `auth-token`.
    requirement: SSO-03
    verification:
      - kind: unit
        ref: tests/backend/auth/test_sso_oidc_bridge.test.js#Phase 42 mocked OIDC bridge contract
        status: pass
      - kind: integration
        ref: cd /home/ubuntu/GitHub/Atius-Capital/ats && npm run test:backend:ci
        status: pass
    human_judgment: false
  - id: D3
    description: Middleware and logout now route production app hosts through `sso.atius.com.br` and clear ATS cookies before Keycloak end-session.
    requirement: SSO-05
    verification:
      - kind: automated_ui
        ref: tests/frontend/e2e/test_sso_global_logout.spec.ts#Phase 42 global logout contract
        status: pass
      - kind: other
        ref: cd /home/ubuntu/GitHub/omni-srv-admin && node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" graphify status
        status: pass
    human_judgment: false
duration: 14 min
completed: 2026-06-28
status: complete
---

# Phase 42 Plan 02: ATS SSO Facade Summary

**ATS agora hospeda a facade `sso.atius.com.br`, troca o callback OIDC com Keycloak no backend e preserva o `auth-token` legado com RBAC ainda decidido pelo banco local.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-28T08:29:00Z
- **Completed:** 2026-06-28T08:42:50Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Adicionei a camada SSO do frontend ATS com allowlist de `return_to`, cookies transitórios de state/nonce/PKCE e shell de login compatível com o `42-UI-SPEC.md`.
- Implementei o bridge OIDC no Fastify para trocar o `code`, validar claims mínimas do `id_token`, mapear exatamente um usuário ATS ativo e emitir só o `auth-token` já usado pela aplicação.
- Rewirei middleware e logout para tratar `sso.atius.com.br` como host canônico de login/logout em produção, mantendo o fallback local em `localhost`.

## Task Commits

1. **Task 1: Implement SSO redirect, state, OIDC, and login facade routes** - `aac2aca` (`feat`)
2. **Task 2: Implement ATS backend OIDC bridge with RBAC-compatible session** - `5644b9e` (`feat`)
3. **Task 3: Wire middleware and logout to canonical SSO host** - `b056646` (`feat`)

## Files Created/Modified

- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/redirects.ts` - contrato central de hosts/prefixos permitidos, `return_to` normalizado e URL canônica de logout.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/state.ts` - geração/leitura/limpeza de cookies transitórios para state, nonce, PKCE e destino final.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/lib/sso/oidc.ts` - leitura fail-closed de env, discovery OIDC, URL de authorization e URL de end-session.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/sso/login/page.tsx` - shell de login/logout completo com estados aprovados e sem vazar parâmetros crus.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/login/route.ts` - valida `return_to`, persiste state/nonce/PKCE e redireciona para Keycloak.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/callback/route.ts` - valida state, chama o bridge backend, encaminha só `auth-token` e limpa cookies transitórios.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/sso.js` - troca server-side do auth code, consulta userinfo, mapeia usuário ATS ativo e reemite a sessão local.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/app/api/sso/logout/route.ts` - limpa variantes do cookie ATS e faz handoff para o end-session do Keycloak.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts` - adiciona `sso.atius.com.br`, monta `return_to` absoluto e manda hosts protegidos de produção para o login central.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/contexts/auth-context.tsx` - troca o logout produtivo para navegação via `/api/sso/logout`.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` - registra o novo subrouter `/auth/sso/callback`.

## Decisions Made

- A facade SSO fica dentro do frontend ATS em vez de um host Keycloak “puro”, porque a bridge precisa controlar allowlist, callback e reemissão do `auth-token`.
- O bridge backend valida issuer/audience/nonce e exige um único match ativo por email/username antes de criar sessão local.
- O logout produtivo passou a ser navegação browser-based, não `fetch`, para garantir limpeza de cookie e redirecionamento RP-initiated sem loop de auto-login.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fechei o bypass de auth nas rewrites de raiz dos hosts protegidos**
- **Found during:** Task 3
- **Issue:** `backtest.atius.com.br`, `strategy.atius.com.br` e `admin.atius.com.br` faziam rewrite de `/` antes da checagem de auth, o que podia deixar a raiz escapar do redirecionamento canônico.
- **Fix:** As rewrites de `/` agora só acontecem quando já existe `auth-token`; sem cookie, o fluxo passa pelo redirect SSO normal.
- **Files modified:** `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`
- **Verification:** `npm run build`, `tests/frontend/e2e/test_sso_global_logout.spec.ts`
- **Committed in:** `b056646`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** Correção necessária para manter a proteção do host canônico coerente com o contrato do plano, sem ampliar escopo além do middleware já tocado.

## Issues Encountered

- Os testes de Wave 0 (`test_sso_redirect_allowlist` e `test_sso_oidc_bridge`) já passavam antes da implementação porque são contratos mockados, então o gate real para integração ficou no build do frontend, no Playwright de logout e no backend CI completo.
- O `npm run test:backend:ci` terminou verde, mas o Jest reportou operações assíncronas abertas em suites antigas de exchanges/Telegram fora do escopo desta fase. Não houve falha, apenas ruído de teardown.

## User Setup Required

None - no external service configuration required in this plan. The code expects `SSO_OIDC_CLIENT_ID` and `SSO_OIDC_CLIENT_SECRET` at runtime, but this plan did not mutate envs or secrets.

## Next Phase Readiness

- O ATS já está pronto para o rollout de edge/publicação do `sso.atius.com.br` na `42-03`, reaproveitando esta facade e o bridge backend.
- A próxima fase só precisa publicar o host, alinhar headers/vhost e validar o smoke do edge; não precisa redesenhar o fluxo de sessão local.

## Requirement Status

This summary advances the implementation side of Phase 42, but the phase is not
complete yet. `42-03` still needs to close the publication gate, edge headers,
final smoke, and rollback/runbook requirements before SSO can be marked
complete in the roadmap and requirements ledger.

## Self-Check: PASSED

- Verified `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/42-02-SUMMARY.md` exists on disk.
- Verified ATS task commits `aac2aca`, `5644b9e`, and `b056646` exist in `/home/ubuntu/GitHub/Atius-Capital/ats`.
