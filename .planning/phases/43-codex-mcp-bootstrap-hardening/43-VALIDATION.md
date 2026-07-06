---
phase: 43
status: drafted
created: 2026-07-04
---

# Phase 43 Validation Strategy

## Validation Architecture

### Dimension 1: Lean baseline inventory

- Base `C:\Users\muniz\.codex\config.toml` contains only the always-on MCP set selected by the phase.
- Browser, OCI, Cloudflare, knowledge, and lab MCP blocks no longer live in the lean baseline.
- Each extracted MCP group exists in a named profile file.

### Dimension 2: Prerequisite hygiene

- `cloudflare-api` is not part of lean startup when `CF_GLOBAL_API_KEY` is absent.
- `obsidian_rest` is validated through reachability preflight, not timeout inflation alone.
- Browser profiles verify local executable/path assumptions before blaming MCP timeout.
- OCI profiles verify `uv`, repo paths, and OCI profile presence before blaming timeout.

### Dimension 3: Explicit startup budgets

- Every remaining non-baseline profile server has an explicit `startup_timeout_sec` when a timeout is relevant.
- No frequently used profile depends on `@latest` package resolution in its hot path without an explicit justification.

### Dimension 4: Cold-start behavior

- `codex doctor --json` on the lean baseline returns MCP status `ok` or an explicitly accepted note, not generic avoidable warnings.
- Profile smoke produces classified outcomes: `ok`, `disabled`, `missing-env`, `unreachable`, or `slow-start`.
- Failure output redacts headers, tokens, and secrets.

### Dimension 5: Documentation and rollback

- Docs define the profile names, when to use them, and exact `codex -p <profile>` commands.
- Docs define backup file patterns and rollback commands before any mutation.
- Docs record that `obsidian_rest` transport failure is a reachability issue first, not a pure timeout issue.

## Planned Result

This phase passes when the lean baseline becomes quiet and predictable, while
the opt-in profiles remain explicit, documented, and testable without secret
leakage.
