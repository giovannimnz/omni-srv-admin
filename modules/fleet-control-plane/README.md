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
| `migrations/0006_omni_version_inventory.sql` | Per-computer `omni-srv-admin` version table (`TbVersion`) with GitHub release fields |
| `migrations/0007_customization_registry.sql` | Managed apps, forks and customization policy registry |
| `migrations/0008_internal_service_pki_commands.sql` | `omni.trust-pki.*` allowlist commands for internal service PKI onboarding |
| `../../docs/fleet/control-plane.md` | Architecture, runbook and human gates |
| `../../cli/omni/fleet.py` | Safe CLI commands, local agent executor and fleet monitor |
| `tools/validate_m004.py` | Offline contract validation and optional live read-only SRV probes |
| `tests/test_m004_contract.py` | Pytest coverage for the M004 contract |
| `scripts/omni-pg-access-guard.sh` | SRV-1 firewall guard: PgBouncer allowed, direct PostgreSQL blocked |
| `scripts/install-omni-fleet-agent.sh` | User-systemd installer for the local node agent |
| `scripts/configure-fleet-direct-peers.sh` | Public-IP SSH fallback aliases and peer map; no public DB exposure |
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
PYTHONPATH=cli python3 -m omni fleet registry sync --all --json
PYTHONPATH=cli python3 -m omni fleet registry show --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet trust-pki plan --json
PYTHONPATH=cli python3 -m omni fleet trust-pki onboard-host --host horistic-srv --json
PYTHONPATH=cli python3 -m omni fleet trust-pki reconcile-host --host horistic-srv --json
PYTHONPATH=cli python3 -m omni fleet trust-pki rotate-host --host horistic-srv --reason ip-change --json
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

Direct fallback is SSH/probe only. PgBouncer remains private on
`10.11.1.11:6432` on the OCI/DRG private plane; `10.100.100.1:6432` stays as
reserve fallback only. Do not expose `DbOmniFleet` on
public IP.

Initial allowlist table: `TbFleetCommands`.

- `omni.noop`: enabled for validation.
- `omni.fleet.heartbeat`: internal telemetry collection.
- `omni.resource.snapshot`: SRV-1 only.
- `ubuntu-dark-theme.apply`: registered but disabled until the Ubuntu 24.04
  dark-theme harness is finalized.
- `omni.trust-pki.*`: internal service PKI onboarding stages rendered by
  `omni fleet trust-pki`; local command templates use argv arrays and remain
  gated by `TbUpdatePlans` approval plus command-level `--execute` for
  mutating stages. `omni.trust-pki.windows.*` is the Windows trust-client path
  for `giovanni-w11-pc` through `OmniFleetAgent`. `reconcile-host` and
  `rotate-host` cover IP/SAN drift for already registered servers.

Install local user agent after migration `0003` is applied:

```bash
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-1
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-2
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-3
```

Windows scheduled-task helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File modules/fleet-control-plane/windows/Install-OmniFleetAgentTask.ps1
```

Configure direct public-IP SSH fallback aliases:

```bash
modules/fleet-control-plane/scripts/configure-fleet-direct-peers.sh
ssh atius-srv-2-direct hostname
ssh atius-srv-3-direct hostname
```

## Live M004 State

- SRV-1: `~/GitHub/omni-srv-admin` exists; local dirty work is preserved.
- SRV-2: `~/GitHub/omni-srv-admin` tracks `main`, worktree clean.
- SRV-3: `~/GitHub/omni-srv-admin` tracks `main`, worktree clean.
- SRV-1: PostgreSQL database `DbOmniFleet` exists with the initial schema.
- `DbOmniFleet` is the canonical PostgreSQL database for `omni-srv-admin`
  runtime state, ops scopes, config items, parameters and slash-command
  registry.
- Migrations through `0007` define the live contract, including `TbVersion` for
  per-computer `omni-srv-admin` installed/GitHub version tracking.
- `modules/fleet-control-plane/configs/omni-version-matrix.json` defines the
  desired release target and scheduler/command lane for SRV-1/SRV-2/SRV-3 and
  `giovanni-w11-pc`.
- Migration `0007` extends the canonical DB with `TbManagedApps`,
  `TbManagedForks` and `TbCustomizationPolicies`, plus inventory mirrors in
  `TbConfigItems`.
- Migration `0003` is applied live: `TbFleetCommands=4`,
  `TbNodeResourcePolicies=3`; SRV-1 has live telemetry in `TbNodeTelemetry`.
- SRV-1/SRV-2/SRV-3 and `giovanni-w11-pc`: fleet DB env files should point to
  PgBouncer at `10.11.1.11:6432`, with `10.100.100.1:6432` as reserve fallback only.
- SRV-1/SRV-2/SRV-3/Horistic and `giovanni-w11-pc` point their fleet DB env to
  PgBouncer at `10.11.1.11:6432`. The Windows path was validated from
  `10.100.100.8` on 2026-07-10; `10.100.100.1:6432` is reserve only.
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
`127.0.0.1:6432` plus `10.11.1.11:6432`. Nodes must use PgBouncer. Direct
PostgreSQL on `10.11.1.11:8745` is blocked from nodes by
`omni-pg-access-guard`.

## Secret Rule

The module may store `secret_ref` pointers only. Raw secrets, license keys,
tokens, passwords and serial numbers must stay out of git, logs, `.planning` and
vault notes.
