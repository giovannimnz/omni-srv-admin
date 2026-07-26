---
phase: 53-primary-relay-and-public-edge
plan: 05D2B
type: execute
wave: 10
depends_on: [53-05D2A]
gap_closure: true
execution_owner: 53-05D2B
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json
  - modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  - modules/rustdesk-fleet/tools/phase53-live-backend.py
  - modules/rustdesk-fleet/tools/phase53-live-adapters.py
  - modules/rustdesk-fleet/tools/phase53-production-adapters.py
  - modules/rustdesk-fleet/tools/phase53_production_adapters.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Runner exposes literal plan/apply/full/rollback/restore-production interfaces with exit 0/2/3/4."
    - "Apply, rollback and restore-production have distinct transaction IDs, journals and immutable receipt boundaries."
    - "All negative authority/source/topology/approval paths create no journal and invoke no provider."
    - "Per D-16, 10.31.1.31 remains executable=false and is rejected by every Phase 53 backend/provider."
    - "The public binding checker is explicit-path, read-only and validates the complete source/evidence/summary ancestry."
  artifacts:
    - path: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      provides: "Complete plan/apply transaction state machine."
    - path: modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
      provides: "Read-only source/live/summary/verification binding checker."
    - path: modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json
      provides: "Non-executable Phase 54 migration boundary."
  key_links:
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/phase53-live-backend.py
      via: "mode selects one capability-disjoint backend before journal creation"
      pattern: "plan|apply|restore-production"
---

<objective>
Implement the full transaction runner, journal separation, migration boundary and read-only binding checker after semantic reconciliation.

Purpose: make every live-capable transition explicit, authority-bound, recoverable and zero-side-effect on failure.
Output: complete runner/backend/adapters, non-executable handoff, checker and adversarial tests.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2A-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-topology.json
@modules/rustdesk-fleet/contracts/phase53-edge.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
</context>

## Artifacts This Phase Produces

- Literal runner CLI/state machine for read-only plan and one owner-approved apply.
- Distinct apply, immutable rollback and restore-production journal contracts.
- Explicit-path binding checker and non-executable migration handoff.

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2B-01: Complete runner and disjoint transaction journals</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/tools/run-phase53-live-gate.py
    @modules/rustdesk-fleet/tools/phase53-live-backend.py
    @modules/rustdesk-fleet/tools/phase53-live-adapters.py
    @modules/rustdesk-fleet/tools/phase53_production_adapters.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json, modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/phase53-live-backend.py, modules/rustdesk-fleet/tools/phase53-live-adapters.py, modules/rustdesk-fleet/tools/phase53-production-adapters.py, modules/rustdesk-fleet/tools/phase53_production_adapters.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <behavior>
    - "Unknown/missing CLI arguments exit 2; missing/drifted authority exits 3; contained apply failure exits 4; plan-ready exits 0."
    - "Full order is preflight, closed backend/API, edge DNAT/forward, IP probes, DNS-last, hostname probes, lifecycle, containment rollback, sealed rollback, distinct production restore."
    - "No negative path creates a journal or calls a provider."
    - "10.31.1.31 is rejected before backend/provider construction."
  </behavior>
  <action>
Create D-16 handoff with current `10.21.1.21`, future `10.31.1.31`, `executable=false` and preserved identity/state/public-edge invariants. Implement exact CLI flags `--repo`, `--live-backend phase53-production`, `--mode plan|apply`, `--stage full|edge-probes|ops-api|lifecycle|rollback|restore-production`, `--operation-plan`, and apply-only `--owner-approval`. Separate read-only and apply factories. Validate source/topology/OperationPlan/approval/admission before creating any journal. Give apply, rollback and restore unique IDs/files; seal rollback bytes before restore and forbid resume across a terminal rollback.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'cli_mode or stage_full or journal or immutable_rollback or restore_production or migration_handoff or zero_side_effect' --disable-warnings</automated>
    <automated>env -u ATIUS_RUN_RUSTDESK_PHASE53_LIVE -u ADMITTED_PHASE53 python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan /nonexistent --owner-approval /nonexistent; test $? -eq 3</automated>
  </verify>
  <acceptance_criteria>Runner ordering and exit matrix are literal; every pre-authority negative is zero-side-effect; rollback and restore cannot share or rewrite transaction identity.</acceptance_criteria>
  <done>The full transaction engine is hermetic and fail-closed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2B-02: Build the explicit-path binding checker</name>
  <read_first>
    @modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
    @modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
    @modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  </read_first>
  <files>modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>
Export `compute_execution_source_binding(...)` and `validate_phase53_binding_chain(...)`. Require every canonical manifest path explicitly; read commit SHAs only from descendant summary/verification; prove source→live-evidence-only→summary-only→independent-verification ancestry, exact diffs, Git-object manifest digests, no self-hash, clean closed source scope and current strict-validator PASS. The checker has no network/provider/write mode and rejects missing/extra/duplicate/stale inputs.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'binding_chain or evidence_only or summary_only or ancestry or self_hash or dirty_scope' --disable-warnings</automated>
    <automated>git diff --check</automated>
  </verify>
  <acceptance_criteria>The checker deterministically rejects every broken binding without discovery, provider construction or writes.</acceptance_criteria>
  <done>The immutable chain can be independently rederived by 05F and 06.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53B-CAP | Elevation of Privilege | runner/backend | critical | mitigate | Capability-disjoint factories and all gates before journal/provider creation. |
| T53B-ROLL | Tampering/DoS | rollback/restore | critical | mitigate | Separate IDs/journals and immutable rollback seal. |
| T53B-BIND | Spoofing/Repudiation | source/evidence chain | critical | mitigate | Explicit paths, ancestry, exact diffs and Git-object hashes. |
| T53B-MIG | Tampering | future address | high | mitigate | D-16 executable=false enforced in every provider/backend. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status |
|---|---|---|---|---|
| GOAL | Phase 53 | Stable recoverable public primary | 05D2T-06 | COVERED |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Phase 53 requirements | 05D-06 | COVERED |
| RESEARCH | transaction/rollback | Ordered apply, containment and restore | 05D2B/05F | COVERED |
| CONTEXT | D-01..D-15 | Runtime through rollback | 05D-06 | COVERED |
| CONTEXT | D-16, D-17 | Migration and stale authority | 05D2B/05E | COVERED |
| CONTEXT | Deferred | Later-phase client/DR work | excluded | EXCLUDED |

No source item is missing.

<verification>Governed hermetic selectors and zero-side-effect CLI negatives only; no live action.</verification>

<success_criteria>
1. Runner, journals and checker are fully testable before live authority.
2. Future migration is unreachable.
3. No source seal is captured until 05D2C broad green.</success_criteria>

<output>Create `53-05D2B-SUMMARY.md` and stop; do not dispatch 05D2C automatically.</output>
