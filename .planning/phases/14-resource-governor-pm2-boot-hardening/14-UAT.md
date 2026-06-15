---
status: testing
phase: 14-resource-governor-pm2-boot-hardening
source: 14-01-SUMMARY.md, 14-05-PLAN.md
started: 2026-06-15T11:38:59Z
updated: 2026-06-15T11:38:59Z
---

## Current Test

number: 1
name: Cold Start Smoke Test (resource-governor services up from scratch)
expected: |
  Resource-governor services (cgroup-init, patcher, watchdog, inviolable watchdog) can be daemon-reloaded and started from a clean state. Slices are created and match the conservative profile. No live mutation is required to confirm.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test (resource-governor services up from scratch)
expected: |
  After `systemctl --user daemon-reload`, the critical governor units install into `timers.target` (not `default.target`). `omni srv1-ops resources status` shows runtime override, stuck jobs, PM2 unit refs, slice state and direct cgroup values coherently.
result: [pending]

### 2. Timer-triggered Inviolable Watchdog
expected: |
  `inviolable-watchdog.service` is timer-triggered (no direct Install target). `inviolable-watchdog.timer` exists with `OnUnitInactiveSec=30s`. The watchdog does not relaunch via broken units, does not try to launch absent nginx, and does not catch XRDP/SSHD children into its cgroup.
result: [pending]

### 3. Resource-Governor Status Drift Report
expected: |
  `omni srv1-ops resources status` reports:
  - runtime override vs base profile
  - stuck jobs (default.target, ats-pm2.service, horistic-pm2.service still listed as stuck, gated for 14-02)
  - PM2 stale-ref detection (pm2-ubuntu.service → /home/ubuntu/ecosystem.atius.js still flagged as warning, not auto-fixed)
  - service/timer state for governor and inviolable units
  - slice properties (CPU, IO, memory, swap, weights)
  - direct cgroup values
result: [pending]

### 4. Direct Cgroup Patcher Reads runtime override
expected: |
  `resource-governor-patcher.py` applies MEMORY_HIGH, MEMORY_MAX and MEMORY_SWAP_MAX from base/runtime config to direct cgroups. Cgroup values reflect the conservative profile (no `max`).
result: [pending]

### 5. Slices (omni-builds/interactive/transfers) Match Profile
expected: |
  `resource-governor-cgroup-init.sh` applies CPU, I/O, weights, memory high/max and swap max to `omni-builds.slice`, `omni-interactive.slice`, `omni-transfers.slice`. Read back: slice properties are within conservative profile and consistent with the versioned config.
result: [pending]

### 6. Jenkins Live on https://jenkins.atius.com.br/ (14-05)
expected: |
  `https://jenkins.atius.com.br/` responds with `x-jenkins: 2.541.3` header and the login form loads with the dark theme (`https://jenkins.atius.com.br/theme-dark/theme.css`).
result: [pending]

### 7. Jenkins systemd Unit Has No Docker-Orphans (14-05)
expected: |
  `/home/ubuntu/.config/systemd/user/container-jenkins.service` does NOT contain `/var/run/docker.sock` or `/usr/bin/docker` mounts. Unit is active (running). Pod `srv1-podman` is reachable.
result: [pending]

### 8. Apps Tracked in omni-srv-admin Registry (14-05+inventory)
expected: |
  `inventory/hosts/atius-srv-1.yaml` has an `apps` section with at least: jenkins, jenkins-agent, cloudbeaver, redis, postgres, router-ai-atius, rclone-gdrive-mount. `omni fleet programs --host atius-srv-1` returns 10+ records (4 modules + 6+ apps) tagged with `kind: omni-module` or `kind: app`.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Gaps

[none yet]
