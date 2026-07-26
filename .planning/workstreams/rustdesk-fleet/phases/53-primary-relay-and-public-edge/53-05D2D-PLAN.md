---
phase: 53-primary-relay-and-public-edge
plan: 05D2D
type: execute
wave: 12
depends_on: [53-05D2C]
gap_closure: true
execution_owner: 53-05D2D
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
  - modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  - modules/rustdesk-fleet/tools/phase53-live-backend.py
  - modules/rustdesk-fleet/tools/build-phase53-authority-plan.py
  - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  - modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "05D2C remains an immutable historical predecessor; 05D2D creates the only current execution-source seal after closing the authority-plan producer gap."
    - "The execution-source allowlist contains exactly 34 paths, adding only build-phase53-authority-plan.py to the prior 33-path runtime/test aggregate; the already-allowlisted validate_phase53_live_evidence.py is upgraded and included in the seven-path seal commit."
    - "A named collector produces one explicit, schema-checked read-only observation outside the repo; missing, stale, synthetic or write-capable input blocks without producing current artifacts."
    - "Mapping and MappingProxyType values canonicalize recursively and deterministically; bytes, secrets, stored verdicts and unsupported objects are rejected."
    - "The producer validates the frozen Phase 52 attestation/contract/two reviews/closeout by Git objects and creates a non-authorizing Phase 53 successor without rewriting any Phase 52 byte."
    - "Exactly six ordered capacity samples are required: srv2 twice, srv3 twice, Horistic twice; srv2/srv3 remain NO-GO with zero cleanup and Horistic must be current/finalized."
    - "A stale OperationPlan is never an input. Five dependent artifacts are promoted from a validated staging set, then the OperationPlan is written last as the sole commit marker binding their digests; consumers reject every partial generation."
    - "Successful plan mode exits zero at AWAITING_OWNER_HASH_APPROVAL with no owner record, journal, RuntimeProvider, ApplyProviderBundle, provider write or live mutation."
    - "The exact seven source paths are committed as the new execution_source_commit; its direct descendant changes only 53-05D2D-SUMMARY.md."
  artifacts:
    - path: modules/rustdesk-fleet/tools/build-phase53-authority-plan.py
      provides: "Pure authority-artifact producer over explicit read-only observations and frozen Git-object inputs."
    - path: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      provides: "Closed 34-path current source manifest containing the authority producer and strict live-evidence validator."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
      provides: "Summary-only descendant recording the superseding source commit/tree and governed gates."
  key_links:
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/build-phase53-authority-plan.py
      via: "mode plan passes only the capability-disjoint read-only bundle and explicit observation"
      pattern: "AWAITING_OWNER_HASH_APPROVAL|build_phase53_authority_plan"
    - from: modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
      to: modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
      via: "sorted 34-path Git-object aggregate and exact seven-path seal commit"
      pattern: "execution_source"
  prohibitions:
    - "Do not read the existing OperationPlan/candidate/capacity files as inputs, infer current observations, or downgrade missing readback to synthetic metadata."
    - "Do not call Phase 52 writers/reseal tools, regenerate Gate A/Gate B/integrated reports, or modify any Phase 52 path."
    - "Do not create an owner approval, apply/rollback/restore journal, provider write or host/OCI/Cloudflare/DNS/Vault mutation."
    - "Do not stage broadly; only the seven declared source files and then the summary-only descendant may be committed."
---

<objective>
Close the missing Phase 53 authority-plan implementation, prove it fail-closed with explicit read-only observations, and supersede the incomplete 05D2C runtime seal before 05E creates any authority evidence.

