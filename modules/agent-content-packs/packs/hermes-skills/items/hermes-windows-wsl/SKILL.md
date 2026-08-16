---
name: hermes-windows-wsl
description: Use when configuring, troubleshooting, migrating, or operating Hermes Agent across native Windows and WSL — dual config sharing, gateway deployment, verified cross-runtime message delivery, MCP path translation, systemd vs Scheduled Task keepalive, and cross-platform MCP setup.
version: 1.1.0
author: Hermes Agent
platforms: [windows, linux]
metadata:
  hermes:
    tags: [hermes, wsl, windows, gateway, mcp, setup, dual-host]
---

# Hermes Windows + WSL Dual Setup

Covers the full pattern of running Hermes Agent on a Windows host with the gateway deployed inside WSL2 for native Linux terminal access, while sharing configuration, API keys, and MCP server definitions across both environments.

For Giovanni's concrete 3-environment YOLO topology on this host (PowerShell 7/cmd.exe, MSYS2 Zsh, local WSL; but only 2 Hermes installs), also see `skill_view(name="hermes-yolo-three-env")`.

## When to Use

- Installing Hermes inside WSL when a Windows-native install already exists
- Moving the gateway from Windows (Scheduled Task) to WSL (systemd or Scheduled Task keepalive)
- Fixing MCP servers that fail in WSL due to Windows path references
- Setting up `chrome-devtools-mcp` cross-platform (shared between Hermes and Codex)
- Debugging HTTP MCP auth failures caused by missing env vars in `.env`
- Keeping WSL background processes alive after `wsl.exe` parent exits
- Diagnosing gateway SIGTERM restart loops (systemd service misconfiguration)
- Fixing Computer Use when a WSL wrapper launches the native Windows CUA driver but its manifest leaks a Win32 command path back to the POSIX subprocess
- Sending a report from a Windows Hermes session through a gateway whose active runtime and home-channel configuration live inside WSL

## Quick Decision Tree

```
Gateway running on Windows?  ──YES──>  Want it in WSL?  ──YES──>  Follow "Gateway Migration" below
     │
     NO (or WSL fresh install) ──>  Follow "Fresh WSL Install"
     
MCP server failing in WSL?  ──>  Check "MCP Path Translation" + "Env Var Auth"
     
chrome-devtools failing?  ──>  Follow "chrome-devtools Cross-Platform"

Gateway keeps restarting?
  ──>  Check "Gateway SIGTERM Loop (Troubleshooting)"
```

---

## 1. Fresh WSL Install

When Hermes is already installed on Windows and you need a parallel install inside WSL:

```bash
# Inside WSL (Ubuntu 24.04+)
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

The installer handles:
- Python 3.11 via uv (bypasses PEP 668 restrictions on Ubuntu 24.04)
- Node.js 22 LTS to `~/.hermes/node/`
- ripgrep + ffmpeg via apt
- Git clone of hermes-agent repo to `~/.hermes/hermes-agent/`
- Virtual environment with full `[all]` dependency set

Post-install, the binary is at:
```
~/.hermes/hermes-agent/venv/bin/hermes
```

Add to PATH:
```bash
export PATH="$HOME/.hermes/hermes-agent/venv/bin:$HOME/.hermes/bin:$PATH"
```

## 2. Sharing Config Between Windows and WSL

The Windows config lives at `C:\Users\<user>\AppData\Local\hermes\` which maps to `/mnt/c/Users/<user>/AppData/Local/hermes/` inside WSL.

### Hard boundary: never share the mutable Hermes home

Windows and WSL must have separate runtime homes:

```text
Windows: C:\Users\<user>\AppData\Local\hermes
WSL:    /home/<user>/.hermes
```

Do **not** export WSL `HERMES_HOME` to `/mnt/c/...`. SQLite WAL files, locks, PIDs, logs, caches, and gateway state are runtime-local; sharing them through DrvFS/NTFS can corrupt `state.db` and make the CLI and gateway operate on different session stores.

A common source is a shared `common-env.sh` that derives `HERMES_HOME` from imported Windows `LOCALAPPDATA`. Branch explicitly and override any imported value in WSL:

```sh
if is_wsl_shell; then
  export HERMES_HOME="${HERMES_HOME_WSL:-$HOME/.hermes}"
  # wsl-sync-windows-env may also import WORKSPACE_STATE; force it back to ext4.
  export WORKSPACE_STATE="${WORKSPACE_STATE_WSL:-$HERMES_HOME/workspace-state.json}"
