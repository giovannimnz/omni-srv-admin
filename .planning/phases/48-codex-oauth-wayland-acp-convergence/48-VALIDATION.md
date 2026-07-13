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
- No negative test touches live channel 5 credentials or leaks token material.

## Stop Conditions

- Owner session remains active on target files.
- Any native 401/403/invalidation remains unresolved.
- Model catalog differs between native Codex, ACP and Wayland.
- Remote ACP only works by weakening auth or approval controls.

## Rollback

Restore the last known-good Router/Wayland service artifacts from verified
backups, disable only the new remote ACP path if needed, preserve native
codex-acp and repeat the full native smoke.

## Completion Evidence

Focused tests under CPU cap, sanitized live probes, ACP lifecycle transcript,
Chromium headless network/console snapshot, backup/rollback paths and durable
notes.
