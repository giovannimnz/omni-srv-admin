---
phase: 36
status: passed
verified: 2026-06-26T10:55:00-03:00
requirements:
  - DOM-06
  - DOM-07
---

# Phase 36 Verification

## Passed Checks

| Check | Result |
|---|---|
| Keycloak service on `srv1` | PASS (`systemctl is-active keycloak` -> `active`) |
| Local Keycloak discovery endpoint | PASS (`http://127.0.0.1:8180/realms/master/.well-known/openid-configuration`) |
| Apache proxy for `auth.atius.com.br` | PASS via local `--resolve` smoke |
| FreeIPA LDAP bind from `srv1` | PASS (`ldapsearch` against `ldap://10.1.1.3:389`) |
| Keycloak LDAP federation provider | PASS |
| Imported FreeIPA user `giovanni` into realm `atius` | PASS |
| OIDC password-grant smoke for `phase36-smoke` client | PASS |
| Legacy Apache SSO surface `admin.atius.com.br` | still responds (`307` to login) |
| Legacy API surface `api.atius.com.br` | still responds (`404`, unchanged route behavior) |

## Requirement Closure

DOM-06 is satisfied:

- Keycloak runs on `srv1`
- it is federated to FreeIPA
- and it exposes a working OIDC path on `auth.atius.com.br`

DOM-07 is satisfied for coexistence:

- the Apache SSO/JWT path remains live and unchanged
- Keycloak is additive only
- no existing application was migrated in this phase

## Residual Notes

- The first federation path uses direct LDAP over the private WireGuard path
  (`ldap://10.1.1.3:389`) with a read-only bind.
- The Keycloak local storage is `dev-file` for this coexistence smoke phase.
- `tmpadm36` is a temporary recovery admin and should not be treated as the
  final administrative model.