else
  export HERMES_HOME="$(shell_host_path "${HERMES_HOME:-$LOCALAPPDATA/hermes}")"
fi
```

Do not only override `HERMES_HOME`: imported auxiliary state variables such as `WORKSPACE_STATE` can still point back to `/mnt/c` and recreate split-brain runtime state.

Safe to copy deliberately: `config.yaml`, `.env`, `auth.json`, `SOUL.md`, `memories/`, and `skills/`. Never copy as live shared state: `state.db*`, `*.lock`, `*.pid`, `logs/`, `cache/`, or `gateway_state.json`.

For corruption recovery, split-brain diagnostics, MCP path normalization, the detached parked-task `/exit` traceback, and an E2E verification recipe, read `references/runtime-home-isolation-and-mcp-shutdown.md`.

**Recommended approach**: Copy (don't symlink) the config to WSL's `~/.hermes/`, then adjust paths:

```bash
# Inside WSL
mkdir -p ~/.hermes
cp "/mnt/c/Users/$USER/AppData/Local/hermes/config.yaml" ~/.hermes/
cp "/mnt/c/Users/$USER/AppData/Local/hermes/.env" ~/.hermes/
```

**Pitfall**: The `.env` file may be missing env vars that are set in the Windows shell profile (`.bashrc`, `.zshrc`) but not persisted to `.env`. Always check with `grep` after copying:

```bash
# Check for missing auth tokens
grep "ATIUS_MCP_TOKEN\|gbrain\|obsidian" ~/.hermes/.env
```

If missing, add them to `.env` (NOT just the shell rc) so Hermes can expand `${VAR_NAME}` references in `config.yaml`.

## 3. MCP Path Translation

Windows paths in `config.yaml` must be translated for WSL:

| Windows path | WSL path |
|---|---|
| `C:\Users\<user>\.ijfw\...` | `/mnt/c/Users/<user>/.ijfw/...` |
| `C:\Program Files\...` | `/mnt/c/Program Files/...` |

**Automated fix** (Python, inside WSL):
```python
with open("/home/muniz/.hermes/config.yaml", "r") as f:
    content = f.read()

replacements = {
    r"C:\Users\muniz\.ijfw": r"/mnt/c/Users/muniz/.ijfw",
    # Add more as needed
}
for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)

with open("/home/muniz/.hermes/config.yaml", "w") as f:
    f.write(content)
```

**Pitfall**: `sed` escaping for Windows backslash paths in bash is error-prone. Prefer Python for path replacements.

### Detecting broken paths

Symptom in `mcp-stderr.log`:
```
Error: Cannot find module '/mnt/c/Users/.../C:\Users\...\server.js'
```
This means a Windows path survived inside a WSL-resolved path — the fix didn't apply or the sed pattern didn't match. Re-run with Python, not sed.

## 4. chrome-devtools Cross-Platform Setup

`chrome-devtools-mcp` (v1.5.0, Google) is the npm package. It is **not** `@anthropic-ai/chrome-devtools-mcp` (that package does not exist).

### Windows

```bash
npm install -g chrome-devtools-mcp@latest
```

Config section:
```yaml
mcp_servers:
  chrome-devtools:
    command: npx
    args:
      - -y
      - chrome-devtools-mcp@latest
    timeout: 60
    connect_timeout: 60   # generous for first npx download
