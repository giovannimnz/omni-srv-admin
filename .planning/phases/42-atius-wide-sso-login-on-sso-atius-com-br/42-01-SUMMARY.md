---
phase: 42-atius-wide-sso-login-on-sso-atius-com-br
plan: 42-01
subsystem: testing
tags: [sso, keycloak, jest, playwright, apache, security]
requires:
  - phase: 36-keycloak-sso-and-coexistence
    provides: Keycloak baseline at auth.atius.com.br and ATS legacy auth-token session contract
provides:
  - Wave 0 redirect allowlist contract tests for the six ATS app hosts
  - Mocked OIDC-to-ATS session and RBAC preservation contract coverage
  - Env-only runtime auth smoke plus redacted secret hygiene and edge smoke scripts
affects: [42-02, 42-03, ats-auth, apache-edge, sso-publication]
tech-stack:
  added: [Jest contract tests, Playwright logout contract, bash smoke scripts]
  patterns: [fail-closed env gating, redacted secret scanning, explicit redirect/header assertions]
key-files:
  created:
    - /home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js
    - /home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_oidc_bridge.test.js
    - /home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_global_logout.spec.ts
    - /home/ubuntu/GitHub/omni-srv-admin/scripts/sso-edge-smoke.sh
    - /home/ubuntu/GitHub/omni-srv-admin/scripts/sso-secret-hygiene-scan.sh
  modified:
    - /home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js
key-decisions:
  - "Wave 0 keeps ATS authorization in the DB by contract: OIDC may identify the user, but permissions.js remains authoritative."
  - "Live auth smoke now requires explicit SSO/ADMIN env vars and never falls back to embedded credentials."
  - "Edge validation stays assertion-driven and dry-run-safe until Phase 42-03 publishes sso.atius.com.br."
patterns-established:
  - "Redirect allowlist contract: exact production hosts plus bounded path prefixes, with encoded bypass rejection."
  - "Logout contract: dual auth-token cleanup variants plus Keycloak RP logout handoff."
requirements-completed: [SSO-01, SSO-02, SSO-03, SSO-04, SSO-05, SSO-06]
coverage:
  - id: D1
    description: "Wave 0 ATS auth contracts cover redirect allowlist, OIDC identity bridging, RBAC preservation, and fail-closed runtime auth smoke."
    requirement: "SSO-02"
    verification:
      - kind: unit
        ref: "tests/backend/auth/test_sso_redirect_allowlist.test.js#Phase 42 redirect allowlist contract"
        status: pass
      - kind: unit
        ref: "tests/backend/auth/test_sso_oidc_bridge.test.js#Phase 42 mocked OIDC bridge contract"
        status: pass
      - kind: integration
        ref: "env -u SSO_TEST_EMAIL -u ADMIN_TEST_EMAIL -u SSO_TEST_PASSWORD -u ADMIN_TEST_PASSWORD RUN_LIVE_API_TESTS=1 npx jest --config jest.backend.runtime.config.js tests/backend/auth/test_sso_auth_endpoints.runtime.test.js --runInBand"
        status: pass
    human_judgment: false
  - id: D2
    description: "Browser logout contract covers Keycloak handoff, no auto-loop, and legacy auth-token cleanup expectations."
    requirement: "SSO-05"
    verification:
      - kind: automated_ui
        ref: "tests/frontend/e2e/test_sso_global_logout.spec.ts#Phase 42 global logout contract"
        status: pass
    human_judgment: false
  - id: D3
    description: "Repo-side SSO smoke tooling covers redacted secret hygiene plus dry-run/local edge assertions for the six ATS app hosts."
    requirement: "SSO-01"
    verification:
      - kind: other
        ref: "bash scripts/sso-secret-hygiene-scan.sh"
        status: pass
      - kind: other
        ref: "bash scripts/sso-edge-smoke.sh --dry-run --assert-app-hosts trade.atius.com.br,painel.atius.com.br,dashboard.atius.com.br,backtest.atius.com.br,strategy.atius.com.br,admin.atius.com.br"
        status: pass
    human_judgment: false
duration: 24 min
completed: 2026-06-28
status: complete
---

# Phase 42 Plan 01: Wave 0 SSO Validation Summary

**Wave 0 now has executable SSO contracts for redirect safety, OIDC-to-ATS session bridging, logout behavior, and edge/secret hygiene before any live publication.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-06-28T08:01:00Z
- **Completed:** 2026-06-28T08:25:10Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added Jest coverage for the six-host redirect allowlist matrix and a mocked OIDC bridge that preserves the current `auth-token` cookie contract while keeping ATS DB RBAC authoritative.
- Hardened the live runtime auth smoke so it fails closed on missing `SSO_*` and `ADMIN_*` credentials instead of falling back to embedded values.
- Added Playwright logout coverage plus two repo-side scripts for redacted secret hygiene and dry-run/local edge/header assertions.

## Task Commits

1. **Task 1: Add Wave 0 auth, redirect, and logout tests** - `9ade5a5` (`test`)
2. **Task 2: Add secret hygiene and edge/header smoke scripts** - `a064205db` (`test`)

## Files Created/Modified

- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js` - executable allowlist/bypass matrix for the six ATS production hosts.
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_oidc_bridge.test.js` - mocked OIDC bridge contract tying identity mapping to legacy cookie issuance and ATS DB RBAC.
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` - fail-closed live auth smoke with required env checks.
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_global_logout.spec.ts` - Playwright logout contract for Keycloak handoff and post-logout stability.
- `scripts/sso-secret-hygiene-scan.sh` - redacted denylist scanner for Phase 42 artifacts and SSO-related files.
- `scripts/sso-edge-smoke.sh` - dry-run/local Apache + curl smoke with explicit status, redirect, JSON, and forwarded-header assertions.

## Decisions Made

- OIDC-to-ATS bridging is validated as identification only in Wave 0; permission grants stay in `permissions.js` and the ATS DB.
- The live runtime smoke now treats missing auth env vars as a hard failure, preventing accidental credential leakage or unapproved live calls.
- The edge smoke script uses explicit assertions for HTTP status, `Location`, discovery JSON, and vhost forwarded headers so a raw `curl` success cannot be misread as a pass.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The ATS repo had a stale `.git/index.lock` from 2026-06-15. No active `git` process existed, so the stale lock was removed and the planned task commit succeeded.
- Playwright initially lacked its Chromium binary in the local cache. The existing project Playwright package was used to install the required browser runtime, after which the logout spec passed.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Next Phase Readiness

- Plan 42-02 can now implement the ATS SSO facade against an explicit contract for redirect validation, OIDC mapping, legacy cookie issuance, and logout behavior.
- Plan 42-03 can reuse `scripts/sso-edge-smoke.sh` and `scripts/sso-secret-hygiene-scan.sh` as the pre-publication gate for Apache/header rollout.

## Self-Check: PASSED

- Verified summary, scripts, and ATS test files exist on disk.
- Verified task commits `9ade5a5` (ATS repo) and `a064205db` (omni-srv-admin repo) exist in their respective repositories.
