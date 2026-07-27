---
phase: 53-primary-relay-and-public-edge
plan: 05D2Q
type: execute
wave: 12
depends_on: [53-05D2C]
gap_closure: true
execution_owner: 53-05D2Q
files_modified:
  - modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py
  - modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-21, Q owns exactly four paths: reusable validator, dedicated test, value-free baseline and direct summary-only child."
    - "The exact seven dirty paths are classified with tracked/untracked from git ls-files, exact porcelain-v1 -z XY, confined regular-file lstat type/mode/size and O_NOFOLLOW streaming SHA-256 in 1 MiB chunks."
    - "Two consecutive passes must match, closing the capture TOCTOU window; captured_at is RFC3339 UTC and captured_head is exact."
    - "The closed duplicate-key-rejecting schema has the exact seven-path set and a canonical self digest; capture writes create-only mode 0600 with fsync/no-replace and emits no payload, diff, stdout or stderr."
    - "The only legal sequence is capture at H, exact at H, source commit S with parent(S)=H, source-only ancestor at S or descendants, summary commit C with parent(C)=S, then summary-form ancestor at C or descendants; exact is never run at S, C or any descendant."
    - "Policy ancestor recomputes every dirty-path field against the baseline without requiring current HEAD=captured_head. Source-only form proves one parent, parent(S)=H, the literal three-path Q source diff and S ancestry to current HEAD; summary form adds one-parent C, parent(C)=S, the literal summary-only diff and C ancestry to current HEAD. `--summary-commit` and `--summary-path` are paired."
    - "Q never modifies, stages, normalizes or reads payload content from the seven dirty paths beyond the bounded hash stream."
  artifacts:
    - path: modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py
      provides: "Reusable capture/exact/ancestor validator for the seven carry-forward paths."
    - path: modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py
      provides: "Positive and adversarial coverage for every stored field, schema, TOCTOU and Git-chain rule."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
      provides: "Canonical value-free baseline."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md
      provides: "Direct summary child binding source/tree/baseline digest."
  key_links:
    - from: modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py
      to: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
      via: "capture, exact and ancestor subcommands over one closed schema"
      pattern: "capture|exact|ancestor|baseline_sha256"
  prohibitions:
    - "Do not modify any of the seven captured paths, source/evidence/Phase 52/54, graphs, AUTONOMOUS-GOAL or historical 53-05 files."
    - "Do not use read_bytes for hashing, follow symlinks, replace an existing baseline or serialize command streams."
---

<objective>
Create and seal a reusable full-field dirty-baseline gate before any new transport source is added.

Purpose: prove exact preservation across R/V/S and exact entry into D without trusting a partial comparison.
Output: validator, dedicated tests, canonical baseline and direct summary-only child.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/STATE.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2Q-01: Build the reusable complete baseline validator</name>
  <files>modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py, modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py</files>
  <behavior>
    - "Capture derives tracked/untracked with git ls-files and exact two-byte porcelain-v1 -z XY for each literal path."
    - "Each entry is confined below repo root and must be a regular non-symlink file; lstat mode/size/type and O_NOFOLLOW SHA-256 streamed in 1 MiB chunks are exact."
    - "Pass one and pass two must have identical HEAD, path set, XY, lstat tuple and SHA-256; a changed byte/status/mode/type or HEAD fails without output replacement."
    - "JSON duplicate keys, unknown fields, missing/extra/duplicate paths, invalid RFC3339, wrong self digest and forbidden payload/stream fields fail."
    - "capture and exact require HEAD=captured_head. Exact is forbidden after S exists. Ancestor always recomputes the full dirty tuple without a current-HEAD equality requirement; source-only form requires one-parent S, parent(S)=captured_head, the exact literal validator/test/baseline source set and S as an ancestor of current HEAD."
    - "Ancestor summary form requires paired --summary-commit/--summary-path, one-parent C, parent(C)=S, exact summary-only diff and C as an ancestor of current HEAD; providing only one summary argument fails."
    - "Capture is create-only mode 0600 with file and parent-directory fsync; existing destination fails."
  </behavior>
  <action>
Per D-21, implement a stdlib-only CLI with literal subcommands `capture`, `exact` and `ancestor`. Hard-code the exact seven repo-relative paths named in the current D2D plan, but derive their stored count from that tuple. Use `git ls-files --error-unmatch -- <path>` for tracked classification and parse `git status --porcelain=v1 -z --untracked-files=all -- <path>` without lossy text normalization to store exact XY. Use dirfd confinement, `lstat`, `os.open(..., O_RDONLY|O_NOFOLLOW)`, `fstat` identity checks before/after and 1 MiB streaming SHA-256. Repeat the complete observation and reject any tuple/HEAD drift.

