# Omni Fleet Control Plane

## Scope

M004 turns the existing fleet inventory into an explicit control-plane contract.
It does not install K3s, Podman orchestration, PostgreSQL, PgBouncer or node
agents on real hosts yet. Live installation remains blocked until the operator
approves secret storage, first-server timing, and execution policy.

The target cluster names are:

| Host | Initial role | Notes |
|---|---|---|
| `ATIUS-SRV-1` | control-plane server | Ubuntu 24.04.4 baseline confirmed locally on 2026-06-13; live install still gated |
| `ATIUS-SRV-2` | node | Future managed node |
| `ATIUS-SRV-3` | node | Future managed node |

K3s and Portainer remain in M005/Phase 13. Portainer's planned public hostname
is `portainer.atius.com.br`.

## Source Of Truth

`inventory/hosts/*.yaml` remains the source of truth. The database stores a
projection of reviewed inventory plus runtime state. The database must not become
an unreviewed second source of truth.

Minimum host fields:

| Field | Requirement |
|---|---|
| `id` | Stable kebab-case host id |
| `role` | Operational role such as `production`, `development` or `sandbox` |
| `owner` | Accountable owner |
| `status` | Inventory status |
| `access.ssh` | SSH target used by controlled operations |
| `platform.provider` | Provider such as `oracle-oci` |
| `platform.os` | OS baseline |
| `platform.arch` | CPU architecture |

Validation command:

```bash
PYTHONPATH=cli python3 -m omni fleet validate-inventory
```

## Server And Node Modes

The install mode is explicit:

```bash
PYTHONPATH=cli python3 -m omni fleet install server --host atius-srv-1
PYTHONPATH=cli python3 -m omni fleet install node --host atius-srv-2
PYTHONPATH=cli python3 -m omni fleet install node --host atius-srv-3
```

Current M004 commands are dry-run contract renderers. `--apply` is intentionally
blocked in this branch.

Server responsibilities:

| Responsibility | Contract |
|---|---|
| Migrations | Runs versioned SQL migrations from `modules/fleet-control-plane/migrations/` |
| Database | Owns PostgreSQL maintenance and backup/restore |
| Pooler | Exposes PgBouncer as the only client/node database endpoint |
| Inventory | Imports reviewed `inventory/hosts` projections |
| Runtime state | Receives heartbeat/status and program inventory |
| Change control | Generates update plans before execution |
| Audit | Stores audit events for installs, updates, license changes and status mutations |

Node responsibilities:

| Responsibility | Contract |
|---|---|
| Agent | Reports heartbeat, service health and installed programs |
| Database access | Uses PgBouncer only |
| Updates | Executes approved update plans only |
| Secrets | Never logs raw tokens, serials or license material |
| Degradation | Keeps local status when server or PgBouncer is unavailable |

## PostgreSQL And PgBouncer

PostgreSQL is central but migrable. The control-plane server owns migrations and
maintenance. Nodes and clients connect only through PgBouncer.

Allowed direct PostgreSQL access:

| Actor | Allowed direct access | Reason |
|---|---:|---|
| control-plane server migration job | yes | schema migration and maintenance |
| backup/restore operator | yes | logical dump/restore |
| fleet nodes | no | must use PgBouncer |
| CLI clients | no | must use PgBouncer or local API facade |

Migration and backup contract:

```bash
# Example future runbook commands; not executed by M004.
pg_dump --format=custom --file fleet-control-plane.dump omni_fleet
pg_restore --clean --if-exists --dbname omni_fleet fleet-control-plane.dump
```

PgBouncer ownership:

| Item | Owner |
|---|---|
| `pgbouncer.ini` | control-plane server module |
| `userlist.txt` or auth backend | secret storage, never git |
| `listen_host` | private server VPN IP, default candidate `10.1.1.1`; never public internet |
| `listen_port` | control-plane runtime config, default `6432` |
| allowed clients | private fleet network, default candidate `10.1.1.0/24` |
| pool mode | deployment config, default candidate `transaction` |

## Data Model

Initial schema lives in
`modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql`.

| Table | Purpose | Requirement |
|---|---|---|
| `hosts` | Reviewed inventory projection | FCP-02 |
| `nodes` | Runtime install mode, agent version, health and heartbeat | FCP-01, FCP-05 |
| `programs` | Installed program registry by host | FCP-06 |
| `versions` | Desired/current version state and update policy | FCP-07 |
| `update_plans` | Proposed changes, approval state and execution result | FCP-07 |
| `licenses` | License metadata and `secret_ref` only | FCP-08 |
| `audit_events` | Actor, host, action, target, result and timestamp | FCP-09 |

Future Podman/K3s work consumes these contracts rather than inventing a separate
source of truth.

## Heartbeat

Heartbeat payload:

| Field | Meaning |
|---|---|
| `host` | Inventory id |
| `agent_version` | Installed node agent version |
| `os` / `arch` | Platform facts |
| `uptime` | Node uptime summary |
| `disk` / `memory` | Capacity summary |
| `service_health` | Key service statuses |
| `status` | `healthy`, `degraded`, `offline` or `unknown` |
| `last_contact` | Last accepted heartbeat timestamp |

If no heartbeat is present, the node is treated as `offline` with
`missing-heartbeat`.

Check current contract output:

```bash
PYTHONPATH=cli python3 -m omni fleet heartbeat --host atius-srv-1 --json
```

## Program Registry And Update Plans

The registry records:

| Field | Meaning |
|---|---|
| `program` | Package, service, module or managed tool name |
| `install_type` | Package manager, binary, container, systemd unit or omni module |
| `current_version` | Version reported by node collector |
| `desired_version` | Target version |
| `source` | Source of installation or desired state |
| `managed_by` | Owning module or operator |
| `update_policy` | `manual`, `plan-first`, `pinned`, or future automation class |

Update plans are generated before execution. They include dry-run output,
approval state and audit references.

```bash
PYTHONPATH=cli python3 -m omni fleet update-plan \
  --host atius-srv-1 \
  --program fork-sync \
  --desired-version v4.1 \
  --json
```

## License And Secret Policy

License records store metadata only:

| Field | Meaning |
|---|---|
| `program` | Licensed program |
| `scope` | Host, user, org or project scope |
| `owner` | Responsible owner |
| `status` | Active, expired, trial or revoked |
| `expires_at` | Optional expiry date |
| `seat_count` | Optional seat count |
| `secret_ref` | Pointer to external secret storage |

Raw license material, tokens, passwords and serials must not be written to git,
`.planning`, logs, vault notes or command output.

## Audit

Audit event fields:

| Field | Meaning |
|---|---|
| `actor` | Human, automation or service account |
| `host` | Inventory id |
| `action` | Install, update, license change, status mutation, migration |
| `target` | Program, node, DB object or config target |
| `result` | Planned, approved, succeeded, failed, blocked |
| `timestamp` | RFC3339 timestamp |
| `metadata` | Redacted structured details |

Local audit inspection command:

```bash
PYTHONPATH=cli python3 -m omni fleet audit --json
```

## Human Gates Before Live Execution

1. Approve where secret/license material lives outside git/log/vault.
2. Approve first implementation shape: CLI-only or API + CLI.
3. Approve update policy: dry-run, explicit approval, rollback and audit event.
4. Re-run host preflight immediately before live install.
5. Run M005 only after M004 contracts are accepted and node preflight passes.
