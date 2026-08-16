---
name: gbrain-mcp-operations
description: Use when auditing, configuring, or troubleshooting GBrain MCP access across Hermes/Codex clients and remote servers, especially thin-client setups that point to an authoritative GBrain host.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gbrain, mcp, hermes, codex, ssh, thin-client, devops]
---

# GBrain MCP Operations

Use this skill when the task is to verify, compare, or improve GBrain MCP configuration across Hermes Agent, Codex, and multiple servers.

## Goal

Establish which machine is the authoritative GBrain, confirm each client points to it, verify MCP connectivity with real commands, and recommend the safest maintainable connection pattern.

## Core workflow

1. Identify the authoritative GBrain host.
   - Prefer direct evidence from config and runtime tests, not assumptions.
   - On the authoritative host, direct local execution is preferred:
     - `command: /home/ubuntu/.local/bin/gbrain`
     - `args: ["serve"]`

2. Inventory local client configuration without exposing secrets.
   - Hermes config usually lives at:
     - Windows: `C:\Users\<user>\AppData\Local\hermes\config.yaml`
     - Linux: `~/.hermes/config.yaml`
   - Codex config usually lives at:
     - Windows: `C:\Users\<user>\.codex\config.toml`
     - Linux: `~/.codex/config.toml`
   - Redact Authorization headers, API keys, tokens, passwords, bearer tokens, and database URLs before reporting.

3. Verify with CLI tests, not just config reads.
   - Hermes:
     - `hermes mcp list`
     - `hermes mcp test gbrain`
   - Codex:
     - `codex mcp list`
     - `codex mcp get gbrain` when available and not blocked by TTY constraints.
   - Direct transport smoke test:
     - run the exact configured command with `--version` only when the wrapper permits it; restricted wrappers may intentionally allow only `serve`.

4. For remote servers, inspect both Hermes and Codex.
   - Check whether Hermes and Codex are installed for the target user.
   - Read only relevant config blocks around `mcp_servers.gbrain`.
   - Run `hermes mcp test gbrain` where Hermes exists.
   - Run `codex mcp list` where Codex exists.

5. Compare transport patterns.
   - Best on the authoritative host: direct local `gbrain serve`.
   - Best on thin clients: a local restricted wrapper/bridge using a dedicated SSH key, pointing to the authoritative host.
   - Acceptable: explicit SSH in MCP config to the authoritative host.
   - Less ideal: public IP and broad private key when a private/VPN IP and dedicated MCP key are available.

## Recommended thin-client pattern

Prefer a local wrapper that hides SSH details from each MCP client and uses a dedicated restricted key.

Windows wrapper example shape:

```bat
@echo off
"C:\Windows\System32\OpenSSH\ssh.exe" -i "%USERPROFILE%\.ssh\id_ed25519_gbrain_mcp" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=15 -o ServerAliveCountMax=2 ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain %*
```

Linux wrapper example shape:

```sh
#!/usr/bin/env sh
set -eu
exec ssh -i "$HOME/.ssh/id_ed25519_gbrain_mcp" \
  -o IdentitiesOnly=yes \
  -o BatchMode=yes \
  -o ConnectTimeout=5 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=2 \
  ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain "$@"
```

Then configure MCP clients to call the wrapper with `serve`.

## Pitfalls

- Do not treat `command not found` on one host as durable proof that a tool is globally unavailable. It may only be absent from that user PATH.
- Restricted GBrain wrappers may reject `--version`; that can be correct. Verify MCP with `serve` through `hermes mcp test gbrain` or `codex mcp list` instead.
- Avoid reporting secrets from config snippets. Redact before summarizing.
- Public IP + broad SSH key works, but is usually inferior to private/VPN IP + dedicated MCP key + `IdentitiesOnly=yes`.
- Do not conflate Obsidian REST MCP failures with GBrain MCP failures; audit them separately.
- When calling `gbrain timeline-add` or other commands through a remote shell, quote every argument or use argv-style subprocess execution. Backticks in timeline text can be interpreted by the remote shell and create false `command not found` noise even if the GBrain write itself succeeded.
- **`connect_timeout: 3` is too tight for HTTP MCP servers when 10+ MCP servers connect in parallel.** The parallel discovery has a 120s outer timeout but individual servers use their own `connect_timeout`. If that is too short, the server gets `CancelledError` during the `asyncio.wait_for` handshake. Symptoms: `hermes mcp list` shows the server as `✓ enabled`, but `hermes mcp test <name>` succeeds while the tools never appear in the session. Fix with `hermes config set mcp_servers.<name>.connect_timeout 15`.
- **HTTP MCP `CancelledError` is silent.** The error is caught and logged at DEBUG level, not shown to the user. If HTTP MCP tools aren't appearing, check `status=failed` via Python introspection (see diagnostics reference).

