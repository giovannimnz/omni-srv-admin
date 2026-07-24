---
phase: 54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re
plan: "02"
subsystem: network-preflight
tags: [oci, drg, dns, wireguard, backup, fail-closed]
requires:
  - phase: 54-01
    provides: fail-closed validation runner and predecessor gate
provides:
  - hash-bound live baseline for OCI, DRG, Horistic, DNS and edge state
  - rollback-readiness receipt with explicit PASS/BLOCK per source
  - fail-closed final gate preventing migration writes
affects: [54-03, 54-04, 54-05, 54-06, 54-07, 54-08, 54-09, 54-10]
tech-stack:
  added: []
  patterns: [read-only live inventory, restore-verified backup, hash-bound gate]
key-files:
  created:
    - .planning/workstreams/network-horistic-readdress/phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-02-EVIDENCE.json
    - .planning/workstreams/network-horistic-readdress/phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-02-GATE.json
    - .planning/workstreams/network-horistic-readdress/phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-ROLLBACK-RECEIPT.json
    - .planning/workstreams/network-horistic-readdress/phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-02-SUMMARY.md
  modified:
    - .planning/workstreams/network-horistic-readdress/STATE.md
decisions:
  - "54-02 remains BLOCK until all baseline and rollback sources are complete and the predecessor gate is fresh."
  - "The preserved public-IP identity is evidence only and does not authorize an OCI rebind or any other migration write."
  - "Phase 52 artifacts remain historical provenance and cannot authorize Phase 54 writes."
metrics:
  duration: 25min
  completed: 2026-07-24
status: blocked
---

# Phase 54 Plan 02: Live Baseline and Rollback Readiness Summary

Hash-bound OCI/DRG/host/DNS/edge baseline with preserved public-IP identity and a fail-closed `BLOCK` on incomplete security, BE3 and fresh backup proofs.

## Outcome

Plan 54-02 did not satisfy its progression criteria. The runner emitted `status: BLOCK`, so no OCI, DNS, WireGuard, BE3, route, address, rebind, release or migration apply was performed.

The reserved public IP was preserved exactly as observed:

- Address: `163.176.232.119`
- Public IP OCID: `ocid1.publicip.oc1.sa-saopaulo-1.amaaaaaa7sd6shia6m45bvej3y3kppgz25tbrvfy4niola7lau5pgpzfkkxa`
- Private IP OCID: `ocid1.privateip.oc1.sa-saopaulo-1.abtxeljre62rb2i4k7s6cwgklhr43gw5o5cvwdgzc66bs6ytsmdjm2ggmuna`
- Assignment state: `ASSIGNED`

## Evidence Captured

- OCI Horistic inventory: instance, both VCNs, subnets, VNICs, private IPs, security-list identifiers, reserved public IP, boot volume and prior backup.
- Central DRG identity and Horistic attachment, including observed route targets to `10.11`, `10.12` and `10.13`.
- Horistic host network, routes, resolvers, services and listeners through the required public SSH fallback after the private route timed out.
- K3s node and workload health from SRV1.
- Internal/public DNS records and CoreDNS configuration hash.
- WireGuard hub peer addresses and handshake state.
- External read-only `oci-admin` address-plan evidence showing the intended `10.31` targets and no target `10.21`.

## Rollback Readiness

The Horistic host backup passed under the 20% CPU guardrail:

- Backup: `/var/backups/omni-srv-admin/phase54/20260724T140756Z-horistic/horistic-configs.tar`
- SHA-256 before/after restore: `2ba907816cd26be24d5c27449b6fab0c6887c9051109f64506d0154f3e1d935e`
- Archive comparison: exit `0`
- Restored files: `194`
- Restored ownership: `root:root`

The earlier partial attempt at `/var/backups/omni-srv-admin/phase54/20260724T140729Z-horistic` was retained as evidence; it failed because this agent-only host has no `/etc/rancher/k3s`.

## Blocking Gaps

| Gate area | Status | Missing proof |
| --- | --- | --- |
| OCI security | BLOCK | Directional ingress/egress rule readback was not exposed |
| Internal DNS authority | BLOCK | Authoritative SOA/NS proof was incomplete |
| BE3 edge | BLOCK | Live S23/S20 reservation, lease, MAC and native export were not authenticated and captured |
| OCI rollback | BLOCK | A fresh boot-volume backup requires a separately authorized OCI write |
| SRV1/SRV3 rollback | BLOCK | Complete native backups and restore drills were not proven |
| Predecessor lineage | BLOCK | The 54-01 gate expired before the final 54-02 evaluation |

## Safety Controls

- `peering.address_plan` was used read-only; the observed production counters remained unchanged.
- The external builder commit is evidence, not a Phase 54 authorization receipt.
- Phase 52 approvals and artifacts were classified `historical_only`.
- The previous `APPLY:3f197cf6` token was not reused.
- No secrets were persisted in the evidence, planning files or commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used the installed Node.js path**

- **Found during:** Execution setup
- **Issue:** `node` was not available on `PATH`.
- **Fix:** Invoked the repository tools with `/home/muniz/.local/bin/node`.

**2. [Rule 3 - Blocking] Retried the Horistic archive with agent-host paths**

- **Found during:** Rollback backup verification
- **Issue:** The first archive attempted to include `/etc/rancher/k3s`, which is absent on this k3s agent.
- **Fix:** Produced a second backup from the host's actual configuration set and verified its hash, extraction and ownership.

**3. [Rule 1 - Bug] Corrected editor target drift**

- **Found during:** Evidence materialization
- **Issue:** One relative edit initially targeted the main checkout instead of the execution worktree.
- **Fix:** Removed the misplaced file and wrote the evidence only in the designated worktree before staging.

## Commits

- `435e554` — `test(54-02): capture fail-closed live baseline`
- `ba6201b` — `test(54-02): emit rollback readiness block`

## Resume Requirements

Resume only after separate backup-only authorization supplies the missing OCI boot backup, SRV1/SRV3 native backup and restore proofs, authenticated BE3 native export/readback, OCI security-rule directions and authoritative internal SOA/NS evidence. Then reissue a fresh 54-01 gate and rerun 54-02.

This checkpoint does not authorize any migration or network write.

## Known Stubs

None.

## Self-Check

PASSED (checkpoint scope):

- Evidence, gate and rollback-receipt JSON files parse successfully.
- All four checkpoint artifacts exist in the execution worktree.
- Technical commits `435e554` and `ba6201b` exist in git history.
- All three machine-readable artifacts independently report `status: BLOCK`.
