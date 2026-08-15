# HTTP MCP Troubleshooting: CancelledError / connect_timeout

## Session trace (2026-07-13)

Debugged why `gbrain_http` and `obsidian_http` MCP servers (HTTP/StreamableHTTP transport through `https://mcp.atius.com.br/`) never appeared as available tools despite being configured and enabled.

## Environment

- Hermes v0.18.2
- Windows 11 host
- 12 MCP servers total: 8 stdio (OCI), 2 HTTP (gbrain/obsidian), 1 HTTP (chrome-devtools), 1 stdio (ijfw-memory)
- `ATIUS_MCP_TOKEN` stored as Windows User Environment Variable (HKCU\Environment)

## Diagnostic steps

### 1. MCP list showed servers as enabled

```
hermes mcp list
  gbrain_http      https://mcp.atius.com.br/...   all   ✓ enabled
  obsidian_http    https://mcp.atius.com.br/...   all   ✓ enabled
```

### 2. MCP test succeeded individually

```
hermes mcp test gbrain_http
  ✓ Connected (1390ms)
  ✓ Tools discovered: 82

hermes mcp test obsidian_http
  ✓ Connected (1500ms)
  ✓ Tools discovered: 16
```

### 3. All tools enabled in per-server config

```
hermes mcp configure gbrain_http
  Currently 82/82 tools enabled
hermes mcp configure obsidian_http
  Currently 16/16 tools enabled
```

### 4. Python introspection revealed `status=failed`

```python
from tools.mcp_tool import get_mcp_status, discover_mcp_tools
discover_mcp_tools()
for s in get_mcp_status():
    print(f'{s["name"]}: {s["status"]}, tools={s["tools"]}')

# Result:
#   gbrain_http: connected=False, tools=0, status=failed
#   obsidian_http: connected=False, tools=0, status=failed
```

### 5. Error detail: CancelledError

```python
from tools import mcp_tool as mt
with mt._lock:
    for name, err in mt._server_connect_errors.items():
        print(f'{name}: {type(err).__name__}')

# Result:
#   gbrain_http: CancelledError
#   obsidian_http: CancelledError
```

## Root cause

The `connect_timeout: 3` (3 seconds) configured for both HTTP servers was insufficient during parallel MCP discovery.

The Hermes code connects to all MCP servers in parallel via `asyncio.gather`. Each server has its own `connect_timeout` used in an `asyncio.wait_for` wrapper:

```python
# mcp_tool.py:4850-4853
connect_timeout = config.get("connect_timeout", _DEFAULT_CONNECT_TIMEOUT)
server = await asyncio.wait_for(
    _connect_server(name, config),
    timeout=connect_timeout,
)
```

With 12 servers connecting simultaneously (8 OCI stdio + 3 HTTP + 1 ijfw), the HTTP servers' 3s timeout was tight. The actual MCP handshake (initialize + tool discover) over HTTPS through the proxy took ~1.1-1.5s in isolation, but under parallel load the cumulative pressure caused timeout.

The `CancelledError` is caught at line 4946-4957 and logged at DEBUG level only — no visible error to the user.

## Fix

```bash
hermes config set mcp_servers.gbrain_http.connect_timeout 15
hermes config set mcp_servers.obsidian_http.connect_timeout 15
```

The `hermes config set nested.key.value` syntax correctly writes to `mcp_servers.<name>.connect_timeout` in `config.yaml`.

The `patch` tool cannot write to `config.yaml` (security restriction — "Refusing to write to Hermes config file"). Use `hermes config set` instead.

## Post-fix verification

```
hermes mcp test gbrain_http    → Connected (1141ms), 82 tools
hermes mcp test obsidian_http  → Connected (1500ms), 16 tools
```

Tools become available in the NEXT session (/new or fresh hermes start), not retroactively in the current session.

## Windows env var note

Execute_code sandboxes do NOT inherit Windows User-level environment variables (HKCU\Environment). When testing MCP discovery in an isolated Python script:

```python
import subprocess
r = subprocess.run(['powershell','-Command',
    '[System.Environment]::GetEnvironmentVariable("ATIUS_MCP_TOKEN","User")'],
    capture_output=True, text=True)
os.environ['ATIUS_MCP_TOKEN'] = r.stdout.strip()
```

Otherwise `${ATIUS_MCP_TOKEN}` remains unresolved and the Authorization header becomes the literal string `Bearer ${ATIUS_MCP_TOKEN}`, which produces HTTP 401 from the proxy.
