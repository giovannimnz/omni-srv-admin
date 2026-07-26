---
phase: 53-primary-relay-and-public-edge
plan: 05D2B
subsystem: infra
tags: [rustdesk, transaction-runner, rollback, git-binding, fail-closed]

requires:
  - phase: 53-05D2A
    provides: "Cross-host D-06 edge authority, provider roles and broad green baseline."
provides:
  - "Literal plan/apply runner with exit 0/2/3/4 semantics and zero-side-effect authority failures."
  - "Distinct apply, immutable rollback and restore-production transaction boundaries."
  - "Explicit-path read-only source/live/summary/verification binding checker."
  - "D-16 non-executable Horistic migration handoff enforced across backend/provider layers."
affects: [53-05D2C, 53-05E, 53-05F, 53-06, rustdesk-fleet]

tech-stack:
  added: []
  patterns:
    - "Validate authority and callback completeness before journal/provider construction."
    - "Hash execution source as sorted path-NUL-Git-blob-OID-LF records."
    - "Seal rollback bytes read-only before a separately identified production restore."

key-files:
  created:
    - modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json
    - modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py
  modified:
    - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
    - modules/rustdesk-fleet/tools/phase53-live-backend.py
    - modules/rustdesk-fleet/tools/phase53-live-adapters.py
    - modules/rustdesk-fleet/tools/phase53_production_adapters.py
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py

key-decisions:
  - "Keep the standalone production CLI free of ambient provider discovery; reviewed callbacks enter only through the post-authority factory seam."
  - "Treat apply, rollback and restore-production as terminally distinct identities and files; restore consumes but cannot rewrite the rollback seal."
  - "Read controlling commit identities only from the summary and independent verification descendants, then compare all evidence bindings against them."

patterns-established:
  - "Pre-authority blockers return exit 3 with journal_created=false and provider_constructed=false."
  - "Binding validation reads explicit canonical paths and Git objects only; it has no network, provider or write capability."

requirements-completed: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]

coverage:
  - id: D1
    description: "Literal transaction CLI, full stage order, disjoint journals and immutable rollback seal."
    requirement: SRV-06
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#cli_mode/stage_full/journal/immutable_rollback/restore_production selectors"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-16 handoff keeps 10.31.1.31 non-executable in every Phase 53 backend/provider boundary."
    requirement: SRV-03
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#test_migration_handoff_is_non_executable_and_future_target_is_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Explicit-path checker proves source to evidence-only to summary-only to independent-verification ancestry and Git-object digests."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#binding_chain/evidence_only/summary_only/ancestry/self_hash/dirty_scope selectors"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-26
status: complete
---

# Phase 53 Plan 05D2B: Transaction and Binding Engine Summary

**Fail-closed plan/apply runner with separately sealed rollback/restore journals, D-16 target denial and Git-object-backed independent binding verification**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-26T05:21:00Z
- **Completed:** 2026-07-26T05:35:41Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added the literal `--live-backend phase53-production --mode plan|apply --stage full|edge-probes|ops-api|lifecycle|rollback|restore-production` interface and explicit 0/2/3/4 outcome contract.
- Implemented full ordered hermetic execution with unique apply/rollback/restore IDs, three distinct journals, immutable rollback bytes and containment failures.
- Added a read-only checker that requires all canonical paths explicitly, rederives Git blob/source/manifest digests, validates exact commit diffs and rejects self-hash, stale ancestry, duplicate inputs and dirty source scope.
- Codified the current `10.21.1.21` to future `10.31.1.31` handoff as `executable=false` and rejected the future address across all Phase 53 backend/provider construction paths.

## Task Commits

Each TDD gate was committed atomically:

1. **Task 1 RED: transaction runner adversarial tests** - `f35f4d963` (test)
2. **Task 1 GREEN: sealed transaction runner and D-16 enforcement** - `71bce8390` (feat)
3. **Task 2 RED: binding-chain Git fixture tests** - `da1c91c10` (test)
4. **Task 2 GREEN: explicit-path binding checker** - `e72d60403` (feat)