Purpose: prevent a serialization-only patch or synthetic preview from being mistaken for current authority.
Output: a tested six-artifact producer, strict validator and a new 34-path source seal; no authority evidence or live mutation.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-PLAN.md
@modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
@modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json
@modules/rustdesk-fleet/contracts/phase52-post-live-successor.json
@modules/rustdesk-fleet/tools/phase53-live-backend.py
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
@modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2D-01: Specify the explicit read-only authority producer in RED</name>
  <files>modules/rustdesk-fleet/tools/build-phase53-authority-plan.py, modules/rustdesk-fleet/tools/phase53-live-backend.py, modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <behavior>
    - "Canonicalization accepts MappingProxyType recursively and produces stable canonical bytes."
    - "The read-only backend has exactly read/preview capabilities and no apply, mutate, contain, rollback or restore callback."
    - "The producer requires an explicit observation carrying fresh topology, supply, six capacity samples, Vault public fingerprint metadata and typed provider prestates/previews."
    - "The Phase 52 successor binds frozen Git objects, both distinct PASS reviews and metadata-only closeout while authorizing no replay/rebaseline/provider/Vault write."
    - "The OperationPlan path is output-only; changing stale destination bytes never changes the new canonical plan."
    - "All six outputs cross-bind execution source commit/tree, successor digest and plan digest, or no output set is promoted."
    - "The strict validator consumes the new authority set plus all seven 05F manifests, accepts immutable source ancestry with exact 34-blob equality, and rejects stale 05B-only evidence or source_head==HEAD coupling."
    - "The sealed builder/runner accepts explicit 05D2H summary and quarantine-pointer paths, validates their commit/digest/generation/exact-absence chain without following symlinks, and binds that receipt into preflight and OperationPlan."
    - "Explicit tests cover owner response/hash/expiry/no-auto-apply and every 05F new-process/full-sequence/lifecycle/rollback/restore/exclusion gate by exact nodeid."
    - "An exact housekeeping-receipt nodeid rejects missing/tampered/conflicting/dangling/escaped receipts and false absence before authority generation."
  </behavior>
  <action>
Add the exact authority, approval and 05F nodeids before implementation. Use temporary fixture repositories and injected observation/bundle callbacks; no test may contact a host/provider. Prove the current code is RED for the mappingproxy crash, missing producer, HEAD-plus-six-contract pseudo-binding, zero-artifact output and empty selector. The approval tests require explicit response/current hash/future expiry/no auto-apply. The 05F tests prove new-process revalidation before journal, one full sequence, lifecycle/two-origin binding, immutable rollback plus distinct restore and all zero-cleanup/migration exclusions. Implement no fallback fixture in production code. This task records the RED output but does not commit; Task 03 creates the sole source commit after GREEN and broad gates.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_successor_attestation_binds_frozen_phase52 modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_descendant_source_binding_rejects_drift modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_read_only_backend_has_no_write_capability modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_operation_plan_writes_exact_six_artifacts_and_rejects_public_vnic_backend_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_capacity_current_requires_six_ordered_samples modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_strict_validator_accepts_authority_and_live_set_with_immutable_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_housekeeping_receipt_is_explicit_current_and_symlink_safe --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_requires_explicit_response modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_hash_and_expiry_are_current modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_no_auto_apply_after_owner_record --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_new_process_revalidates_authority_before_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_full_sequence_is_single_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_lifecycle_and_two_origin_probes_are_bound modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_immutable_rollback_and_distinct_restore_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_zero_cleanup_migration_and_stale_output_prestate_remain_untouched --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
  </verify>
  <done>All sixteen exact nodeids exist—eight authority, three owner-approval and five 05F—and each RED group fails for intended missing behavior rather than rc5/no-tests.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2D-02: Implement and adversarially verify the authority producer</name>
  <files>modules/rustdesk-fleet/tools/build-phase53-authority-plan.py, modules/rustdesk-fleet/tools/phase53-live-backend.py, modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>
Implement a recursive canonical projection for Mapping/MappingProxyType and sequences, rejecting unsupported types, secrets and stored verdicts. Extend ReadOnlyProviderBundle only with explicit read/preview callbacks; retain the capability set exactly `{"read","preview"}` and prove absence of all write interfaces.

