---
phase: 36
plan: 36-01
status: complete
completed: 2026-06-26T10:55:00-03:00
requirements:
  - DOM-06
  - DOM-07
key-files:
  created:
    - docs/domain/keycloak-freeipa-coexistence.md
    - .planning/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md
  modified:
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
metrics:
  keycloak_version: 26.6.3
  java_version: 21
  oidc_smoke: passed
  freeipa_federation: passed
  legacy_apache_sso: unchanged
---

# Summary: 36-01 Keycloak LDAP federation, OIDC endpoint and Apache SSO coexistence smoke

## Outcome

Phase 36 passed.

Keycloak now runs natively on `atius-srv-1`, federated to FreeIPA, with a
working OIDC token path on `auth.atius.com.br` and without breaking the legacy
Apache SSO/JWT surfaces.

## What changed

| Item | Result |
|---|---|
| Keycloak runtime on `srv1` | PASS |
| Java 21 runtime for Keycloak | PASS |
| Private Keycloak listener | `127.0.0.1:8180` |
| Apache reverse proxy for `auth.atius.com.br` | PASS |
| FreeIPA-backed LDAP federation in realm `atius` | PASS |
| `phase36-smoke` OIDC client | PASS |
| Password grant smoke with `giovanni@ATIUS.INTERNAL` | PASS |
| Legacy Apache auth surfaces (`admin.atius.com.br`, `api.atius.com.br`) | still answering |

## Important technical notes

- Keycloak 26.6.3 was installed from the official Quarkus distribution.
- The first usable admin recovery account was `tmpadm36` in the `master` realm.
- The LDAP federation provider needed `ipaUniqueID` as UUID attribute; `nsUniqueID`
  failed import for FreeIPA users.
- The OIDC smoke was executed through Apache with:
  `curl --resolve auth.atius.com.br:443:127.0.0.1 ...`
- No application was migrated away from the existing Apache/JWT SSO path in
  this phase.

## Scope control

- Keycloak remains additive.
- Existing apps keep using the old SSO path.
- `auth.atius.com.br` is wired at Apache level for controlled smoke only; this
  phase did not perform app migration.
