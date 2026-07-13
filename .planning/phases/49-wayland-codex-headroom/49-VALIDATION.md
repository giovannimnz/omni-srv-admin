# Phase 49 Validation - Wayland Codex Headroom

## Required Proof

- Package version, tag commit and artifact hash match the approved pin.
- Proxy listens only on loopback and journals contain no auth headers/prompts.
- Active `/home/ubuntu/.codex` config, AGENTS and SQLite hashes do not change.
- Isolated direct Codex passes OAuth, HTTP Responses, WebSocket completion,
  tools, apply_patch, cancel/reconnect and model/effort parity.
- Eligible workload reports transformed content and savings greater than zero.
- codex-acp lifecycle remains protocol-compatible through Headroom.
- Wayland passes Chromium headless conversation/stream/approval/cancel/resume.
- Rollback restores native `Wayland -> codex-acp -> codex` with no lost task.

## Stop Conditions

- Any mutation of active Codex SQLite/provider tags.
- 401/403, missing scope, incomplete WebSocket completion or reconnect loop.
- Requests route through proxy but eligible transforms/savings stay zero.
- ACP or Wayland requires bypassing approval/auth policy.

## Rollback

Switch the Wayland launch seam to native CODEX_HOME, drain and restart only the
affected service, stop/disable Headroom, preserve canary state for forensics and
rerun Phase 48 native validation. Use `headroom unwrap codex` only with the exact
isolated CODEX_HOME that was wrapped.

## Completion Evidence

Version/hash, service state, direct/ACP/Wayland transcripts, savings telemetry,
Chrome DevTools headless evidence, rollback rehearsal and Obsidian/GBrain notes.
