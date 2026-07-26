---
phase: 53-primary-relay-and-public-edge
plan: 05D2C
type: execute
wave: 11
depends_on: [53-05D2B]
gap_closure: true
execution_owner: 53-05D2C
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
  - modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "The closed allowlist names every live contract/tool/template/unit/Quadlet/installer/ops API/probe/checker and no evidence/planning receipt."
    - "Dirty, missing, extra or changed allowlisted paths block the seal."
    - "The complete governed RustDesk suite exits zero immediately before sealing."
    - "Explicit pathspec staging creates execution_source_commit; no broad git add is allowed."
    - "53-05D2C-SUMMARY.md is a separate direct descendant and no source changes follow the seal."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      provides: "Closed sorted source allowlist and canonical Git blob aggregate."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
      provides: "Separate descendant recording the final source commit/tree."
  key_links:
    - from: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      to: modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
      via: "canonical sorted path/NUL/blob/LF aggregate and dirty-scope validation"
      pattern: "execution_source"
---

<objective>
Seal the final execution source only after broad green and closed-scope verification.

Purpose: ensure 05E approval and 05F live execution bind the exact complete source, not a partial or dirty tree.
Output: closed source scope, final execution source commit and summary-only descendant.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2A-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2B-SUMMARY.md
</context>

## Artifacts This Phase Produces

- Closed source allowlist covering every production-consumed Phase 53 byte.
- Canonical source tree digest and exact `execution_source_commit`.
- Summary-only descendant carrying the seal without changing source.

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2C-01: Close and adversarially verify the execution-source scope</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/contracts/phase53-edge.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
    @modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>
Create a sorted duplicate-free allowlist containing all Phase 53 live contracts (topology, edge, runtime, ops API, provider, migration), nftables template, all systemd units/timers/slice, both server Quadlets, canonical server installer, ops API, apply/probe tools including PowerShell probe, topology discovery, runner/backend/all adapters, strict validator, binding checker and both Phase 53 test files. Exclude evidence, summaries, approvals and planning. Implement canonical SHA-256 over sorted `path NUL Git-blob-OID LF` records. Tests reject unknown, missing, extra, symlinked, dirty and modified entries.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'execution_source or source_scope or dirty_scope or source_tree_digest' --disable-warnings</automated>
  </verify>
  <acceptance_criteria>The allowlist is closed over every live consumer and rejects all mutable authority/evidence paths and dirty-scope variants.</acceptance_criteria>
  <done>The exact sealable source set is deterministic.</done>
</task>

<task type="auto">
  <name>Task 53-05D2C-02: Require broad green, seal with explicit pathspecs and write descendant summary</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
    @modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md</files>
  <action>
Run the full governed RustDesk suite and require exit 0. Require every allowlisted path clean relative to the pending 05D2C patch and reject unrelated changes inside scope. Stage only the three 05D2C source paths with literal `git add -- path...`; never use broad staging. Commit them as the final `execution_source_commit`, prove 05D/05D2T/05D2A/05D2B ancestry and recompute the aggregate from that Git object. Then write `53-05D2C-SUMMARY.md` with commit/tree/path count/test command and create a direct summary-only descendant. Any later source correction invalidates the seal and repeats this task.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests --disable-warnings</automated>
    <automated>git diff --check</automated>
  </verify>
  <acceptance_criteria>Broad suite exits zero; source commit contains only explicit staged source changes and all predecessor source as ancestors; direct descendant changes only the summary.</acceptance_criteria>
  <done>The immutable execution source is sealed and ready for new authority generation.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53C-OMIT | Tampering | closed allowlist | critical | mitigate | Explicit exhaustive path inventory plus missing/extra tests. |
| T53C-DIRT | Tampering | shared checkout | critical | mitigate | Scope-local dirty rejection and literal pathspec staging. |
| T53C-SEAL | Repudiation | source commit | critical | mitigate | Broad green, ancestry, Git-object aggregate and summary-only descendant. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status |
|---|---|---|---|---|
| GOAL | Phase 53 | Stable recoverable public primary | 05D2T-06 | COVERED |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Complete Phase 53 source | 05D2C | COVERED |
| RESEARCH | source currentness | Immutable production binding | 05D2C | COVERED |
| CONTEXT | D-01..D-17 | All locked decisions | 05D-06 | COVERED |
| CONTEXT | Deferred | Later phase work | excluded | EXCLUDED |

No source item is missing.

<verification>Full governed suite, source-scope checks and git structural checks only; no authority/live mutation.</verification>

<success_criteria>
1. Broad suite exits zero.
2. Source allowlist is exhaustive and clean.
3. Source and summary commits are structurally separate.</success_criteria>

<output>Create `53-05D2C-SUMMARY.md` in a direct summary-only descendant and stop.</output>
