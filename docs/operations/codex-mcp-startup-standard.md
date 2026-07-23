# Codex MCP Startup Standard

Status: active on `GIOVANNI-W11-PC` since 2026-07-05.

Detailed MCP protocol, topology, validation, and production behavior for the
shared ATIUS HTTP MCP endpoints live in
[Codex ATIUS HTTP MCP Contract](./codex-gbrain-obsidian-mcp.md).

## Goal

Keep normal Codex startup lean. MCPs that depend on external services, browsers,
OCI stacks, or secrets must not block the default boot path.

Default `C:\Users\muniz\.codex\config.toml` should keep only:

- `node_repl`
- `gbrain_http`
- `obsidian_http`
- `oci_admin_http`

The three ATIUS HTTP MCPs are the approved operational exceptions and share
the Vault-backed `ATIUS_MCP_TOKEN`. The GitHub MCP may still appear from the
installed GitHub plugin. Other heavy or externally-dependent MCPs belong in
opt-in templates or launchers. Chrome DevTools, `ijfw-memory`, OpenAI Developer
Docs, Cloudflare API, local Oracle OCI MCPs, Playwright, filesystem, and lab
servers must not be added to the default `config.toml`.

## Current Layout

Backups created during the 2026-07-05 fix:

```text
C:\Users\muniz\.codex\backups\config.toml.phase43-mcp-split-20260705-073221.bak
C:\Users\muniz\.codex\backups\cloudflare-plugin.mcp.phase43-disable-20260705-073221.json.bak
/root/atius-vault-export-env.phase43-20260705-073221.bak on atius-srv-3
```

Optional MCP template files:

```text
C:\Users\muniz\.codex\knowledge-mcp.config.toml
C:\Users\muniz\.codex\browser-mcp.config.toml
C:\Users\muniz\.codex\memory-mcp.config.toml
C:\Users\muniz\.codex\docs-mcp.config.toml
C:\Users\muniz\.codex\oci-mcp.config.toml
C:\Users\muniz\.codex\cloud-ops-mcp.config.toml
C:\Users\muniz\.codex\lab-mcp.config.toml
```

Codex `0.142.5` accepts `-c mcp_servers...` overrides, but `codex mcp list`
does not reliably prove that `-p <profile>` loaded MCP profile files. Treat the
files above as local templates plus documentation until profile loading is
verified by a real runtime session.

## Cloudflare

The Cloudflare plugin MCP manifest was disabled without removing Cloudflare
skills:

```text
C:\Users\muniz\.codex\plugins\cache\openai-curated\cloudflare\bd2122cb\.mcp.json
C:\Users\muniz\.codex\plugins\cache\openai-curated-remote\cloudflare\0.1.2\.mcp.json
```

Current content should be:

```json
{ "mcpServers": {} }
```

Use the launcher when Cloudflare API MCP is needed:

```powershell
codex-cloud-ops mcp list
codex-cloud-ops
```

`codex-cloud-ops` loads `CF_GLOBAL_API_KEY` from the machine secrets vault into
the child Codex process only. It does not persist or print the value.
It also re-disables an auto-restored Cloudflare plugin manifest before starting
Codex, so the Vault-backed launcher remains the only Cloudflare MCP path.

For any other MCP or CLI that needs credentials, consult
[Atius Automation Secret Registry](../security/atius-automation-secret-registry.md)
first and load the exact `atius-vault-env <profile>` profile in the child
process. Do not depend on GBrain, Obsidian, `.zshrc`, `.env`, copied tokens, or
the parent Codex process environment as the credential source.

Wrapper paths:

```text
C:\Users\muniz\.local\bin\atius-vault-env.ps1
C:\Users\muniz\.local\bin\atius-vault-env.cmd
C:\Users\muniz\.local\bin\codex-cloud-ops.ps1
C:\Users\muniz\.local\bin\codex-cloud-ops.cmd
```

## Smoke

