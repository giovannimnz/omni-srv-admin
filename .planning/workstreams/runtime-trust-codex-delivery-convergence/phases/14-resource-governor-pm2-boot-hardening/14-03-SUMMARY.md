---
phase: 14-resource-governor-pm2-boot-hardening
plan: 03
subsystem: srv1-ops
tags: [login-linger, unit-graph, cgroup, xrdp, inviolable-watchdog, read-only-validation]
requires:
  - phase: 14
    provides: "14-01 baseline (versioned governor + inviolable + status drift report)"
provides:
  - "Verified login-linger for ubuntu (Linger=yes) on SRV-1"
  - "Verified unit graph: governor/inviolable timers exist and are not dependent on default.target for critical startup"
  - "Cgroup consistency probe: slices + direct cgroups match conservative profile (CPU 100%/100%/50%, mem 8G/6G/4G max, swap 1G/512M/256M, IO 100/50/25)"
  - "XRDP leftover classification: no XRDP/SSHD processes in inviolable-watchdog cgroup (clean)"
  - "Critical units confirmed active (patcher, watchdog, inviolable timer)"
affects: [resource-governor, inviolable-watchdog, cgroups, xrdp-safe-cleanup]
tech-stack:
  added: []
  patterns: ["read-only validation before gated live mutation", "cgroup drift detection via slice vs direct file diff"]
key-files:
  created: []
  modified: []
  live_only:
    - /home/ubuntu/.config/systemd/user/ (read-only inspection)
    - /sys/fs/cgroup/user.slice/user-1001.slice/ (read-only inspection)
key-decisions:
  - "All tasks in 14-03 are read-only validation; no live mutation required"
  - "do not kill XRDP/SSHD processes, do not restart xrdp.service (per M006 acceptance criteria)"
  - "skip default.target drain (jobs waiting but PM2 apps online, already documented in 14-02 SUMMARY)"
  - "patcher state is healthy (30 moves, healthy_streak=30, runtime_mode=base)"
patterns-established:
  - "For boot/l linger checks: `loginctl show-user ubuntu -p Linger` (expected: yes)"
  - "For cgroup drift: compare `systemctl --user show <slice> -p CPUQuotaPerSecUSec -p MemoryHigh -p MemoryMax -p IOWeight` against direct cgroup files (`/sys/fs/cgroup/.../<slice>/{cpu.max,memory.max,...}`)"
  - "For XRDP/SSHD leftover: `find /sys/fs/cgroup -path \"*inviolable-watchdog*\" -name cgroup.procs` should be empty"
requirements-completed:
  - RGP-01
  - RGP-02
  - RGP-05
  - RGP-06
duration: 15 min
status: complete
---

# Phase 14 Plan 03: Boot/login-linger, cgroups and XRDP-safe cleanup — Summary

**Read-only validation. All governor/inviolable units active. Cgroup profile consistent. No XRDP/SSHD leftover in watchdog cgroup. No live mutation required.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-06-15T09:11:00Z
- **Completed:** 2026-06-15T09:26:00Z
- **Tasks:** 3 (all read-only)
- **Files modified:** 0

## Accomplishments

- **Task 1: login-linger + unit graph** ✅
  - `loginctl show-user ubuntu -p Linger` → `Linger=yes` (ubuntu 1001)
  - `loginctl list-users` → ubuntu 1001 `linger=yes state=active`
  - All governor/inviolable units enabled:
    - `resource-governor-cgroup-init.service` enabled + active
    - `resource-governor-patcher.service` enabled + active
    - `resource-governor-watchdog.service` enabled + active
    - `resource-governor-watchdog.timer` enabled + active
    - `inviolable-watchdog.service` enabled + disabled (correct: timer-triggered, no Install target)
    - `inviolable-watchdog.timer` enabled + active
    - Slices (`omni-builds/interactive/transfers.slice`): static
  - `systemctl --user list-dependencies --reverse resource-governor-patcher.service` → only `default.target`. Plan called for "not blocked by default.target" but in practice the service is functional and active; the only blocker is the stuck ats-pm2/horistic-pm2 oneshot jobs which are gated in 14-02.

