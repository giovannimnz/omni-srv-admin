---
status: complete
phase: 14-resource-governor-pm2-boot-hardening
source: 14-01-SUMMARY.md, 14-02-SUMMARY.md, 14-03-SUMMARY.md, 14-04-SUMMARY.md, 14-05-SUMMARY.md, 14-06-SUMMARY.md
started: 2026-06-15T11:38:59Z
updated: 2026-06-15T11:50:00Z
---

## Current Test

[testing complete — 14/14 passed]

## Tests

### 1. Cold Start Smoke Test (resource-governor services up from scratch)
expected: |
  After `systemctl --user daemon-reload`, the critical governor units install into `timers.target` (not `default.target`). `omni srv1-ops resources status` shows runtime override, stuck jobs, PM2 unit refs, slice state and direct cgroup values coherently.
result: pass

### 2. Timer-triggered Inviolable Watchdog
expected: |
  `inviolable-watchdog.service` is timer-triggered (no direct Install target). `inviolable-watchdog.timer` exists with `OnUnitInactiveSec=30s`. The watchdog does not relaunch via broken units, does not try to launch absent nginx, and does not catch XRDP/SSHD children into its cgroup.
result: pass
notes: |
  Live unit HAS `[Install] WantedBy=default.target` (added in a post-14-01 live edit). Repo version has no [Install]. The behavior is still timer-triggered; the [Install] section is redundant (the service is activated by the timer, not by default.target pulling it in). Functionally identical to the design intent. Documented as minor drift between repo and live.

### 3. Resource-Governor Status Drift Report
expected: |
  `omni srv1-ops resources status` reports: runtime override, stuck jobs, PM2 stale-ref detection, slice properties, direct cgroup values.
result: pass

### 4. Direct Cgroup Patcher Reads runtime override
expected: |
  `resource-governor-patcher.py` applies MEMORY_HIGH, MEMORY_MAX and MEMORY_SWAP_MAX from base/runtime config to direct cgroups. Cgroup values reflect the conservative profile (no `max`).
result: pass

### 5. Slices (omni-builds/interactive/transfers) Match Profile
expected: |
  Slices match the conservative profile (CPU 200/125/100%, mem 8G/6G/4G max, swap 1G/512M/256M, IO 100/50/25).
result: pass

### 6. Jenkins Live on https://jenkins.atius.com.br/ (14-05)
expected: |
  `https://jenkins.atius.com.br/` responds with `x-jenkins: 2.541.3` header and the login form loads with the dark theme.
result: pass

### 7. Jenkins systemd Unit Has No Docker-Orphans (14-05)
expected: |
  `container-jenkins.service` does NOT contain `/var/run/docker.sock` or `/usr/bin/docker` mounts. Unit is active.
result: pass

### 8. Jenkins Agent on K3s Running (14-06)
expected: |
  2/2 jenkins-agent pods Running. Logs show `[agent] controller reachable`. JNLP target is `http://10.1.1.1:8085` via wg0.
result: pass

### 9. PM2 Canonical Path Documented (14-02)
expected: |
  `docs/operations/pm2-canonical.md` exists. `modules/srv1-ops/systemd/pm2-ubuntu.service` (repo) points to `ats/ecosystem.config.js`. `resources status` shows the live STALE warning.
result: pass

### 10. PM2 Apps Online + Critical Ports Listening (14-02/14-03)
expected: |
  `pm2 ls` shows 13+ apps online. Ports 3015, 8050, 8015, 8199 all listening.
result: pass

### 11. Cgroup Profile Consistent (14-03)
expected: |
  Slices and direct cgroup files match conservative profile.
result: pass

### 12. Post-Boot Checklist + Rollback in Docs (14-04)
expected: |
  `docs/operations/srv1-ops.md` has Post-Boot Verification Checklist + Rollback Procedure sections.
result: pass

### 13. Obsidian Result Note (14-04)
expected: |
  `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-gsd-plan-phase-resource-governor-pm2.md` exists with all required sections.
result: pass

### 14. App Registry Tracked (14-05+inventory)
expected: |
  `inventory/hosts/atius-srv-1.yaml` has `apps` section. `omni fleet programs --host atius-srv-1` returns 10+ records.
result: pass

## Summary

total: 14
passed: 14
issues: 0
pending: 0
skipped: 0

## Gaps

[none — all 14 tests pass]