Implement `build-phase53-authority-plan.py` with three capability-disjoint subcommands. `collect-observation` invokes only the audited ReadOnlyProviderBundle callbacks, writes one schema-checked observation beneath an explicit `/tmp` path and proves zero write interfaces/calls. `build-plan` receives that explicit observation from the runner, checks TTL/schema/order/currentness and never discovers ambient credentials/routes. `record-owner` consumes only a structured response file plus the current OperationPlan, revalidates owner/decision/hash/expiry/risk acknowledgement, and writes only `edge-forwarder-owner-approval.json`; it cannot construct apply/runtime providers.

The producer validates the execution source through the public binding checker, requiring 05D2D source commit/tree ancestry and exact allowlisted blob equality. It reads the frozen successor/contract/review-1/review-2 Git objects at `e552c876f32cc87bb0d97b71308056f30423c452`, requires direct parent `6bb2e0abad5cad3eb1ff750bcb92130c06ee0f6c`, reads the metadata-only closeout Git object at `11fa627fdd27c7032f0029cd594bc2e1241e20bb`, and proves ancestry `6bb2e0a → e552c87 → 11fa627 → current`. It validates the six source paths declared by the successor against `source_freeze_commit=6bb2e0a` and every closeout input digest. Current-worktree or untracked narrative bytes cannot influence the successor digest and are never a reason to rewrite/reseal Phase 52.

`build-plan` creates exactly `topology-discovery.json`, `phase52-successor-attestation.json`, `candidate-admission.json`, `capacity-current.json`, `preflight.json` and `edge-forwarder-operation-plan.json`. It builds the non-authorizing successor, candidate admission/preflight state, six-sample capacity-current record and fresh canonical OperationPlan from current topology/prestate/previews. The existing destination OperationPlan and old confirmation/approval hashes are never opened.

Prepare all six authority payloads in a private temporary directory and validate exact names/schemas/cross-digests/value-free flags. Promote the five dependent artifacts first and write `edge-forwarder-operation-plan.json` last as the only commit marker; it contains the exact generation ID and digests of the five dependencies. Consumers accept a generation only when the marker and all five files match. Inject a failure after every promotion boundary and prove that no partial set is accepted as current. While awaiting, require owner approval absent and emit rc0 `AWAITING_OWNER_HASH_APPROVAL`; on missing/stale/drifted observation, emit BLOCKED and leave the marker absent/stale. Never import/call apply backend or construct RuntimeProvider/ProviderBundle/journals. Keep the GREEN implementation uncommitted through this task; Task 03 owns the sole exact seven-path source commit.

Upgrade `validate_phase53_live_evidence.py` in the same sealed source. Its strict input set is the six authority artifacts, owner approval and the seven 05F manifests; it validates OperationPlan/owner/source/tree/transaction/lifecycle/rollback/restore/metrics cross-bindings, uses immutable source ancestry plus exact 34-blob equality instead of `source_head == current HEAD`, and rejects the obsolete 05B-only compatibility/parity/server-evaluation set as executable proof. It remains read-only and value-free.

