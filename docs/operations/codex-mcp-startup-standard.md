# Codex MCP Startup Standard

Status: active on `GIOVANNI-W11-PC` since 2026-07-05.

Detailed MCP protocol, topology, validation, and production behavior for the
shared GBrain/Obsidian knowledge endpoints live in
[Codex GBrain + Obsidian MCP Contract](./codex-gbrain-obsidian-mcp.md).

## Goal

Keep normal Codex startup lean. MCPs that depend on external services, browsers,
OCI stacks, or secrets must not block the default boot path.

Default `C:\Users\muniz\.codex\config.toml` should keep only:

- `node_repl`
- `gbrain`

The GitHub MCP may still appear from the installed GitHub plugin. Heavy or
externally-dependent MCPs belong in opt-in templates or launchers.

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
C:\Users\muniz\.codex\plugins\cache\openai-curated\cloudflare\d6169bef\.mcp.json
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
codex-doctor: ok, configured_mcp_servers=2
codex-mcp-list: ok, default list excludes heavy optional MCPs
```

Run optional checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile knowledge-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile browser-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile oci-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile cloud-ops-mcp
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-mcp-startup-smoke.ps1 -Profile lab-mcp
```

Observed 2026-07-05:

- `knowledge-mcp`: validate `ATIUS_MCP_TOKEN`, public GBrain health
  `https://mcp.atius.com.br/gbrain/health` when exposed, MCP `initialize` on
  `https://mcp.atius.com.br/gbrain`, and session-aware MCP `initialize` on
  `https://mcp.atius.com.br/obsidian`.
- `gbrain`: SRV-1 HTTP MCP remains on local backend `127.0.0.1:3131`; the
  standard client path is the public edge, not the old SSH or wg0-only route.
  `POST initialize` is the canonical smoke; `/gbrain/health` may be absent on
  some edge revisions and should not be treated as the primary gate.
- `browser-mcp`: Chrome executable and `npx` present.
- `oci-mcp`: `uv`, `oracle-oci-mcp`, and OCI config present.
- `lab-mcp`: `npx` present.
- `cloud-ops-mcp`: process env is `missing-env`, but `CF_GLOBAL_API_KEY` is available via `atius-vault-env cloudflare`; use `codex-cloud-ops`.

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
