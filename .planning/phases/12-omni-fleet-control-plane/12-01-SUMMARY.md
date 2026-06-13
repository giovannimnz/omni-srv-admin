---
phase: 12
plan: 01
padded: 12-01
slug: fleet-control-plane-foundation
status: contract-implemented
completed: 2026-06-13
branch: codex/omni-fleet-control-plane-m004
---

# 12-01 Summary — Fleet Control Plane Foundation

## Result

M004 now has an implemented, safe control-plane contract. No remote host was
modified and live install remains blocked by human gates.

## Delivered

- `docs/fleet/control-plane.md` defines the server/node model, inventory source
  of truth, PostgreSQL/PgBouncer rule, heartbeat, program registry, update
  plans, license metadata and audit contract.
- `modules/fleet-control-plane/configs/control-plane.example.yaml` defines the
  non-secret runtime config shape.
- `modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql` defines
  the initial PostgreSQL schema for hosts, nodes, programs, versions,
  update_plans, licenses and audit_events.
- `cli/omni/fleet.py` exposes safe M004 commands:
  - `omni fleet validate-inventory`
  - `omni fleet install server --host <host>`
  - `omni fleet install node --host <host>`
  - `omni fleet heartbeat --host <host>`
  - `omni fleet programs --host <host>`
  - `omni fleet update-plan --host <host> --program <name> --desired-version <version>`
  - `omni fleet audit`
  - `omni fleet status --all`
- `support-template` inventory now includes `platform.arch: unknown`, so the
  minimum inventory validation passes across all host records.

## Verification

```bash
python3 -m compileall -q cli/omni
PYTHONPATH=cli python3 -m omni fleet validate-inventory
PYTHONPATH=cli python3 -m omni fleet status --all
PYTHONPATH=cli python3 -m omni fleet install server --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet install node --host atius-srv-2 --json
PYTHONPATH=cli python3 -m omni fleet heartbeat --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet programs --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet update-plan --host atius-srv-1 --program fork-sync --desired-version v4.1 --json
PYTHONPATH=cli python3 -m omni fleet install server --host atius-srv-1 --apply
```

Expected result for the final command: blocked with an error because live
execution is not enabled in M004.

## Remaining Gates

- Approve secret/license storage outside git, logs, `.planning` and vault.
- Confirm SRV-1 is on Ubuntu 24.04 before live server install, or approve a
  bootstrap-only exception.
- Decide CLI-only vs API + CLI for the first live implementation.
- Approve update-plan policy before any node applies changes.
- Run M005 only after these contracts are accepted or explicitly waived.
