# WSL Gateway Setup Session — 2026-07-13

Full transcript of migrating Hermes Gateway from Windows Scheduled Task to WSL2,
fixing chrome-devtools MCP, and achieving cross-platform MCP server connectivity.

## Environment

- **Windows**: 11, git-bash/MSYS shell, Node.js v24.18.0 via fnm
- **WSL**: Ubuntu 24.04 LTS, systemd not initially enabled
- **Hermes**: v0.18.2 (Windows), v0.18.2 fresh install (WSL)
- **Model**: deepseek-v4-pro via Atius Router (custom provider)

## Initial State

- `chrome-devtools (stdio) — failed` in session startup
- Gateway running as Windows Scheduled Task `Hermes_Gateway`
- `gbrain_http` and `obsidian_http` working (82 + 18 tools) in CLI session
- `config.yaml` had `mcp_servers.chrome-devtools.connect_timeout: 10`

## Fixes Applied

### 1. chrome-devtools MCP

- Package: `chrome-devtools-mcp` v1.5.0 (Google, NOT `@anthropic-ai/...`)
- Installed globally: `npm install -g chrome-devtools-mcp@latest`
- Config change: `connect_timeout: 10` → `connect_timeout: 60` (via sed)
- Registers 29 tools when working

### 2. WSL Hermes Install

- Used `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
- Installed Python 3.11.15 (uv), Node.js 22.23.1, ripgrep, ffmpeg
- Cloned to `~/.hermes/hermes-agent`, venv at `venv/`
- Binary: `~/.hermes/hermes-agent/venv/bin/hermes`

### 3. Config Migration

- Copied `config.yaml` from `/mnt/c/Users/muniz/AppData/Local/hermes/` to `~/.hermes/`
- Copied `.env` (missing `ATIUS_MCP_TOKEN` initially — added later)
- Path fix for `ijfw-memory`: `C:\Users\muniz\.ijfw\...` → `/mnt/c/Users/muniz/.ijfw/...` (Python, not sed)

### 4. Auth Token Discovery

- Config showed `Authorization: Bearer ${ATIU...KEN}` (Hermes redaction)
- Actual var: `ATIUS_MCP_TOKEN` (discovered via `od -c`)
- Token was in shell env but NOT in `.env` — added to `.env` for gateway

### 5. Gateway Migration

- Disabled Windows Scheduled Task `Hermes_Gateway`
- Created `~/.config/systemd/user/hermes-gateway.service` (for post-reboot)
- Enabled `systemd=true` in `/etc/wsl.conf` (requires WSL restart)
- Created `start-wsl-gateway.bat` + Scheduled Task `Hermes_Gateway_WSL` (immediate)
- Key insight: `wsl.exe` must stay alive as foreground process

### 6. WSL Process Keepalive

The bat file runs `wsl.exe ... hermes gateway run` WITHOUT `start /b` or `& exit`.
This keeps one `wsl.exe` handle open, preventing WSL2 VM termination.
The Scheduled Task wraps this as a persistent launcher.

## Final State

```
WSL Gateway PID: 32941 (150MB RSS)

MCP servers:
  gbrain_http    (HTTP) — 82 tools  ✅
  obsidian_http  (HTTP) — 18 tools  ✅
  chrome-devtools (stdio) — 29 tools ✅
  ijfw-memory    (stdio) — 17 tools ✅
  ─────────────────────────────────────
  TOTAL: 146 tools from 4 servers
```

## Error Logs (for future reference)

### chrome-devtools timeout (initial failure)
```
WARNING tools.mcp_tool: MCP server 'chrome-devtools' initial connection failed
```
Root cause: `connect_timeout: 10` + npx download on first run.

### ijfw-memory path corruption
```
Error: Cannot find module '/mnt/c/Users/muniz/AppData/Local/hermes/C:\Users\muniz\.ijfw\mcp-server\src\server.js'
```
Root cause: Windows path survived sed replacement (cwd prepended).

### HTTP 401 on gbrain/obsidian
```
WARNING tools.mcp_tool: Failed to connect to MCP server 'gbrain_http': Client error '401 Unauthorized'
```
Root cause: `ATIUS_MCP_TOKEN` not in `.env` (only in shell env).

## Commands for Future Sessions

```bash
# Check WSL gateway health
wsl.exe -d Ubuntu-24.04 -- bash -c 'ps aux | grep "[h]ermes gateway"'

# Check MCP registration
wsl.exe -d Ubuntu-24.04 -- bash -c \
  'grep "registered.*tool.*from.*server" ~/.hermes/logs/agent.log | tail -5'

# Restart gateway (inside WSL)
pkill -f "hermes gateway"
# Scheduled Task will auto-restart, or run:
schtasks /run /tn "Hermes_Gateway_WSL"

# View gateway errors
wsl.exe -d Ubuntu-24.04 -- bash -c 'tail -50 ~/.hermes/logs/errors.log'

# View MCP stderr
wsl.exe -d Ubuntu-24.04 -- bash -c 'tail -50 ~/.hermes/logs/mcp-stderr.log'
```
