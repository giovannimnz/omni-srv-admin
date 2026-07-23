# Phase 29: Runtime Repair - PM2 and K3s

**Execution window:** 2026-06-25T04:41Z to 2026-06-25T04:44Z
**Scope:** `atius-srv-3`, `horistic-srv`
**Operator request:** make K3s available on `horistic-srv` and resolve missing `pm2-ubuntu` on `atius-srv-3` and `horistic-srv`.

## Changes executed

| Host | Change | Result | Remote log |
| --- | --- | --- | --- |
| `atius-srv-3` | Installed PM2 globally with npm and created `pm2-ubuntu.service` oneshot systemd unit for user `ubuntu`. | `pm2-ubuntu` active/enabled, PM2 7.0.1. | `/home/ubuntu/gsd-phase29-pm2-repair-20260625T044143Z.log` |
| `horistic-srv` | Installed PM2 globally with npm and created `pm2-ubuntu.service` oneshot systemd unit for user `horistic`. | `pm2-ubuntu` active/enabled, PM2 7.0.1. | `/home/horistic/gsd-phase29-pm2-repair-20260625T044143Z.log` |
| `horistic-srv` | Installed K3s as worker agent using existing cluster endpoint `https://10.1.1.1:6443`. | `k3s-agent` active/enabled, node `horistic-srv` Ready. | `/home/horistic/gsd-phase29-k3s-agent-install-20260625T044214Z.log` |

## K3s topology decision

`horistic-srv` was joined as `k3s-agent` worker, not as a fourth etcd/control-plane server. The existing cluster already has 3 control-plane/etcd members: `atius-srv-1`, `atius-srv-2`, and `atius-srv-3`. Adding a fourth etcd member would create an even-numbered etcd set and would not improve quorum safety.

## Validation

Cluster node list after repair:

| Node | Status | Role | Internal IP |
| --- | --- | --- | --- |
| `atius-srv-1` | Ready | control-plane,etcd | 10.1.1.1 |
| `atius-srv-2` | Ready | control-plane,etcd | 10.1.1.2 |
| `atius-srv-3` | Ready | control-plane,etcd | 10.1.1.7 |
| `horistic-srv` | Ready | worker | 10.1.1.4 |

Service state after repair:

| Host | `pm2-ubuntu` | `k3s` | `k3s-agent` |
| --- | --- | --- | --- |
| `atius-srv-1` | active/enabled | active/enabled | not-found |
| `atius-srv-2` | active/enabled | active/enabled | not-found |
| `atius-srv-3` | active/enabled | active/enabled | not-found |
| `horistic-srv` | active/enabled | not-found | active/enabled |

## Artifacts

- Post-repair inventory: `29-POST-RUNTIME-REPAIR-INVENTORY.md`.
- Host inventory files updated: `inventory/hosts/atius-srv-3.yaml`, `inventory/hosts/horistic-srv.yaml`.
- Monitoring script updated to include `k3s-agent`: `scripts/g18-pro-esm-inventory.py`.

No K3s token, API secret, or credential was written to this artifact.
