# Omni Fleet Control Plane

## Scope

M004 turns the existing fleet inventory into a live control-plane foundation.
It does not install K3s or Podman orchestration. It does establish the shared
`omni-srv-admin` repo on SRV1/SRV2/SRV3, central PostgreSQL database
`DbOmniFleet` on SRV-1, and PgBouncer-only database access for clients/nodes.
`DbOmniFleet` is the PostgreSQL database for `omni-srv-admin`; tables use
quoted `Tb...` identifiers such as `TbHosts` and `TbUpdatePlans`.

The target cluster names are:

| Host | Initial role | Notes |
|---|---|---|
| `ATIUS-SRV-1` | control-plane server | Ubuntu 24.04.4; DB owner for `DbOmniFleet` |
| `ATIUS-SRV-2` | node | Ubuntu 24.04.4; repo and PgBouncer DB path validated |
| `ATIUS-SRV-3` | node | Ubuntu 24.04.4; repo and PgBouncer DB path validated |

K3s and Portainer remain in M005/Phase 13. Portainer's planned public hostname
is `portainer.atius.com.br`.

## Source Of Truth

`inventory/hosts/*.yaml` remains the source of truth for reviewed host identity:
ids, roles, ownership and access facts. PostgreSQL is the source of truth for
runtime state, ops scopes, config items, runtime parameters and slash-command
registry. The database must not become an unreviewed second source for host
identity.

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

Current M004 install/update commands remain dry-run renderers. The live
foundation was applied manually with backups and validation; generic `--apply`
is still blocked until service-agent execution is implemented.

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
| Ops config | Stores per-host ops scopes, parameters and config items in PostgreSQL |
| Slash commands | Registers agent-facing commands through CLI-Anything-compatible metadata |

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
pg_dump --format=custom --file fleet-control-plane.dump DbOmniFleet
pg_restore --clean --if-exists --dbname DbOmniFleet fleet-control-plane.dump
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

SRV-1 live enforcement:

- PgBouncer listens on `127.0.0.1:6432` and `10.1.1.1:6432`.
- PostgreSQL direct port `8745` remains local for server-side maintenance.
- SRV-2/SRV-3 must connect to `10.1.1.1:6432`; direct `10.1.1.1:8745` is blocked.
- Live M004 database is `DbOmniFleet` on SRV-1.
- `DbOmniFleet` is also the canonical `omni-srv-admin` database for ops/config
  state; do not create parallel local config stores for the same facts.
- SRV-1/SRV-2/SRV-3 read `/etc/omni-srv-admin/fleet-db.env` and query
  `DbOmniFleet` through PgBouncer.
- PgBouncer auth currently remains compatible with existing services; stricter
  auth is a follow-up hardening item, not a reason to bypass PgBouncer.

## Data Model

Versioned schema lives in `modules/fleet-control-plane/migrations/`.

| Table | Purpose | Requirement |
|---|---|---|
| `TbHosts` | Reviewed inventory projection | FCP-02 |
| `TbNodes` | Runtime install mode, agent version, health and heartbeat | FCP-01, FCP-05 |
| `TbPrograms` | Installed program registry by host | FCP-06 |
| `TbVersions` | Desired/current version state and update policy | FCP-07 |
| `TbUpdatePlans` | Proposed changes, approval state and execution result | FCP-07 |
| `TbLicenses` | License metadata and `secret_ref` only | FCP-08 |
| `TbAuditEvents` | Actor, host, action, target, result and timestamp | FCP-09 |
| `TbOpsScopes` | Per-host ops areas such as `srv1-ops`, `srv2-ops`, `srv3-ops` | FCP-11, FCP-12 |
| `TbConfigItems` | Runtime parameters/config values stored in DB, with `secret_ref` for sensitive data | FCP-11, FCP-12 |
| `TbSlashCommands` | Slash-command catalog using CLI-Anything as provider | FCP-13 |
| `TbSlashCommandBindings` | Command-to-host/scope policy and apply mode | FCP-13 |

Future Podman/K3s work consumes these contracts rather than inventing a separate
source of truth.

## Ops Scopes And Config

Each server gets an explicit ops scope:

| Scope | Host | Directory | Runtime truth |
|---|---|---|---|
| `srv1-ops` | `atius-srv-1` | `modules/srv1-ops` | PostgreSQL `TbConfigItems` |
| `srv2-ops` | `atius-srv-2` | `modules/srv2-ops` | PostgreSQL `TbConfigItems` |
| `srv3-ops` | `atius-srv-3` | `modules/srv3-ops` | PostgreSQL `TbConfigItems` |

The filesystem directories remain useful for scripts, templates, bootstrap,
exported examples and versioned code. Operational parameters and mutable config
must resolve from PostgreSQL through PgBouncer. Sensitive values must be stored
as `secret_ref`, never raw values.

## CLI-Anything Slash Commands

Agent-facing slash commands are registered in PostgreSQL and use the
CLI-Anything convention as the integration model. The baseline command set is:

| Command | Provider | Purpose |
|---|---|---|
| `/cli-anything` | `cli-anything` | Build a full CLI harness |
| `/cli-anything:refine` | `cli-anything` | Improve an existing harness |
| `/cli-anything:test` | `cli-anything` | Run harness tests |
| `/cli-anything:validate` | `cli-anything` | Validate against `HARNESS.md` |
| `/cli-anything:list` | `cli-anything` | List available harnesses |
| `/omni-srv-admin` | `cli-anything` | Planned generated harness for Omni operations |

The long-term target is `cli-anything-omni-srv-admin` for slash-command coverage
of all high-value `omni-srv-admin` workflows. Ad-hoc slash commands should be
treated as temporary until represented in `TbSlashCommands`.

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
