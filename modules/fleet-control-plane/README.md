# fleet-control-plane

M004 foundation for the Omni Fleet Control Plane.

This module defines and validates the live fleet foundation required before any
K3s/Portainer work: repo rollout, central database schema, runtime configuration
shape and safe CLI surface.

## Current Artifacts

| Path | Purpose |
|---|---|
| `configs/control-plane.example.yaml` | Example runtime config without secrets |
| `migrations/0001_fleet_control_plane.sql` | Initial PostgreSQL schema contract |
| `migrations/0002_ops_config_slash_commands.sql` | Ops scopes, DB-backed config/parameters and CLI-Anything slash-command registry |
| `migrations/0003_agent_executor_monitoring.sql` | Agent executor, command allowlist, telemetry and resource policies |
| `../../docs/fleet/control-plane.md` | Architecture, runbook and human gates |
| `../../cli/omni/fleet.py` | Safe CLI commands, local agent executor and fleet monitor |
| `tools/validate_m004.py` | Offline contract validation and optional live read-only SRV probes |
| `tests/test_m004_contract.py` | Pytest coverage for the M004 contract |
| `scripts/omni-pg-access-guard.sh` | SRV-1 firewall guard: PgBouncer allowed, direct PostgreSQL blocked |
| `scripts/install-omni-fleet-agent.sh` | User-systemd installer for the local node agent |
| `systemd/omni-pg-access-guard.service` | Boot-time service for the firewall guard |
| `systemd/omni-fleet-agent.service` | Persistent local node agent service |

## Safe Commands

```bash
PYTHONPATH=cli python3 -m omni fleet validate-inventory
PYTHONPATH=cli python3 -m omni fleet install server --host atius-srv-1
PYTHONPATH=cli python3 -m omni fleet install node --host atius-srv-2
PYTHONPATH=cli python3 -m omni fleet heartbeat --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet agent heartbeat --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet monitor hosts --json
PYTHONPATH=cli python3 -m omni fleet programs --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet update-plan --host atius-srv-1 --program fork-sync --desired-version v4.1 --json
PYTHONPATH=cli python3 -m omni fleet queue-update --host atius-srv-3 --program ubuntu-dark-theme --desired-version 24.04-v1 --command-key ubuntu-dark-theme.apply --json
```

`--apply` is intentionally blocked on `install` and legacy `update-plan`.
Executable work goes through `queue-update` and the target host's local
`omni fleet agent once/loop --apply`.

## Validation

```bash
scripts/verify-m004-fleet-control-plane.sh
OMNI_M004_LIVE=1 scripts/verify-m004-fleet-control-plane.sh
```

The live mode uses SSH, ping, service/listener inspection, repo smoke checks and
read-only DB queries through PgBouncer. It must report direct PostgreSQL access
from nodes as blocked.

## Agent Executor Model

```text
SRV-2 CLI
  -> queue-update in DbOmniFleet/TbUpdatePlans through PgBouncer
  -> SRV-3 local omni-fleet-agent claims host_id=atius-srv-3
  -> SRV-3 executes allowlisted command locally
  -> result/audit/telemetry written back through PgBouncer
```

There is no direct SSH apply path in this model.

Initial allowlist table: `TbFleetCommands`.

- `omni.noop`: enabled for validation.
- `omni.fleet.heartbeat`: internal telemetry collection.
- `omni.resource.snapshot`: SRV-1 only.
- `ubuntu-dark-theme.apply`: registered but disabled until the Ubuntu 24.04
  dark-theme harness is finalized.

Install local user agent after migration `0003` is applied:

```bash
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-1
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-2
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-3
```

## Live M004 State

- SRV-1: `~/GitHub/omni-srv-admin` exists; local dirty work is preserved.
- SRV-2: `~/GitHub/omni-srv-admin` tracks `main`, worktree clean.
- SRV-3: `~/GitHub/omni-srv-admin` tracks `main`, worktree clean.
- SRV-1: PostgreSQL database `DbOmniFleet` exists with the initial schema.
- `DbOmniFleet` is the canonical PostgreSQL database for `omni-srv-admin`
  runtime state, ops scopes, config items, parameters and slash-command
  registry.
- Migration `0003` is applied live: `TbFleetCommands=4`,
  `TbNodeResourcePolicies=3`; SRV-1 has live telemetry in `TbNodeTelemetry`.
- SRV-1/SRV-2/SRV-3: `/etc/omni-srv-admin/fleet-db.env` points to PgBouncer at
  `10.1.1.1:6432`.
- PgBouncer auth material remains outside git/log/vault.

## Ops And Config Rule

Each server has an ops scope: `srv1-ops`, `srv2-ops`, `srv3-ops`. The directories
under `modules/*-ops` contain scripts, templates, bootstrap and exported
examples. Runtime parameters and mutable config belong in PostgreSQL
`TbConfigItems` and must be read through PgBouncer. Sensitive values use
`secret_ref`; raw secrets stay out of DB, git, logs and vault.

## Slash Command Rule

Agent-facing slash commands should be represented in PostgreSQL
`TbSlashCommands` and use CLI-Anything conventions. Baseline commands are
`/cli-anything`, `/cli-anything:refine`, `/cli-anything:test`,
`/cli-anything:validate`, `/cli-anything:list` and planned `/omni-srv-admin`.

## SRV-1 PgBouncer Enforcement

Live SRV-1 uses PostgreSQL on `127.0.0.1:8745` and PgBouncer on
`127.0.0.1:6432` plus `10.1.1.1:6432`. Nodes must use PgBouncer. Direct
PostgreSQL on `10.1.1.1:8745` is blocked from nodes by
`omni-pg-access-guard`.

## Secret Rule

The module may store `secret_ref` pointers only. Raw secrets, license keys,
tokens, passwords and serial numbers must stay out of git, logs, `.planning` and
vault notes.
