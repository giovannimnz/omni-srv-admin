# Omni Fleet Control Plane

## Scope

M004 turns the existing fleet inventory into a live control-plane foundation.
It does not install K3s or Podman orchestration. It does establish the shared
`omni-srv-admin` repo on SRV1/SRV2/SRV3, central PostgreSQL database
`DbOmniFleet` on SRV-1, and PgBouncer-only database access for clients/nodes.
`DbOmniFleet` is the PostgreSQL database for `omni-srv-admin`; tables use
quoted `Tb...` identifiers such as `TbHosts`, `TbUpdatePlans` and
`TbNodeTelemetry`.

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
on `install` and legacy `update-plan` remains blocked. Real execution is now
modeled through `queue-update` plus the target host's local `omni fleet agent`.

Server responsibilities:

| Responsibility | Contract |
|---|---|
| Migrations | Runs versioned SQL migrations from `modules/fleet-control-plane/migrations/` |
| Database | Owns PostgreSQL maintenance and backup/restore |
| Pooler | Exposes PgBouncer as the only client/node database endpoint |
| Inventory | Imports reviewed `inventory/hosts` projections |
| Runtime state | Receives heartbeat/status, program inventory and omni-srv-admin version inventory |
| Change control | Generates update plans before execution |
| Monitoring | Reads fleet telemetry from `TbNodeTelemetry` and falls back to local cache |
| Audit | Stores audit events for installs, updates, license changes and status mutations |
| Ops config | Stores per-host ops scopes, parameters and config items in PostgreSQL |
| Slash commands | Registers agent-facing commands through CLI-Anything-compatible metadata |

Node responsibilities:

| Responsibility | Contract |
|---|---|
| Agent | Reports heartbeat, service health and installed programs |
| Database access | Uses PgBouncer only |
| Updates | Executes approved update plans only, locally on the target host |
| Monitoring | Publishes load, CPU, memory, disk, I/O, PSI and service health |
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
| `listen_host` | private server VPN IP, default candidate `10.100.100.1`; never public internet |
| `listen_port` | control-plane runtime config, default `6432` |
| allowed clients | OCI private peers `10.12.0.0/16`, `10.13.0.0/16`, `10.14.0.0/16`, `10.21.0.0/16`, with `wg100` reserve `10.100.100.0/24` |
| pool mode | deployment config, default candidate `transaction` |

SRV-1 live enforcement:

- PgBouncer listens on `127.0.0.1:6432` and `10.11.1.11:6432`.
- PostgreSQL direct port `8745` remains local for server-side maintenance.
- SRV-2/SRV-3/SRV-4/Horistic fleet peers must connect to `10.11.1.11:6432`; the live allowlist accepts OCI private ranges `10.12.0.0/16`, `10.13.0.0/16`, `10.14.0.0/16`, `10.21.0.0/16` plus reserve `wg100` peers.
- `10.100.100.1:6432` remains reserve fallback only. Windows now uses `10.11.1.11:6432`; direct reachability from `10.100.100.8` was validated on 2026-07-10.
- Direct PostgreSQL on `10.11.1.11:8745` stays blocked from nodes.
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
| `TbVersions` | Desired/current program version state and update policy | FCP-07 |
| `TbVersion` | Per-computer `omni-srv-admin` installed/Git state and GitHub release target | FCP-16 |
| `TbUpdatePlans` | Proposed changes, approval state and execution result | FCP-07 |
| `TbLicenses` | License metadata and `secret_ref` only | FCP-08 |
| `TbAuditEvents` | Actor, host, action, target, result and timestamp | FCP-09 |
| `TbOpsScopes` | Per-host ops areas such as `srv1-ops`, `srv2-ops`, `srv3-ops` | FCP-11, FCP-12 |
| `TbConfigItems` | Runtime parameters/config values stored in DB, with `secret_ref` for sensitive data | FCP-11, FCP-12 |
| `TbSlashCommands` | Slash-command catalog using CLI-Anything as provider | FCP-13 |
| `TbSlashCommandBindings` | Command-to-host/scope policy and apply mode | FCP-13 |
| `TbFleetCommands` | Agent command allowlist and host scope | FCP-14 |
| `TbNodeTelemetry` | Load, CPU, memory, disk, I/O, pressure and service health samples | FCP-15 |
| `TbNodeResourcePolicies` | Per-host thresholds for active demand/load-balancing decisions | FCP-15 |

