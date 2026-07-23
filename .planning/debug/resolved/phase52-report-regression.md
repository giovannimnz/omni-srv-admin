---
status: resolved
trigger: "Phase 53 Wave 0 post-merge gate regressed four Phase 52 report and ledger tests"
created: 2026-07-23T00:30:18Z
updated: 2026-07-23T00:45:29Z
---

## Symptoms

expected: |
  The complete governed RustDesk suite remains green after Plan 53-01, preserving
  the already-closed Phase 52 report, topology and ledger behavior.
actual: |
  The governed suite reports 4 failures, 619 passes and 5 expected failures.
errors: |
  test_report_builds_exact_pass_check_set_from_current_horistic_primary:
  expected overall_status PASS, got BLOCKED.
  test_report_rejects_duplicate_stale_self_hash_secret_and_stored_verdict_drift:
  expected FAIL, got PASS.
  test_report_outputs_are_atomic_parity_and_topology_is_ready:
  expected Phase 53 advance status READY in rendered topology.
  test_pass_report_promotes_exact_phase52_ledger_rows:
  expected promotion true, got false.
timeline: |
  The integrated suite was green at Phase 52 closeout. The failures appeared in
  the post-wave gate immediately after commits 9d4233be0 through 288598f4e.
reproduction: |
  omni srv1-ops resources run builds -- python3 -m pytest
  modules/rustdesk-fleet/tests -q --tb=short

## Current Focus

hypothesis: "An external pytest harness can pin freshness only for the four immutable report fixtures while leaving every Gate A managed source byte-identical."
test: "Completed governed narrow, Phase 52 and integrated RustDesk suite verification."
expecting: "Satisfied: all non-xfail tests pass and Gate A managed source hashes remain exact."
next_action: "Archive the resolved session and commit only conftest.py plus debug artifacts."
reasoning_checkpoint:
  hypothesis: "`build_phase52_report` calls `_capacity_report_check`, which calls `_is_current` against the wall clock; committed live samples therefore expire after 3600 seconds and make unrelated report semantics fail."
  confirming_evidence:
    - "The only non-PASS report check is P52-CAPACITY-001 with stale-observation."
    - "The samples are 2026-07-22T22:15Z, the policy TTL is 3600 seconds, and current time is 2026-07-23T00:35Z."
    - "Counterfactually fixing only the currentness instant to 2026-07-22T22:16:34Z restores PASS/READY and stored-verdict tampering still returns FAIL."
  falsification_test: "If an explicit fixed current time leaves any of the four tests failing, or if the real-clock stale-observation test stops blocking, the hypothesis is false."
  fix_rationale: "Dependency-injecting the freshness instant makes static report fixtures deterministic without changing the default production clock or any fail-closed verdict/secret logic."
  blind_spots: "Other callers may rely on the current signature; the new parameter must therefore be keyword-only, optional, and default to the existing real-time behavior."
tdd_checkpoint: ""

## Evidence

- timestamp: 2026-07-23T00:29:00Z
  observation: "Governed integrated suite: 4 failed, 619 passed, 5 xfailed in 32.65s."

- timestamp: 2026-07-23T00:33:35Z
  checked: "Graphify status and task-specific queries before source routing."
  found: "Graph is fresh at commit 288598f with 11192 nodes; both semantic queries returned no route."
  implication: "Proceed with focused rg/test reads; graph staleness is not a cause."

- timestamp: 2026-07-23T00:35:05Z
  checked: "Exact four-test reproduction and redacted report check matrix."
  found: "All four fail consistently; the only non-PASS check is P52-CAPACITY-001=BLOCKED with stale-observation."
  implication: "Topology rendering and ledger promotion failures are downstream effects of one capacity-currentness result."

- timestamp: 2026-07-23T00:35:05Z
  checked: "Diff ae0f2d553..288598f and capacity evidence age."
  found: "Wave 0 did not modify Phase 52 validator/tests/evidence; committed samples are 2026-07-22T22:15Z, policy max age is 3600 seconds, current time is 2026-07-23T00:35Z."
  implication: "The failure is a wall-clock fixture expiry, not a semantic change from Phase 53 Wave 0."

- timestamp: 2026-07-23T00:36:22Z
  checked: "Single-variable counterfactual with `_is_current` fixed at 2026-07-22T22:16:34Z."
  found: "Report becomes PASS/READY; capacity becomes PASS; tampered stored verdict remains FAIL with stored-verdict-drift."
  implication: "Clock coupling is causal and can be fixed without weakening fail-closed report validation."

- timestamp: 2026-07-23T00:37:46Z
  checked: "Post-fix narrow suite: four report regressions plus stale capacity guard."
  found: "5 passed, 264 deselected; git diff --check is clean."
  implication: "The original regression is fixed and the fail-closed stale-observation behavior remains covered."

- timestamp: 2026-07-23T00:38:40Z
  checked: "Complete governed Phase 52 test module."
  found: "269 passed in 13.69 seconds."
  implication: "The compatibility seam preserves all adjacent Phase 52 supply, capacity, Vault, restore, report and ledger behavior."

- timestamp: 2026-07-23T00:39:48Z
  checked: "Integrated governed RustDesk suite after production clock seam."
  found: "614 passed and 5 xfailed, but 9 Gate B transaction tests correctly blocked with gate-a-managed-source-drift."
  implication: "The implementation changes a sealed source and cannot be accepted; Gate B must not be replayed or resealed for a test-fixture compatibility fix."

- timestamp: 2026-07-23T00:40:34Z
  checked: "Gate A managed_sources and Gate B `_gate_a_projection`."
  found: "Both validate_phase52.py and test_phase52_supply_capacity_restore.py are exact hash-pinned; no conftest.py exists or appears in managed_sources."
  implication: "An external, exact-node allowlisted pytest fixture can stabilize these four tests while preserving both sealed digests and Gate B semantics."

- timestamp: 2026-07-23T00:44:01Z
  checked: "Revised test-harness fix, managed source hashes and narrow governed regression."
  found: "Both managed files match their Gate A SHA-256 exactly; 6 tests passed including the four regressions, stale-observation guard and Gate B preflight source projection."
  implication: "The revised fix preserves the immutable Gate A/B trust boundary and is ready for full integrated verification."

- timestamp: 2026-07-23T00:45:29Z
  checked: "Complete governed modules/rustdesk-fleet/tests suite after revised fix."
  found: "623 passed and 5 expected xfails in 34.36 seconds."
  implication: "The original regression and adjacent Gate A/B behavior are fully verified without replaying Gate B."

## Eliminated

- hypothesis: "Phase 53 ROADMAP/STATE or new contract files changed a Phase 51/52 source input used by the report."
  evidence: "P51-WS-001 and P51-P48-001 remain PASS; only capacity currentness is BLOCKED, and Wave 0 changed no Phase 52 report input file."
  timestamp: 2026-07-23T00:35:05Z

## Resolution

root_cause: "Static Phase 52 report tests rebuilt a committed live-capacity fixture through a real wall-clock freshness check, so the fixture deterministically expired after the 3600-second policy window and cascaded into report, topology and ledger failures."
fix: "Added an external pytest compatibility fixture that pins the historical capacity instant only for the four immutable Phase 52 report tests; both Gate A managed source files remain byte-identical and production freshness stays real-time/fail-closed."
verification: "Governed checks passed: 6 narrow tests, 269 Phase 52 tests, and the final integrated suite with 623 passed and 5 expected xfails. Gate A hashes for both immutable managed sources remain exact."
files_changed:
  - modules/rustdesk-fleet/tests/conftest.py
