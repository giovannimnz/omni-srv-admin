# Phase 48 Validation - Codex OAuth and Wayland ACP Convergence

## Required Proof

- Router metadata, refresh, regenerate start/complete and probe are sanitized.
- Auth matrix distinguishes Router client auth from Codex upstream 401, 403,
  `token_invalidated`, `refresh_token_invalidated` and `invalid_api_key`.
- Native Codex auth works without Headroom and model/effort catalog tests pass.
- Local codex-acp passes initialize, session/new, prompt, tool, approval,
  cancel, resume and shutdown.
- Remote gateway passes authenticated Upgrade, approvals, reconnect and clean
  error propagation.
- Wayland Chromium-headless smoke passes model selection, effort, streaming,
  approval and cancel/resume.
- Canonical `*.atius.internal` owner FQDNs resolve to OCI/DRG addresses and
  strict FreeIPA/SSSD host-key trust fails closed for missing or changed keys.
- Warm encrypted OpenSSH multiplexing publishes cold/warm/interactive
  mean/p50/p95/p99 and failures; 13-15 ms remains a stretch reference, not an
  SLA or a reason to enable plaintext/HPN NoneSwitch.
- A direct Codex conversation can opt into ACP stdio-over-SSH through the
  existing `AcpAgentManager -> AcpAgentV2 -> AcpSession -> ProcessAcpClient`
  chain, with local UI/SQLite `cwd` and owner-side `agentCwd`.
- Active read/write/edit/search/Git/watchers/LSP/test/build/runtime execute on
  the owner filesystem. NFS remains byte-stable and is used only for
  discovery, picker, light read/diff, compatibility and fallback.
- Wayland fork protected paths are installed before owner-local source edits;
  full fork-sync, CPU-capped tests/build, Chromium headless, host outage,
  reconnect, cancel and per-host rollback all pass.
- No negative test touches live channel 5 credentials or leaks token material.

## Stop Conditions

- Owner session remains active on target files.
- Any native 401/403/invalidation remains unresolved.
- Model catalog differs between native Codex, ACP and Wayland.
- Remote ACP only works by weakening auth or approval controls.
- Any owner alias accepts TOFU, plaintext, dynamic remote commands, agent/env
  forwarding, an unexpected identity, or an untrusted host key.
- Any owner-local active operation or callback reads/writes through NFS, or a
  team/cron session reaches the owner transport.
- A planned owner-local Wayland path is not protected before its first edit,
  CPU containment cannot be proven, or a visible browser is launched.

## Rollback

Restore the last known-good Router/Wayland service artifacts from verified
backups, disable only the new remote ACP path if needed, preserve native
codex-acp and repeat the full native smoke.

## Completion Evidence

Focused tests under CPU cap, sanitized live probes, ACP lifecycle transcript,
Chromium headless network/console snapshot, four-host owner-local matrix,
latency/resource distributions, NFS invariance, fork-sync proof,
backup/rollback paths and durable notes.
