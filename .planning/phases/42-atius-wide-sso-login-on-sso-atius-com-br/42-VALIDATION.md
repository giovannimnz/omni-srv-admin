---
phase: 42
slug: atius-wide-sso-login-on-sso-atius-com-br
status: draft
nyquist_compliant: true
wave_0: required
created: 2026-06-28
---

# Phase 42 Validation Contract

This file converts the `42-RESEARCH.md` validation architecture into the
minimum test infrastructure the execution plan must create before live SSO
changes. Phase 42 planning must not assume DNS, Apache, Keycloak clients, ATS
runtime auth, or secrets have been changed yet.

## Test Infrastructure

| Layer | Tooling | Canonical command |
|-------|---------|-------------------|
| ATS backend unit/runtime | Jest 30.2.0 | `cd /home/ubuntu/GitHub/Atius-Capital/ats && npx jest --config jest.backend.config.js tests/backend/auth/test_sso_redirect_allowlist.test.js --runInBand` |
| ATS backend CI auth/RBAC | Jest backend CI | `cd /home/ubuntu/GitHub/Atius-Capital/ats && npm run test:backend:ci` |
| Browser SSO/logout | Playwright 1.58.2 | `cd /home/ubuntu/GitHub/Atius-Capital/ats && npx playwright test tests/frontend/e2e/test_sso_global_logout.spec.ts --project=chromium --workers=1` |
| Edge smoke | Apache + curl | `apache2ctl configtest && curl --resolve sso.atius.com.br:443:127.0.0.1 -I https://sso.atius.com.br/login` |
| Secret hygiene | ripgrep denylist | `rg -n "SSO_TEST_PASSWORD|ADMIN_TEST_PASSWORD|client_secret|JWT_SECRET=.*[^<]|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY" /home/ubuntu/GitHub/Atius-Capital/ats .planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br` |

## Sampling Rate

- Before code mutation: run the focused unit for the touched auth/redirect
  module if it exists; otherwise create the Wave 0 test first and run it red.
- Before any live DNS/proxy publication: run `apache2ctl configtest`, local
  `--resolve` smoke for `sso.atius.com.br`, and rollback checklist dry run.
- Before enabling OIDC for ATS users: run backend auth/RBAC tests, OIDC bridge
  tests, no-open-redirect matrix, cookie attribute inspection, and logout E2E.
- Before closing the phase: run the full Phase 42 battery and record evidence in
  the phase summary without copying secrets or raw tokens.

## Per-Requirement Verification Map

| Req ID | Required verification | Automation status |
|--------|-----------------------|-------------------|
| SSO-01 | `sso.atius.com.br` DNS/proxy/vhost contract validates locally and has rollback steps before live publication. | Wave 0 script or documented manual-gated smoke required. |
| SSO-02 | Keycloak discovery/auth-code/logout endpoints remain reachable through the Phase 36 baseline while legacy ATS login remains usable. | Add regression that checks OIDC discovery plus existing ATS auth runtime path. |
| SSO-03 | OIDC callback bridge issues or preserves ATS-compatible session state and backend RBAC continues to permit/block by ATS DB permissions. | Add Jest bridge/RBAC test before implementation is marked green. |
| SSO-04 | Redirect allowlist rejects external hosts, protocol-relative URLs, userinfo URLs, non-HTTPS targets, subdomain confusion, and unknown paths. | Add focused Jest matrix first; this is the first Wave 0 test. |
| SSO-05 | Logout clears Keycloak browser SSO plus `.atius.com.br` and no-domain ATS cookies without auto-login loop. | Add Playwright/global header smoke and Set-Cookie inspection. |
| SSO-06 | Secrets are env-only or root-only; tests fail closed when live credentials are absent; no secrets enter Git, planning files, logs, or Obsidian. | Add denylist scan and remove hardcoded runtime-test fallbacks before live smoke. |

## Wave 0 Requirements

- Create `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_redirect_allowlist.test.js` before redirect implementation or proxy cutover.
- Create `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_oidc_bridge.test.js` before callback/session bridge implementation is considered covered.
- Create `/home/ubuntu/GitHub/Atius-Capital/ats/tests/frontend/e2e/test_sso_global_logout.spec.ts` before enabling shared logout for users.
- Update `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` so live smoke credentials come only from environment variables and fail closed when absent.
- Add an edge smoke script or phase runbook covering `sso.atius.com.br` Apache configtest, local `--resolve` curl, expected headers, and rollback.

## Manual-Only Verifications

- Authenticated Cloudflare or registrar mutation is manual-gated until a
  credentialed API path exists. The plan must include export/screenshot or API
  evidence without storing secrets.
- Production Keycloak client creation or client-secret rotation is manual-gated
  and must reference root-only secret storage, not planning docs.
- User acceptance for first ATS login/logout must be recorded as pass/block with
  timestamp and target host, but without account identifiers beyond non-secret
  usernames if unavoidable.

## Validation Sign-Off

- [ ] Wave 0 tests/scripts exist and fail closed before implementation.
- [ ] No-open-redirect matrix is green.
- [ ] Legacy ATS login, refresh, logout, and backend RBAC remain green.
- [ ] `sso.atius.com.br` edge smoke is green locally before live DNS/proxy change.
- [ ] Keycloak login and RP-initiated logout are green through the deployed baseline.
- [ ] Secret hygiene scan is green and no raw token/cookie/secret is copied into evidence.
