# Codex ACP ATIUS Sync Guards

This fork publishes the Codex ACP runtime used by the authenticated remote
agent gateway on `atius-srv-3`.

## Network invariant

- Bind the gateway to the SRV-3 OCI/DRG address `10.13.1.13:18789`.
- Trust the SRV-1 reverse proxy through its OCI/DRG address `10.11.1.11`.
- Publish only `wss://codex-acp.atius.com.br/gateway`; token authentication and
  device pairing remain mandatory.
- `10.100.100.0/24` is reserve fallback only. Never select it while the OCI/DRG
  path is available.

## Required custom behavior

- Track the Codex Rust crates used by the installed Codex CLI.
- Preserve `agent-profile` loading from `/home/ubuntu/.codex/agents/*.toml`.
- Advertise model, reasoning effort, service tier, and Power configuration.
- Keep `plugins.allow=["acpx"]`; no discovered plugin may auto-load implicitly.
- Run through `scripts/codex-acp-atius-wrapper.sh` so the single-user runtime
  keeps `CODEX_HOME=/home/ubuntu/.codex` and `HERMES_HOME=/home/ubuntu/.hermes`.
- Keep the default Codex sandbox policy sourced from the canonical
  `/home/ubuntu/.codex/config.toml` (`danger-full-access` in this environment).

## Verification after upstream sync

```bash
cd /home/ubuntu/GitHub/codex-acp
CARGO_BUILD_JOBS=1 cargo check
CARGO_BUILD_JOBS=1 cargo test --lib
```

Heavy Cargo commands must run inside the fleet build profile or a user scope
limited to `CPUQuota=80%` on the four-vCPU `atius-srv-3` host.