Parse JSON with an object-pairs duplicate detector and accept only the closed schema. Compute `baseline_sha256` over canonical JSON with that field omitted. For capture, use exclusive creation, mode 0600, flush/fsync and parent-directory fsync; never print the baseline or command stdout/stderr. `exact` recomputes every field only while HEAD is captured H and must refuse once S exists. `ancestor` always accepts explicit `--source-commit` and optionally the paired `--summary-commit` plus `--summary-path`; it recomputes every baseline field from the current worktree without requiring current HEAD to equal captured H. Source-only validation requires S to have exactly one parent equal to H, its unfiltered diff to equal the literal set `{modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py, modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json}`, and S to be an ancestor of current HEAD. Summary validation additionally requires C to have exactly one parent equal to S, its unfiltered diff to equal only `53-05D2Q-SUMMARY.md`, and C to be an ancestor of current HEAD. Reject unpaired summary arguments. Tests must use isolated temporary Git repositories and cover the legal H→S→C sequence plus positive tracked/untracked XY and negative symlink, directory, mode/status/content drift, duplicate keys, TOCTOU, exact-after-S, stale source ancestry, merge parents, wrong parent, unpaired summary args and extra source/summary diffs.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py --disable-warnings</automated>
  </verify>
  <done>The validator independently recomputes every promised field and both Git policies with adversarial coverage.</done>
</task>

<task type="auto">
  <name>Task 53-05D2Q-02: Capture exact baseline and seal the source-summary pair</name>
  <files>modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py, modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md</files>
  <action>
Capture against the literal baseline path at H, then run `exact` once while HEAD is still H and before staging. Commit exactly validator, test and baseline with literal pathspecs, producing S with parent(S)=H. Never run `exact` again. Immediately run source-only `ancestor --source-commit S`. Create `53-05D2Q-SUMMARY.md` containing captured H, source commit/tree, the exact three-path literal set, baseline digest, validator/test result and explicit zero-authority/zero-mutation flags, without payload content. Commit only the summary as C with parent(C)=S, then run summary-form `ancestor` with the paired summary arguments. The seven captured paths remain unstaged and full-field equal throughout.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'ROOT=$(git rev-parse --show-toplevel); BASE="$ROOT/.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json"; SUMMARY_REL=.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md; SOURCE=$(git rev-parse HEAD^); CHILD=$(git rev-parse HEAD); EXPECTED=$(printf "%s\n" .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py | LC_ALL=C sort); /usr/bin/python3 "$ROOT/modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py" ancestor --repo "$ROOT" --baseline "$BASE" --source-commit "$SOURCE"; /usr/bin/python3 "$ROOT/modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py" ancestor --repo "$ROOT" --baseline "$BASE" --source-commit "$SOURCE" --summary-commit "$CHILD" --summary-path "$SUMMARY_REL"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE" | LC_ALL=C sort)" = "$EXPECTED"; test "$(git diff-tree --root --no-commit-id --name-only -r "$CHILD")" = "$SUMMARY_REL"; git diff --check'</automated>
  </verify>
  <done>The literal validator/test/baseline source set and direct one-path summary child are sealed; ancestor recomputes all seven dirty paths at the descendant tip without an impossible post-commit exact call.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53Q-DIRT | Tampering | seven carry-forward paths | critical | mitigate | Two-pass full tuple plus O_NOFOLLOW streaming digest and exact/ancestor policies. |
| T53Q-TOCTOU | Tampering | capture window | critical | mitigate | HEAD and file identity are rechecked before exclusive durable output. |
| T53Q-LEAK | Information Disclosure | baseline | high | mitigate | Closed metadata-only schema and no payload/diff/stdout/stderr serialization. |
| T53Q-CHAIN | Repudiation | source/summary | high | mitigate | Exact three-path source, direct summary-only child and captured-head parent proof. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Trustworthy current execution source | 05D2Q | COVERED | Full reusable baseline gate protects preserved dirt. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Preserve pending implementation inputs | 05D2Q | COVERED | All seven downstream paths are exact. |
| RESEARCH | Immutable source and serialized writer | 05D2Q | COVERED | Create-only artifact and exact Git chain. |
| CONTEXT | D-17, D-21 | Current source and carry-forward | 05D2Q | COVERED | Complete field recomputation replaces partial checks. |
| CONTEXT | Deferred Ideas | Client rollout/migration/standby | excluded | EXCLUDED | No deferred scope. |

No source item is missing.

<verification>
- Dedicated hermetic tests cover every positive/negative blocker field.
- Literal exact/ancestor commands prove the sealed pair and unchanged dirt.
</verification>

<success_criteria>
1. Q owns exactly four paths.
2. Every baseline field is independently recomputed with TOCTOU and schema defenses.
3. The only sequence is H capture/exact → one-parent S with the literal three-path diff → one-parent C with the literal summary-only diff; ancestor remains valid from descendants.
4. No captured path changes.
</success_criteria>

<output>Create the exact Q source/summary pair and stop for 53-05D2R.</output>