Run baseline:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile baseline
```

Expected baseline:

```text
codex-doctor: ok
codex-mcp-list: ok, canonical ATIUS HTTP MCPs present and retired aliases absent
```

Run optional checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile knowledge-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile browser-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile memory-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile docs-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile oci-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile cloud-ops-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile lab-mcp
```

Observed 2026-07-22:

- `knowledge-mcp`: validate `ATIUS_MCP_TOKEN`, the three canonical registry
  names, public GBrain health
  `https://mcp.atius.com.br/gbrain/health` when exposed, MCP `initialize` on
  `https://mcp.atius.com.br/gbrain`, and session-aware MCP `initialize` on
  `https://mcp.atius.com.br/obsidian`. It also validates anonymous `401`,
  authenticated `initialize => 200`, identity `oci-admin`, and nine tools on
  `https://mcp.atius.com.br/oci-admin`.
- `gbrain`: SRV-1 HTTP MCP remains on local backend `127.0.0.1:3131`; the
  standard client path is the public edge, not the old SSH or wg0-only route.
  `POST initialize` is the canonical smoke; `/gbrain/health` may be absent on
  some edge revisions and should not be treated as the primary gate.
- `obsidian`: `10.11.1.11:27124` is the DRG primary private path; public Codex MCP uses `https://mcp.atius.com.br/obsidian`.
- `browser-mcp`: Chrome executable and `npx` present.
- `oci-mcp`: legacy opt-in local `uv`/`oracle-oci-mcp` toolchain and OCI config;
  this is separate from the canonical remote `oci_admin_http` entry.
- `lab-mcp`: `npx` present.
- `cloud-ops-mcp`: process env is `missing-env`, but `CF_GLOBAL_API_KEY` is available via `atius-vault-env cloudflare`; use `codex-cloud-ops`.

HTTP contract standard (validated 2026-07-10):

- Raw `GET`/`HEAD` to `/gbrain`, `/obsidian`, and `/oci-admin` should return
  `405` with `Allow: POST, DELETE`.
- Canonical MCP smoke is not raw `GET`; use authenticated `POST initialize` with:
  - `Authorization: Bearer $ATIUS_MCP_TOKEN`
  - `Content-Type: application/json`
  - `Accept: application/json, text/event-stream`
- Expected live results:
  - `gbrain`: `initialize => 200`, `tools/list => 200`
  - `obsidian`: `initialize => 200`, `notifications/initialized => 202`, `tools/list => 200`
  - `oci-admin`: anonymous `initialize => 401`; authenticated
    `initialize => 200`, `serverInfo.name=oci-admin`, `tools/list => 200/9`

## Rollback

Restore the Codex config:

```powershell
Copy-Item -LiteralPath C:\Users\muniz\.codex\backups\config.toml.phase43-mcp-split-20260705-073221.bak -Destination C:\Users\muniz\.codex\config.toml -Force
```

Restore the Cloudflare plugin MCP manifest:

```powershell
Copy-Item -LiteralPath C:\Users\muniz\.codex\backups\cloudflare-plugin.mcp.phase43-disable-20260705-073221.json.bak -Destination C:\Users\muniz\.codex\plugins\cache\openai-curated\cloudflare\d6169bef\.mcp.json -Force
```

Restore the remote Vault exporter:

```powershell
ssh -T -i C:\Users\muniz\.ssh\private.pem ubuntu@10.100.100.1 "ssh -T atius-srv-3-vpn 'sudo cp /root/atius-vault-export-env.phase43-20260705-073221.bak /usr/local/sbin/atius-vault-export-env && sudo chmod 700 /usr/local/sbin/atius-vault-export-env'"
```

Do not paste secret values into chat, docs, shell history, Obsidian, GBrain, or
Git logs.

For GBrain service validation, prefer `systemctl --user show
gbrain-http-mcp.service -p ActiveState -p SubState -p MainPID` plus
`curl http://127.0.0.1:3131/health`. Avoid copying full `systemctl status`
output to shared logs because the startup banner may include administrative
token material.
