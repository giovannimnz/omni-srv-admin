---
phase: 36
title: "Validation - Keycloak SSO and coexistence"
date: 2026-06-26
status: passed
requirements:
  - DOM-06
  - DOM-07
---

# Phase 36 Validation

Phase 36 validates as complete.

## Evidence Reviewed

- `36-VERIFICATION.md` is marked `status: passed`.
- Keycloak is active and reachable locally.
- Apache proxy for `auth.atius.com.br` passed local smoke.
- FreeIPA LDAP federation exists and imported a user.
- Legacy Apache SSO and API surfaces remained live.

## Nyquist Gap Review

| Axis | Result | Notes |
|---|---|---|
| Functional | PASS | OIDC discovery, LDAP federation and token smoke are covered. |
| Coexistence | PASS | Legacy SSO/API were not migrated or broken. |
| Security | PASS | Federation uses private LDAP path; no secrets are documented. |
| Residual | WARN | Keycloak local storage remains `dev-file` for this smoke phase. |
