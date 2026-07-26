---
phase: 53-primary-relay-and-public-edge
plan: 05D2T
subsystem: infra
tags: [rustdesk, oci, vnic, drg, topology, read-only]
requires:
  - phase: 53-05D
    provides: translated edge authority and capability-disjoint provider boundary
provides:
  - exact dual-VNIC atius-srv-1 edge and Horistic backend topology contract
  - fail-closed read-only topology observation validator
  - current value-free non-authorizing topology receipt
affects: [53-05D2A, 53-05D2B, 53-05D2C, 53-05E, 53-05F]
tech-stack:
  added: []
  patterns:
    - capability-free parsing of externally collected read-only observations
    - semantic-digest receipts without raw provider identifiers
key-files:
  created:
    - modules/rustdesk-fleet/contracts/phase53-topology.json
    - modules/rustdesk-fleet/tools/discover-phase53-topology.py
    - modules/rustdesk-fleet/tests/test_phase53_topology.py
    - modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
  modified: []
key-decisions:
  - "The public-IP VNIC 10.0.0.238 and the OCI-primary route/SNAT VNIC 10.11.1.11 are distinct atius-srv-1 roles."
  - "The stale edge-forwarder OperationPlan and every prior hash or typed confirmation are rejected as authority."
  - "The 10.31.1.31 Horistic handoff remains executable=false throughout Phase 53."
patterns-established:
  - "Current topology observations enter through a bounded read-only JSON transport; the validator exposes no provider, host, shell, plan or approval capability."
  - "Receipts retain semantic digests and check identifiers, never raw IPs, OCIDs, OperationPlan material or secrets."
requirements-completed: [SRV-03, SRV-04]
coverage:
  - id: D1
    description: Exact edge public binding, dual VNIC ownership, backend separation, DRG routes and deterministic return path
    requirement: SRV-03
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_topology.py#exact topology and adversarial drift cases"
        status: pass
    human_judgment: false
  - id: D2
    description: Current topology receipt rejects stale authority and authorizes no live action
    requirement: SRV-04
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/evidence/phase53/topology-discovery.json#status PASS with eight semantic checks"
        status: pass
    human_judgment: false
duration: 10min
completed: 2026-07-26
status: complete
---

# Phase 53 Plan 05D2T: Read-Only Topology Authority Summary

**Exact dual-VNIC atius-srv-1 edge, Horistic backend, DRG routes and deterministic return identity proved by a value-free non-authorizing receipt**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-26T04:35:00Z
- **Completed:** 2026-07-26T04:45:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Codified `137.131.140.20` as RESERVED/ASSIGNED on the `atius-srv-1` public VNIC at `10.0.0.238`, distinct from the OCI-primary route/SNAT VNIC at `10.11.1.11`.
- Proved the `horistic-srv` backend at `10.21.1.21` has no public IP on that private address; `163.176.232.119` remains attached to the separate `10.0.0.65` VNIC.
- Required both central DRG attachments, cross-CIDR route-table targets, forward/reverse host routes and the deterministic `10.11.1.11` edge return identity.
- Emitted a current receipt with eight semantic checks, no raw topology/provider identifiers, and explicit `authorizes_live=false`, `committed_authority=false` and `mutation_performed=false`.

## Task Commits

1. **Task 53-05D2T-01 RED: adversarial topology tests** - `5521e4142`
2. **Task 53-05D2T-01 GREEN: strict contract and discovery validator** - `9705694c7`
3. **Task 53-05D2T-02: current non-authorizing discovery receipt** - `2d25da9c8`

## Verification

- Governed topology suite: `18 passed`.
- Current governed discovery: `status=PASS`, eight semantic checks, no mutation.
- Receipt redaction scan: no IP addresses, OCIDs, typed confirmations or stale OperationPlan hashes.
- `git diff --check`: PASS.
- Resource governor containment: structural PASS at `CPUQuota=80%`, equal to the configured 20% total host CPU; swap pressure remained warning-only.

## Decisions Made

- Public attachment and return-path identities are intentionally different. The public IP binds to `10.0.0.238`, while traffic to the backend uses the `10.11.1.11` OCI-primary route identity and must SNAT to that deterministic source.
- The discovery validator consumes only a bounded observation document from explicit read-only OCI/host collection. It cannot create an OperationPlan, approval, provider mutation or host command.
- Receipt `PASS` means only that current topology matches D-06/D-16/D-17. It does not authorize 05D2A, 05E, 05F or any live infrastructure action.

## Deviations from Plan

None in the declared five-file ownership or read-only safety boundary.

## Issues Encountered

- The local GBrain CLI could not connect because PgBouncer rejected the configured `statement_timeout` startup parameter. Execution continued from current workstream/Graphify/repo evidence and the root executor's fresh read-only OCI/host readbacks; no historical claim was promoted to current truth.
- Graphify was fresh at the required starting HEAD. It became commit-stale after the three scoped plan commits; refresh is deferred to the root executor's serialized post-wave Graphify update because this agent is forbidden from mutating Graphify artifacts outside its five-file ownership.

## TDD Gate Compliance

- RED commit exists: `5521e4142`.
- GREEN commit exists after RED: `9705694c7`.
- No refactor commit was needed.

## Known Stubs

None.

## User Setup Required

None. This plan performed no OCI, Cloudflare or host mutation and created no OperationPlan or approval.

## Next Phase Readiness

The topology prerequisite is a current read-only `PASS`, but all live authority remains false. The root orchestrator may consider `53-05D2A` only after it incorporates this plan through the normal serial wave boundary; this executor stops here and does not dispatch it.

## Self-Check: PASSED

- All five declared files exist.
- RED, GREEN and receipt commits exist.
- Receipt invariants and redaction checks pass.
- No goal-blocking stubs or unplanned security surface were found.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-26*
