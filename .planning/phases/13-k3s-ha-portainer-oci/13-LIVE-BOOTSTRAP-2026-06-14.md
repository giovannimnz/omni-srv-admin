---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-14
status: live-cluster-green
branch: codex/k3s-portainer-oci-plan
command: autonomous-live-execution
---

# Phase 13 Live Bootstrap — 2026-06-14

## Result

K3s HA cluster is live across SRV-1, SRV-2 and SRV-3.

Portainer Community Edition is deployed in the cluster and reachable through the existing Apache edge.

## Live Cluster

| Node | Role | Internal IP | Status | Version | Runtime |
|---|---|---|---|---|---|
| atius-srv-1 | control-plane,etcd | 10.1.1.1 | Ready | v1.35.5+k3s1 | containerd://2.2.3-k3s1 |
| atius-srv-2 | control-plane,etcd | 10.1.1.2 | Ready | v1.35.5+k3s1 | containerd://2.2.3-k3s1 |
| atius-srv-3 | control-plane,etcd | 10.1.1.7 | Ready | v1.35.5+k3s1 | containerd://2.2.3-k3s1 |

## Bootstrap Actions

- Created critical local backups on all three hosts under `~/.backups/k3s-preflight/`.
- Disabled and persisted off swap on all three hosts.
- Enabled `overlay`, `br_netfilter`, `net.ipv4.ip_forward=1`, bridge iptables sysctls.
- Installed persistent systemd firewall guard: `atius-k3s-firewall.service`.
- Installed K3s `v1.35.5+k3s1` with embedded etcd.
- Installed Helm `v3.21.1` on SRV-1.
- Installed Portainer chart `portainer/portainer`, image `portainer/portainer-ce:lts`.
- Installed persistent Portainer port-forward service: `k3s-portainer-portforward.service`.
- Initialized Portainer admin account. Password is stored on SRV-1 at `/home/ubuntu/.secrets/portainer-admin-password` with mode `0600` (not committed, not logged).
- Registered local Kubernetes environment in Portainer as endpoint `atius-k3s` (`Type=5`, URL `https://kubernetes.default.svc`).
- Updated Apache `portainer.atius.com.br` proxy from `http://127.0.0.1:9005` to `https://127.0.0.1:9443`.
- Created Cloudflare proxied CNAME `portainer.atius.com.br -> docker.atius.com.br`.

## Security Controls

Host firewall guard on each node:

- Allows K3s control-plane/kubelet/VXLAN ports from:
  - `lo`
  - `wg0`, source `10.1.1.0/24`
  - pod CIDR `10.42.0.0/16`
- Drops non-cluster traffic to:
  - TCP `6443,2379,2380,10250,10257,10259`
  - UDP `8472`

Apache edge:

- `docker.atius.com.br` proxies to `https://127.0.0.1:9443/`.
- `portainer.atius.com.br` proxies to `https://127.0.0.1:9443/`.

## Validation

| Check | Result |
|---|---|
| `kubectl get nodes -o wide` | 3/3 Ready |
| `kubectl get pods -A` | CoreDNS, local-path-provisioner, metrics-server Running |
| DaemonSet smoke | 3/3 pods Running, one per node |
| DNS smoke | every smoke pod resolved `kubernetes.default.svc.cluster.local -> 10.43.0.1` |
| Portainer rollout | `deployment/portainer` successfully rolled out |
| Portainer local API | `https://127.0.0.1:9443/api/system/status` returned Version `2.39.3` |
| Portainer admin login | `POST /api/auth` returned JWT; token was not logged |
| Portainer endpoint | `GET /api/endpoints` returned `ENDPOINT_COUNT=1`, endpoint `atius-k3s`, `Type=5`, `Status=1` |
| Docker public endpoint | `https://docker.atius.com.br/api/system/status` returned Version `2.39.3` |
| Portainer public endpoint | `https://portainer.atius.com.br/api/system/status` returned Version `2.39.3` |
| SRV services | `k3s` active on SRV-1/SRV-2/SRV-3 |
| Firewall services | `atius-k3s-firewall` active on SRV-1/SRV-2/SRV-3 |
| Etcd snapshot | `atius-post-bootstrap-20260614-000034-atius-srv-1-1781406035` saved |

## Backups

Critical backups created before K3s live mutation:

| Host | Backup | SHA256 |
|---|---|---|
| SRV-1 | `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-1-20260613-235405.tgz` | `21bc116c4cb5feaf04fdfe1afcb479cee48b46ddd7ca51c701df472d547986fd` |
| SRV-2 | `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-2-20260613-235406.tgz` | `026b167e0d55ee3d6e3dd5294d90f129a8146b20d925097618c637ed6fa1d57f` |
| SRV-3 | `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-3-20260614-025406.tgz` | `c3eb1659ce66b738bb58a0c59c3f4dd65a836de01c9c8d758a993b6d4bebb7b3` |

GDrive backup note: SRV-1 full GDrive backup was already running during execution; no new rclone job was started to avoid quota collision.

## Remaining Follow-ups

- [ ] Add external uptime/health watchdog for K3s API and Portainer.
- [ ] Decide if Portainer should remain pinned to SRV-1 via nodeSelector or move to a replicated HA layout with RWX storage.
- [ ] Add formal OCI snapshot IDs when available in each OCI account.
- [ ] Add Cloudflare Access policy before sharing Portainer broadly.
- [ ] Add Prometheus/Grafana observability from `13-03-PLAN.md`.
