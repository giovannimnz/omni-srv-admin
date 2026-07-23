---
status: complete
phase: 36-keycloak-sso-and-coexistence
source:
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md
updated: 2026-06-26T19:45:00-03:00
---

# Phase 36 UAT

## Tests

### 1. Keycloak Service and Discovery

expected: Keycloak is active on `srv1` and exposes OIDC discovery.
result: [passed]
notes: `systemctl is-active keycloak` and local discovery endpoint passed.

### 2. FreeIPA Federation

expected: Keycloak can bind to FreeIPA LDAP and import a domain user.
result: [passed]
notes: LDAP bind passed and user `giovanni` was imported into realm `atius`.

### 3. OIDC Smoke and Coexistence

expected: OIDC smoke succeeds while legacy Apache SSO/API surfaces remain live.
result: [passed]
notes: Password-grant smoke passed for `phase36-smoke`; legacy surfaces stayed
unchanged.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
blocked: 0
