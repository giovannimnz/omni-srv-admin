---
phase: 14-resource-governor-pm2-boot-hardening
plan: 01
subsystem: infra
tags: [systemd, cgroups, pm2, xrdp, resource-governor, inviolable-watchdog]
requires:
  - phase: 14
    provides: "Phase 14 context, live incident note and M006 requirements"
provides:
  - "Versioned resource-governor and inviolable-watchdog units outside default.target for critical startup"
  - "resources install dry-run and real install coverage for governor/inviolable units"
  - "resource-governor status report for runtime mode, stale jobs, PM2 unit refs, slices and direct cgroups"
affects: [resource-governor, srv1-ops, pm2-hardening, xrdp-safe-cleanup]
tech-stack:
  added: []
  patterns: ["read-only live status before gated systemd/PM2 changes", "timers.target anchoring for critical user units"]
key-files:
  created:
    - modules/srv1-ops/systemd/inviolable-watchdog.service
    - modules/srv1-ops/systemd/inviolable-watchdog.timer
  modified:
    - cli/omni/srv1_ops.py
    - docs/operations/resource-governor.md
    - docs/operations/srv1-ops.md
    - modules/srv1-ops/scripts/inviolable-watchdog.sh
    - modules/srv1-ops/scripts/resource-governor-cgroup-init.sh
    - modules/srv1-ops/scripts/resource-governor-patcher.py
    - modules/srv1-ops/scripts/resource-governor-status.py
    - modules/srv1-ops/scripts/resource-governor-watchdog.py
    - modules/srv1-ops/systemd/omni-builds.slice
    - modules/srv1-ops/systemd/omni-interactive.slice
    - modules/srv1-ops/systemd/omni-transfers.slice
    - modules/srv1-ops/systemd/resource-governor-cgroup-init.service
    - modules/srv1-ops/systemd/resource-governor-patcher.service
    - modules/srv1-ops/systemd/resource-governor-watchdog.service
key-decisions:
  - "Critical governor services install into timers.target instead of default.target."
  - "inviolable-watchdog.service is timer-triggered and has no direct Install target."
  - "resource-governor-status.py is the read-only gate before PM2/XRDP cleanup work."
patterns-established:
  - "Status command reports both systemd slices and direct cgroups for drift detection."
  - "PM2 boot path drift is surfaced as a warning, not auto-fixed in 14-01."
requirements-completed:
  - RGP-01
  - RGP-02
  - RGP-05
duration: 55 min
completed: 2026-06-15
---

# Phase 14 Plan 01: Versionar governor/inviolable e status/install coverage Summary

**Resource governor and inviolable watchdog guardrails versioned with install dry-run, status drift reporting and default.target-independent critical units.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-06-15T06:51:00Z
- **Completed:** 2026-06-15T07:46:30Z
- **Tasks:** 3
- **Files modified:** 16

## Accomplishments

- Reconciled the repo with the live fix note for cgroup init, patcher, watchdog and inviolable watchdog behavior.
- Moved critical governor services to `timers.target` and left `inviolable-watchdog.service` timer-triggered, avoiding `default.target` as the critical install path.
- Expanded `omni srv1-ops resources status` to report runtime override, stuck jobs, stale PM2 ecosystem refs, service/timer state, slice properties and direct cgroup values.
- Updated the direct cgroup patcher so memory high/max/swap limits are applied from `resource-governor.env` and runtime override.

## Task Commits

1. **Task 1-3: Versioned artifacts, install/status guardrails and static verification** - `ba3368d4c` (`feat(14-01)`)

**Plan metadata:** this summary commit.

## Files Created/Modified

- `cli/omni/srv1_ops.py` - Added explicit install sets for governor/inviolable timers and services.
- `modules/srv1-ops/systemd/inviolable-watchdog.service` - Versioned service using repo script, `KillMode=process` and `TimeoutStartSec=120`.
- `modules/srv1-ops/systemd/inviolable-watchdog.timer` - Versioned timer with `OnUnitInactiveSec=30s`.
- `modules/srv1-ops/systemd/resource-governor-*.service` - Critical services no longer install through `default.target`.
- `modules/srv1-ops/scripts/resource-governor-status.py` - Added status sections for units, stuck jobs, stale PM2 refs, slices and direct cgroups.
- `modules/srv1-ops/scripts/resource-governor-patcher.py` - Loads runtime override and applies configured CPU, I/O, memory and weights to direct cgroups.
- `modules/srv1-ops/scripts/resource-governor-cgroup-init.sh` - Applies CPU, I/O, weights, memory high/max and swap max to systemd slice cgroups.
- `modules/srv1-ops/scripts/inviolable-watchdog.sh` - Uses real ATS/Horistic ecosystems, `systemctl --no-block`, transient XRDP/SSHD units and ignores absent nginx.

## Decisions Made

- `14-01` only surfaces PM2 stale jobs and the broken `pm2-ubuntu.service` path; live PM2 cleanup remains gated for `14-02`.
- No live `enable`, `restart`, `stop`, `pm2 kill` or XRDP action was executed.
- The three `omni-*.slice` files were included because RGP-02 requires slice defaults to match the versioned config/status story.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Direct cgroups lacked full memory profile coverage**
- **Found during:** Task 2 (status guardrails)
- **Issue:** Read-only status showed direct cgroups could report `memory.high=max` and `memory.swap.max=max`, while the plan requires cgroups and slices to expose profile drift.
- **Fix:** Extended `resource-governor-patcher.py` to apply `MEMORY_HIGH`, `MEMORY_MAX` and `MEMORY_SWAP_MAX` from base/runtime config.
- **Files modified:** `modules/srv1-ops/scripts/resource-governor-patcher.py`
- **Verification:** `py_compile`, status output and grep checks passed.
- **Committed in:** `ba3368d4c`

**Total deviations:** 1 auto-fixed (missing critical coverage).
**Impact on plan:** Required for RGP-02; no live service mutation or scope creep.

## Issues Encountered

- Live read-only status still reports `default.target`, `ats-pm2.service` and `horistic-pm2.service` stuck, and `pm2-ubuntu.service` still points to `/home/ubuntu/ecosystem.atius.js`.
- Those are expected follow-up targets for `14-02` and `14-03`, not `14-01` live mutations.

## Verification

- `python3 -m py_compile cli/omni/srv1_ops.py modules/srv1-ops/scripts/resource-governor-patcher.py modules/srv1-ops/scripts/resource-governor-status.py modules/srv1-ops/scripts/resource-governor-watchdog.py`
- `bash -n modules/srv1-ops/scripts/resource-governor-cgroup-init.sh`
- `bash -n modules/srv1-ops/scripts/inviolable-watchdog.sh`
- `git diff --check`
- `systemd-analyze verify --user ...`
- `PYTHONPATH=cli python3 -m omni srv1-ops resources install --dry-run --no-run-audit-now`
- `PYTHONPATH=cli python3 -m omni srv1-ops resources status`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `14-02` and `14-03`.

`14-02` should address the stale PM2 jobs and `/home/ubuntu/ecosystem.atius.js` path with a current snapshot and explicit gate before any stop/restart.

`14-03` should validate login-linger, unit graph and cgroup consistency after the versioned patches.

---
*Phase: 14-resource-governor-pm2-boot-hardening*
*Completed: 2026-06-15*
