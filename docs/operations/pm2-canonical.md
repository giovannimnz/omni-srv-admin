# PM2 Canonical Boot Path

**Phase:** 14-02
**Last updated:** 2026-06-15

This document is the source of truth for how PM2 is supposed to boot on
SRV-1 (`ATIUS-SRV-1`) and how the systemd units interlock with the PM2
daemon, the user-level oneshot managers and the apps.

## Components

| Component | Path | Role |
|---|---|---|
| `pm2-ubuntu.service` (system unit) | `/etc/systemd/system/pm2-ubuntu.service` (live); repo at `modules/srv1-ops/systemd/pm2-ubuntu.service` | System-level PM2 daemon wrapper. Boots `pm2-runtime` with the canonical ecosystem. |
| `ats-pm2.service` (user oneshot) | `/home/ubuntu/.config/systemd/user/ats-pm2.service` | Runs `pm2-runtime start ats/ecosystem.config.js` to seed ATS apps. |
| `horistic-pm2.service` (user oneshot) | `/home/ubuntu/.config/systemd/user/horistic-pm2.service` | Runs `pm2 start horistic-api` to seed Horistic API. |
| `atius-web.service` (user oneshot) | `/home/ubuntu/.config/systemd/user/atius-web.service` | Runs `pm2 start atius-web` to seed Atius Web. |
| Canonical ATS ecosystem | `/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js` | Single source of truth for ATS apps. |
| Canonical Horistic ecosystem | `/home/ubuntu/GitHub/Atius-Capital/horistic/ecosystem.config.js` | Single source of truth for Horistic. |
| PM2 binary | `/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2` and `pm2-runtime` | Installed via nvm. |
| PM2_HOME | `/home/ubuntu/.pm2` | PM2 dump/restore location. |

## Canonical Path

1. **system boot:** `multi-user.target` brings up `pm2-ubuntu.service` (the system daemon wrapper).
2. **daemon:** `pm2-runtime` runs in foreground as the systemd service. The daemon stays alive.
3. **user session:** user-level `default.target` brings up the oneshot managers (`ats-pm2.service`, `horistic-pm2.service`, `atius-web.service`).
4. **oneshot managers:** each runs `pm2 start <app>` once. With `RemainAfterExit=yes` they stay "active" after success.
5. **PM2 daemon** owns the actual processes. If a process dies, PM2 resurrects it (per ecosystem config).

## What was wrong before 14-02

- `pm2-ubuntu.service` (system) referenced `/home/ubuntu/ecosystem.atius.js` which does NOT exist.
- The unit was enabled but `inactive` (status 125, `No such file or directory`).
- The user-level `ats-pm2.service` / `horistic-pm2.service` / `atius-web.service` were also `inactive` because of stuck `default.target` jobs.
- **HOWEVER** the PM2 daemon was still running, having been started by some other route (likely a manual `pm2 resurrect` after a previous crash or a one-off shell).
- All 13 critical apps (12 ATS + 1 Horistic) were online. Trading bots active.

## Why we did not auto-restart PM2

Per the live fix note `60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md` and
M006 acceptance criteria, "live execution must not stop PM2 daemons,
trading processes, XRDP, or stale user jobs without an explicit gate and
current process snapshot."

We did NOT:
- `systemctl restart pm2-ubuntu.service` (would kill the daemon + all apps)
- `pm2 kill` (would terminate all 13 apps)
- `systemctl --user restart ats-pm2.service` (would re-trigger start loop, possibly duplicate apps)

We DID:
- Snapshot `pm2 jlist` + `systemctl --user list-jobs` to `/home/ubuntu/.logs/resource-governor/pm2-hardening-<TS>/`
- Replace the repo-version `pm2-ubuntu.service` to point to the canonical ecosystem
- Surface the stale path in `omni srv1-ops resources status` (already in 14-01)
- Reset failed job state with `systemctl --user reset-failed`
- Document this canonical path

## What 14-02 still needs (gated work)

If/when the user gives explicit gate:

- `sudo systemctl disable --now pm2-ubuntu.service` (it is already inactive; this just removes the auto-start on next reboot)
- `systemctl --user reset-failed` on stuck oneshots (does not kill apps, only clears failure flag)
- Re-test reboot path with `systemctl --user reboot` equivalent (NOT recommended in production)

## Recovery

If PM2 daemon dies and apps don't come back:

1. **Snapshot first:** `pm2 jlist > /tmp/pm2-jlist-$(date +%s).json`
2. **Manually restart daemon:** `pm2-runtime /home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js` (or use `pm2 resurrect` if PM2_HOME dump is current)
3. **Verify critical ports:**
   - `nc -z 127.0.0.1 3015` (atius-web)
   - `nc -z 127.0.0.1 8050` (horistic-api)
   - `nc -z 127.0.0.1 8015` (atius-api)
   - `nc -z 127.0.0.1 8199` (atius-webhook-signals)
4. **Re-seed user oneshots if needed:** `systemctl --user start ats-pm2.service horistic-pm2.service atius-web.service`

## References

- Repo: `modules/srv1-ops/systemd/pm2-ubuntu.service` (canonical version)
- Vault: `60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md` (original live fix)
- 14-01 SUMMARY: `.planning/phases/14-resource-governor-pm2-boot-hardening/14-01-SUMMARY.md`
- 14-02 PLAN: `.planning/phases/14-resource-governor-pm2-boot-hardening/14-02-PLAN.md`
