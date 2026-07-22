---
phase: 52-supply-chain-capacity-and-recoverable-placement
plan: 03
subsystem: infra
tags: [rustdesk, capacity, ssh, zero-cleanup, serial-fallback]
requires:
  - phase: 52-supply-chain-capacity-and-recoverable-placement
    provides: approved capacity policy, immutable supply evidence, and serial placement contract
provides:
  - bounded read-only capacity probe with pre-construction mutation rejection
  - current persisted NO-GO evidence for atius-srv-2 and atius-srv-3
  - preliminary Horistic capacity eligibility without a placement claim
affects: [52-vault-restore, 52-full-candidate-gate, 53-primary-relay, 54-horistic-canary, 57-dr]
tech-stack:
  added: []
  patterns: [ssh argv allowlist, two-sample integer admission, persisted predecessor NO-GO]
key-files:
  created:
    - modules/rustdesk-fleet/evidence/phase52/capacity-atius-srv-2.json
    - modules/rustdesk-fleet/evidence/phase52/capacity-atius-srv-3.json
    - modules/rustdesk-fleet/evidence/phase52/capacity-horistic-srv.json
    - modules/rustdesk-fleet/evidence/phase52/capacity-summary.json
  modified:
    - modules/rustdesk-fleet/tools/validate_phase52.py
    - modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py
    - modules/rustdesk-fleet/contracts/placement-decision.json
key-decisions:
  - "Only capacity-sample may reach remote SSH command construction during Plan 52-03; every write or remediation class is rejected first."
  - "Atius capacity failure is persisted as current NO-GO and routes forward without cleanup; Horistic remains preliminary until the full gate."
  - "Phase 52 topology review is PASS, while Phase 53, 54, and 57 reviews remain just-in-time gates immediately before their phases."
patterns-established:
  - "Fallback routing consumes persisted predecessor evidence rather than an in-memory or operator-supplied verdict."
  - "Capacity eligibility updates only the capacity stage and cannot select a primary."
requirements-completed: []
coverage:
  - id: D1
    description: The capacity preflight rejects cleanup, mutation, and every bounded full-gate write before constructing remote commands.
    requirement: SRV-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#zero_cleanup and capacity routing tests"
        status: pass
    human_judgment: false
  - id: D2
    description: Current serial evidence proves both Atius candidates NO-GO before Horistic preliminary eligibility, with no selected primary.
    requirement: SRV-01
    verification:
      - kind: integration
        ref: "validate_phase52.py --only capacity-live (expected exit 2 BLOCKED)"
        status: pass
      - kind: unit
        ref: "modules/rustdesk-fleet/tests (188 passed under omni-builds.slice)"
        status: pass
    human_judgment: false
duration: 6min
completed: 2026-07-22
status: complete
---

# Phase 52 Plan 03: Read-Only Capacity Routing Summary

**A fail-closed SSH capacity runner now persists current Atius NO-GO verdicts before routing to preliminary Horistic eligibility, without cleanup, remote writes, or primary selection.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-22T02:41:07Z
- **Completed:** 2026-07-22T02:47:18Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Enforced one remote action class, `capacity-sample`, through `ssh -n`, BatchMode, connection timeout, fixed aliases, and a constant read-only probe; cleanup, remediation, reclamation, pruning, deletion, move, compression, vacuum, glob, symlink, artifact, backup, restore, evidence-write, and rollback-removal actions are rejected before command construction.
- Collected two current raw byte/inode samples per reached candidate in strict order. `atius-srv-2` and `atius-srv-3` are persisted `NO-GO` because they exceed the 78% predeploy and 80% projected-post thresholds; no remediation was attempted.
- Persisted Horistic as `PRELIMINARY_ELIGIBLE` only, with separate future server/client resource domains, no independent-DR claim, just-in-time Phase 53/54/57 review flags, all non-capacity stages pending, and `selected_candidate=null`.

## Task Commits

1. **Task 52-03-01 RED:** `2789aee0b` — failing mutation-boundary and serial-routing tests.
2. **Task 52-03-01 GREEN:** `96e859b21` — read-only SSH builder, sample collector, and chain derivation.
3. **Task 52-03-02:** `c0f69c9d8` — live evidence, placement capacity state, and BLOCKED validator.

## Verification

- `capacity-live` returned expected exit `2`: `P52-CAPACITY-LIVE-001=BLOCKED` because Vault, backups, restore, `capacity_finalize`, rollback, and topology-security remain pending.
- Focused capacity/placement/routing suite: `110 passed` under `omni-builds.slice`.
- Full RustDesk suite: `188 passed` under `omni-builds.slice`.
- `py_compile`, exact JSON assertions, plan-owned `git diff --check`, and secret-term scan passed.
- Every capacity record has two samples, `read_only=true`, `mutation_performed=false`, and a current supply digest.

## Decisions Made

- Remote probe output intentionally reports non-capacity tooling as `not-observed`; this plan does not invoke Podman or a write-capable wrapper remotely. Plan 05 must prove the effective tooling before any bounded full-gate write.
- A later candidate is reachable only after its predecessor's `NO-GO` evidence file has been atomically written locally.
- Capacity PASS on Horistic changes only `capacity_status`; it cannot synthesize Vault, backup, restore, finalize, rollback, or topology-security PASS.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Quoted the constant remote Python probe as one SSH command argument**

- **Found during:** Task 52-03-02 pre-live command review.
- **Issue:** Separate remote argv elements would be joined by OpenSSH and parsed by the remote shell without preserving the multiline script boundary.
- **Fix:** Kept the local command as an array but encoded one constant, shell-quoted `python3 -c` remote command after the fixed alias.
- **Files modified:** `modules/rustdesk-fleet/tools/validate_phase52.py`.
- **Verification:** Six read-only live probes completed; the serial CLI returned the expected BLOCKED verdict and all tests passed.
- **Committed in:** `c0f69c9d8`.

**2. [Rule 2 - Correctness] Kept Phase 52 requirements pending after the routing-only wave**

- **Found during:** Plan closeout.
- **Issue:** SCP-04/SRV-01/SRV-05/SRV-07 require the later Vault, real backup/restore, final capacity, rollback, and report gates.
- **Fix:** `requirements-completed` remains empty and placement remains BLOCKED.
- **Verification:** All six non-capacity stages are PENDING and no selected candidate exists.
- **Committed in:** plan metadata commit.

**Total deviations:** 2 auto-fixed correctness issues. **Impact:** no authority expansion; both changes preserve fail-closed execution and truthful requirement state.

## Issues Encountered

None. All remote aliases accepted the bounded read-only probe and no authentication gate occurred.

## Known Stubs

- `podman_graphroot`, `podman_version`, and in some hosts `resource_wrapper`/`resource_profile` are intentionally `not-observed`. This plan forbids invoking write-capable runtime tooling; Plan 05 must prove these fields before a full-gate write or placement selection.

## User Setup Required

None. No package, artifact, Vault value, backup, restore runtime, service, client, listener, DNS record, or public edge was installed or changed.

## Next Phase Readiness

Ready for `52-04-PLAN.md`: implement the Vault tmpfs/no-output and isolated backup/restore control plane. Placement remains BLOCKED, and Windows installation remains Phase 54.

## Self-Check: PASSED

- All four capacity evidence files exist and agree with strict routing order.
- All three task commits exist.
- Both Atius candidates are current NO-GO, Horistic is preliminary only, and `selected_candidate` remains null.
- No tracked file deletion, remote mutation, secret value, Windows install, or primary/standby claim occurred.

---
*Phase: 52-supply-chain-capacity-and-recoverable-placement*
*Completed: 2026-07-22*
