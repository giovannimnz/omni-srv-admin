# Gateway SIGTERM Loop — Diagnostic Session (2026-07-19)

Full transcript and raw data from diagnosing a WSL Hermes gateway stuck in a systemd SIGTERM death loop for 10+ hours.

## Problem Summary

- **863 SIGTERMs** on 2026-07-18 (14:14 to midnight BRT)
- **16 SIGTERMs** on 2026-07-19 (00:01 to 00:11 BRT)
- Each cycle: gateway starts → runs ~20-25s → receives SIGTERM from systemd (PID 1) → exits code 1 → systemd restarts after 10s (`RestartSec=10`) → repeat
- Stabilized at 00:11 BRT and stayed stable thereafter (PID 251)

## Root Cause

Manually-created systemd service file at `/etc/systemd/system/hermes-gateway.service` with problematic directives:

```
StartLimitIntervalSec=0          # disables rate limiting → infinite loop
ExecStart=...gateway run --replace   # --replace flag shouldn't be in ExecStart
KillMode=mixed                   # sends SIGTERM to main, then SIGKILL to rest
KillSignal=SIGTERM               # redundant with KillMode=mixed
TimeoutStopSec=210               # unusually long stop timeout
StandardOutput=journal           # not harmful, but not default
StandardError=journal            # not harmful, but not default
WantedBy=multi-user.target       # system-level, not user-level
```

The service was created by hand rather than via `hermes gateway install --system`, which auto-generates the correct unit.

The `hermes gateway status` command detected this: **"⚠ Installed gateway service definition is outdated"**

## Diagnostic Commands Used

### 1. Gateway log analysis

```bash
# Count total SIGTERMs
grep -c "Received SIGTERM" ~/.hermes/logs/gateway.log
# Result: 1758 (across all log files combined, ~863 on Jul 18 alone)

# SIGTERM timing pattern (uniform ~35s spacing = systemd restart loop)
grep "Received SIGTERM" ~/.hermes/logs/gateway.log | \
  awk '{print $1, $2}' | sort | uniq -c | sort -rn | head -15
# Result: all entries at 1 count each, spaced ~34-36s apart

# Last 5 SIGTERMs
grep "Received SIGTERM" ~/.hermes/logs/gateway.log | tail -5
```

### 2. Systemd service inspection

```bash
# Current service file (broken)
cat /etc/systemd/system/hermes-gateway.service

# systemd state
systemctl show hermes-gateway.service -p ActiveState -p SubState -p MainPID -p NRestarts
# NRestarts=0 (reset after stabilization)

# Full journal for the unit
journalctl -u hermes-gateway.service --no-pager | tail -100
```

The journal showed messages ONLY from the gateway process (`python[PID]`) — no systemd-level `Started`/`Stopping`/`Stopped` transitions. This is because the gateway's log output goes to journal and the unit messages were rotated/corrupted.

### 3. WSL dmesg (host VM reboots)

```bash
dmesg -T | tail -40
```

Showed multiple WSL VM shutdown/reboot cycles:
```
systemd-journald[47]: Received SIGTERM from PID 1 (systemd-shutdow).
EXT4-fs (sdd): unmounting filesystem ...
[~4 seconds later]
EXT4-fs (sdd): mounted filesystem ...
WSL (2 - init-systemd(Ubuntu-24.04)) ERROR: WaitForBootProcess: /sbin/init failed to start within 10000ms
```

These were SEPARATE from the gateway SIGTERMs — the WSL itself was unstable.

### 4. Windows Scheduled Tasks

```bash
iconv -f UTF-16 -t UTF-8 /mnt/c/Windows/System32/Tasks/Hermes_Gateway
iconv -f UTF-16 -t UTF-8 /mnt/c/Windows/System32/Tasks/Hermes_Gateway_WSL
```

- `Hermes_Gateway`: DISABLED (`<Enabled>false</Enabled>`), runs `.cmd` on boot
- `Hermes_Gateway_WSL`: ENABLED, runs VBS script at boot with 1min delay, `ExecutionTimeLimit=PT72H`

### 5. Gateway status (built-in diagnostic)

```bash
hermes gateway status
```

This was the key diagnostic — it auto-detected the outdated service definition and suggested the fix.

### 6. Service file diff (broken vs correct)

The current (broken) file vs what `hermes gateway install --system` would generate:

```
-StartLimitIntervalSec=0        # REMOVED
-ExecStart=...python -m hermes_cli.main gateway run --replace  # → hermes gateway run
-KillMode=mixed                 # REMOVED
-KillSignal=SIGTERM             # REMOVED
-TimeoutStopSec=210             # REMOVED
-StandardOutput=journal         # REMOVED
-StandardError=journal          # REMOVED
-WantedBy=multi-user.target     # → default.target
```

## Exit Diag Log (JSONL)

The `~/.hermes/logs/gateway-exit-diag.log` (20,565 lines) records every gateway start/exit as JSON. Key entries for this incident:

```json
{"tag": "gateway.start", "pid": 219, "replace": true, "argv": ["...gateway", "run", "--replace"]}
{"tag": "gateway.exit_nonzero", "pid": 219}
{"tag": "atexit.hook", "pid": 219, "sys_exc": "(None, None, None)"}
```

All rapid-cycle starts had `"replace": true` — confirming they were from the systemd service (which uses `--replace`). The VBS/Scheduled Task gateway uses `"replace": false`.

The last entry before stabilization:
```json
{"tag": "gateway.start", "pid": 251, "replace": true, ...}
```

PID 251 is the one that survived and is still running.

## Why Did It Stabilize?

Not definitively determined. The journal was corrupted/rotated and systemd-level messages were lost. The cycle ran from ~14:14 BRT (Jul 18) to ~00:11 BRT (Jul 19) — roughly 10 hours. Possible explanations:

- A systemd timer or cron job that was triggering `systemctl stop` expired
- WSL VM reboot cleared some conflicting state
- Resource contention resolved (loadavg was 1.2-1.7 during the loop)
- Manual intervention

## Fix Applied

The recommended fix (not yet executed — awaiting confirmation):

```bash
# Option A:
sudo hermes gateway restart --system    # auto-refreshes the unit

# Option B:
sudo hermes gateway uninstall --system
sudo hermes gateway install --system --run-as-user $USER --start-now
```
