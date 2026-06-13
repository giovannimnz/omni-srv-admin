---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-13
status: blocked-before-live-mutation
branch: codex/k3s-portainer-oci-plan
command: gsd-execute-phase
---

# Phase 13 Execution Checkpoint — 2026-06-13

## Result

`gsd-execute-phase` was started for M005 / Phase 13. Execution stopped before
Task 5 by design. No K3s install, Portainer install, OCI firewall change,
Cloudflare Tunnel change, swap change, `/etc/rancher` write or Kubernetes
resource creation was performed.

Safe work completed:

- Task 0 branch/worktree check: branch `codex/k3s-portainer-oci-plan`, clean at start.
- Task 1/2 live read-only validation across SRV-1/SRV-2/SRV-3.
- Read-only Apache/DNS/Portainer edge check.
- YAML syntax validation for K3s, Portainer, cloudflared and host inventory.
- Plan corrections to preserve the live gates and remove unsafe token handling.

## Live Host Snapshot

| Host | OS | Kernel | Arch | Time sync | WireGuard | Root disk | Swap | K3s |
|---|---|---|---|---|---|---|---|---|
| ATIUS-SRV-1 | Ubuntu 24.04.4 LTS | 6.17.0-1016-oracle | aarch64 | yes | `wg0 10.1.1.1/32` | 60G free / 70% used | `/swapfile` 10G active | absent |
| ATIUS-SRV-2 | Ubuntu 24.04.4 LTS | 6.17.0-1016-oracle | aarch64 | yes | `wg0 10.1.1.2/24` | 60G free / 70% used | none reported | absent |
| ATIUS-SRV-3 | Ubuntu 24.04.4 LTS | 6.17.0-1016-oracle | aarch64 | yes | `wg0 10.1.1.7/32` | 137G free / 30% used | none reported | absent |

Routes to `10.1.1.1`, `10.1.1.2` and `10.1.1.7` resolve over `wg0` from all
three hosts.

## Current Port State

- K3s candidate TCP ports `6443`, `2379`, `2380` and `10250` returned
  connection refused between all node pairs. This is expected before install.
- SRV-1 PgBouncer remains on `10.1.1.1:6432` and `127.0.0.1:6432`.
- SRV-1 PostgreSQL direct listener remains on `0.0.0.0:8745`/`[::]:8745`; node
  clients must continue to use PgBouncer.
- Apache has `portainer.atius.com.br` configured and proxying to
  `127.0.0.1:9005`.
- `portainer.atius.com.br` does not resolve in public DNS at this checkpoint.
- `docker.atius.com.br` resolves through Cloudflare and returns HTTP 503, which
  matches the prior operational decision to keep old Portainer disabled.

## Template Validation

Parsed successfully with PyYAML:

- `modules/k3s-ha-portainer-oci/k3s/config-srv1.example.yaml`
- `modules/k3s-ha-portainer-oci/k3s/config-srv2.example.yaml`
- `modules/k3s-ha-portainer-oci/k3s/config-srv3.example.yaml`
- `modules/k3s-ha-portainer-oci/k8s/portainer-values.yaml`
- `modules/k3s-ha-portainer-oci/k8s/cloudflared-deployment.yaml`
- `inventory/hosts/atius-srv-1.yaml`
- `inventory/hosts/atius-srv-2.yaml`
- `inventory/hosts/atius-srv-3.yaml`

Template corrections made:

- K3s node network fixed to WireGuard `wg0` with `flannel-iface: "wg0"`.
- K3s critical server values are now explicit and consistent across all three
  server templates: `cluster-cidr=10.42.0.0/16`,
  `service-cidr=10.43.0.0/16`, `cluster-dns=10.43.0.10`,
  `cluster-domain=cluster.local`, `flannel-backend=vxlan`,
  `disable=traefik,servicelb` and `secrets-encryption=true`.
- K3s `tls-san` entries now include all three WireGuard node IPs and all three
  hostnames to support API access/failover by private node identity.
- Portainer values now pin Community Edition explicitly with
  `enterpriseEdition.enabled=false`, `image.repository=portainer/portainer-ce`,
  `service.type=ClusterIP` and
  `trusted_origins.domains=portainer.atius.com.br`.