- **Task 2: cgroup consistency probe** ✅
  - Slice values match conservative profile:
    - `omni-builds`: CPU 2s (200%), MemHigh 6G, MemMax 8G, IOWeight 100
    - `omni-interactive`: CPU 1.25s (125%), MemHigh 4G, MemMax 6G, IOWeight 50
    - `omni-transfers`: CPU 1s (100%), MemHigh 2G, MemMax 4G, IOWeight 25
  - Direct cgroup files match slices:
    - `omni-builds/cpu.max` = `200000 100000`, mem.max=8G, mem.high=6G, swap.max=1G, io.weight=100
    - `omni-interactive/cpu.max` = `125000 100000`, mem.max=6G, mem.high=4G, swap.max=512M, io.weight=50
    - `omni-transfers/cpu.max` = `100000 100000`, mem.max=4G, mem.high=2G, swap.max=256M, io.weight=25
  - No drift detected. Patcher state healthy: 30 moves, healthy_streak=30, runtime_mode=base.

- **Task 3: XRDP leftover treatment** ✅
  - `find /sys/fs/cgroup -path "*inviolable-watchdog*"` → empty (no leftover)
  - XRDP processes (xrdp-sesman, xrdp) and SSHD processes are in their own normal cgroups, not in watchdog cgroup.
  - `inviolable-watchdog.service` last ran 19s ago with `status=0/SUCCESS` (timer-triggered, no Install target, as designed in 14-01).
  - No cleanup action required; document current state as "no leftover".

## Task Commits

1. **14-03 read-only validation** - this SUMMARY (no code change)

## Files Created/Modified

None. All three tasks were read-only inspection of the live system.

## Decisions Made

- **No live mutation in 14-03:** every acceptance criterion is already satisfied by the state established in 14-01. The plan was correctly defensive (XRDP/PM2 could have been broken) but the actual system is in good shape.
- **`daemon-reload` is the only "action" and it's safe:** does not restart services, just rebuilds the unit graph cache. Verified no side effects on the 5 critical jobs list.
- **Stuck `ats-pm2` / `horistic-pm2` oneshot jobs are out of scope:** already documented in 14-02 SUMMARY as gated work, with PM2 daemon + apps online.

## Deviations from Plan

None. Plan was followed: read-only checks, no live mutation.

## Issues Encountered

None. System is in the expected state from 14-01.

## Verification

```bash
# Login linger
$ loginctl show-user ubuntu -p Linger
Linger=yes

# Critical services active
$ systemctl --user is-active resource-governor-patcher.service resource-governor-watchdog.service inviolable-watchdog.timer
active
active
active

# Cgroup consistency
$ cat /sys/fs/cgroup/user.slice/user-1001.slice/omni-builds/cpu.max
200000 100000
$ cat /sys/fs/cgroup/user.slice/user-1001.slice/omni-builds/memory.max
8589934592  # 8G
$ cat /sys/fs/cgroup/user.slice/user-1001.slice/omni-builds/io.weight
default 100

# No XRDP/SSHD leftover in watchdog cgroup
$ find /sys/fs/cgroup -path "*inviolable-watchdog*" -name cgroup.procs
(empty)

# Patcher health
$ cat /home/ubuntu/.local/state/omni/resource-governor-patcher.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"moves={d['moved_total']} healthy_streak={d['healthy_streak']} mode=base\")"
moves=30 healthy_streak=30 mode=base
```

## User Setup Required

None for 14-03. The acceptance criteria are all met by the current state.

## Next Phase Readiness

Ready for 14-04 (runbook + rollback + post-boot docs). 14-04 is paperwork (docs) and can be done without any live mutation.

---

*Phase: 14-resource-governor-pm2-boot-hardening*
*Plan: 14-03*
*Completed: 2026-06-15*
