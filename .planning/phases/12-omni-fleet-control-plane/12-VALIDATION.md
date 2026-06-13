---
phase: 12
name: omni-fleet-control-plane
date: 2026-06-13
status: live-implemented
method: pytest + offline harness + live SSH/repo/DB probes + multi-agent scenario review
branch: codex/omni-fleet-control-plane-m004
---

# Phase 12 Validation — Omni Fleet Control Plane

## Result

M004 is implemented for the intended live base. The live SRV1/SRV2/SRV3 network
is reachable, each host has `~/GitHub/omni-srv-admin`, SRV-1 owns central
database `omni_fleet`, all three hosts can query it through PgBouncer, and
direct PostgreSQL access from nodes is blocked.

## Automated Commands

```bash
scripts/verify-m004-fleet-control-plane.sh
PYTHONPATH=cli python3 modules/fleet-control-plane/tools/validate_m004.py --live --json
```

## Offline Contract Scenarios

| ID | Scenario | Result |
|---|---|---|
| M004-OFF-01 | SRV1/SRV2/SRV3 inventory source-of-truth | PASS |
| M004-OFF-02 | master/server + node/slave install plan matrix | PASS |
| M004-OFF-03 | safe CLI dry-run contracts execute; `--apply` blocked | PASS |
| M004-OFF-04 | PostgreSQL + PgBouncer + license schema contract | PASS |
| M004-OFF-05 | heartbeat + program registry + audit contracts | PASS |
| M004-OFF-06 | future Podman/K3s contract is documented | PASS |

## Live Read-Only Results

| Scope | Result |
|---|---:|
| SSH identity probes | 3 PASS |
| `~/GitHub/omni-srv-admin` repo + CLI smoke | 3 PASS |
| VPN full-mesh ping | 6 PASS |
| SRV-1 PostgreSQL/PgBouncer readiness | 1 PASS |
| Central `omni_fleet` query through PgBouncer | 3 PASS |
| Node PgBouncer access on `10.1.1.1:6432` | 2 PASS |
| Node direct PostgreSQL access blocked on `10.1.1.1:8745` | 2 PASS |

Live summary: `26 PASS`, `0 BLOCKED`, `0 FAIL`.

## Host Evidence

| Host | Observed OS | Arch | VPN |
|---|---|---|---|
| ATIUS-SRV-1 | Ubuntu 24.04.4 LTS | aarch64 | 10.1.1.1 |
| ATIUS-SRV-2 | Ubuntu 24.04.4 LTS | aarch64 | 10.1.1.2 |
| ATIUS-SRV-3 | Ubuntu 24.04.4 LTS | aarch64 | 10.1.1.7 |

## Master/Slave Scenario Matrix

| Scenario | Current Expected Result | Live Gate |
|---|---|---|
| SRV-1 as master/server | Dry-run plan renders PostgreSQL, migrations, PgBouncer, inventory import and audit | PASS as contract |
| SRV-2 as node/slave | Dry-run plan renders agent, heartbeat, registry, PgBouncer-only DB path and approved update execution | PASS as contract |
| SRV-3 as node/slave | Same as SRV-2 | PASS as contract |
| SRV-2 promoted to master/server | Render `install server --host atius-srv-2`; require dump/restore, PgBouncer endpoint switch and split-brain prevention before live | SIMULATED ONLY |
| SRV-3 promoted to master/server | Render `install server --host atius-srv-3`; require disk/preflight, dump/restore and PgBouncer endpoint switch before live | SIMULATED ONLY |
| SRV-1 demoted to node/slave | Render `install node --host atius-srv-1`; must not accept writes after demotion | SIMULATED ONLY |
| Node offline | Missing heartbeat becomes `offline/missing-heartbeat`; update execution stays blocked | PASS as contract |
| PgBouncer unavailable | Nodes must degrade and must not attempt direct PostgreSQL | PASS as network policy; agent behavior remains future implementation |

## PgBouncer Gate

Contract now uses private fleet endpoint:

```yaml
pgbouncer:
  listen_host: 10.1.1.1
  listen_port: 6432
  allowed_client_networks:
    - 10.1.1.0/24
```

Current live state:

1. SRV-1 PgBouncer listens on `10.1.1.1:6432`.
2. SRV-2 and SRV-3 connect to PgBouncer successfully.
3. SRV-1/SRV-2/SRV-3 query `omni_fleet` through PgBouncer successfully.
4. SRV-2 and SRV-3 cannot connect to direct PostgreSQL on `10.1.1.1:8745`.
5. PgBouncer auth material remains outside git/log/vault.
6. Firewall enforcement is installed through `omni-pg-access-guard`.

## Live Repo + DB Rollout

- SRV-1: `~/GitHub/omni-srv-admin` exists; local dirty work is preserved and was not overwritten.
- SRV-2: `~/GitHub/omni-srv-admin` updated to `main@88d35c7`, worktree clean, CLI smoke passed.
- SRV-3: `~/GitHub/omni-srv-admin` updated to `main@88d35c7`, worktree clean, CLI smoke passed.
- SRV-1: PostgreSQL database `omni_fleet` exists with the initial schema.
- SRV-1: `hosts`, `nodes` and `programs` tables are seeded from the intended SRV1/SRV2/SRV3 fleet base.
- SRV-1/SRV-2/SRV-3: `/etc/omni-srv-admin/fleet-db.env` points clients to `10.1.1.1:6432`.
- Secrets remain outside git/log/vault.

Live changes applied:

- SRV-1 `/etc/pgbouncer/pgbouncer.ini`: `listen_addr` set to
  `127.0.0.1,10.1.1.1`.
- SRV-1 `/usr/local/sbin/omni-pg-access-guard.sh`: allows node access to
  `6432` and blocks remote direct PostgreSQL `8745`.
- SRV-1 `/etc/systemd/system/omni-pg-access-guard.service`: persists the guard
  before PgBouncer starts.
- SRV-2 `wg-quick@wg0`: restarted because live `wg0` had lost its
  `10.1.1.2/24` address even though `/etc/wireguard/wg0.conf` already contained
  it.

Backups were created under `/root/omni-pg-access-backups/` on SRV-1 and
`/root/wg0.conf.pre-pgbouncer-*.bak` on SRV-2 before live edits/restarts.
The live DB/PgBouncer change also backed up SRV-1 PgBouncer files under
`/root/omni-fleet-live-backups/`.

## Multi-Agent Review Inputs

Two independent agents reviewed the validation scope:

- Contract/test gap reviewer: required automated tests for FCP-01..FCP-10,
  invalid inventory, PgBouncer contract, heartbeat, registry, update plan,
  license/audit safety and Podman/K3s compatibility.
- Multi-host matrix reviewer: required SRV1/SRV2/SRV3 identity, full-mesh,
  server/node role, PgBouncer-only DB access, direct PostgreSQL denial and
  promote/demote simulations.

Both reviews confirmed that live promote/demote and node DB access must stay
blocked until the live control plane is intentionally deployed.
