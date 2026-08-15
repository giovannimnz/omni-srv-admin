# Agent Content Fleet Sync

Git-backed source-of-truth for curated Hermes and Codex content packs across Giovanni's fleet.

## Purpose

Distribute useful agent content safely across:
- Hermes runtimes
- Codex runtimes
- Windows / WSL / Linux hosts

Without sharing mutable runtime state.

## Current packs

- `hermes-skills`
- `codex-skills`
- `shared-agent-content`

## Safety rules

Never sync:
- `state.db*`
- `.env`
- `auth.json`
- logs/caches
- gateway state
- cron locks/state
- PID / WAL / SHM / lockfiles
- secrets or credentials

## CLI shape

```bash
omni agent-content packs
omni agent-content targets --pack hermes-skills
omni agent-content validate-pack --pack hermes-skills
omni agent-content sync --pack hermes-skills --target windows-hermes-default --dry-run
omni agent-content sync --pack hermes-skills --target windows-hermes-default --apply
```

## Current v1 pilot

Hermes:
- hermes-wslinterop-restore
- hermes-windows-wsl
- hermes-cross-runtime-bridge
- hermes-yolo-three-env
- gbrain-mcp-operations

Codex:
- atius-sso
- atius-sso-governed-release-closeout

Shared:
- notebooklm bridge references/content

## Notes

- `external_dirs` remains a local tactical tool, not the fleet backbone.
- Apply is manual; drift detection can later run on schedule in dry-run mode.