```

### WSL

Same config works — `npx` auto-downloads on first use. Node.js is installed by the Hermes installer at `~/.hermes/node/`. No separate `npm install -g` needed.

### Sharing with Codex

Both Hermes Agent and Codex reference the same `mcp_servers` block. Point Codex's config to the same `chrome-devtools` entry. The MCP server process is spawned independently per client — no conflict.

### Verification

The server registers **29 tools**: `click`, `close_page`, `drag`, `emulate`, `evaluate_script`, `fill`, `fill_form`, `get_console_message`, `get_network_request`, `handle_dialog`, `hover`, `lighthouse_audit`, `list_console_messages`, `list_network_requests`, `list_pages`, `navigate_page`, `new_page`, `performance_analyze_insight`, `performance_start_trace`, `performance_stop_trace`, `press_key`, `resize_page`, `select_page`, `take_heapsnapshot`, `take_screenshot`, `take_snapshot`, `type_text`, `upload_file`, `wait_for`.

## 4.5. Driving Native Windows Apps from a Hermes Session Running in WSL

`hermes computer-use install` detects the OS of the Hermes process. When Hermes runs inside WSL, that command installs the **Linux** Cua Driver, which targets AT-SPI/WSLg and does not give UIAutomation access to native Win32 applications. To control native Windows apps while keeping Hermes in WSL, install the Windows Cua Driver and expose it to WSL through a small launcher.

### Step 1: Verify or restore WSLInterop

```bash
# A missing WSLInterop registration causes powershell.exe/cmd.exe to fail
# with "cannot execute binary file: Exec format error".
if [ ! -e /proc/sys/fs/binfmt_misc/WSLInterop ]; then
  sudo sh -c "printf ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register"
fi

/mnt/c/Windows/System32/cmd.exe /c "echo %COMPUTERNAME%"
```

WSL normally registers this automatically. If it disappears again after a reboot, diagnose WSL initialization rather than repeatedly assuming PowerShell itself is broken.

### Step 1.5: Persist the WSLInterop repair when `/proc/sys/fs/binfmt_misc/WSLInterop` disappears

A one-shot manual register fixes the current shell, but on this host the entry had disappeared while `binfmt_misc` itself was still mounted and `systemd-binfmt.service` was intentionally skipped under WSL (`ConditionVirtualization=!wsl`). That means a normal reboot/startup path may not recreate `WSLInterop` for you.

When you confirm this pattern:

- `/proc/sys/fs/binfmt_misc/status` exists
- `/proc/sys/fs/binfmt_misc/WSLInterop` is missing
- `powershell.exe` / `cmd.exe` fail with `Exec format error`
- `systemctl status systemd-binfmt` shows the WSL condition was not met

install a local self-heal inside WSL:

```bash
sudo tee /usr/local/sbin/ensure-wslinterop >/dev/null <<'EOF'
#!/bin/sh
set -eu
if [ ! -e /proc/sys/fs/binfmt_misc/status ]; then
  exit 0
fi
if [ -e /proc/sys/fs/binfmt_misc/WSLInterop ]; then
  exit 0
fi
printf ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register
EOF
sudo chmod 0755 /usr/local/sbin/ensure-wslinterop

sudo tee /etc/systemd/system/wslinterop-restore.service >/dev/null <<'EOF'
[Unit]
Description=Restore WSL Windows interop binfmt entry
DefaultDependencies=no
After=local-fs.target proc-sys-fs-binfmt_misc.mount systemd-modules-load.service
Before=multi-user.target
ConditionPathExists=/proc/sys/fs/binfmt_misc/register

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ensure-wslinterop
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable wslinterop-restore.service
sudo systemctl restart wslinterop-restore.service
```

Then verify end-to-end instead of trusting the unit alone:

```bash
powershell.exe -NoProfile -Command 'Write-Output INTEROP_OK'
/home/muniz/.local/bin/wsl-sync-windows-env --refresh >/tmp/out 2>/tmp/err && wc -c /tmp/err
zsh -lic 'powershell.exe -NoProfile -Command "Write-Output ZSH_OK"'
```

If you want to prove persistence, deliberately remove the entry and let the service restore it:

```bash
sudo sh -c 'echo -1 > /proc/sys/fs/binfmt_misc/WSLInterop'
sudo systemctl restart wslinterop-restore.service
cat /proc/sys/fs/binfmt_misc/WSLInterop
```

Treat this as a WSL runtime fault, not a Windows shell-profile problem.

### Step 2: Install the native Windows driver

Run the canonical upstream Windows installer through PowerShell:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
  $ErrorActionPreference="Stop"
  Set-Location $env:USERPROFILE
  $p=Join-Path $env:TEMP "cua-driver-install.ps1"
  Invoke-WebRequest -UseBasicParsing \
    "https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.ps1" \
    -OutFile $p
  & $p
'
```

