# Phase 48 Execution Checkpoint - 2026-07-12

## Recommendation

Continue Phase 48 with native Codex model parity and Wayland's live port now
green. Do not begin Headroom until Router Phase 32 evidence, deterministic Go
verification and the full local/remote ACP lifecycle are complete.

## Ownership Audit

- `router-ai-atius` target backend files under `controller/`, `service/`,
  `relay/`, and `router/` did not appear dirty in the focused diff, but the
  repo still has active planning/docs churn for Phase 32.
- The exact Phase 48 implementation targets in `wayland` and `codex-acp` are
  now clean. Untracked `.orig`/`.wayland` artifacts remain outside those
  target paths and were preserved.
- User-provided session context indicated concurrent work in Wayland
  (`019f2ba1-1982-7c03-a17d-3ce28c589ac1`) and Router
  (`019f3e9a-9964-7912-a982-65596e9954d3`); no reset or overwrite was done.

## Read-only Findings

### Router

- Phase 32 plan exists and targets backend lifecycle/auth files.
- `./scripts/podman-admin.sh profile-run` is present on `atius-srv-1`.
- `/usr/local/go/bin/go` exists and `profile-run -- go version` passes.
- Focused Go tests under the CPU wrapper still fail/timeout because the
  nested CGO/compiler guard loses temporary and cache artifacts such as
  `_cgo_export.c` and `.cache/go-build` objects. No code failure was proven.
- Existing Phase 32 verification remains `blocked` at 5/6: live channel 5 is
  still access-token-only, has no refresh token, and requires Router-owned
  OAuth regeneration.
- The live `/home/ubuntu/.codex/auth.json` was updated at 2026-07-12 15:08 UTC.
- Native `codex exec` with `gpt-5.4` returned `NATIVE_CODEX_SMOKE_OK`.
- Canonical Codex `0.144.1` now resolves through login zsh,
  `/home/ubuntu/.local/bin/codex` and `/usr/local/bin/codex`.
- Native `codex exec` with `gpt-5.6-sol` returned `GPT56_NATIVE_OK` in
  read-only ephemeral mode.
- The build CPU guard now resolves `npm`/`npx` through NVM v24.13.1 while
  preserving the 20 percent build cgroup.
- `codex doctor` returned `18 ok`, `0 warn`, `0 fail`; an eight-second TUI
  smoke reported none of the deprecated hooks, Cloudflare login, or unsupported
  service-tier warnings.
- The Cloudflare plugin/MCP is disabled only for this Wayland runtime; ATIUS
  Cloudflare automation remains on the Vault-hydrated control path.

### Wayland

- Live service is active on `atius-srv-3`.
- Initial audit detected runtime drift, now reconciled in current inventory and
  runbooks:
  - inventory/docs still declare `25808`
  - active systemd override exports `PORT=25725`
  - journal confirms `WebUI running on http://0.0.0.0:25725`
  - public `https://wayland.atius.com.br/api/auth/status` returns `200`
- This drift invalidates any ACP/Wayland parity proof until the canonical port
  is reconciled.

### codex-acp

- Installed binary exists and is executable:
  - `/home/ubuntu/.local/bin/codex-acp`
  - `/home/ubuntu/.local/bin/codex-acp-atius`
- Wrapper help returns successfully.
- `cargo` and `rustc` are available at `/home/ubuntu/.cargo/bin/` and the
  installed `codex-acp-atius --help` passes.
- Wayland logs show repeated native OAuth failure: refresh token revoked,
  access token expired, Codex Responses WebSocket HTTP 401, and ACP
  `unauthorized` turn failures.

## Current Stop Conditions

- Router-owned OAuth regeneration has not completed; the live credential is
-  still reported as blocked by stale Phase 32 artifacts; native `gpt-5.4`
  authentication now passes, but Router-owned regeneration evidence still
  needs reconciliation.
- Model parity is green for the native GPT-5.6 smoke and ACP catalog.
- Wayland runtime, Apache target, inventory and current runbooks now agree on
  `25725`; `25808` remains only in dated historical evidence.
- Therefore native OAuth/model parity and local/remote ACP lifecycle proof
  cannot be marked green, and Phase 49 Headroom remains gated.

## Next Unblock Steps

1. Reconcile stale Router Phase 32 OAuth evidence with the newly refreshed
   auth state and repeat the sanitized probe plus refresh.
2. Repair the Router test executor's nested CGO/cache handling, then rerun the
   focused CPU-capped tests.
3. Complete local ACP prompt/tool/approval/cancel/resume/shutdown, then remote
   ACP and Wayland lifecycle validation.

## Tooling Note

The global `gsd-check-update.cmd` wrapper points to the absent
`C:\Program Files\nodejs\node.exe`; its referenced JavaScript runs with the
active fnm Node binary. The hook was not modified because this is independent
of the Phase 48 runtime blocker.
