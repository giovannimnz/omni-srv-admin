---
phase: 12
name: omni-fleet-control-plane
date: 2026-06-13
status: validated-with-live-blockers
method: pytest + offline harness + live read-only SSH probes + multi-agent scenario review
branch: codex/omni-fleet-control-plane-m004
---

# Phase 12 Validation — Omni Fleet Control Plane

## Result

M004 is validated as a contract and test harness. The live SRV1/SRV2/SRV3
network is reachable, and direct PostgreSQL access from nodes is blocked.

Live node-to-PgBouncer access is not ready yet:

- SRV-1 has PostgreSQL and PgBouncer active locally.
- PgBouncer is listening on `127.0.0.1:6432`.
- SRV-2 and SRV-3 cannot reach `10.1.1.1:6432`.

This is a correct blocker for live Fleet node operation. It must remain blocked
until PgBouncer is intentionally bound to the private fleet endpoint and access
is restricted to the approved fleet network.

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
| VPN full-mesh ping | 6 PASS |
| SRV-1 local PostgreSQL/PgBouncer readiness | 1 PASS |
| Node direct PostgreSQL access blocked on `10.1.1.1:5432` | 2 PASS |
| Node PgBouncer access on `10.1.1.1:6432` | 2 BLOCKED |

Live summary: `18 PASS`, `2 BLOCKED`, `0 FAIL`.

## Host Evidence

| Host | Observed OS | Arch | VPN |
|---|---|---|---|
| ATIUS-SRV-1 | Ubuntu 24.04.4 LTS | aarch64 | 10.1.1.1 |
| ATIUS-SRV-2 | Ubuntu 22.04.5 LTS | aarch64 | 10.1.1.2 |
| ATIUS-SRV-3 | Ubuntu 22.04.5 LTS | aarch64 | 10.1.1.7 |

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
| PgBouncer unavailable | Nodes must degrade and must not attempt direct PostgreSQL | PARTIAL: direct PostgreSQL blocked, PgBouncer remote unavailable |

## PgBouncer Gate

Contract now uses private fleet endpoint:

```yaml
pgbouncer:
  listen_host: 10.1.1.1
  listen_port: 6432
  allowed_client_networks:
    - 10.1.1.0/24
```

Do not mark live Fleet node DB access complete until:

1. SRV-1 PgBouncer listens on `10.1.1.1:6432` or an approved private endpoint.
2. SRV-2 and SRV-3 connect to PgBouncer successfully.
3. SRV-2 and SRV-3 still cannot connect to direct PostgreSQL on `10.1.1.1:5432`.
4. PgBouncer auth material is stored outside git/log/vault.
5. The change has a rollback and audit event.

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
