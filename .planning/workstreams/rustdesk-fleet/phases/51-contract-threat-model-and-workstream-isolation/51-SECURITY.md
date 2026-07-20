---
phase: 51
status: approved
threats_total: 12
threats_open: 0
blocking_threshold: high
asvs_version: 5.0.0
---

# Phase 51 Security Contract

This document projects the authoritative machine contract in `modules/rustdesk-fleet/contracts/threat-model.json`. It does not replace that contract or the accountable operational review.

## Trust Boundaries

| Boundary | Data Crossing | Enforcement |
|---|---|---|
| operator review -> product decision | six mandatory/accepted-absence statements | deterministic GO, NO-GO or BLOCKED derivation |
| versioned contract -> validator | untrusted JSON fields, paths and enums | strict parsing, exact sets and fail-closed status |
| Vault authority -> repo references | role/path/field names only | no secret values or value-derived hashes |
| permission contract -> later clients | desired local allow/deny profiles | OSS limitation recorded; later negative tests required |

## Threat Register

| ID | STRIDE | Severity | Status | Owner | Mitigation evidence |
|---|---|---|---|---|---|
| T-01 | Spoofing/Tampering | high | mitigated | rustdesk-operator | P51-EV-THREAT-T01 |
| T-02 | Information Disclosure | high | mitigated | vault-owner | P51-EV-THREAT-T02 |
| T-03 | Information Disclosure/Elevation | high | mitigated | vault-owner | P51-EV-THREAT-T03 |
| T-04 | Elevation/Tampering | high | mitigated | rustdesk-operator | P51-EV-THREAT-T04 |
| T-05 | Repudiation/Elevation | high | mitigated | accountable-reviewer | P51-EV-THREAT-T05 |
| T-06 | Denial of Service/Tampering | high | mitigated | rustdesk-operator | P51-EV-THREAT-T06 |
| T-07 | Tampering/Elevation | high | mitigated | fleet-owner | P51-EV-THREAT-T07 |
| T-08 | Denial of Service | high | mitigated | fleet-owner | P51-EV-THREAT-T08 |
| T-09 | Tampering/Repudiation | high | mitigated | gsd-workstream-owner | P51-EV-THREAT-T09 |
| T-10 | Repudiation | high | mitigated | evidence-owner | P51-EV-THREAT-T10 |
| T-11 | Information Disclosure | medium | mitigated | evidence-owner | P51-EV-THREAT-T11 |
| T-12 | Elevation/Repudiation | high | mitigated | vault-owner | P51-EV-THREAT-T12 |

Any high threat changed to a status other than `mitigated` or `resolved` makes advancement `BLOCKED`.

## Permission Profiles and OSS Boundary

`admin-maintenance` allows screen, keyboard/mouse, clipboard, terminal and remote restart. `support-observe` allows screen view only. File transfer, audio, TCP tunnel, privacy mode, recording and remote config modification are denied in both profiles.

These are desired local policies with per-client verification and negative tests. They are not claimed as centralized OSS RBAC. If SSO/OIDC, RBAC, MFA, central API, central device policy or human-attributed audit is mandatory, the product decision is `NO-GO` for OSS and requires Pro.

## ASVS Mapping

- Baseline L1/control set: `v5.0.0-2.1.1`, `2.2.1`, `2.2.2`, `2.3.1`, `6.1.1`, `6.3.1`, `8.1.1`, `8.2.1`, `8.2.2`, `8.3.1`, `11.4.1`, `15.3.1`.
- Risk-based V16 L2 subset: `v5.0.0-16.1.1`, `16.2.5`, `16.3.3`, `16.4.2`, `16.5.1`, `16.5.3`.

## Accepted Risks Log

No unresolved threat risk is accepted. Giovanni Muniz explicitly accepted the six missing centralized OSS controls for the current single-operator product boundary; any future requirement for one of those controls reopens the Pro gate.

## Audit Notes

- Server private/public roles are reserved under `kv/atius/rustdesk/server`; five unique target roles are reserved under `kv/atius/rustdesk/targets/<canonical-host-id>`. The accountable Vault owner approved all six references at `2026-07-20T07:38:59Z`; no value was read or recorded.
- Phase 51 proves one-to-one role/reference distinctness only. Live value creation and non-output value-distinctness proof belong to Phase 52.
- Client IDs and permission profiles remain separate typed assets referenced by path; no ID or secret value is present here.
- Runtime enforcement, client behavior and transport evidence belong to later phases.
- Summary prose cannot close this gate.

## Sign-Off

- [x] Accountable operator reviewed all six enterprise controls.
- [x] Vault owner approved the reserved identity and target paths.
- [x] Current machine validation report agrees with this projection.

**Approval:** approved by Giovanni Muniz at `2026-07-20T07:59:32Z`