- `cloudflare/cloudflared` pinned to `2026.6.0` from the official GitHub
  release API instead of `latest`.
- K3s token replacement changed to a Python file rewrite so the token is not
  expanded into process arguments.
- Cloudflare Secret creation changed to stdin instead of `--from-literal`.

## Blockers

Do not run Task 5 until all are resolved:

- OCI snapshot IDs or equivalent backup IDs for SRV-1, SRV-2 and SRV-3 are not
  recorded in their respective OCI accounts.
- OCI CLI/config is not available in this execution shell, so snapshots and
  per-account security rules were not independently verified.
- Host firewall rules for K3s ports on `wg0` only are not yet applied/validated.
- SRV-1 swap is still active and must be disabled/persisted off during Task 5.
- Human approval to write `/etc/rancher/k3s/config.yaml` and install K3s is not
  recorded.

Cloudflare Tunnel token and `portainer.atius.com.br` DNS are publication gates,
not K3s bootstrap gates. If they remain unavailable, stop before Task 9 and do
not expose Portainer/Grafana.

## Next Execution Steps

1. Create/verify OCI snapshots or equivalent backups for all three nodes in
   their respective OCI accounts.
2. Record snapshot IDs in this phase log before any mutation.
3. Run serial `/etc` config backups on each node and review tar warnings.
4. Confirm OCI public ingress keeps `6443`, `2379-2380`, `8472`, `10250` closed
   in all three OCI accounts.
5. Apply/validate host firewall rules allowing K3s only on `wg0` between
   `10.1.1.x` nodes.
6. After explicit approval, continue with Task 5.
7. Before publishing Portainer/Grafana, create Cloudflare Tunnel
   `atius-k3s-portainer`, configure `portainer.atius.com.br` and provide the
   token only in shell.

## Post-Checkpoint Addition

After this checkpoint, PTP fallback full-mesh was added as `13-02-PLAN.md`.
It does not unblock Task 5 by itself. It is a production-ready gate: design and
validate SRV-1 <-> SRV-2, SRV-1 <-> SRV-3 and SRV-2 <-> SRV-3 fallback before
declaring M005 production-ready.

After the observability discussion, `13-03-PLAN.md` was added. It installs
Prometheus/Grafana after K3s/Portainer and defines the control loop boundary:
Prometheus and Alertmanager detect/notify; Omni Fleet executes approved
actions through M004 DB/audit contracts.

Template hardening validation after the post-checkpoint addition:

- PyYAML parsed all K3s, Portainer, cloudflared and host inventory YAML files.
- Consistency check passed for all critical K3s values across
  `config-srv1.example.yaml`, `config-srv2.example.yaml` and
  `config-srv3.example.yaml`.
- Portainer values check passed for CE, `ClusterIP`, `lts`,
  `portainer/portainer-ce` and `trusted_origins=portainer.atius.com.br`.

## Latest Read-only Revalidation

Executed after the observability/control-loop plan update:

| Host | OS/kernel | Disk | Swap | wg0/ping/routes | K3s | Firewall note |
|---|---|---|---|---|---|---|
| SRV-1 | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | 63G free / 68% used | active `9.9Gi/9Gi` | PASS to `10.1.1.1/2/7` over `wg0` | absent; ports `6443/2379/2380/10250/8472` not listening | `ufw` inactive |
| SRV-2 | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | 63G free / 68% used | none | PASS to `10.1.1.1/2/7` over `wg0` | absent; ports `6443/2379/2380/10250/8472` not listening | `ufw` inactive |
| SRV-3 | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | 137G free / 30% used | none | PASS to `10.1.1.1/2/7` over `wg0` | absent; ports `6443/2379/2380/10250/8472` not listening | `ufw` inactive |

Additional notes:

- Docker CLI/service is absent on all three hosts in this snapshot.
- Podman is present (`4.9.3`) on all three hosts.
- `portainer.atius.com.br` and `grafana.atius.com.br` did not resolve through
  `getent ahosts` in this shell; treat DNS as a publication gate.
- SRV-1 active swap remains a Task 5 mutation item and must be backed up,
  disabled and persisted only after the live mutation gates are satisfied.
- Host firewall remains a blocker: K3s ports must be allowed only over `wg0`
  before install.
