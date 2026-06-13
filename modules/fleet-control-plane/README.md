# fleet-control-plane

M004 foundation for the Omni Fleet Control Plane.

This module is contract-first. It defines the database schema, runtime
configuration shape and safe CLI surface required before any K3s/Portainer work.
It does not install services on the hosts yet.

## Current Artifacts

| Path | Purpose |
|---|---|
| `configs/control-plane.example.yaml` | Example runtime config without secrets |
| `migrations/0001_fleet_control_plane.sql` | Initial PostgreSQL schema contract |
| `../../docs/fleet/control-plane.md` | Architecture, runbook and human gates |
| `../../cli/omni/fleet.py` | Safe CLI commands for inventory validation and dry-run plans |

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

## Secret Rule

The module may store `secret_ref` pointers only. Raw secrets, license keys,
tokens, passwords and serial numbers must stay out of git, logs, `.planning` and
vault notes.
