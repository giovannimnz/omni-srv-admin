# Agent Content Packs

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
- xrdp-abnt2-fleet
- oci-arm64-new-server-bootstrap

Shared:
- notebooklm bridge references/content

## Automation workflow

### Validate only

```bash
bash modules/agent-content-packs/scripts/agent-content-validate-all.sh
```

### Dry-run local targets

```bash
bash modules/agent-content-packs/scripts/agent-content-workflow.sh dry-run-local
```

### Dry-run fleet targets

```bash
bash modules/agent-content-packs/scripts/agent-content-workflow.sh dry-run-fleet
```

### Dry-run all targets

```bash
bash modules/agent-content-packs/scripts/agent-content-workflow.sh dry-run-all
```

### Apply local targets

```bash
bash modules/agent-content-packs/scripts/agent-content-workflow.sh apply-local --yes-sync
```

### Apply fleet targets

```bash
bash modules/agent-content-packs/scripts/agent-content-workflow.sh apply-fleet --yes-sync
```

`agent-content sync --apply` is fail-closed for `ssh-linux` targets until a
reviewed per-file remote transaction with rollback exists. Fleet apply must not
be used to bypass that guard. `$xrdp-abnt2-fleet` may be installed locally from
the reviewed source, then verified by source/installed tree hashes.

### Generate drift report

```bash
bash modules/agent-content-packs/scripts/agent-content-drift-report.sh
```

The drift script writes JSONL reports under:
- `modules/agent-content-packs/reports/`

## Operational policy

- Always run `validate` before sync.
- Always run dry-run before apply.
- Apply remains manual.
- Backups are per-item/per-execution.
- Drift detection can be automated; apply should remain human-controlled.

## Notes

- `external_dirs` remains a local tactical tool, not the fleet backbone.
- srv2 Codex has a different home layout (`/home/ubuntu/.codex/codex/...`) and is explicitly modeled in targets.
