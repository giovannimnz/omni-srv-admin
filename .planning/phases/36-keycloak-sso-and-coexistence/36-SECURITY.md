---
phase: 36
slug: keycloak-sso-and-coexistence
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 36 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| Browser/API to Keycloak | `auth.atius.com.br` exposes the additive OIDC smoke endpoint through Apache. | OIDC auth requests and tokens |
| Keycloak to FreeIPA | Keycloak federates users from FreeIPA over the private LDAP path. | LDAP identity attributes |
| Legacy Apache SSO to Keycloak coexistence | Existing Apache SSO/JWT surfaces continue unchanged. | Existing auth cookies/JWT flow and new OIDC smoke flow |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-36-01 | Spoofing | OIDC/SSO boundary | high | mitigate | Keycloak was deployed as additive only on `auth.atius.com.br`; legacy Apache SSO and API surfaces were smoke-tested unchanged. | closed |
| T-36-02 | Information Disclosure | LDAP bind and recovery admin secrets | high | mitigate | Keycloak and FreeIPA bind secrets are documented as root-only env files; no secret values are recorded in repo artifacts. | closed |
| T-36-03 | Tampering | FreeIPA user federation | high | mitigate | LDAP federation is documented as private and controlled; the phase did not migrate applications or replace production auth paths. | closed |

## Accepted Risks Log

No accepted risks.

## Evidence

- `36-VERIFICATION.md` records Keycloak service, discovery, Apache proxy, LDAP bind, user import and OIDC smoke as passed.
- `docs/domain/keycloak-freeipa-coexistence.md` records root-only secret handling and coexistence boundaries.
- `36-UAT.md` records 3/3 UAT checks passed.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|---|---:|---:|---:|---|
| 2026-07-05 | 3 | 3 | 0 | Codex inline secure-phase |

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

Approval: verified 2026-07-05
