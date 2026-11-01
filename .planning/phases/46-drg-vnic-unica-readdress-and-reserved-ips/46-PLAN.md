# Phase 46 Plan: DRG Readdressing, Single-VNIC Unification, and 100% Reserved Public IPs

- **Milestone:** v1.2 — Unified Fleet DRG & Single-VNIC Modernization
- **Phase:** 46
- **Status:** READY FOR REVIEW / PLANNED
- **Governance:** `omni-srv-admin` & `oci-admin` (Orchestrator `8a2d864b-6210-42a3-a0aa-7a29da78f4f7`)

## Objective
Readdress all OCI core and partner instances to canonical, non-overlapping `/16` CIDR blocks (`10.1`..`10.4` for ATIUS Core; `10.51` and `10.52` for Partners), eliminate legacy Dual-VNIC setups in favor of native Single-VNIC architecture, and enforce 100% Reserved Public IP discipline across Oracle Cloud.

## Plan Breakdown

### Task 46-01: Update OCI Admin Address Contract and Peering Engine (TDD)
- Update `_TARGET_ADDRESS_ROWS` in `app/oci_client/peering_actions.py` in `oci-admin`.
- Update test expectations in `tests/test_peering_addressing.py`.
- Run pytest suite to ensure zero CIDR collision and accurate OperationPlan generation.

### Task 46-02: Promote and Verify 100% Reserved Public IPs
- Promote `137.131.190.161` on `atius-srv-1` from Ephemeral to Reserved in tenancy `atius1`.
- Audit public IP on `aln-srv` (`alnrec`) to ensure it is Reserved.
- Ensure all other servers maintain their verified Reserved Public IPs (`64.181.185.218`, `163.176.178.228`, `164.152.48.22`, `163.176.232.119`).

### Task 46-03: Stage New VCNs and Attachments on Central DRG
- Create target VCNs (`10.1.0.0/16`, `10.2.0.0/16`, etc.) and subnets via `oci-admin-cli` / `oci_plan`.
- Create DRG attachments to central DRG `Brasil - Sao Paulo`.
- Configure route tables and security lists without interrupting existing workloads.

### Task 46-04: Host-by-Host Migration to Single-VNIC (Waves 3A, 3B, 3C)
- Wave 3A: Partner nodes (`horistic-srv` to `10.51.0.1`, `aln-srv` to `10.52.0.2`).
- Wave 3B: Secondary core nodes (`atius-srv-2` to `10.2.0.2`, `atius-srv-4` to `10.4.0.4`).
- Wave 3C: Core controllers (`atius-srv-3` Vault/Landscape to `10.3.0.3`, then `atius-srv-1` Edge Gateway/DNS to `10.1.0.1`).

### Task 46-05: Service Re-pointing, DNS Updates, and Verification
- Update CoreDNS `/etc/coredns/hosts` and propagate `*.atius.internal`.
- Update Vault listeners, TLS certs, and env helpers across all hosts.
- Rebind Apache upstreams, K3s control-plane flags, and Prometheus node-exporter scrapes.
- Validate end-to-end telemetry and issue `<!-- GOAL_COMPLETE -->`.
