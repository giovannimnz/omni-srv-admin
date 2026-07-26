---
phase: 53-primary-relay-and-public-edge
plan: 05D2T
type: execute
wave: 8
depends_on: [53-05D]
gap_closure: true
execution_owner: 53-05D2T
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-topology.json
  - modules/rustdesk-fleet/tools/discover-phase53-topology.py
  - modules/rustdesk-fleet/tests/test_phase53_topology.py
  - modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md
autonomous: true
requirements: [SRV-03, SRV-04]
must_haves:
  truths:
    - "Per D-06, current read-only inventory proves atius-srv-1/137.131.140.20/10.0.0.238 is the edge and horistic-srv/10.21.1.21 is the backend."
    - "The receipt proves VNIC ownership, DRG path and a deterministic edge-return path; any drift blocks before semantic reconciliation."
    - "Per D-17, the stale OperationPlan is explicitly rejected and is never an authority input."
    - "Per D-16, 10.31.1.31 is recorded only as a non-executable future handoff."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-topology.json
      provides: "Value-free exact current topology and non-executable migration boundary."
    - path: modules/rustdesk-fleet/tools/discover-phase53-topology.py
      provides: "Read-only bounded OCI/host topology discovery and drift gate."
    - path: modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
      provides: "Current non-authorizing receipt; never part of execution-source authority."
  key_links:
    - from: modules/rustdesk-fleet/tools/discover-phase53-topology.py
      to: modules/rustdesk-fleet/contracts/phase53-topology.json
      via: "strict equality over edge VNIC, backend, DRG and return-path facts"
      pattern: "137\\.131\\.140\\.20|10\\.0\\.0\\.238|10\\.21\\.1\\.21"
---

<objective>
Establish the read-only topology authority required by D-06, D-16 and D-17 before any edge semantic rewrite.

Purpose: fail closed if the proved OCI/VNIC/DRG topology differs from the operator-approved cross-host design.
Output: strict topology contract, bounded discovery tool/tests and a current value-free non-authorizing receipt.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md
@modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
@inventory/hosts/atius-srv-1.yaml
@inventory/hosts/horistic-srv.yaml
</context>

## Artifacts This Phase Produces

- `phase53-topology.json`: exact edge/backend/return-path contract without secret values or mutable receipt hashes.
- `discover-phase53-topology.py`: read-only provider/host inventory parser with bounded output and zero mutation capability.
- `topology-discovery.json`: current observation receipt marked `authorizes_live=false` and `committed_authority=false`.

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2T-01: Codify and prove current edge/backend topology</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
    @modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
    @inventory/hosts/atius-srv-1.yaml
    @inventory/hosts/horistic-srv.yaml
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-topology.json, modules/rustdesk-fleet/tools/discover-phase53-topology.py, modules/rustdesk-fleet/tests/test_phase53_topology.py</files>
  <behavior>
    - "Accept only profile atius1 RESERVED/ASSIGNED 137.131.140.20 bound to 10.0.0.238 on an atius-srv-1 VNIC."
    - "Accept only Horistic backend 10.21.1.21 with no public IP on that private address; 163.176.232.119 remains a different reserved VNIC."
    - "Require a complete DRG/route-table path plus return-path policy from backend to 10.0.0.238."
    - "Reject the stale OperationPlan source/hash and executable 10.31.1.31."
  </behavior>
  <action>
Create the strict D-06 topology contract and a bounded read-only discovery CLI. The contract must name edge host/profile/public/private/VNIC ownership, backend host/private address, DRG route and return-path expectations, and D-16 future destination with `executable=false`. The CLI may call only inventory/read methods, must never expose provider mutation methods, and must emit stable value-free identifiers/digests. Tests use hermetic inventory fixtures for correct ownership, public-IP reassignment, wrong VNIC/host, missing route, asymmetric return path, Horistic public-IP confusion, stale OperationPlan reuse and executable future handoff.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_topology.py --disable-warnings</automated>
  </verify>
  <acceptance_criteria>The code can distinguish the proved cross-host topology from every stale/single-host/misassigned variant without any provider write capability.</acceptance_criteria>
  <done>The exact D-06/D-16 topology is machine-readable and adversarially tested.</done>
</task>

<task type="auto">
  <name>Task 53-05D2T-02: Run read-only discovery and issue a non-authorizing receipt</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/tools/discover-phase53-topology.py
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/topology-discovery.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md</files>
  <action>
Run the discovery tool against current read-only OCI inventory and bounded host route/readback. Require exact edge/VNIC/backend/DRG/return-path equality and explicitly mark the stale OperationPlan rejected. Write only a value-free receipt with `authorizes_live=false`, `committed_authority=false`, `mutation_performed=false`, current observation timestamps and semantic digests. PASS continues automatically; contradiction exits BLOCKED and does not create a topology checkpoint or mutate infrastructure.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 modules/rustdesk-fleet/tools/discover-phase53-topology.py --repo . --output modules/rustdesk-fleet/evidence/phase53/topology-discovery.json --json</automated>
    <automated>git diff --check</automated>
  </verify>
  <acceptance_criteria>Receipt proves the exact current topology, contains no secret or approval material, authorizes nothing, and any drift blocks before 05D2A.</acceptance_criteria>
  <done>Current topology is proved read-only and ready for semantic reconciliation.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53T-SPOOF | Spoofing | OCI public-IP/VNIC identity | critical | mitigate | Exact profile/state/private-IP/VNIC/host equality with current readback. |
| T53T-ROUTE | Tampering/DoS | DRG and return path | critical | mitigate | Complete route-table/attachment and deterministic return-path proof. |
| T53T-REPLAY | Repudiation | stale OperationPlan | critical | mitigate | D-17 explicit rejection; receipt is non-authorizing and source-old hashes are forbidden. |
| T53T-FUTURE | Elevation of Privilege | 10.31.1.31 handoff | high | mitigate | D-16 executable=false plus adversarial rejection. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status |
|---|---|---|---|---|
| GOAL | Phase 53 | Stable hardened primary through approved public edge | 05D2T-06 | COVERED |
| REQ | SRV-02 | Rootless hardened backend | 05D/05D2A/05F | COVERED |
| REQ | SRV-03 | Exact translated edge/native negatives | 05D2T/05D2A/05F | COVERED |
| REQ | SRV-04 | Reserved IP, DNS and external proof | 05D2T/05D2A/05E/05F | COVERED |
| REQ | SRV-06 | Lifecycle persistence | 05D2B/05F/06 | COVERED |
| REQ | OPS-01 | Separate authenticated ops API | 05D2A/05F/06 | COVERED |
| RESEARCH | nftables/OCI | Cross-host DNAT/forward, ct-original distinction, effective ingress | 05D2T/05D2A | COVERED |
| CONTEXT | D-01..D-15 | Runtime, edge, API, lifecycle and rollback | 05D-06 | COVERED |
| CONTEXT | D-16, D-17 | Non-executable migration and stale-plan rejection | 05D2T/05D2B/05E | COVERED |
| CONTEXT | Deferred | Clients, fleet rollout and DR | excluded | EXCLUDED |

No source item is missing.

<verification>Only governed tests, read-only inventory and structural diff checks run; no live mutation or approval is created.</verification>

<success_criteria>
1. Exact current topology and return path are proved without writes.
2. Stale OperationPlan reuse and topology drift block.
3. The receipt is value-free and explicitly non-authorizing.
</success_criteria>

<output>Create `53-05D2T-SUMMARY.md` and stop; do not dispatch 05D2A automatically.</output>
