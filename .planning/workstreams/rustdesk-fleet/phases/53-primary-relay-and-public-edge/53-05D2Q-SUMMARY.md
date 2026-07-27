---
phase: 53-primary-relay-and-public-edge
plan: 05D2Q
subsystem: infra
tags: [rustdesk, git, sha256, dirty-baseline, supply-chain]
requires:
  - phase: 53-05D2C
    provides: "Revision 5 convergence and the authorized Q execution boundary"
provides:
  - "Create-only metadata baseline for the exact seven carry-forward dirty paths"
  - "Reusable exact/ancestor validator for the legal H to S to C Git chain"
  - "Hermetic positive and adversarial coverage for baseline and ancestry policy"
affects: [53-05D2R, 53-05D2V, 53-05D2S, 53-05D2D]
tech-stack:
  added: []
  patterns:
    - "Two-pass O_NOFOLLOW file observation with streaming SHA-256"
    - "Direct source commit plus summary-only child"
key-files:
  created:
    - modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py
    - modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py
    - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
    - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md
  modified: []
key-decisions:
  - "Preserve the plan-mandated H to S to C chain: exact ran once at H and is forbidden after S."
  - "Keep the baseline value-free and recompute every dirty-path field under ancestor policy."
patterns-established:
  - "Capture is exclusive, durable, mode 0600, duplicate-key rejecting and self-digested."
  - "Only literal path sets may enter the source and summary commits."
requirements-completed: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
coverage:
  - id: D1
    description: "Complete value-free dirty baseline and reusable validator"
    requirement: SRV-02
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py (23 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Literal one-parent source chain and summary-only child policy"
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "validate-phase53-dirty-baseline.py ancestor"
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-07-27
status: complete
---

# Phase 53 Plan 05D2Q Summary

**Full-field dirty-baseline gate sealed the seven carry-forward paths into a direct H to S source chain, ready for a summary-only child**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-27T01:17:00Z
- **Completed:** 2026-07-27T01:29:09Z
- **Tasks:** 2
- **Files created:** 4

## Sealed Binding

- **Captured H:** `917b7ae676e614f3d0d185bf27265ee9a729e09a`
- **Captured at:** `2026-07-27T01:29:09Z`
- **Source S:** `911e73729de304ab166d44f5d2c0b117426b2dfa`
- **Source tree:** `6bfe07797d2b6a6377fdab879857ba95f471fcef`
- **Baseline SHA-256:** `32b64c371639b63a571fc654cab442a116a3c57313249f402e740a57bcb20ad6`
- **Parent(S) = H:** `true`
- **Source path count:** `3`

The literal source set is:

1. `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json`
2. `modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py`
3. `modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py`

## Accomplishments

- Captured exact tracked/untracked classification, porcelain XY, regular-file type, mode, size and streaming SHA-256 for all seven paths in two identical passes.
- Enforced closed duplicate-key-rejecting JSON, canonical self digest, RFC3339 UTC timestamp and exclusive mode-0600 durable creation.
- Proved the legal H to S to C policy, including parent, literal diff and descendant ancestry checks.
- Covered content, status, mode, symlink, directory, TOCTOU, schema, digest, source and summary adversarial cases.

## Verification

- `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py --disable-warnings`
  - Result: `23 passed in 7.65s`
  - Resource containment: `CPUQuota=80%` on this 4-vCPU host, equal to the required 20% total host CPU.
- `capture` succeeded at H and created the baseline with worktree mode `0600`.
- The sole permitted `exact` invocation succeeded at H before staging.
- Source-only `ancestor --source-commit 911e73729de304ab166d44f5d2c0b117426b2dfa` succeeded at S.

## Authority and Mutation Flags

| Flag | Value |
|---|---|
| `external_authority_used` | `false` |
| `vault_write_performed` | `false` |
| `ssh_write_performed` | `false` |
| `provider_write_performed` | `false` |
| `captured_paths_mutated` | `false` |
| `captured_paths_staged` | `false` |
| `historical_gap_accepted` | `false` |
| `phase_53_r_started` | `false` |

## Task Commits

1. **Tasks 53-05D2Q-01 and 53-05D2Q-02 source seal** — `911e73729de304ab166d44f5d2c0b117426b2dfa`

The summary itself must be committed as the direct one-path child C of S and is therefore not self-referential here.

## Files Created

- `modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py` — stdlib-only capture/exact/ancestor validator.
- `modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py` — isolated temporary-Git positive and adversarial tests.
- `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json` — value-free seven-path baseline.
- `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md` — direct summary-only child payload.

## Decisions Made

- Followed D-21 exactly: Q owns only its four declared paths and performs no external mutation.
- The plan-specific single S commit takes precedence over generic multi-commit TDD sequencing because parent(S)=H and the literal three-path diff are security invariants.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The resource governor doctor reported a pre-existing swap-pressure warning (`99.99%`), while structural containment, CPU quota and the scoped suite all passed.

## User Setup Required

None - no external service configuration was used.

## Next Phase Readiness

- Q is sealed after the direct summary-only child and its summary-form ancestor validation pass.
- Plan 53-05D2R remains outside this authorization and must not start without separate authority.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-27*