Implement a reusable symlink-safe `validate_housekeeping_receipt(...)` in the sealed builder/runner path. It takes explicit `53-05D2H-SUMMARY.md` and `/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json` paths; proves the summary commit is a descendant of the 05D2D summary and changed only that summary; uses `lstat`/`lexists`; confines pointer, generation directory, manifest and unique backup rows beneath the fixed quarantine root; requires regular non-symlink files, current uid, modes 0700/0600, exact generation/digests, complete state, unique exact moved/source sets and all seven canonical paths lexically absent. It rejects missing/tampered/conflicting/dangling/escaped receipts. `build-plan` requires this receipt and binds `05D2H_summary_commit`, `quarantine_manifest_sha256`, generation ID and canonical-seven absent digest into both `preflight.json` and the last-written OperationPlan. No H receipt may be inferred from ambient files or orchestrator memory.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_successor_attestation_binds_frozen_phase52 modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_descendant_source_binding_rejects_drift modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_read_only_backend_has_no_write_capability modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_operation_plan_writes_exact_six_artifacts_and_rejects_public_vnic_backend_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_capacity_current_requires_six_ordered_samples modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_strict_validator_accepts_authority_and_live_set_with_immutable_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_housekeeping_receipt_is_explicit_current_and_symlink_safe --disable-warnings</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_requires_explicit_response modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_hash_and_expiry_are_current modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_no_auto_apply_after_owner_record --disable-warnings</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_new_process_revalidates_authority_before_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_full_sequence_is_single_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_lifecycle_and_two_origin_probes_are_bound modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_immutable_rollback_and_distinct_restore_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_zero_cleanup_migration_and_stale_output_prestate_remain_untouched --disable-warnings</automated>
  </verify>
  <done>Eight authority, three owner-approval and five 05F exact tests pass; adversarial variants cannot synthesize authority, accept stale 05B evidence/housekeeping receipts or invoke a write capability.</done>
</task>

<task type="auto">
  <name>Task 53-05D2D-03: Seal the 34-path source after governed current and legacy lanes</name>
  <files>modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json, modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py, modules/rustdesk-fleet/tools/phase53-live-backend.py, modules/rustdesk-fleet/tools/build-phase53-authority-plan.py, modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md</files>
  <action>
Add only `build-phase53-authority-plan.py` to the prior sorted source allowlist, making exactly 34 paths; keep the upgraded `validate_phase53_live_evidence.py` in its existing allowlisted slot and include it in the exact seven source files owned by this plan. Version the checker’s seal-path contract to those seven files. Run all sixteen exact nodeids as three closed groups—eight authority, three owner-approval and five 05F—then the governed current broad lane with only the canonical nine Phase 52 Gate-B nodeids deselected; require rc0, zero failures/errors, exactly nine deselections and exactly the existing single validate_phase53.py owner xfail. Run the exact-nine legacy lane into `/tmp`, require rc1 and classify exactly eight managed-source drift refusals plus one local-only/no-network CLI refusal. Do not invoke the frozen Phase 52 current-lane helper or regenerate Phase 52 evidence.

