---
phase: 53-primary-relay-and-public-edge
plan: 05D2C
type: execute
wave: 11
depends_on: [53-05D2B]
gap_closure: true
execution_owner: 53-05D2C
files_modified:
  - .planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
  - modules/rustdesk-fleet/evidence/ledger.json
  - modules/rustdesk-fleet/tests/test_phase51_contracts.py
  - modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
  - modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "The clean HEAD-bound ROADMAP planning ancestor assigns SCP-01 to Phase 55, not Phase 51, before execution begins; the executor leaves ROADMAP.md unchanged."
    - "SCP-01 has one final owner, Phase 55, and remains pending until all five clients are installed; Phase 54 is only a partial prerequisite."
    - "The requirement ledger has seven current passed requirements and 29 pending requirements, with no evidence_catalog claim for pending SCP-01."
    - "The closed allowlist contains exactly 33 Phase 53 live/test paths and excludes REQUIREMENTS.md, ledger.json, test_phase51_contracts.py and every evidence/planning receipt."
    - "Dirty, missing, extra or changed allowlisted paths block the seal."
    - "The complete governed RustDesk suite exits zero immediately before sealing."
    - "Explicit pathspec staging of exactly six non-summary files creates execution_source_commit; no broad git add is allowed."
    - "53-05D2C-SUMMARY.md is a separate direct descendant and no source changes follow the seal."
  artifacts:
    - path: .planning/workstreams/rustdesk-fleet/ROADMAP.md
      provides: "Planning-ancestor ownership map assigning SCP-01 only to Phase 55."
    - path: .planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
      provides: "Canonical single-owner SCP-01 traceability at Phase 55/Pending."
    - path: modules/rustdesk-fleet/evidence/ledger.json
      provides: "Truthful SCP-01 fleet-rollout-live pending row without catalog evidence."
    - path: modules/rustdesk-fleet/tests/test_phase51_contracts.py
      provides: "Regression coverage for seven passed, 29 pending and exact SCP-01 ownership/status."
    - path: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      provides: "Closed sorted 33-path Phase 53 source allowlist and canonical Git blob aggregate."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
      provides: "Separate descendant recording the final source commit/tree."
  key_links:
    - from: .planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
      to: modules/rustdesk-fleet/evidence/ledger.json
      via: "single Phase 55 owner and pending status for SCP-01"
      pattern: "SCP-01"
    - from: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      to: modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
      via: "canonical sorted path/NUL/blob/LF aggregate and dirty-scope validation"
      pattern: "execution_source"
---

<objective>
Repair the truthful SCP-01 ownership/status prerequisite, then seal the final execution source only after focused, selector and broad green verification.

Purpose: prevent a historical Phase 51 scope artifact from laundering fleet-install completion, and ensure 05E approval and 05F live execution bind the exact complete Phase 53 source rather than a partial or dirty tree.
Output: converged traceability/ledger contract, closed 33-path source scope, final six-path execution source commit and summary-only descendant.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2A-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2B-SUMMARY.md
</context>

## Artifacts This Phase Produces

- Truthful SCP-01 single-owner traceability and pending ledger state.
- Closed source allowlist covering every production-consumed Phase 53 byte.
- Canonical source tree digest and exact `execution_source_commit`.
- Summary-only descendant carrying the seal without changing source.

The planning commit containing this plan must already move SCP-01 from the
Phase 51 requirement list to the Phase 55 requirement list in `ROADMAP.md`.
That planning commit is an ancestor prerequisite, not an execution-owned path;
the executor verifies it and never edits or stages `ROADMAP.md`.

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2C-01: Converge SCP-01 traceability and ledger truth</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/ROADMAP.md
    @.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
    @modules/rustdesk-fleet/evidence/ledger.json
    @modules/rustdesk-fleet/tests/test_phase51_contracts.py
  </read_first>
  <files>.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md, modules/rustdesk-fleet/evidence/ledger.json, modules/rustdesk-fleet/tests/test_phase51_contracts.py</files>
  <behavior>
    - "HEAD's committed ROADMAP lists SCP-01 under Phase 55 and omits it from Phase 51; both index and worktree copies are clean and read-only during execution."
    - "The canonical traceability parser sees exactly `SCP-01 | Phase 55 | Pending`, never a multi-phase owner."
    - "The SCP-01 ledger row is owner_phase 55, acceptance_kind fleet-rollout-live, status pending and last_verified_at null."
    - "RDF-V19-SCP-01 remains the stable evidence_ids reservation on the pending row but is absent from evidence_catalog."
    - "Exactly seven requirements are currently passed and 29 are pending; SCP-01 is asserted explicitly as Phase 55/pending."
  </behavior>
  <action>
