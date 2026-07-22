---
phase: 52-supply-chain-capacity-and-recoverable-placement
plan: 02
subsystem: infra
tags: [rustdesk, capacity, placement, integer-arithmetic, ssh]
requires:
  - phase: 52-supply-chain-capacity-and-recoverable-placement
    provides: immutable Phase 52 supply pins and current official supply evidence
provides:
  - exact capacity and retention contract bound to accountable approval
  - deterministic serial placement state machine with capacity_finalize
  - current two-sample read-only proposal for all three candidates
affects: [52-capacity-routing, 52-vault-restore, 52-full-candidate-gate, 53-primary-relay]
tech-stack:
  added: []
  patterns: [integer-only admission, recomputed verdicts, approval-source digest, read-only remote sampling]
key-files:
  created:
    - modules/rustdesk-fleet/contracts/capacity-policy.json
    - modules/rustdesk-fleet/contracts/placement-decision.json
    - modules/rustdesk-fleet/tests/fixtures/invalid/phase52-capacity-placement-mutations.json
    - modules/rustdesk-fleet/evidence/phase52/capacity-proposal.json
  modified:
    - modules/rustdesk-fleet/tools/validate_phase52.py
    - modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py
    - .planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-OPERATIONAL-DECISIONS.md
key-decisions:
  - "All byte and inode gates use checked raw integer arithmetic; rounded or float evidence is rejected."
  - "Both Atius candidates remain current capacity NO-GO with zero cleanup; Horistic is only FULL-GATE-PENDING."
  - "A proposal can remain honestly BLOCKED after approval is complete because no full candidate gate ran."
patterns-established:
  - "Capacity policy and live observations are separate, with approval and input digests binding them."
  - "Placement selection is recomputed from the ordered eight-stage vector and cannot trust stored candidate fields."
requirements-completed: []
coverage:
  - id: D1
    description: Exact 78/80 byte and inode admission, named reservations, and capacity_finalize reconciliation are fail-closed.
    requirement: SRV-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#capacity and placement matrix (55 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: The ordered placement contract rejects bypass, partial vectors, stored-verdict drift, Windows evidence, and Horistic domain conflation.
    requirement: SRV-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#placement tests"
        status: pass
    human_judgment: false
  - id: D3
    description: Two current bounded read-only samples per candidate are bound to Giovanni Muniz's exact approval without host mutation.
    requirement: SRV-01
    verification:
      - kind: integration
        ref: "python3 modules/rustdesk-fleet/tools/validate_phase52.py --repo . --only capacity-proposal --evidence-dir modules/rustdesk-fleet/evidence/phase52 (expected exit 2 BLOCKED)"
        status: pass
    human_judgment: false
duration: 14min
completed: 2026-07-22
status: complete
---

# Phase 52 Plan 02: Capacity and Placement Contracts Summary

**Exact integer admission, accountable zero-cleanup policy, serial fallback semantics, and a current read-only three-candidate proposal now block safely until the full candidate gate runs.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-22T02:19:41Z
- **Completed:** 2026-07-22T02:34:02Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Materialized D-04/D-05/D-06 exactly: 128 MiB/day for 30 days, 4 GiB state, two independent 4 GiB backups, A local, B managed GDrive, retention through Phase 57 PASS plus 30 days, deletion only after new approval, and no cleanup authority.
- Implemented checked integer admission and `capacity_finalize`, including actual A/B bounds, materialized-reservation reconciliation, retained log/state/image terms, currentness, same mount, inodes, and final 80% inequality.
- Sampled every candidate twice through bounded `ssh -n` read-only probes. `atius-srv-2` and `atius-srv-3` remain capacity `NO-GO`; Horistic passes only preliminary capacity and remains `FULL-GATE-PENDING` with no selected primary.

## Task Commits

