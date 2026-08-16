# Phase 10 governed runbook

## Scope

This runbook covers the reusable ATS SSO lifecycle only.

Out of scope:

- AdGuard app-local `/login` rollout
- Apache facade work for Phase 11
- non-ATS applications

## Current stable contract

- Canonical public URL: `/login`
- Compatibility surface: `/sso`
- Central logout: `POST /api/sso/logout`
- Allowed browser origins:
  - `https://adguard.atius.com.br`
  - `https://sso.atius.com.br`
- Fixed completion URI:
  - `https://sso.atius.com.br/login?logout=complete`

## Release flow

1. Generate candidate under `10-04-candidate.json`
2. Validate candidate
3. Generate external approval
4. Validate approval
5. Run apply/rollback/reapply
6. Validate release
7. Run browser closeout
8. Run vision review
9. Generate Phase 11 handoff artifact
10. Finalize Graphify post-summary

## Known pitfalls

- Do not leave old approval or release artifacts in the canonical path before regenerating candidate.
- On this host, `/tmp` is not safe for Jest, Playwright, or mktemp-heavy scripts. Prefer a controlled `TMPDIR`.
- Browser closeout against live runtime only makes sense after the newest central delta has been promoted.
- A green verdict does not replace reading detail fields such as warning-bearing secret scans.

## Phase 11 contract reminder

The handoff to Phase 11 must declare:

- `login.publicPath=/login`
- `ssoCompatibility.publicPath=/sso`
- `vendorLogoutBridge.publicPath=/logout`
- `vendorLogoutBridge.method=POST`
- `vendorLogoutBridge.mode=same-origin-post`

That handoff enables the AdGuard remediation phase but does not approve it by itself.

