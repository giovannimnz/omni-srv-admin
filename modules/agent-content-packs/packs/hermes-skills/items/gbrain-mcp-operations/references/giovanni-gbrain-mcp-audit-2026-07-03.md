# GIOVANNI-W11-PC / atius-srv fleet GBrain MCP audit — 2026-07-03

## Durable lesson

For Giovanni's fleet, the preferred GBrain MCP architecture is:

- One authoritative GBrain on `atius-srv-1`.
- The authoritative host uses direct local execution: `/home/ubuntu/.local/bin/gbrain serve`.
- Thin clients use private/VPN addressing (`10.1.1.1`) and ideally a restricted local wrapper with a dedicated MCP SSH key.
- Avoid public IP plus broad personal private key when private IP plus dedicated MCP key is available.

## Findings from the session

### GIOVANNI-W11-PC

Hermes:

- Config: `C:\Users\muniz\AppData\Local\hermes\config.yaml`
- MCP `gbrain`: explicit SSH to `ubuntu@10.1.1.1`
- Remote command: `/home/ubuntu/.local/bin/gbrain serve`
- Verification: `hermes mcp test gbrain` connected and discovered 89 tools.

Codex:

- Config: `C:\Users\muniz\.codex\config.toml`
- MCP `gbrain`: explicit SSH using `C:\Windows\System32\OpenSSH\ssh.exe`
- Uses key: `C:\Users\muniz\.ssh\private.pem`
- Target observed: `ubuntu@137.131.190.161`
- Remote command: `/home/ubuntu/.local/bin/gbrain serve`
- Version smoke test returned `gbrain 0.42.36.0`.

Local restricted bridge exists:

- `C:\Users\muniz\.local\bin\gbrain.cmd`
- Uses `C:\Users\muniz\.ssh\id_ed25519_gbrain_mcp`
- Uses `IdentitiesOnly=yes`, `BatchMode=yes`, keepalive options.
- Points to `ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain`.

Recommendation: move Codex to match the restricted bridge/private-IP pattern used by Hermes and the Linux thin clients.

### atius-srv-1

- Authoritative GBrain host.
- GBrain version observed: `0.42.36.0`.
- Hermes exists and uses direct local `/home/ubuntu/.local/bin/gbrain serve`.
- `hermes mcp test gbrain` connected and discovered 89 tools.
- Codex config exists with local GBrain, but `codex` was not available in PATH for user `ubuntu` during this audit.

### atius-srv-2

- Hermes exists and uses explicit SSH to `ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain serve`.
- Codex exists and uses explicit SSH to the same target.
- Local wrapper `/home/ubuntu/.local/bin/gbrain` exists and bridges to `10.1.1.1`.
- `hermes mcp test gbrain` connected and discovered 89 tools.

Recommendation: optionally point clients to the local wrapper to reduce config duplication.

### atius-srv-3

- Same effective pattern as atius-srv-2.
- Hermes/Codex point to `ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain serve`.
- Local wrapper exists.
- `hermes mcp test gbrain` connected and discovered 89 tools.

### horistic-srv

- Hermes was not installed/configured for user `horistic` in this audit.
- Codex exists and uses `/home/horistic/.local/bin/gbrain serve`.
- Wrapper uses dedicated key `/home/horistic/.ssh/id_ed25519_gbrain_mcp`.
- Wrapper points to `ubuntu@10.1.1.1 /home/ubuntu/.local/bin/gbrain`.
- Wrapper is restricted and rejects non-allowed subcommands such as `--version`; this is expected for a hardened bridge.

## Reporting style for future audits

Report as a compact matrix by host/client, then list only actionable deviations:

- GIOVANNI-W11-PC Codex using public IP + broad key instead of private IP + restricted wrapper.
- Missing/disabled clients, if relevant.
- MCPs unrelated to GBrain, such as Obsidian REST SSL failures, as separate findings only.
