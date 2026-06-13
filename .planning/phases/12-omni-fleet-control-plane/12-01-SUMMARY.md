---
phase: 12
plan: 01
padded: 12-01
slug: fleet-control-plane-foundation
status: live-implemented
completed: 2026-06-13
branch: codex/omni-fleet-control-plane-m004
---

# 12-01 Summary — Fleet Control Plane Foundation

## Result

M004 now has an implemented live control-plane foundation. The base repo/DB path
is active on SRV1/SRV2/SRV3; destructive generic apply paths remain blocked by
human gates.

## Delivered

- `docs/fleet/control-plane.md` defines the server/node model, inventory source
  of truth, PostgreSQL/PgBouncer rule, heartbeat, program registry, update
  plans, license metadata and audit contract.
- `modules/fleet-control-plane/configs/control-plane.example.yaml` defines the
  non-secret runtime config shape.
- `modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql` defines
  the initial PostgreSQL schema for hosts, nodes, programs, versions,
  update_plans, licenses and audit_events.
- `modules/fleet-control-plane/migrations/0002_ops_config_slash_commands.sql`
  extends `omni_fleet` into the canonical `omni-srv-admin` DB for ops scopes,
  config items, runtime parameters and CLI-Anything slash-command registry.
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
- `modules/fleet-control-plane/tools/validate_m004.py` validates M004 contract
  scenarios offline and can run read-only live probes against SRV1/SRV2/SRV3.
- `modules/fleet-control-plane/tests/test_m004_contract.py` adds pytest coverage
  for inventory validation, server/node plans, PgBouncer contract, heartbeat,
  programs, update-plan blocking and audit redaction.
- `scripts/verify-m004-fleet-control-plane.sh` runs the complete M004 validation
  suite.
- `.planning/phases/12-omni-fleet-control-plane/12-VALIDATION.md` records the
  multi-agent scenario matrix and live validation results.

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
PYTHONPATH=cli pytest -q modules/fleet-control-plane/tests/test_m004_contract.py
scripts/verify-m004-fleet-control-plane.sh
PYTHONPATH=cli python3 modules/fleet-control-plane/tools/validate_m004.py --live --json
```

Latest validation result:

- pytest: `12 passed`
- offline harness: `6 PASS`, `0 FAIL`
- live harness: `26 PASS`, `0 BLOCKED`, `0 FAIL`

Migration `0002` applied live through PgBouncer and added:

- `ops_scopes`
- `config_items`
- `slash_commands`
- `slash_command_bindings`

SRV-1/SRV-2/SRV-3 have `~/GitHub/omni-srv-admin`, query central DB
`omni_fleet` through PgBouncer on `10.1.1.1:6432`, and direct PostgreSQL access
from SRV-2/SRV-3 to `10.1.1.1:8745` is blocked by `omni-pg-access-guard`.

## Remaining Gates

- Keep `/etc/omni-srv-admin/fleet-db.env` outside git, logs, `.planning` and vault.
- Keep mutable ops config and runtime parameters in PostgreSQL; local
  `modules/*-ops` files are scripts/templates/bootstrap/export only.
- Move PgBouncer global auth from compatibility `trust` to stricter auth in a
  separate hardening task after checking existing services.
- Decide CLI-only vs API + CLI for the first service-agent implementation.
- Approve update-plan policy before any node applies changes.
- Run M005 only after the current IP/port baseline is consulted and a new
  pre/post network snapshot is stored in the vault.
