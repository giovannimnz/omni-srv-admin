---
phase: 34
slug: freeipa-dns-and-client-enrollment
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 34 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| WireGuard/CoreDNS to FreeIPA | Fleet clients resolve `atius.internal` through scoped CoreDNS forwarding to the private SRV3 gateway. | DNS, Kerberos, LDAP and HTTP(S) control traffic |
| SRV3 host to FreeIPA container | `atius-srv-3` forwards only required FreeIPA ports to the isolated container network. | Realm enrollment and auth traffic |
| Operator to bootstrap secrets | Enrollment evidence and bootstrap material remain root-only on the server. | Admin/enrollment credentials |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-34-01 | Spoofing/Tampering | FreeIPA DNS path | high | mitigate | CoreDNS forwarding is scoped to `atius.internal`; no public Cloudflare/Apache FreeIPA exposure was added; `ipa.atius.internal` resolves privately through WireGuard. | closed |
| T-34-02 | Information Disclosure | Bootstrap and enrollment evidence | high | mitigate | Root-only evidence paths are documented; secrets are explicitly excluded from repo, vault docs and chat. | closed |
| T-34-03 | Denial of Service | Real host enrollment | high | mitigate | Disposable enrollment ran before real host enrollment; CoreDNS and SRV3 rollback anchors were captured; first real host was limited to `atius-srv-3`. | closed |

## Accepted Risks Log

No accepted risks.

## Evidence

- `34-VERIFICATION.md` records DNS, enrollment, `kinit`, `ipa ping`, group and sudo smoke as passed.
- `docs/domain/freeipa-dns-client-enrollment.md` records private exposure, rollback and root-only evidence handling.
- `34-UAT.md` records 3/3 UAT checks passed.

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
