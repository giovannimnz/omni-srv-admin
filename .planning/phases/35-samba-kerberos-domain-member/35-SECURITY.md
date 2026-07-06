---
phase: 35
slug: samba-kerberos-domain-member
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 35 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| SMB clients to `atius-srv-1` | Domain users access the `Shared` share through Samba. | File metadata and share data |
| Samba to FreeIPA/Kerberos | `srv1` uses FreeIPA/Kerberos identity for SMB auth. | Kerberos tickets and CIFS keytab usage |
| `srv2` legacy share to `srv1` | Existing share data was copied before service cutover. | Existing file data |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-35-01 | Spoofing | Samba authentication | high | mitigate | `srv1` is enrolled in `ATIUS.INTERNAL`; `cifs/atius-srv-1.atius.internal` and `/etc/samba/samba.keytab` were verified; Kerberos `smbclient -k` smoke passed. | closed |
| T-35-02 | Tampering | Share cutover | high | mitigate | Data was copied to `/srv/Shared` and checked for matching size before disabling old Samba services on `srv2`. | closed |
| T-35-03 | Information Disclosure | Samba keytab and domain credentials | high | mitigate | Keytab stays on the host; no keytab or credential material is stored in repo artifacts; docs record only paths and smoke outcomes. | closed |

## Accepted Risks Log

No accepted risks.

## Evidence

- `35-VERIFICATION.md` records host enrollment, keytab validity, service state and Kerberos SMB smoke as passed.
- `docs/domain/samba-freeipa-cutover.md` records the cutover model and backup anchors.
- `35-UAT.md` records 3/3 UAT checks passed.

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
