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
| `../../docs/fleet/control-plane.md` | Architecture, runbook and human gates |
| `../../cli/omni/fleet.py` | Safe CLI commands for inventory validation and dry-run plans |
| `tools/validate_m004.py` | Offline contract validation and optional live read-only SRV probes |
| `tests/test_m004_contract.py` | Pytest coverage for the M004 contract |
| `scripts/omni-pg-access-guard.sh` | SRV-1 firewall guard: PgBouncer allowed, direct PostgreSQL blocked |
| `systemd/omni-pg-access-guard.service` | Boot-time service for the firewall guard |

## Safe Commands

```bash
PYTHONPATH=cli python3 -m omni fleet validate-inventory
PYTHONPATH=cli python3 -m omni fleet install server --host atius-srv-1
PYTHONPATH=cli python3 -m omni fleet install node --host atius-srv-2
PYTHONPATH=cli python3 -m omni fleet heartbeat --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet programs --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet update-plan --host atius-srv-1 --program fork-sync --desired-version v4.1 --json
```

`--apply` is intentionally blocked in M004.

## Validation

```bash
scripts/verify-m004-fleet-control-plane.sh
OMNI_M004_LIVE=1 scripts/verify-m004-fleet-control-plane.sh
```

The live mode uses SSH, ping, service/listener inspection, repo smoke checks and
read-only DB queries through PgBouncer. It must report direct PostgreSQL access
from nodes as blocked.

## Live M004 State

- SRV-1: `~/GitHub/omni-srv-admin` exists; local dirty work is preserved.
- SRV-2: `~/GitHub/omni-srv-admin` exists at `main@35bf94b`, worktree clean.
- SRV-3: `~/GitHub/omni-srv-admin` exists at `main@35bf94b`, worktree clean.
- SRV-1: PostgreSQL database `omni_fleet` exists with the initial schema.
- SRV-1/SRV-2/SRV-3: `/etc/omni-srv-admin/fleet-db.env` points to PgBouncer at
  `10.1.1.1:6432`.
- PgBouncer auth material remains outside git/log/vault.

## SRV-1 PgBouncer Enforcement

Live SRV-1 uses PostgreSQL on `127.0.0.1:8745` and PgBouncer on
`127.0.0.1:6432` plus `10.1.1.1:6432`. Nodes must use PgBouncer. Direct
PostgreSQL on `10.1.1.1:8745` is blocked from nodes by
`omni-pg-access-guard`.

## Secret Rule

The module may store `secret_ref` pointers only. Raw secrets, license keys,
tokens, passwords and serial numbers must stay out of git, logs, `.planning` and
vault notes.
