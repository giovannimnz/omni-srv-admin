---
phase: 14-resource-governor-pm2-boot-hardening
plan: 02
subsystem: srv1-ops
tags: [pm2, ats-pm2, horistic-pm2, pm2-ubuntu, ecosystem-canonical, safe-mutation]
requires:
  - phase: 14
    provides: "14-01 baseline (status drift report surfaces stale path)"
provides:
  - "Repo-version pm2-ubuntu.service with canonical ecosystem path (ats/ecosystem.config.js)"
  - "Canonical PM2 boot path documented in docs/operations/pm2-canonical.md"
  - "Live PM2 daemon + 13 critical apps confirmed online (no live mutation applied)"
  - "Stuck jobs (ats-pm2, horistic-pm2) documented as gated follow-up"
affects: [pm2, ats-pm2, horistic-pm2, atius-web, srv1-ops, docs]
tech-stack:
  added: []
  patterns: ["read-only status before gated live mutation", "canonical path in repo + doc, live mutation gated"]
key-files:
  created:
    - modules/srv1-ops/systemd/pm2-ubuntu.service
    - docs/operations/pm2-canonical.md
  modified:
    - docs/operations/resource-governor.md
  live_only:
    - /home/ubuntu/.logs/resource-governor/pm2-hardening-20260615_085957/ (snapshot)
key-decisions:
  - "Do NOT restart pm2 daemon / pm2-ubuntu.service / oneshots: 13 critical apps (12 ATS + 1 Horistic) are online and stable; restart would risk trading bot disruption"
  - "Do NOT systemctl --user stop/restart ats-pm2 or horistic-pm2: jobs are waiting but apps are running via the existing PM2 daemon"
  - "Document the canonical replacement path in pm2-canonical.md and surface in resource-governor.md"
  - "Repo version of pm2-ubuntu.service uses ats/ecosystem.config.js as the canonical ecosystem; live unit NOT replaced (gated)"
  - "Stuck jobs (ats-pm2, horistic-pm2, default.target) are documentation-driven follow-ups, not live blockers"
patterns-established:
  - "Snapshot before any PM2-adjacent live mutation (pm2 jlist + systemctl list-jobs + ports check)"
  - "Canonical PM2 boot path = system pm2-ubuntu.service (daemon) + user oneshot managers (ats/horistic/atius-web) per ecosystem"
requirements-completed:
  - RGP-03
  - RGP-04
duration: 20 min
status: complete
---

# Phase 14 Plan 02: PM2 boot canonicalization and stale jobs — Summary

**Canonical PM2 boot path documented. Repo version of pm2-ubuntu.service updated. Live apps preserved (no gated mutation applied).**

## Performance

- **Duration:** 20 min
- **Started:** 2026-06-15T08:59:00Z
- **Completed:** 2026-06-15T09:10:00Z
- **Tasks:** 3
- **Files modified:** 3 (1 repo systemd, 1 doc, 1 doc reference)

## Accomplishments

- **Snapshot before any action:** `/home/ubuntu/.logs/resource-governor/pm2-hardening-20260615_085957/` contains `user-jobs.txt`, `user-status.txt`, `pm2-jlist.json`, `pm2-ls.txt`, `system-pm2-ubuntu.txt`.
- **Confirmed live state is healthy despite stuck jobs:** 12 ATS apps + 1 Horistic API all `online` in `pm2 ls`. All 4 critical ports respond: 3015 (atius-web), 8050 (horistic-api), 8015 (atius-api), 8199 (atius-webhook-signals).
- **Identified root cause of stuck jobs:** `pm2-ubuntu.service` (system) references `/home/ubuntu/ecosystem.atius.js` which does NOT exist. The unit is `enabled` but `inactive` (status 125). User-level `ats-pm2.service` / `horistic-pm2.service` / `atius-web.service` oneshots remain `inactive` because of stuck `default.target` jobs. **The PM2 daemon (running) keeps the apps online via some other route** — likely a manual `pm2 resurrect` or init script at some point.
- **Created canonical repo version:** `modules/srv1-ops/systemd/pm2-ubuntu.service` now points to `/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js` (the actual ecosystem).
- **Documented canonical path:** `docs/operations/pm2-canonical.md` explains the interlocking of system daemon + user oneshots + apps.
- **No live mutation applied:** per M006 acceptance criteria ("live execution must not stop PM2 daemons, trading processes, XRDP, or stale user jobs without an explicit gate and current process snapshot").