Stage with literal pathspecs and commit exactly the seven source files. Compute the 34-path Git-object aggregate at that commit. Create `53-05D2D-SUMMARY.md` in a direct summary-only descendant containing the source commit/tree, predecessor 05D2C commit/tree, exact gate results and zero-authority/live flags. Prove exact seven-path/source and one-path/summary diffs, direct parentage, predecessor ancestry, equal SOURCE/HEAD 34-path bindings and clean source at HEAD. Any source change repeats the seal.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_successor_attestation_binds_frozen_phase52 modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_descendant_source_binding_rejects_drift modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_read_only_backend_has_no_write_capability modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_operation_plan_writes_exact_six_artifacts_and_rejects_public_vnic_backend_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_capacity_current_requires_six_ordered_samples modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_strict_validator_accepts_authority_and_live_set_with_immutable_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_housekeeping_receipt_is_explicit_current_and_symlink_safe --disable-warnings</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_requires_explicit_response modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_hash_and_expiry_are_current modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_no_auto_apply_after_owner_record --disable-warnings</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_new_process_revalidates_authority_before_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_full_sequence_is_single_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_lifecycle_and_two_origin_probes_are_bound modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_immutable_rollback_and_distinct_restore_transaction modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05f_zero_cleanup_migration_and_stale_output_prestate_remain_untouched --disable-warnings</automated>
    <automated>bash -euo pipefail -c 'TMP_DIR=$(mktemp -d /tmp/rustdesk-05d2d-current.XXXXXX); trap "rm -rf -- \"$TMP_DIR\"" EXIT; set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests --disable-warnings --junitxml="$TMP_DIR/current.xml" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_preflight_candidate_binds_gate_a_and_managed_sources" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_two_distinct_pass_reviews_on_exact_hash_set" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;0]" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;1]" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;2]" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;3]" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_rejects_stale_source_and_execute_live_never_reaches_network" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_cli_without_explicit_execute_live_is_local_only" --deselect "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_remote_bootstrap_recomputes_canonical_hash_and_private_digest_ephemerally" | tee "$TMP_DIR/current.out"; CURRENT_RC=${PIPESTATUS[0]}; set -e; test "$CURRENT_RC" -eq 0; env CURRENT_XML="$TMP_DIR/current.xml" CURRENT_OUT="$TMP_DIR/current.out" python3 -c "import os,re,xml.etree.ElementTree as ET; from pathlib import Path; rows=list(ET.parse(os.environ[\"CURRENT_XML\"]).getroot().iter(\"testcase\")); assert sum(row.find(\"failure\") is not None for row in rows)==0; assert sum(row.find(\"error\") is not None for row in rows)==0; skipped=[row for row in rows if row.find(\"skipped\") is not None]; assert len(skipped)==1; marker=skipped[0].find(\"skipped\"); assert marker.get(\"type\")==\"pytest.xfail\"; nodeid=skipped[0].get(\"classname\",\"\")+\"::\"+skipped[0].get(\"name\",\"\"); assert nodeid==\"modules.rustdesk-fleet.tests.test_phase53_primary_edge::test_future_implementation_symbol_is_red_only_for_owner_plan[tools/validate_phase53.py-53-06]\"; counts=[int(value) for value in re.findall(r\"([0-9]+) deselected\",Path(os.environ[\"CURRENT_OUT\"]).read_text(encoding=\"utf-8\"))]; assert counts==[9], counts"'</automated>
    <automated>bash -euo pipefail -c 'TMP_DIR=$(mktemp -d /tmp/rustdesk-05d2d-legacy.XXXXXX); trap "rm -rf -- \"$TMP_DIR\"" EXIT; set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q --disable-warnings --junitxml="$TMP_DIR/legacy.xml" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_preflight_candidate_binds_gate_a_and_managed_sources" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_two_distinct_pass_reviews_on_exact_hash_set" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;0]" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;1]" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;2]" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_requires_exact_offline_check_schema_and_counts[&lt;lambda&gt;3]" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_finalize_rejects_stale_source_and_execute_live_never_reaches_network" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_cli_without_explicit_execute_live_is_local_only" "modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py::test_remote_bootstrap_recomputes_canonical_hash_and_private_digest_ephemerally"; LEGACY_RC=$?; set -e; test "$LEGACY_RC" -eq 1; env LEGACY_XML="$TMP_DIR/legacy.xml" python3 -c "import importlib.util,os; from pathlib import Path; tool=Path(\"modules/rustdesk-fleet/tools/phase52-post-live-lanes.py\").resolve(); spec=importlib.util.spec_from_file_location(\"phase52_post_live_lanes\",tool); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); verdict=module.lane_legacy(Path(os.environ[\"LEGACY_XML\"])); assert verdict[\"test_count\"]==verdict[\"failure_count\"]==9; assert verdict[\"error_count\"]==verdict[\"skip_count\"]==0; assert verdict[\"gate_a_managed_source_drift_count\"]==8; assert verdict[\"cli_local_only_case_count\"]==1 and verdict[\"network_attempted\"] is False"'</automated>
    <automated>bash -euo pipefail -c 'SOURCE_COMMIT=$(git rev-parse HEAD^); SUMMARY_COMMIT=$(git rev-parse HEAD); test "$(git rev-parse "${SUMMARY_COMMIT}^")" = "$SOURCE_COMMIT"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE_COMMIT" | LC_ALL=C sort)" = "$(printf "%s\n" modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json modules/rustdesk-fleet/tests/test_phase53_primary_edge.py modules/rustdesk-fleet/tools/build-phase53-authority-plan.py modules/rustdesk-fleet/tools/phase53-live-backend.py modules/rustdesk-fleet/tools/run-phase53-live-gate.py modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py | LC_ALL=C sort)"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SUMMARY_COMMIT")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md"; PREDECESSOR_COMMIT=$(git log -n1 --format=%H -- .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md); PLAN_COMMIT=$(git log -n1 --format=%H -- .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-PLAN.md); test -n "$PREDECESSOR_COMMIT"; test -n "$PLAN_COMMIT"; git merge-base --is-ancestor "$PREDECESSOR_COMMIT" "$SOURCE_COMMIT"; git merge-base --is-ancestor "$PLAN_COMMIT" "$SOURCE_COMMIT"'</automated>
    <automated>env SOURCE_COMMIT="$(git rev-parse HEAD^)" SUMMARY_COMMIT="$(git rev-parse HEAD)" python3 -c 'import importlib.util,json,os; from pathlib import Path; repo=Path(".").resolve(); checker=repo/"modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py"; spec=importlib.util.spec_from_file_location("phase53_binding_checker",checker); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); payload=json.loads((repo/"modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json").read_text()); paths=module.validate_execution_source_scope_payload(payload); assert len(paths)==34; source=os.environ["SOURCE_COMMIT"]; summary=os.environ["SUMMARY_COMMIT"]; source_binding=module.compute_execution_source_binding(repo=repo,execution_source_commit=source,manifest_paths=paths); head_binding=module.compute_execution_source_binding(repo=repo,execution_source_commit=summary,manifest_paths=paths); assert source_binding["execution_source_tree_sha256"]==head_binding["execution_source_tree_sha256"] and source_binding["blobs"]==head_binding["blobs"] and source_binding["manifest_paths"]==head_binding["manifest_paths"]==paths; module.require_clean_execution_source(repo=repo,execution_source_commit=source,manifest_paths=paths,expected_tree=source_binding["execution_source_tree_sha256"])'</automated>
    <automated>bash -euo pipefail -c 'test "$(jq ".paths|length" modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json)" = 34; git diff --check'</automated>
  </verify>
  <done>A new exact seven-path source commit and summary-only descendant supersede 05D2C for all 05E/05F authority checks.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Severity | Mitigation |
