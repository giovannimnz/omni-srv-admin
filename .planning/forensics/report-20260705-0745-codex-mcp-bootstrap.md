# Forensics: Codex MCP Bootstrap

Date: 2026-07-05

## Symptom

Codex startup reported MCP failures and 30-second timeouts for Cloudflare,
Obsidian REST, memory, filesystem, sequentialthinking, Chrome/Playwright, and
OCI MCP servers.

## Evidence

- `codex doctor --json` before correction timed out at 60 seconds.
- `codex mcp list` before correction showed all heavy MCPs enabled in the default config.
- Environment audit showed `CF_GLOBAL_API_KEY`, `CF_API_TOKEN`, `CLOUDFLARE_API_TOKEN`, and Obsidian env aliases absent from Windows Process/User/Machine env.
- Obsidian notes from 2026-06-21 and 2026-06-22 showed prior incidents where increasing timeouts did not fix broken MCP paths or authorization prerequisites.
- `docs/security/atius-secrets-vaults.md` documented Cloudflare variables in `kv/atius/cloudflare/api` and the `atius-vault-env cloudflare` loader.

## Root Causes

1. Default `config.toml` was overloaded with optional MCPs that depend on network, browser, OCI, npm, or secrets prerequisites.
2. `cloudflare-api` existed twice: once in local `config.toml` with `CF_GLOBAL_API_KEY`, and once through the installed Cloudflare plugin MCP manifest.
3. `CF_GLOBAL_API_KEY` was present in the machine secrets vault but not loaded into the Windows Codex startup environment.
4. The remote Vault env exporter was broken: it piped Vault JSON into `python3 -` while also using a heredoc for the Python program, so Python saw EOF instead of JSON.

## Fixes Applied

- Moved optional MCPs out of default `C:\Users\muniz\.codex\config.toml`.
- Left default configured MCPs as `node_repl` and `gbrain`.
- Disabled only the Cloudflare plugin MCP manifest by changing its `mcpServers` to `{}`.
- Fixed `/usr/local/sbin/atius-vault-export-env` on `atius-srv-3` to write Vault JSON to a temp file before Python parses it.
- Added Windows wrappers for `atius-vault-env` and `codex-cloud-ops`.
- Added repeatable smoke script and operational docs.

## Validation

- `codex doctor --json`: `overallStatus=ok`, `configured_mcp_servers=2`.
- `codex --strict-config doctor --json`: `overallStatus=ok`.
- `codex mcp list`: no default `cloudflare-api`, `obsidian_rest`, OCI, Playwright, filesystem, memory, or sequentialthinking entries.
- `atius-vault-env cloudflare`: emitted redacted exports including `CF_GLOBAL_API_KEY`.
- `codex-cloud-ops mcp list`: `cloudflare-api` present with `bearer_token_env_var=CF_GLOBAL_API_KEY`.
- `scripts/codex-mcp-startup-smoke.ps1` baseline, knowledge, browser, OCI, and lab checks passed; Cloudflare check correctly reports `missing-env` unless launched through the vault-aware path.

## Recommendations

- Keep default Codex startup minimal.
- Use `codex-cloud-ops` for Cloudflare MCP work.
- Do not paste Vault values into docs, chat, shell history, or Git.
- Treat `codex -p <profile> mcp list` as untrusted evidence on Codex `0.142.5`; prefer smoke checks and `-c` injection for MCP activation.