## Write-path resilience

`put_page` performs chunking/embedding and may time out while reads remain healthy. Handle this as a recoverable write-path condition:

1. After any timeout, call `get_page` before retrying; the write may have committed after the client deadline.
2. If the page is absent and the server reports `embedding governor queue timeout before dispatch`, stop blind `put_page` retries.
3. Preserve high-value facts on an existing project/incident with several small `add_timeline_entry` calls, then verify with `get_timeline`.
4. For a new master page, stage Markdown on the authoritative host and run `/home/ubuntu/.local/bin/gbrain capture --file ... --slug ... --type ... --json` through the configured SSH alias.
5. Treat CLI stdout as a receipt, not final proof. `written:false` can mean “no file mirror” on a SQL-backed brain while the page was accepted; always confirm with `get_page`.
6. Add explicit graph relationships with `add_link` and verify with `traverse_graph`.

Prefer a compact master page plus thematic timeline/reference entries over a single oversized page. Keep independent provenance tags for inventory, decisions, telemetry, research, and plans.

See `references/write-fallback-embedding-governor.md` for the exact fallback and verification sequence.

## Verification checklist

For each host/client combination, report:

- Host and user inspected.
- Whether Hermes exists and whether `hermes mcp test gbrain` connects.
- Whether Codex exists and whether `codex mcp list` shows gbrain enabled.
- The configured target host/IP and remote command.
- Whether the path is direct-local, wrapper, or explicit SSH.
- Whether it points to the authoritative GBrain host.
- Recommended correction, if any.

## Diagnostics: HTTP MCP tools not appearing in session

When HTTP/StreamableHTTP MCP servers (configured with `url:` instead of `command:`) show as `✓ enabled` in `hermes mcp list` and pass `hermes mcp test <name>` but their tools never appear in the agent's tool list:

### 1. Check server status

```bash
hermes mcp list
hermes mcp test <name>
hermes mcp configure <name>  # press Enter to see enable/skip counts
```

### 2. Check for CancelledError (most common cause)

When discovery ran but the `connect_timeout` was too tight, the server shows `status=failed`. Introspect from Python:

```python
import os
os.environ['HERMES_HOME'] = '~/.hermes'  # or your Hermes home
from tools.mcp_tool import discover_mcp_tools, get_mcp_status
from tools import mcp_tool as mt

# Force fresh discovery
mt._servers.clear()
mt._server_connecting.clear()
mt._server_connect_errors.clear()
tools = discover_mcp_tools()

# Show status
for s in get_mcp_status():
    print(f'{s["name"]}: {s["status"]}, tools={s["tools"]}')

# Show specific error
with mt._lock:
    for name, err in mt._server_connect_errors.items():
        print(f'{name}: {type(err).__name__}: {err}')
```

`CancelledError` on HTTP servers means `connect_timeout` was reached during the MCP handshake.

### 3. Fix connect_timeout

```bash
hermes config set mcp_servers.<name>.connect_timeout 15
```

Recommended value: 15s for HTTP MCP through a proxy/TLS endpoint (handshake + tool discovery in serial takes 1-2s, but parallel load with 10+ servers amplifies latency).

### 4. Verify in a fresh session

The change applies on next `hermes` startup / `/new`. The current session retains stale cached state.

### 5. Check Windows User Environment Variable resolution

On Windows, tokens stored as User-level environment variables (HKCU\Environment) are NOT inherited by `execute_code` sandbox processes or test scripts. The real `hermes` session inherits them fine. To verify in an isolated context, explicitly propagate:

```python
import subprocess
r = subprocess.run(['powershell','-Command',
    '[System.Environment]::GetEnvironmentVariable("VAR_NAME","User")'],
    capture_output=True, text=True)
os.environ['VAR_NAME'] = r.stdout.strip()
```

## References

- `references/giovanni-gbrain-mcp-audit-2026-07-03.md` — concrete audit findings and preferred standard from the GIOVANNI-W11-PC / atius-srv fleet review.
- `references/http-mcp-troubleshooting.md` — detailed session trace and root-cause analysis for HTTP MCP `CancelledError` and `connect_timeout` debugging.
- `references/write-fallback-embedding-governor.md` — safe fallback from `put_page` timeouts to timeline entries and authoritative-host `capture --file`, with mandatory read-back verification.