Before reading ownership, require both `git diff --quiet -- .planning/workstreams/rustdesk-fleet/ROADMAP.md` and `git diff --cached --quiet -- .planning/workstreams/rustdesk-fleet/ROADMAP.md`; a dirty or staged ROADMAP blocks execution. Read the ownership text only from `git show HEAD:.planning/workstreams/rustdesk-fleet/ROADMAP.md`, not from the worktree, and assert that HEAD omits SCP-01 from the Phase 51 `**Requirements**` line and includes it on the Phase 55 `**Requirements**` line. Capture `ROADMAP_COMMIT` from `git log -n1 --format=%H -- .planning/workstreams/rustdesk-fleet/ROADMAP.md`, require it non-empty and an ancestor of HEAD, and treat that commit as the planning prerequisite. Treat `ROADMAP.md` as read-only: do not edit, stage or include it in either execution commit. Change the traceability row to exactly `SCP-01 | Phase 55 | Pending`; Phase 54 remains a partial prerequisite and must not be encoded as an owner. In the ledger, set SCP-01 to `owner_phase: 55`, `acceptance_kind: fleet-rollout-live`, `status: pending` and `last_verified_at: null`; retain `RDF-V19-SCP-01` only in the row's `evidence_ids` reservation and remove its object from `evidence_catalog`. Update the Phase 51 ledger contract test to expect the exact seven currently passed requirement IDs, 29 pending rows, the explicit Phase 55/pending SCP-01 traceability and ledger fields, the retained reservation, and the absence of catalog evidence. Do not change `validate_phase51.py` or regenerate frozen Phase 51 reports/verification: those artifacts remain historical and pinned.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'ROADMAP=.planning/workstreams/rustdesk-fleet/ROADMAP.md; git diff --quiet -- "$ROADMAP"; git diff --cached --quiet -- "$ROADMAP"; ROADMAP_COMMIT=$(git log -n1 --format=%H -- "$ROADMAP"); test -n "$ROADMAP_COMMIT"; git merge-base --is-ancestor "$ROADMAP_COMMIT" HEAD; git show "HEAD:$ROADMAP" | python3 -c "import sys; text=sys.stdin.read(); phase51=text.split(\"### Phase 51:\",1)[1].split(\"### Phase 52:\",1)[0]; phase55=text.split(\"### Phase 55:\",1)[1].split(\"### Phase 56:\",1)[0]; assert \"**Requirements**: SCP-02, SCP-03, SCP-05\" in phase51 and \"SCP-01\" not in phase51; assert \"**Requirements**: SCP-01, CLI-03, CLI-05, CLI-08, CLI-09\" in phase55"'</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase51_contracts.py -k 'requirement_ledger' --disable-warnings</automated>
  </verify>
  <acceptance_criteria>The current parser, traceability and ledger agree that SCP-01 completes only in Phase 55 after the full five-client rollout, while historical Phase 51 closeout remains unchanged.</acceptance_criteria>
  <done>The first full-suite blocker is removed without claiming that SCP-01 is complete.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2C-02: Close and adversarially verify the 33-path execution-source scope</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/contracts/phase53-edge.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
    @modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>