1. **Task 52-02-01 RED:** `30f39ed62` — failing capacity, finalize, placement, co-location, and negative-mutation tests.
2. **Task 52-02-01 GREEN:** `1911f39f1` — exact capacity/placement contracts and fail-closed validator logic.
3. **Task 52-02-02:** `6dee15b2a` — approval-bound current read-only proposal and proposal validator.

## Verification

- Focused capacity/approval/placement suite: `55 passed` under `omni-builds.slice`.
- Full RustDesk suite: `133 passed` under `omni-builds.slice`.
- Capacity proposal CLI: expected exit `2`, `P52-CAPACITY-001=BLOCKED`, because the full candidate gate has not run.
- `py_compile` and plan-owned `git diff --check` passed.
- Graphify is fresh at `6dee15b`: `stale=false`, `commit_stale=false`.
- `mutation_performed=false`, `selected_candidate=null`, `windows_install_performed=false`, and no secret material was recorded.

## Decisions Made

- Filesystem reserved blocks are legitimate: raw `used` and `available` counters may sum to less than `total`, but neither may exceed `total`.
- A candidate with both preliminary samples passing capacity remains `FULL-GATE-PENDING`; capacity alone cannot become placement PASS.
- Missing local wrapper/Podman observations are recorded as `not-observed`, not inferred. The later full gate must prove them before Horistic can be selected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Accepted filesystem-reserved blocks without weakening raw counter checks**

- **Found during:** Task 52-02-02 live sampling.
- **Issue:** `statvfs` correctly reports reserved filesystem blocks, so `used_bytes + available_bytes` can be less than `total_bytes`.
- **Fix:** Require each raw counter to be bounded by total instead of requiring false equality.
- **Files modified:** `modules/rustdesk-fleet/tools/validate_phase52.py`, test file.
- **Verification:** `test_capacity_accepts_reserved_filesystem_blocks` and full suite pass.
- **Committed in:** `6dee15b2a`.

**2. [Rule 2 - Correctness] Avoided premature Phase 52 requirement closure**

- **Found during:** Plan closeout.
- **Issue:** This contract/proposal wave contributes to SCP-04/SRV-01/SRV-05/SRV-07 but does not complete the live Vault/restore/full-candidate advance gate.
- **Fix:** `requirements-completed` remains empty; Phase 52 requirements stay pending until Plans 03-06 prove them live.
- **Verification:** Proposal remains `BLOCKED`, no selected candidate exists, and the roadmap gate is unchanged.
- **Committed in:** plan metadata commit.

**Total deviations:** 2 auto-fixed correctness issues. **Impact:** both changes strengthen truthful fail-closed behavior without expanding operational authority.

## Issues Encountered

- The first encoded remote probe command had incorrect shell quoting and failed before execution. It was corrected to one quoted remote command; all six actual probes then succeeded read-only.
- One full-suite attempt was refused before test execution because the governor transiently observed one escaped hot process. A fresh doctor check returned `structural_ok=true`; the governed retry passed 133/133. No guardrail was bypassed.

## Known Stubs

- `capacity-proposal.json` records `not-observed` for the `omni` wrapper on `atius-srv-3`/Horistic and for Podman on Horistic. These are deliberate fail-closed observations, not defaults; Plans 03/05 must prove the effective tooling before any full-gate write or selection.

## User Setup Required

None. No package, image, server, client, listener, Vault value, backup, restore runtime, or public edge was installed or created.

## Next Phase Readiness

Ready for `52-03-PLAN.md`: persist the ordered current capacity routing evidence with zero cleanup. Current placement remains BLOCKED and Windows installation remains Phase 54.

## Self-Check: PASSED

- All seven plan-owned artifacts exist.
- All three task commits exist.
- Focused and full suites passed under the governed builds profile.
- Proposal is current, approval-bound, secret-free, mutation-free, and honestly BLOCKED.

---
*Phase: 52-supply-chain-capacity-and-recoverable-placement*
*Completed: 2026-07-22*
