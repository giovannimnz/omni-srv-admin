# Phase 28 Plan 02: G18 Upgrade Gate Checklist

**Generated:** 2026-06-24T22:14:06Z  
**Requirement:** G18-02  
**Mode:** read-only/prep only

No Phase 28 live mutation was executed. This checklist is produced from
`.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md`
and the canonical runbook `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md`.

## Gate Rule

Phase 29 package mutation is blocked until every required host has:

1. Fresh inventory captured within 2 hours of the mutation window.
2. Ubuntu Pro attached and ESM Apps/Infra enabled.
3. Token-path posture approved without exposing token contents.
4. Apt sources reviewed.
5. Held packages reviewed.
6. Pending package scope approved.
7. Reboot-required state captured.
8. Disk thresholds accepted or remediated.
9. Landscape client/SaaS posture accepted.
10. RDP/XRDP baseline references captured without restart.
11. Real OCI snapshot ID or signed exception.
12. GDrive or equivalent backup path.
13. `dpkg --get-selections`, package list, kernel capture, `pro collect-logs`, and written checkpoint.

## Fleet Gate Summary

| Host | Overall | Primary BLOCK items |
| --- | --- | --- |
| atius-srv-1 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real snapshot missing; disk 86% warning; Landscape registration no; package rollback artifacts missing; written checkpoint missing. |
| atius-srv-2 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real snapshot missing; disk 86% warning; Landscape registration no; package rollback artifacts missing; written checkpoint missing. |
| atius-srv-3 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real snapshot missing; Landscape registration no; PM2 posture needs operator acceptance; package rollback artifacts missing; written checkpoint missing. |

## atius-srv-1 Checklist

| Check | Evidence from inventory | Gate |
| --- | --- | --- |
| Host target | `ubuntu@10.1.1.1`, VPN `10.1.1.1`, public `137.131.190.161` | PASS |
| Fresh inventory | Baseline inventory generated in Phase 28; must be regenerated if older than 2h at Phase 29 window | BLOCK |
| Ubuntu Pro attached | true | PASS |
| ESM Apps | enabled | PASS |
| ESM Infra | enabled | PASS |
| Token metadata | `/home/ubuntu/secrets/ubuntu-pro-token.txt` missing; `/home/ubuntu/ubuntu-pro-token.txt` missing | BLOCK |
| Apt source review | ESM DEB822 sources present; many one-line and `.distUpgrade` files listed | REVIEW |
| Held packages | none reported | PASS |
| Pending packages | 44 total; 15 ESM Apps; 0 ESM Infra; 29 non-ESM | REVIEW |
| Reboot required | no | PASS |
| Disk thresholds | `/`, `/boot`, `/var` 86% warning with about 30 GB available | BLOCK |
| Landscape | `landscape-client` active/enabled, registration check no | BLOCK |
| RDP/XRDP | `xrdp` and `xrdp-sesman` active/enabled; network map primary display `:1`, VNC `5901` | PASS |
| PM2 | `pm2-ubuntu` active/enabled | PASS |
| K3s | active/enabled | PASS |
| OCI snapshot | `pending-250f...a298a94c`, not a real OCI image ID | BLOCK |
| Backup path | `ATIUS-SRV/SRV-1/Backup` | REVIEW |
| `dpkg --get-selections` | Not captured for Phase 29 window | BLOCK |
| Pro status capture | Not captured for Phase 29 window | BLOCK |
| Upgradable capture | Baseline exists; fresh Phase 29 capture required | BLOCK |
| Kernel capture | Baseline kernel `6.17.0-1016-oracle`; fresh Phase 29 capture required | BLOCK |
| `pro collect-logs` | Not captured for Phase 29 window | BLOCK |
| Written checkpoint | Not present | BLOCK |

Required clearing artifacts:

- Fresh host preflight bundle path.
- Token metadata proof or signed no-attach-fallback exception.
- Real `ocid1.image...` snapshot ID or signed no-OCI-restore exception.
- Disk warning acceptance or cleanup/checkpoint note.
- Landscape SaaS/client evidence or signed exception.
- Operator approval record with package scope and no-reboot/no-service-restart posture.

## atius-srv-2 Checklist