Keep the allowlist sorted, duplicate-free and exactly 33 paths covering all Phase 53 live contracts (topology, edge, runtime, ops API, provider, migration), nftables template, all systemd units/timers/slice, both server Quadlets, canonical server installer, ops API, apply/probe tools including PowerShell probe, topology discovery, runner/backend/all adapters, strict validator, binding checker and both Phase 53 test files. Exclude `.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md`, `modules/rustdesk-fleet/evidence/ledger.json`, `modules/rustdesk-fleet/tests/test_phase51_contracts.py`, all other evidence, summaries, approvals and planning from the execution aggregate. Implement canonical SHA-256 over sorted `path NUL Git-blob-OID LF` records. The binding checker must accept an execution-source commit whose exact changed-path set is the six non-summary files owned by this plan while hashing only the 33 allowlisted Phase 53 paths; tests reject unknown, missing, extra, symlinked, dirty and modified entries, any seventh non-summary commit path, and inclusion of the three SCP-01 convergence paths in the execution allowlist.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'execution_source or source_scope or dirty_scope or source_tree_digest' --disable-warnings</automated>
  </verify>
  <acceptance_criteria>The selector remains green for the exact 33-path Phase 53 source aggregate, the exact six-path seal commit and all mutable authority/evidence/dirt adversarial variants.</acceptance_criteria>
  <done>The exact sealable source set is deterministic.</done>
</task>

<task type="auto">
  <name>Task 53-05D2C-03: Require broad green, seal six exact paths and write descendant summary</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
    @modules/rustdesk-fleet/evidence/ledger.json
    @modules/rustdesk-fleet/tests/test_phase51_contracts.py
    @modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
    @modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  </read_first>
  <files>.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md, modules/rustdesk-fleet/evidence/ledger.json, modules/rustdesk-fleet/tests/test_phase51_contracts.py, modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md</files>
  <action>
After Task 01's planning-ancestor and focused Phase 51 ledger gates and Task 02's 05D2C selector are green, run the full governed RustDesk module suite and require exit 0. Require every allowlisted path clean relative to the pending 05D2C patch and reject unrelated changes inside scope. Stage exactly `.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md`, `modules/rustdesk-fleet/evidence/ledger.json`, `modules/rustdesk-fleet/tests/test_phase51_contracts.py`, `modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json`, `modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py` and `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` with literal `git add --` pathspecs; never edit or stage `ROADMAP.md`, and never use broad staging. Commit exactly those six non-summary files as the final `execution_source_commit`. Then write `53-05D2C-SUMMARY.md` with commit/tree/33-path count, `ROADMAP_COMMIT` and all ordered test commands, and create a direct summary-only descendant whose sole changed path is that summary. After both commits exist, derive `SOURCE_COMMIT=HEAD^` and `SUMMARY_COMMIT=HEAD`; use unfiltered `git diff-tree --root --no-commit-id --name-only -r` to prove the source commit has exactly the six declared paths and the summary commit has only `53-05D2C-SUMMARY.md`; prove `SUMMARY_COMMIT^ == SOURCE_COMMIT`. Recalculate `ROADMAP_COMMIT` from the last commit that changed `ROADMAP.md` because Task 03 runs in a new shell, resolve the commits that last changed the 05D, 05D2T, 05D2A and 05D2B summaries, and require ROADMAP_COMMIT plus all four predecessor commits to be ancestors of SOURCE_COMMIT with `git merge-base --is-ancestor`. Load the source-scope JSON payload and pass it explicitly to `validate_execution_source_scope_payload(payload)`; use only the validator's returned exact sorted 33 paths for `compute_execution_source_binding` at SOURCE_COMMIT and SUMMARY_COMMIT, require identical `execution_source_tree_sha256`, blobs and manifest paths, and call `require_clean_execution_source` against SOURCE_COMMIT using that digest while HEAD is the summary descendant. Any later source correction invalidates the seal and repeats this task.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests --disable-warnings</automated>
    <automated>bash -euo pipefail -c 'SOURCE_COMMIT=$(git rev-parse HEAD^); SUMMARY_COMMIT=$(git rev-parse HEAD); test "$(git rev-parse "${SUMMARY_COMMIT}^")" = "$SOURCE_COMMIT"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE_COMMIT" | LC_ALL=C sort)" = "$(printf "%s\n" .planning/workstreams/rustdesk-fleet/REQUIREMENTS.md modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json modules/rustdesk-fleet/evidence/ledger.json modules/rustdesk-fleet/tests/test_phase51_contracts.py modules/rustdesk-fleet/tests/test_phase53_primary_edge.py modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py | LC_ALL=C sort)"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SUMMARY_COMMIT")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md"; ROADMAP_COMMIT=$(git log -n1 --format=%H -- .planning/workstreams/rustdesk-fleet/ROADMAP.md); test -n "$ROADMAP_COMMIT"; git merge-base --is-ancestor "$ROADMAP_COMMIT" "$SOURCE_COMMIT"; for PREDECESSOR_SUMMARY in .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2A-SUMMARY.md .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2B-SUMMARY.md; do PREDECESSOR_COMMIT=$(git log -n 1 --format=%H -- "$PREDECESSOR_SUMMARY"); test -n "$PREDECESSOR_COMMIT"; git merge-base --is-ancestor "$PREDECESSOR_COMMIT" "$SOURCE_COMMIT"; done'</automated>
    <automated>env SOURCE_COMMIT="$(git rev-parse HEAD^)" SUMMARY_COMMIT="$(git rev-parse HEAD)" python3 -c 'import importlib.util,json,os; from pathlib import Path; repo=Path(".").resolve(); checker=repo/"modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py"; spec=importlib.util.spec_from_file_location("phase53_binding_checker",checker); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); payload=json.loads((repo/"modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json").read_text()); paths=module.validate_execution_source_scope_payload(payload); assert len(paths)==33; source=os.environ["SOURCE_COMMIT"]; summary=os.environ["SUMMARY_COMMIT"]; source_binding=module.compute_execution_source_binding(repo=repo,execution_source_commit=source,manifest_paths=paths); head_binding=module.compute_execution_source_binding(repo=repo,execution_source_commit=summary,manifest_paths=paths); assert source_binding["execution_source_tree_sha256"]==head_binding["execution_source_tree_sha256"] and source_binding["blobs"]==head_binding["blobs"] and source_binding["manifest_paths"]==head_binding["manifest_paths"]==paths; module.require_clean_execution_source(repo=repo,execution_source_commit=source,manifest_paths=paths,expected_tree=source_binding["execution_source_tree_sha256"])'</automated>
  </verify>
  <acceptance_criteria>The ordered focused, selector and full-suite gates exit zero; the source commit changes exactly six explicit paths and contains all predecessor source as ancestors; the direct descendant changes only the summary.</acceptance_criteria>
  <done>The immutable execution source is sealed and ready for new authority generation.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53C-OMIT | Tampering | closed allowlist | critical | mitigate | Explicit exhaustive path inventory plus missing/extra tests. |