Future Podman/K3s work consumes these contracts rather than inventing a separate
source of truth.

## Landscape / Omni Governance

Landscape self-hosted is now the durable Ubuntu machine-management endpoint for
the managed fleet, but it does not replace Omni Fleet as the reviewed inventory,
governance and audit plane.

Canonical operating model:

- `docs/fleet/landscape-omni-governance.md`

Boundary summary:

| Plane | Owns | Does not own |
|---|---|---|
| Omni Fleet | Reviewed inventory, desired-state governance, approved update plans, audit, PgBouncer-backed runtime state | Kubernetes workload operations or ad-hoc host console sessions |
| Landscape self-hosted | Ubuntu machine management, package activity UI, client registration, Ubuntu Pro/ESM visibility and script execution under gate | Fleet identity source of truth, K3s workloads or unrestricted repair automation |
| Landscape SaaS | Fallback/reference path | Durable endpoint for this milestone |
| Cockpit | Host-level break-glass console | Central package compliance or fleet automation |
| K3s/Portainer | Cluster and container workload administration | OS patch governance or fleet identity |
| Observability | Metrics, logs, alerts and dashboards | Automatic repair execution |

Admin surfaces must stay behind explicit gates: HTTPS proxy/auth, Cloudflare
Access when enabled, Apache auth/SSO or WireGuard. Direct anonymous admin
console exposure is not an accepted state.

## Program Collectors And Desired-State Profiles

Phase 31 adds host-local read-only collectors and desired-state profile
rendering.

Collector command:

```bash
PYTHONPATH=cli python3 -m omni fleet agent collect-programs --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet agent collect-programs --host atius-srv-1 --db --json
```

The collector records observations from package managers, language package
managers, PM2, systemd and container engines. Missing tools are warnings, not
fleet failures. The collector must not run package/service mutation commands.

Desired-state profile command:

```bash
PYTHONPATH=cli python3 -m omni fleet profiles managed-apps --json
PYTHONPATH=cli python3 -m omni fleet profiles managed-apps --db --json
```

The first seed comes from `modules/managed-apps/configs/programs.json`, which
already models managed browser programs, repositories, policies and
customizations. Execution remains separate: remediation must create or use
approved `TbUpdatePlans` and run locally on the target host agent.

## CVE/USN Reporting And Landscape Parity

Phase 32 adds read-only security reporting from Ubuntu Pro Client and documents
Landscape/Omni parity.

Commands:

```bash
PYTHONPATH=cli python3 -m omni fleet security report --host atius-srv-1 --json
PYTHONPATH=cli python3 -m omni fleet security report --host atius-srv-1 --db --json
PYTHONPATH=cli python3 -m omni fleet landscape-parity --json
```

Canonical parity doc:

- `docs/fleet/landscape-parity.md`