| Check | Evidence from inventory | Gate |
| --- | --- | --- |
| Host target | `ubuntu@10.1.1.2`, VPN `10.1.1.2`, public `129.148.47.32` | PASS |
| Fresh inventory | Baseline inventory generated in Phase 28; must be regenerated if older than 2h at Phase 29 window | BLOCK |
| Ubuntu Pro attached | true | PASS |
| ESM Apps | enabled | PASS |
| ESM Infra | enabled | PASS |
| Token metadata | `/home/ubuntu/secrets/ubuntu-pro-token.txt` missing; `/home/ubuntu/ubuntu-pro-token.txt` missing | BLOCK |
| Apt source review | ESM DEB822 sources present; one-line and `.distUpgrade` files listed | REVIEW |
| Held packages | none reported | PASS |
| Pending packages | 10 total; 3 ESM Apps; 0 ESM Infra; 7 non-ESM | REVIEW |
| Reboot required | no | PASS |
| Disk thresholds | `/`, `/boot`, `/var` 86% warning with about 30 GB available | BLOCK |
| Landscape | `landscape-client` active/enabled, registration check no | BLOCK |
| RDP/XRDP | `xrdp` and `xrdp-sesman` active/enabled; network map primary display `:1`, VNC `5901`; legacy 5900 must remain closed | PASS |
| PM2 | `pm2-ubuntu` active/enabled | PASS |
| K3s | active/enabled | PASS |
| OCI snapshot | `pending-ef73...9692c21e`, not a real OCI image ID | BLOCK |
| Backup path | `ATIUS-SRV/SRV-2/Backup` | REVIEW |
| `dpkg --get-selections` | Not captured for Phase 29 window | BLOCK |
| Pro status capture | Not captured for Phase 29 window | BLOCK |
| Upgradable capture | Baseline exists; fresh Phase 29 capture required | BLOCK |
| Kernel capture | Baseline kernel `6.17.0-1016-oracle`; fresh Phase 29 capture required | BLOCK |
| `pro collect-logs` | Not captured for Phase 29 window | BLOCK |
| Written checkpoint | Not present | BLOCK |

Required clearing artifacts:

- Fresh host preflight bundle path.
- Token metadata proof or signed no-attach-fallback exception.
- Real `ocid1.image...` snapshot ID or signed no-OCI-restore exception.
- Disk warning acceptance or cleanup/checkpoint note.
- Landscape SaaS/client evidence or signed exception.
- Operator approval record with package scope and no-reboot/no-service-restart posture.

## atius-srv-3 Checklist

| Check | Evidence from inventory | Gate |
| --- | --- | --- |
| Host target | `ubuntu@10.1.1.3`, VPN `10.1.1.3`, public `136.248.126.12` | PASS |
| Fresh inventory | Baseline inventory generated in Phase 28; must be regenerated if older than 2h at Phase 29 window | BLOCK |
| Ubuntu Pro attached | true | PASS |
| ESM Apps | enabled | PASS |
| ESM Infra | enabled | PASS |
| Token metadata | `/home/ubuntu/secrets/ubuntu-pro-token.txt` missing; `/home/ubuntu/ubuntu-pro-token.txt` missing | BLOCK |
| Apt source review | ESM DEB822 sources present; one-line and DEB822 third-party sources listed | REVIEW |
| Held packages | none reported | PASS |
| Pending packages | 21 total; 15 ESM Apps; 0 ESM Infra; 6 non-ESM | REVIEW |
| Reboot required | no | PASS |
| Disk thresholds | `/`, `/boot`, `/var` 61% ok | PASS |
| Landscape | `landscape-client` active/enabled, registration check no | BLOCK |
| RDP/XRDP | `xrdp` and `xrdp-sesman` active/enabled; network map primary display `:1`, VNC `5901` | PASS |
| PM2 | `pm2-ubuntu` inactive/not-found | REVIEW |
| K3s | active/enabled | PASS |
| OCI snapshot | `pending-5c21...0e9d2d49`, not a real OCI image ID | BLOCK |
| Backup path | `ATIUS-SRV/SRV-3/Backup` | REVIEW |
| `dpkg --get-selections` | Not captured for Phase 29 window | BLOCK |
| Pro status capture | Not captured for Phase 29 window | BLOCK |
| Upgradable capture | Baseline exists; fresh Phase 29 capture required | BLOCK |
| Kernel capture | Baseline kernel `6.17.0-1016-oracle`; fresh Phase 29 capture required | BLOCK |
| `pro collect-logs` | Not captured for Phase 29 window | BLOCK |
| Written checkpoint | Not present | BLOCK |

Required clearing artifacts:

- Fresh host preflight bundle path.
- Token metadata proof or signed no-attach-fallback exception.
- Real `ocid1.image...` snapshot ID or signed no-OCI-restore exception.
- Landscape SaaS/client evidence or signed exception.
- Operator acceptance that `pm2-ubuntu` inactive/not-found is expected for sandbox, or a separate Production Guard note.
- Operator approval record with package scope and no-reboot/no-service-restart posture.

## Required Operator Approval Fields

Each host approval must include:

- host
- inventory report path
- preflight bundle path
- snapshot ID or exception
- backup path
- package scope
- expected no-reboot/no-service-restart posture
- RDP validation owner
- Landscape SaaS validation owner
- rollback path
- operator name
- signed timestamp

## Result

G18-02 is prepared but not cleared for Phase 29 mutation. Every required host
has a concrete PASS/BLOCK checklist, and every BLOCK item has an artifact that
can clear it. Phase 28 remains read-only/prep only.