| T53C-DIRT | Tampering | shared checkout | critical | mitigate | Scope-local dirty rejection and literal pathspec staging. |
| T53C-SEAL | Repudiation | source commit | critical | mitigate | Broad green, ancestry, Git-object aggregate and summary-only descendant. |
| T53C-SCP01 | Tampering | roadmap ownership, requirement traceability and ledger | high | mitigate | Planning ancestor assigns SCP-01 only to Phase 55; executor leaves ROADMAP unchanged; pending state, no catalog evidence, exact seven/29 counts and focused contract tests prevent premature closure or historical Phase 51 authority laundering. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status |
|---|---|---|---|---|
| GOAL | Phase 53 | Stable recoverable public primary | 05D2T-06 | COVERED |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Complete Phase 53 source | 05D2C | COVERED |
| REQ | SCP-01 | Cross-phase ledger prerequisite remains Phase 55/Pending; 05D2C corrects metadata only and does not complete it | 05D2C | COVERED |
| RESEARCH | source currentness | Immutable production binding | 05D2C | COVERED |
| CONTEXT | D-01..D-17 | All locked decisions | 05D-06 | COVERED |
| CONTEXT | Deferred | Later phase work | excluded | EXCLUDED |

No source item is missing.

<verification>Focused Phase 51 ledger contracts, the 05D2C selector, the full governed module suite, source-scope checks and git structural checks only; no authority/live mutation.</verification>

<success_criteria>
1. SCP-01 is Phase 55/Pending with seven current passes, 29 pending rows and no catalog evidence.
2. The focused ledger gate, 05D2C selector and broad suite exit zero in that order.
3. The source allowlist has exactly 33 Phase 53 live/test paths and is clean.
4. The exact six-path source commit and summary-only direct descendant are structurally separate.</success_criteria>

<output>Create `53-05D2C-SUMMARY.md` in a direct summary-only descendant and stop.</output>