The installer places the binary under:

```text
C:\Users\<user>\AppData\Local\Programs\Cua\cua-driver\bin\cua-driver.exe
```

It also registers a highest-privilege logon task so the daemon runs in the interactive Windows session. Start it immediately and verify Windows UIA/capture:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
  $exe="$env:LOCALAPPDATA\Programs\Cua\cua-driver\bin\cua-driver.exe"
  & $exe autostart kick
  Start-Sleep -Seconds 2
  & $exe doctor
'
```

Expected checks include `interactive session`, `UI Automation`, and `EnumWindows visible` as OK.

### Step 3: Expose the Windows binary as `cua-driver` inside WSL

Create `~/.local/bin/cua-driver`:

```bash
#!/usr/bin/env bash
set -euo pipefail
WINDOWS_CUA='/mnt/c/Users/<user>/AppData/Local/Programs/Cua/cua-driver/bin/cua-driver.exe'
if [[ ! -x "$WINDOWS_CUA" ]]; then
  printf 'Windows cua-driver not found: %s\n' "$WINDOWS_CUA" >&2
  exit 127
fi
exec "$WINDOWS_CUA" "$@"
```

Then:

```bash
chmod 0755 ~/.local/bin/cua-driver
hash -r
hermes computer-use doctor
```

A working bridge reports `cua-driver ... on win32`, `UIAutomation is reachable`, and `Windows Graphics Capture will succeed`. This is stronger evidence than merely finding the executable.

### Step 3.5: Validate the manifest execution domain

A passing `doctor` is necessary but not sufficient. The wrapper can launch the native binary successfully while `cua-driver manifest` advertises its Win32 executable path back to Hermes. If the POSIX backend accepts that drive-letter path literally, MCP startup fails even though every doctor check passes.

Inspect the manifest and require its `mcp_invocation.command` to remain executable from WSL. Preserve manifest arguments, but retain the already-resolved WSL wrapper when the command is a generic self-reference or a Win32 absolute path to the same driver. Continue honoring genuinely different helper commands.

After correcting the boundary, verify a real end-to-end operation — `computer_use(action="list_apps")` followed by a capture of a native Windows app — instead of stopping at `doctor`.

See `references/computer-use-wsl-win32-manifest.md` for the backend rule, wrapper fallback, regression cases, end-to-end verification, and safe client-session recovery.

### Step 4: Start a fresh Hermes session

Tool schemas are selected when a Hermes conversation starts. If the current session began before the binary existed, `computer_use` remains absent from that conversation even though `hermes tools list` shows the toolset enabled. Start `/new` (or exit and relaunch Hermes) so the next session loads the tool.

For direct bridge verification before restarting Hermes:

```bash
cua-driver call get_accessibility_tree '{}'
```

This should return native Windows processes and visible windows. Do not install only the Linux driver and assume it can drive Win32; the reported platform in `hermes computer-use doctor` must be `win32` for this pattern.

## 5. Gateway Migration: Windows → WSL

### Step 1: Stop and disable the Windows gateway

```powershell
schtasks /end /tn "Hermes_Gateway"
schtasks /change /tn "Hermes_Gateway" /disable
```

### Step 2: Enable systemd in WSL

Edit `/etc/wsl.conf` inside WSL:
```ini
[boot]
systemd=true
```

Requires WSL restart to take effect: `wsl.exe --shutdown`

### Step 3: Create systemd user service

```ini
# ~/.config/systemd/user/hermes-gateway.service
[Unit]
Description=Hermes Agent Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PATH=/home/muniz/.local/bin:/home/muniz/.hermes/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/muniz/.hermes/hermes-agent/venv/bin/hermes gateway run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable hermes-gateway
loginctl enable-linger $USER   # survive logout
```

### Step 4: Immediate start (before WSL reboot)

Systemd won't be active until WSL reboots. For NOW, use a Windows Scheduled Task that keeps `wsl.exe` alive:

**`start-wsl-gateway.bat`**:
```batch
@echo off
REM Keep wsl.exe alive to prevent WSL VM termination
wsl.exe -d Ubuntu-24.04 -u muniz --exec bash -c "export PATH=/home/muniz/.local/bin:/home/muniz/.hermes/bin:$PATH && /home/muniz/.hermes/hermes-agent/venv/bin/hermes gateway run >> /home/muniz/.hermes/logs/gateway.log 2>&1"
```

```powershell
schtasks /create /tn "Hermes_Gateway_WSL" `
  /tr "C:\Users\muniz\AppData\Local\hermes\start-wsl-gateway.bat" `
  /sc onstart /delay 0001:00 /ru muniz /f
