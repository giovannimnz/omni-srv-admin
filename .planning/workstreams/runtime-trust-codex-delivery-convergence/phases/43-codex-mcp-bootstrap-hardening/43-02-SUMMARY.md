---
phase: 43-codex-mcp-bootstrap-hardening
plan: 43-02
type: summary
status: completed
date: 2026-07-05
---

# 43-02 Summary

## Changes

- Split heavy MCPs out of `C:\Users\muniz\.codex\config.toml`.
- Default Codex config now keeps only `node_repl` and `gbrain` as configured MCP servers.
- Created optional MCP template files under `C:\Users\muniz\.codex\*.config.toml`.
- Disabled the Cloudflare plugin MCP manifest while preserving Cloudflare skills.
- Fixed `/usr/local/sbin/atius-vault-export-env` on `atius-srv-3`; the old script consumed stdin with a Python heredoc before reading Vault JSON.
- Added Windows wrappers:
  - `C:\Users\muniz\.local\bin\atius-vault-env.ps1`
  - `C:\Users\muniz\.local\bin\atius-vault-env.cmd`
  - `C:\Users\muniz\.local\bin\codex-cloud-ops.ps1`
  - `C:\Users\muniz\.local\bin\codex-cloud-ops.cmd`
- Added `scripts/codex-mcp-startup-smoke.ps1`.
- Added `docs/operations/codex-mcp-startup-standard.md`.
- Updated `docs/operations/codex-runtime-standard.md` and `docs/security/atius-secrets-vaults.md`.

## Validation

```text
codex doctor --json
overallStatus=ok
configured_mcp_servers=2
```

```text
codex mcp list
default configured MCPs: gbrain, node_repl
plugin MCPs: github
cloudflare-api absent from default
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile baseline
codex-doctor=ok
codex-mcp-list=ok
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile knowledge-mcp
obsidian-rest-reachability=ok
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile browser-mcp
chrome-executable=ok
npx=ok
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile oci-mcp
uv=ok
oracle-oci-mcp paths=ok
OCI config=ok
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile lab-mcp
npx=ok
```

```text
scripts/codex-mcp-startup-smoke.ps1 -Profile cloud-ops-mcp
profile-file=ok
CF_GLOBAL_API_KEY=missing-env in current process
CF_GLOBAL_API_KEY=available via atius-vault-env cloudflare
```

```text
codex-cloud-ops mcp list
cloudflare-api auth=Bearer token
bearer_token_env_var=CF_GLOBAL_API_KEY
```

## Backups

```text
C:\Users\muniz\.codex\backups\config.toml.phase43-mcp-split-20260705-073221.bak
C:\Users\muniz\.codex\backups\cloudflare-plugin.mcp.phase43-disable-20260705-073221.json.bak
/root/atius-vault-export-env.phase43-20260705-073221.bak on atius-srv-3
```

## Residual Risk

- `codex mcp list` in Codex `0.142.5` does not reliably prove that `-p <profile>` loaded MCP profile files; even a missing profile name is ignored. Use `-c` injection or the dedicated `codex-cloud-ops` launcher for Cloudflare until this behavior is fixed upstream or verified through a real runtime session.
- Optional template files are still useful as local source material and timeout policy, but not as the only activation mechanism.