`pro fix` is not an automatic remediation path. Use `pro fix --dry-run` for
manual inspection, or create an approved `TbUpdatePlans` entry for any real
mutation.

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
PYTHONPATH=cli python3 -m omni fleet agent heartbeat --host atius-srv-1 --json
```

`agent heartbeat --db` writes through PgBouncer to `TbNodes` and
`TbNodeTelemetry`. The command refuses DB env files that do not point to
`10.11.1.11:6432/DbOmniFleet`; `10.100.100.1:6432` is reserve fallback only for documented exceptions, and it must not fall back to direct PostgreSQL.

## Cross-Server Monitoring

Any SRV can read the same central status view:

```bash
PYTHONPATH=cli python3 -m omni fleet monitor hosts
PYTHONPATH=cli python3 -m omni fleet monitor hosts --json
```

Default behavior:

1. Read `DbOmniFleet` through PgBouncer.
2. Return all hosts with status, agent version, last contact, load, memory,
   disk and service health.
3. If PgBouncer/DB is unavailable, degrade to local heartbeat cache under
   `/home/ubuntu/.logs/fleet/heartbeats`.
4. Do not attempt direct PostgreSQL bypass.

Telemetry exists to support the central Omni idea: active demand control and
load-balancing decisions based on real resource pressure. Initial inputs are:

| Input | Source |
|---|---|
| CPU count and load averages | `os.getloadavg()` / CPU count |
| Memory total/available/used percent | `/proc/meminfo` |
| Disk root total/used/used percent | `shutil.disk_usage("/")` |
| Disk cumulative read/write bytes | `/proc/diskstats` |
| PSI pressure | `/proc/pressure/{cpu,memory,io}` |
| Service health | `systemctl is-active` for known Omni services |

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

For executable plans, use `queue-update`. This creates or updates a row in
`TbUpdatePlans`; it does not SSH into the target host and does not execute on
the requester.

```bash
PYTHONPATH=cli python3 -m omni fleet queue-update \
  --host atius-srv-3 \
  --program ubuntu-dark-theme \
  --desired-version 24.04-v1 \
  --command-key ubuntu-dark-theme.apply \
  --json
```

Approved execution is local to the target host:

```bash
PYTHONPATH=cli python3 -m omni fleet agent once --host atius-srv-3 --db --apply
PYTHONPATH=cli python3 -m omni fleet agent loop --host atius-srv-3 --apply
```

Execution rules:

- Agent claims only rows where `host_id` matches its local host.
- `approval_state=approved`, `approved_by` and `approved_at` are required.
- `lease_owner`/`lease_expires_at` prevent two agents from executing the same
  plan.
- `idempotency_key` prevents duplicate central requests from creating repeated
  work.
- `target_command` must exist in `TbFleetCommands` or the local emergency
  allowlist.
- Host-specific allowlists prevent an SRV-1-only command from running on SRV-3.
- Output is redacted before local audit or DB execution output.

The `ubuntu-dark-theme.apply` command key is registered disabled until the
Ubuntu 24.04 dark-theme module exposes a finalized idempotent CLI-Anything
harness. This keeps the integration path ready without allowing an unsafe theme
script to run fleet-wide.

## Agent Service

User-level systemd unit:

```bash
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-1
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-2
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-3
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-4
```

Antes de instalar, hidrate o cache root-only
`/etc/omni-srv-admin/fleet-db.env` a partir do profile Vault `omni-fleet`.
O instalador então escreve `/etc/omni-srv-admin/fleet-agent.env`, copia
`omni-fleet-agent.service` to `~/.config/systemd/user/`, reloads systemd user
and enables the service. This should not drop RDP/XRDP; it only starts a user
service loop.

## Direct IP Fallback

OCI/DRG private networking is the primary server-to-server plane where
validated. `wg100` remains reserve/fallback and direct public-IP SSH/probe is
break-glass only, not public database access.

```bash
modules/fleet-control-plane/scripts/configure-fleet-direct-peers.sh
ssh atius-srv-1-direct hostname
ssh atius-srv-2-direct hostname
ssh atius-srv-3-direct hostname
```

The script writes:

- `/etc/omni-srv-admin/fleet-peers.json`
- a backed-up `~/.ssh/config` block with `*-vpn` and `*-direct` aliases

`fleet-peers.json` explicitly records:

```json
{
  "database": {
    "primary": "10.11.1.11:6432",
    "public_fallback_enabled": false
  }
}
```

Rationale: opening PgBouncer/PostgreSQL on public IP would increase blast
radius. Direct public IP is for emergency SSH/probe and future bootstrap only.

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
