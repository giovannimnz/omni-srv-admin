---
phase: 52-supply-chain-capacity-and-recoverable-placement
plan: 04
subsystem: security-recovery-control-plane
tags: [vault, tmpfs, sqlite, backup, restore, rollback, rustdesk]
requires:
  - phase: 52-03
    provides: current serial capacity routing and zero-cleanup candidate evidence
provides:
  - exact-reference Vault hydration with tmpfs and no-output guarantees
  - independently generated state-only backups and fresh isolated restore primitives
  - reusable fail-closed full-candidate stage runner with persisted NO-GO
affects: [52-05, 52-06, phase-53, phase-57]
tech-stack:
  added: []
  patterns: [dedicated-safe-fd, ephemeral-hmac, state-only-tar, verify-before-delete]
key-files:
  created:
    - modules/rustdesk-fleet/tools/rustdesk-vault-hydrate
    - modules/rustdesk-fleet/tests/fixtures/invalid/phase52-vault-restore-mutations.json
  modified:
    - modules/rustdesk-fleet/tools/validate_phase52.py
    - modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py
key-decisions:
  - "Vault providers receive only approved path/field references over stdin; secret values never enter argv or evidence."
  - "Backup archives contain only db_v2.sqlite3; identity is rehydrated from Vault and verified by public fingerprint."
  - "Rollback removes only marked disposable restore targets after restore, listener, service-active and service-enabled checks pass."
patterns-established:
  - "Secret results leave the helper only through a dedicated descriptor and contain aggregate metadata or a public fingerprint."
  - "Candidate gates persist a complete NO-GO stage vector before fallback and always retain verified backups on failure."
requirements-completed: []
coverage:
  - id: D1
    description: "Exact approved Vault references hydrate server identity on confirmed tmpfs without secret-bearing output."
    requirement: SRV-05
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#vault helper tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two state-only backups restore a valid SQLite database into a fresh isolated target while preserving identity proof."
    requirement: SRV-07
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#backup restore state machine tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Rollback and candidate fallback remain fail-closed across archive, SQLite, fingerprint, network and cleanup failures."
    requirement: SRV-07
    verification:
      - kind: unit
        ref: "python3 -m pytest modules/rustdesk-fleet/tests -q (199 passed)"
        status: pass
    human_judgment: false
duration: 13min
completed: 2026-07-22
status: complete
---

# Phase 52 Plan 04: Vault and Isolated Recovery Control Plane Summary

**No-output Vault hydration plus independently verified state-only backups, fresh SQLite restore and fail-closed disposable rollback are ready for the live candidate loop.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-22T02:53:43Z
- **Completed:** 2026-07-22T03:06:13Z
- **Tasks:** 2
- **Files modified:** 4 implementation/test artifacts

## Accomplishments

- Enforced the exact six approved Vault paths and seven path/field references, with `0700` tmpfs runtime, `0600` files, fresh in-memory HMAC distinctness and aggregate-only safe output.
- Implemented quiesced source validation, two separately created state-only archives, archive allowlist/mode/hash verification and fresh isolated SQLite restore.
- Added fingerprint, no-public-listener, stopped/disabled and marker-bound cleanup gates plus a reusable full candidate stage runner that persists NO-GO before fallback.

## Task Commits

1. **Task 52-04-01 RED: Vault hydration contract tests** — `ef22cf046`
2. **Task 52-04-01 GREEN: no-output Vault hydration** — `7821c66f9`
3. **Task 52-04-02 RED: recovery state machine tests** — `17dae67e0`
4. **Task 52-04-02 GREEN: isolated recovery state machine** — `df5c328d0`

## Files Created/Modified

- `modules/rustdesk-fleet/tools/rustdesk-vault-hydrate` — stdin-safe shell entrypoint with xtrace disabled, restrictive umask and fail-secure cleanup trap.
- `modules/rustdesk-fleet/tools/validate_phase52.py` — Vault metadata/runtime validation, backup/restore/rollback primitives and candidate stage runner.
- `modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py` — runtime-generated secret sentinel and disposable recovery tests.
- `modules/rustdesk-fleet/tests/fixtures/invalid/phase52-vault-restore-mutations.json` — non-secret negative catalog for Vault, archive, SQLite, fingerprint, network and cleanup failures.

## Decisions Made

- The helper accepts a provider executable path, not secret values. The provider contract receives only the exact approved references on stdin and returns values into the same short-lived helper operation; raw provider streams are never forwarded.
- Backup A and B use independent creation calls and retain only `db_v2.sqlite3`; their local/GDrive retention placement remains governed by `capacity-policy.json` and is materialized only in Plan 05.
- `run_full_candidate_gate` runs rollback even after an earlier candidate-stage failure, skips unsafe later stages and invokes the persistence callback before any fallback decision.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Resource-governor `doctor_ok` reported advisory swap-pressure/audit warnings during some runs; `structural_ok=true`, the required `cpu.max=80000 100000` containment held, and every test completed inside `omni-builds.slice`.

## Known Stubs

None. The live provider binding, pinned runtime consumption, backup B managed transfer and remote candidate operations are deliberate Plan 05 inputs, not placeholder implementations in this plan.

## Threat Flags

None beyond the Vault/runtime/archive trust boundaries already enumerated in the Plan 52-04 threat model.

## User Setup Required

None. No Vault value, remote candidate, production service, public listener, DNS/edge, client install or Windows host was changed.

## Next Phase Readiness

Ready for `52-05-PLAN.md` to invoke the same engine serially for every reached candidate, materialize backup A/B retention, execute `capacity_finalize`, persist NO-GO before fallback and select only a complete full-vector PASS. Phase 52 requirements remain pending until that live gate and Plan 52-06 report/ledger closeout pass.

## Self-Check: PASSED

- All four task commits exist and no tracked file was deleted.
- `121/121` Phase 52 tests and `199/199` RustDesk fleet tests passed under the governed builds profile.
- `bash -n` and `py_compile` passed for the helper and validator.
- Graphify was rebuilt at `df5c328` with `stale=false` and `commit_stale=false` before metadata closeout.
- No secret value, live remote mutation, public listener, production service or Windows install was produced.

---
*Phase: 52-supply-chain-capacity-and-recoverable-placement*
*Completed: 2026-07-22*