## Files Created/Modified

- `modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json` - Non-authorizing D-16 current/future handoff.
- `modules/rustdesk-fleet/tools/run-phase53-live-gate.py` - Literal CLI, full transaction sequences, exit matrix and sealed journals.
- `modules/rustdesk-fleet/tools/phase53-live-backend.py` - Capability-disjoint backend target enforcement.
- `modules/rustdesk-fleet/tools/phase53-live-adapters.py` - Production authority target rejection before provider binding.
- `modules/rustdesk-fleet/tools/phase53_production_adapters.py` - Strict current backend target validation.
- `modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py` - Read-only explicit-path Git/evidence ancestry verifier.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` - TDD and adversarial transaction/binding coverage.

## Decisions Made

- The standalone CLI never infers provider callbacks from ambient PATH, SSH configuration, credentials or network state. Hermetic and reviewed deployment embeddings inject the provider factory only after every scalar/source/authority gate passes.
- A successful full run intentionally performs lifecycle, containment rollback and a separate production restore so D-13/D-14 evidence cannot collapse into one mutable transaction identity.
- The binding checker derives live/summary/source commit authority from descendant summary/verification metadata, then verifies evidence fields and exact `git show` bytes rather than trusting stored verdicts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved the existing provider target blocker contract**

- **Found during:** Task 1 compatibility selector
- **Issue:** The first D-16 implementation returned a new blocker string for `10.31.1.31`, breaking the existing strict provider-manifest test.
- **Fix:** Retained `provider-manifest-target-invalid` while still explicitly rejecting the future address in every backend/provider layer.
- **Files modified:** `phase53-live-backend.py`, `phase53-live-adapters.py`, `phase53_production_adapters.py`, `test_phase53_primary_edge.py`
- **Verification:** Compatibility selector passed 20 tests; full Phase 53 test file passed.
- **Committed in:** `71bce8390`

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Compatibility was preserved without weakening D-16 or expanding scope.

## Issues Encountered

- The resource governor reported swap pressure above its warning threshold, while structural containment remained healthy at `CPUQuota=80%`, zero escaped builds and all test commands exited zero.
- Graphify became commit-stale after the scoped commits (`built_at_commit=71bce83`, current `e72d604`). Refresh is deferred to the root serialized writer because Graphify artifacts are already dirty and outside this executor's exact ownership.

## TDD Gate Compliance

- Task 1 RED `f35f4d963` precedes GREEN `71bce8390`.
- Task 2 RED `da1c91c10` precedes GREEN `e72d60403`.
- Both RED selectors failed for the intended missing behavior before implementation.

## Known Stubs

None. The lack of ambient production provider discovery is an intentional security boundary; the reviewed post-authority injection seam is fully exercised hermetically.

## Verification

- Transaction/journal selector: **9 passed, 194 deselected**.
- Binding-chain selector: **3 passed, 203 deselected**.
- Backend/provider compatibility selector: **20 passed, 183 deselected**.
- Complete governed Phase 53 test file: **205 passed, 1 xfailed**.
- Required negative apply CLI: **exit 3**, no journal, no provider construction and no mutation.
- `git diff --check`: **passed**.
- No live host, OCI, Cloudflare, DNS or provider mutation was performed.

## User Setup Required

None.

## Next Phase Readiness

- `53-05D2C` can add the closed execution-source allowlist and seal the source only after its required complete RustDesk suite is green.
- `53-05E`, `53-05F` and every live mutation remain downstream-gated; this summary is not authority, approval or live evidence.

## Self-Check: PASSED

- All eight declared source/test paths and this summary exist.
- RED/GREEN commits `f35f4d963`, `71bce8390`, `da1c91c10` and `e72d60403` exist.
- No declared path is left modified or untracked after the task commits.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-26*