|---|---|---|---|
| T53D2D-SYNTH | Spoofing | critical | Explicit current observation is mandatory; no ambient or synthetic production fallback. |
| T53D2D-SOURCE | Tampering | critical | New 34-path Git-object seal, ancestry, exact blobs and clean-scope checks. |
| T53D2D-REPLAY | Tampering/Repudiation | critical | Stale plan is output-only forbidden input; Phase 52 is verified at the frozen Git commit. |
| T53D2D-CAP | Elevation of Privilege | critical | Capability-disjoint read-only bundle and tests that fail if any write callback exists/runs. |
| T53D2D-PARTIAL | Integrity | high | Five dependencies promote from validated staging; OperationPlan is the last-written commit marker and consumers reject incomplete generations. |
| T53D2D-SECRET | Information Disclosure | high | Recursive secret/verdict scan and value-free evidence schemas. |
</threat_model>

<success_criteria>
1. Sixteen explicit nodeids pass in three closed groups: eight authority, three owner-approval and five 05F; no group can collapse to rc5.
2. MappingProxyType serialization is deterministic and safe.
3. Missing/stale readback blocks without current artifact promotion.
4. Phase 52 remains byte-frozen and non-authorizing.
5. Current source is resealed over exactly 34 paths in an exact seven-path commit.
6. No authority, owner record, journal, provider write or live mutation occurs.
</success_criteria>

<output>Create `53-05D2D-SUMMARY.md` in a direct summary-only descendant and stop. 05E runs in a new process.</output>