schtasks /run /tn "Hermes_Gateway_WSL"
```

**Critical**: The `wsl.exe` process MUST stay alive. When all `wsl.exe` instances exit, WSL2 terminates all Linux processes including the gateway. The `.bat` file above runs `wsl.exe` in the foreground (no `start /b`, no `nohup &` with exit) — this is intentional. The Scheduled Task keeps one `wsl.exe` handle open for the lifetime of the gateway.

### Verification

```bash
# Inside WSL
ps aux | grep "[h]ermes gateway"
grep "registered.*tool.*from.*server" ~/.hermes/logs/agent.log | tail -5
```

Expected: registered tools from the configured MCP servers; use the current runtime's actual counts rather than hard-coding a historical total.

## 5.5. Sending through the WSL gateway from a Windows session

A native Windows CLI can correctly report “no gateway process” while the authoritative gateway is healthy inside WSL. Do not restart or enable the disabled Windows Scheduled Task until checking the intended WSL runtime.

1. Inspect both runtimes:
   - Windows: `hermes gateway status`
   - WSL: `wsl.exe -d <distro> -- bash -lc 'hermes gateway status && hermes status --all'`
2. Read `Messaging Platforms` from the WSL `hermes status --all` output to identify the configured home platform. Do not guess a chat ID from memory.
3. Stage the report as a text file. A Windows path such as `C:\Users\<user>\AppData\Local\Temp\report.txt` is `/mnt/c/Users/<user>/AppData/Local/Temp/report.txt` inside WSL.
4. Send with the WSL configuration:

```powershell
wsl.exe -d Ubuntu-24.04 -- bash -lc `
  'hermes send --to telegram --subject "[Report]" --file /mnt/c/Users/<user>/AppData/Local/Temp/report.txt --json'
```

5. Treat exit code 0 alone as insufficient. Require JSON `success:true` plus the expected `platform`, `chat_id`, and returned `message_id` before reporting delivery.
6. `hermes send` reuses platform credentials and, for bot-token platforms, does not require the gateway process itself to be running. Still inspect the WSL runtime first so the message uses the authoritative config/home channel.
7. Keep secrets and private identifiers out of staged reports. Prefer links/slugs to authoritative Obsidian/GBrain records instead of duplicating sensitive raw inventories.

See `references/gateway-cross-runtime-send.md` for the verified recipe and failure-avoidance checklist.

## 6. Env Var Auth for HTTP MCP Servers

When `config.yaml` uses `${VAR_NAME}` expansion for MCP auth headers:

```yaml
mcp_servers:
  gbrain_http:
    url: https://mcp.atius.com.br/gbrain
    headers:
      Authorization: Bearer ${ATIUS_MCP_TOKEN}
```

The variable MUST exist in `~/.hermes/.env`, NOT just in the shell environment. The gateway reads `.env` at startup, not the shell profile.

**Pitfall**: `hermes config` output redacts env var values with `...` (e.g. `${ATIU...KEN}`). Use `od -c` or `cat -v` on the raw file to see the actual variable name.

