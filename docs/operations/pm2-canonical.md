# PM2 Canonical Boot Path

**Phase:** 14-02
**Last updated:** 2026-06-21

This document is the source of truth for how PM2 is supposed to boot on
SRV-1 (`ATIUS-SRV-1`) and how the systemd units interlock with the PM2
daemon, the user-level oneshot managers and the apps.

## Components

| Component | Path | Role |
|---|---|---|
| `pm2-ubuntu.service` (system unit) | `/etc/systemd/system/pm2-ubuntu.service` (live); repo at `modules/srv1-ops/systemd/pm2-ubuntu.service` | Single system-level PM2 boot owner. Runs `pm2 resurrect` from `/home/ubuntu/.pm2/dump.pm2`, which must contain ATS + Horistic. Implemented as `Type=oneshot` + `RemainAfterExit=yes`, without `PIDFile`, to avoid systemd protocol races during resurrect. |
| `ats-pm2.service` (legacy user oneshot) | `/home/ubuntu/.config/systemd/user/ats-pm2.service` | Disabled live. Do not re-enable; it races with `pm2-ubuntu.service`. |
| `horistic-pm2.service` (legacy user oneshot) | `/home/ubuntu/.config/systemd/user/horistic-pm2.service` | Disabled live. Do not re-enable; it previously only managed part of Horistic. |
| `atius-web.service` (legacy user oneshot) | `/home/ubuntu/.config/systemd/user/atius-web.service` | Static legacy unit. Do not depend on it from healthchecks. |
| Canonical ATS ecosystem | `/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js` | Single source of truth for ATS apps. |
| Canonical Horistic ecosystem | `/home/ubuntu/GitHub/Atius-Capital/horistic/ecosystem.config.js` | Single source of truth for Horistic. |
| PM2 binary | `/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2` and `pm2-runtime` | Installed via nvm. |
| PM2_HOME | `/home/ubuntu/.pm2` | PM2 dump/restore location. |

## Canonical Path

1. **system boot:** `multi-user.target` brings up `pm2-ubuntu.service`.
2. **restore:** `pm2-ubuntu.service` runs `pm2 resurrect` with `PM2_HOME=/home/ubuntu/.pm2`.
3. **PM2 dump:** `/home/ubuntu/.pm2/dump.pm2` restores both namespaces:
   - `atius`: 12 current apps, including dynamic account bots captured by `pm2 save`.
   - `horistic`: 5 apps.
4. **PM2 daemon** owns the actual processes. If a process dies, PM2 restarts it according to the app definition.
5. **omni watchdog:** `inviolable-watchdog` validates full ATS and Horistic stacks and may relaunch individual ecosystems if PM2 apps or critical ports are missing.

After any intentional PM2 topology change:

```bash
pm2 save --force
node - <<'NODE'
const fs=require('fs');
const apps=JSON.parse(fs.readFileSync('/home/ubuntu/.pm2/dump.pm2','utf8'));
const counts={};
for (const a of apps) counts[a.namespace || a.pm2_env?.namespace || 'default']=(counts[a.namespace || a.pm2_env?.namespace || 'default']||0)+1;
console.log(counts);
NODE
```

Expected current baseline: `{ atius: 12, horistic: 5 }`.

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

## 2026-06-18 Incident Closure

After a reboot at `2026-06-18 14:21:12 -03`, public Horistic sites failed because only part of the Horistic PM2 stack was available. The root cause was a split boot contract:

- `pm2-ubuntu.service` was enabled but still running an old `pm2-runtime /home/ubuntu/ecosystem.atius.js` path.
- `horistic.service` started Horistic and then ran `pm2 save`, overwriting `dump.pm2` with a Horistic-only view.
- User units `horistic-pm2.service` and `atius-web.service` stayed stuck in `activating`, spawning competing PM2 daemons.

Fix applied:

- `pm2 save` with the current 17-app fleet (`atius: 12`, `horistic: 5`).
- `pm2-ubuntu.service` regenerated as the single `pm2 resurrect` boot owner.
- `horistic.service`, `ats-pm2.service` and `horistic-pm2.service` disabled live.
- `atius-web-healthcheck.service` decoupled from the static legacy `atius-web.service`.
- `inviolable-watchdog` updated to validate the full ATS and Horistic PM2 stacks instead of only partial apps.

## 2026-06-21 PIDFile Race Closure

After a reboot at `2026-06-21 08:29 -03`, `pm2-ubuntu.service` restored processes but systemd marked the unit failed:

- `Can't open PID file /home/ubuntu/.pm2/pm2.pid`
- `Failed with result 'protocol'`
- `Start request repeated too quickly`

The live PM2 daemon had 17 processes, but `/home/ubuntu/.pm2/dump.pm2` had drifted to 6 entries. Fix applied:

- `/etc/systemd/system/pm2-ubuntu.service` and the repo source in `modules/srv1-ops/systemd/pm2-ubuntu.service` changed from `Type=forking` + `PIDFile` to `Type=oneshot` + `RemainAfterExit=yes`.
- `pm2 save --force` rewrote `/home/ubuntu/.pm2/dump.pm2` with the current baseline: `{ atius: 12, horistic: 5 }`.
- `systemctl reset-failed pm2-ubuntu.service && systemctl start pm2-ubuntu.service` completed with `active (exited)` and `ExecStart ... status=0/SUCCESS`.

## Recovery

If PM2 daemon dies and apps don't come back:

1. **Snapshot first:** `pm2 jlist > /tmp/pm2-jlist-$(date +%s).json`
2. **Manually restart daemon:** `pm2 resurrect` if PM2_HOME dump is current.
3. **Verify critical ports:**
   - `nc -z 127.0.0.1 3015` (atius-web)
   - `nc -z 127.0.0.1 8050` (horistic-api)
   - `nc -z 127.0.0.1 8015` (atius-api)
   - `nc -z 127.0.0.1 8199` (atius-webhook-signals)
4. **If a namespace is incomplete:** start from the ecosystem and save again:
   - `cd /home/ubuntu/GitHub/Atius-Capital/ats && pm2 start ecosystem.config.js --update-env && pm2 save --force`
   - `cd /home/ubuntu/GitHub/Atius-Capital/horistic && pm2 start ecosystem.config.js --update-env && pm2 save --force`

## References

- Repo: `modules/srv1-ops/systemd/pm2-ubuntu.service` (canonical version)
- Vault: `60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md` (original live fix)
- Vault: `61-Incidents/2026-06-21-atius-horistic-pm2-boot-pidfile.md` (PIDFile race closure)
- 14-01 SUMMARY: `.planning/phases/14-resource-governor-pm2-boot-hardening/14-01-SUMMARY.md`
- 14-02 PLAN: `.planning/phases/14-resource-governor-pm2-boot-hardening/14-02-PLAN.md`