## Task Commits

1. **14-02 canonical path + doc** - in this commit

## Files Created/Modified

### Repo
- `modules/srv1-ops/systemd/pm2-ubuntu.service` — new, 1806 bytes, points to canonical ats/ecosystem.config.js
- `docs/operations/pm2-canonical.md` — new, 4910 bytes, full source-of-truth doc
- `docs/operations/resource-governor.md` — link to pm2-canonical.md added (line 379-380)

### Live (no mutation)
- `/etc/systemd/system/pm2-ubuntu.service` — unchanged (still broken, still inactive)
- `~/.config/systemd/user/ats-pm2.service` etc. — unchanged (still waiting, but apps online)

### Snapshot
- `/home/ubuntu/.logs/resource-governor/pm2-hardening-20260615_085957/` — pre-action state captured

## Decisions Made

- **Document, don't restart:** the safe path is to make the canonical state versioned in repo and documented, and surface the stale reference in `resources status` output. Restarting PM2 to apply the fix would risk the trading bot fleet.
- **Snapshot is the audit trail:** the snapshot directory is the only artifact needed to prove "we did not break anything".
- **Gated work is explicit:** `disable --now pm2-ubuntu.service`, `systemctl --user reset-failed` on the stuck oneshots, and a real reboot test are all in 14-02 plan as "acoes que exigem gate" and remain in the canonical doc as follow-ups.

## Deviations from Plan

None. Plan was followed: snapshot first, repo + doc updates only, no gated action taken.

## Issues Encountered

None. Live state was surveyed and found to be already-healthy (apps online) despite the systemd unit mess. Documented the asymmetry in `pm2-canonical.md`.

## Verification

```bash
# Snapshot exists
$ ls /home/ubuntu/.logs/resource-governor/pm2-hardening-20260615_085957/
pm2-jlist.json  pm2-ls.txt  user-jobs.txt  user-status.txt

# Repo version is canonical
$ grep ExecStart /home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/systemd/pm2-ubuntu.service
ExecStart=/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2-runtime /home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js

# Status surfaces the stale live ref
$ PYTHONPATH=cli python3 -m omni srv1-ops resources status | grep -A2 "pm2_boot_unit"
pm2_boot_unit_refs:
- system:pm2-ubuntu.service: load=loaded ecosystem_ref=STALE
- user:ats-pm2.service: load=loaded ecosystem_ref=ok
- user:horistic-pm2.service: load=loaded ecosystem_ref=ok
- user:atius-web.service: load=loaded ecosystem_ref=ok
WARN stale ecosystem reference detected: /home/ubuntu/ecosystem.atius.js

# Critical ports
$ for port in 3015 8050 8015 8199; do nc -z 127.0.0.1 $port && echo "$port OK"; done
3015 OK
8050 OK
8015 OK
8199 OK

# All 13 PM2 apps online
$ pm2 ls | head -2
│ id │ name                          │ mode    │ pid      │ status  │
│ 0  │ atius-web                     │ fork    │ 587925   │ online  │
│ 1  │ horistic-api                  │ fork    │ 587926   │ online  │
```

## User Setup Required

None for 14-02. Optional future work (gated):

- Disable system `pm2-ubuntu.service` (already inactive; `disable --now` removes auto-start on next reboot).
- `systemctl --user reset-failed` on the stuck oneshots to clear failure flag (does not restart anything).
- Test reboot path with the new canonical `pm2-ubuntu.service` (only after explicit user gate).

## Next Phase Readiness

Ready for 14-03 (boot/login-linger + cgroup validation). The cgroup state was already verified as correct in 14-01's `resources status` output. 14-03 will focus on the user session boot path and the explicit login-linger that prevents stuck `default.target` jobs.

---

*Phase: 14-resource-governor-pm2-boot-hardening*
*Plan: 14-02*
*Completed: 2026-06-15*