**Diagnostic**: 401 errors in agent.log mean the token wasn't expanded. Check:
1. `.env` file exists and contains the variable
2. Variable name matches exactly (case-sensitive)
3. No trailing whitespace in `.env` lines

## 7. Key Paths Reference

| What | Windows | WSL |
|------|---------|-----|
| Hermes config | `C:\Users\<user>\AppData\Local\hermes\config.yaml` | `~/.hermes/config.yaml` (copy) |
| Hermes .env | `C:\Users\<user>\AppData\Local\hermes\.env` | `~/.hermes/.env` (copy) |
| Hermes binary | `~/.local/bin/hermes` (via pip) | `~/.hermes/hermes-agent/venv/bin/hermes` |
| Gateway logs | `C:\Users\<user>\AppData\Local\hermes\logs\` | `~/.hermes/logs/` |
| MCP stderr | `~/.hermes/logs/mcp-stderr.log` | `~/.hermes/logs/mcp-stderr.log` |
| agent.log | `~/.hermes/logs/agent.log` | `~/.hermes/logs/agent.log` |
| systemd service | N/A | `~/.config/systemd/user/hermes-gateway.service` |

## 8. Gateway SIGTERM Loop (Troubleshooting)

**Symptom**: Gateway restarts every ~35 seconds. Log fills with `Received SIGTERM — initiating shutdown` with `under_systemd=yes` and `parent_pid=1`.

**Root cause**: A manually-created systemd service file at `/etc/systemd/system/hermes-gateway.service` with problematic parameters (`KillMode=mixed`, `KillSignal=SIGTERM`, `StartLimitIntervalSec=0`, `--replace` in ExecStart) that diverges from what `hermes gateway install` generates. The service was created by hand instead of via the supported `hermes gateway install --system` command.

**Diagnostic checklist** (run in order):

1. **Check gateway status** — the built-in status command detects outdated service definitions:
   ```bash
   hermes gateway status
   ```
   If it shows `⚠ Installed gateway service definition is outdated`, the unit file is stale.

2. **Count SIGTERM events** to gauge severity:
   ```bash
   grep -c "Received SIGTERM" ~/.hermes/logs/gateway.log
   ```

3. **Check SIGTERM timing pattern** — if they're evenly spaced (~35s), it's a systemd restart loop:
   ```bash
   grep "Received SIGTERM" ~/.hermes/logs/gateway.log | awk '{print $1, $2}' | sort | uniq -c | sort -rn | head -15
   ```

4. **Compare the service file against known-good** — the current file likely has `--replace`, `KillMode=mixed`, `KillSignal=SIGTERM`, and `StartLimitIntervalSec=0`:
   ```bash
   cat /etc/systemd/system/hermes-gateway.service
   systemctl show hermes-gateway.service -p NRestarts
   ```

5. **Check systemd journal** for the unit's lifecycle — look for the pattern of start→SIGTERM→exit code 1→restart:
   ```bash
   journalctl -u hermes-gateway.service --no-pager | grep -E "SIGTERM|Starting" | tail -20
   ```

6. **Check for competing gateway instances** — a Scheduled Task `.vbs` script may be launching a second `hermes gateway run` (without `--replace`) that conflicts:
   ```bash
   ps aux | grep "gateway"
   cat /mnt/c/Windows/System32/Tasks/Hermes_Gateway_WSL | iconv -f UTF-16 -t UTF-8
   ```

**How the loop works mechanically**:
- The manually-created service uses `KillMode=mixed` + `KillSignal=SIGTERM` + `StartLimitIntervalSec=0`
- Systemd sends SIGTERM to the main PID after it detects the service stopped (or some external trigger)
- Gateway exits with code 1 (`signal-initiated shutdown`)
- `Restart=on-failure` + `RestartSec=10` restarts it
- `StartLimitIntervalSec=0` removes the rate-limit brake — infinite loop

**Fix** — use the supported install command which auto-generates the correct unit:

```bash
# Option A (fastest — refreshes the unit in place):
sudo hermes gateway restart --system

# Option B (clean reinstall):
sudo hermes gateway uninstall --system
sudo hermes gateway install --system --run-as-user $USER --start-now
```

**Verification after fix**:
```bash
hermes gateway status               # should show no "outdated" warning
systemctl show hermes-gateway.service -p NRestarts -p ActiveState
grep -c "Received SIGTERM" ~/.hermes/logs/gateway.log  # should not increase
```

See `references/gateway-sigterm-loop-diag.md` for the full session transcript and raw diagnostic output.

## 9. Common Pitfalls

1. **Manually-created systemd service file causes SIGTERM loop** — never hand-write `/etc/systemd/system/hermes-gateway.service`. Always use `hermes gateway install --system` which generates the correct unit with proper `Type=simple`, no `KillMode` overrides, no `--replace` in ExecStart, and rate-limited restart behavior. A manually-crafted file with `KillMode=mixed`, `KillSignal=SIGTERM`, and `StartLimitIntervalSec=0` will death-loop the gateway indefinitely.

2. **`nohup ... &` inside `wsl.exe -c '...'` doesn't persist** — the bash process exits, WSL kills children. Use a Scheduled Task with foreground `wsl.exe` or systemd.

3. **`hermes config set mcp_servers.*` may silently not write** — verify with `grep` after setting. If it didn't stick, edit `config.yaml` directly with sed or Python.

4. **`sed` + Windows paths in YAML = escaping hell** — the backslash escape chains (`\\\\\\\\` in bash → `\\\\` in sed → `\\` in file) often fail. Prefer Python `data.replace()`.

5. **PEP 668 blocks `pip install --user` on Ubuntu 24.04** — the Hermes installer uses `uv` with its own Python 3.11, bypassing the system Python entirely.

6. **`connect_timeout: 10` is too short for `npx`-based MCP servers** — first run downloads the npm package which can take 30-60s. Use `connect_timeout: 60`.

7. **A local Hermes session can look like a config/tool problem when the real issue is a corrupted `state.db`** — if `session_search` throws FTS corruption errors, `hermes sessions stats` dies with `sqlite3.DatabaseError: database disk image is malformed`, or `hermes doctor` flags `state.db` write-health / FTS corruption, stop treating it as a model/router/MCP issue. Backup `C:\Users\<user>\AppData\Local\hermes\state.db` first, then run `hermes doctor` and `hermes sessions repair`. If repair also fails with `database disk image is malformed`, preserve both the original DB and the `.malformed-backup-*` copy and switch to a SQLite salvage/rebuild workflow rather than repeated Hermes-level retries.

8. **Detached MCP cleanup can throw `RuntimeError: Event loop is closed` on Windows Hermes shutdown** — if the exit traceback points at `tools/mcp_tool.py` waiting helpers and `task.cancel()`, patch the cleanup path to tolerate loop teardown instead of treating it as an MCP credential or transport issue. Add a best-effort cancel helper that checks `task.get_loop().is_closed()` and swallows `RuntimeError` during final cleanup of lifecycle waiter tasks.

## See Also

- `references/wsl-gateway-setup-session.md` — Full session transcript of the WSL gateway migration (2026-07-13)
- `references/gateway-sigterm-loop-diag.md` — SIGTERM death-loop diagnostic session (2026-07-19): root cause, diagnostic commands, raw log excerpts, and fix procedure
- `references/gateway-cross-runtime-send.md` — verified Windows-to-WSL delivery with `hermes send`, home-channel discovery, path translation, and JSON receipt validation
- `references/runtime-home-isolation-and-mcp-shutdown.md` — dual-home isolation, session DB corruption symptoms, `session_search`/FTS failure signs, and MCP shutdown traceback fix pattern
- `skill_view(name="hermes-wslinterop-restore")` — dedicated fix path for missing `/proc/sys/fs/binfmt_misc/WSLInterop`, stale-cache env sync fallback, and persistent WSL interop self-heal
- `skill_view(name="hermes-agent")` — Hermes Agent core skill (MCP config reference, CLI commands)
- `skill_view(name="msys2-shells-windows")` — MSYS2 zsh setup on Windows (alternative to WSL)
