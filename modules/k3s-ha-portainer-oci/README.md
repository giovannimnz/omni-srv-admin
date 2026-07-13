# k3s-ha-portainer-oci

Execution package for M005 / Phase 13.

This module keeps the K3s HA + Portainer setup reproducible without committing
tokens or live kubeconfig files. The current branch is ready up to preflight and
template generation. Live installation remains gated by OCI snapshots,
OCI/host firewall confirmation and the out-of-band Cloudflare Tunnel token.
SRV-1, SRV-2 and SRV-3 are in separate OCI accounts, so all OCI gates are
validated per account; there is no shared NSG/VCN assumption.
The K3s node network is now canonically the OCI/DRG private plane (`10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`), with `wg100` / `10.100.100.0/24` retained as reserve dual-bind only.
The templates also pin K3s critical server values consistently across all
three servers: `cluster-cidr=10.42.0.0/16`, `service-cidr=10.43.0.0/16`,
`cluster-dns=10.43.0.10`, `cluster-domain=cluster.local`,
`flannel-backend=vxlan`, `disable=traefik,servicelb` and
`secrets-encryption=true`.
PTP fallback mesh design lives in
`.planning/phases/13-k3s-ha-portainer-oci/13-02-PLAN.md` and is required before
production-ready, but it is not active in these templates.

## Contents

| Path | Purpose |
|---|---|
| `k3s/config-srv1.example.yaml` | First K3s server config template |
| `k3s/config-srv2.example.yaml` | Join config template for SRV-2 |
| `k3s/config-srv3.example.yaml` | Join config template for SRV-3 |
| `k8s/portainer-values.yaml` | Helm values for Portainer CE LTS |
| `k8s/kube-prometheus-stack-values.yaml` | Helm values for Prometheus/Grafana observability |
| `k8s/cloudflared-deployment.yaml` | Cloudflare Tunnel deployment without token |
| `k8s/cpu-20-defaults.yaml` | Namespace `LimitRange` defaulting managed containers to `500m` CPU |
| `k8s/pod-500m-strict.yaml` | Workload namespace `LimitRange` enforcing pod CPU max `500m` |
| `logrotate/docker-json-containers` | Docker JSON log rotation installed during preflight on SRV-2/SRV-3 |

## Resource Unit

Managed k3s workloads use `1 pod = 500m CPU = 0.5 host CPU/vCPU`.
Two replicas/pods at this standard equal `1000m`, or one full CPU core. Because
Kubernetes accounts CPU per container, one-container pods must set
`requests.cpu=500m` and `limits.cpu=500m`; multi-container pods must split that
same pod budget explicitly.

## Still Required Before Install

- OCI snapshots or equivalent backups for all three instances/block volumes in
  their respective OCI accounts.
- OCI NSG/Security List rules per account keeping K3s ports closed publicly.
- Cloudflare remotely-managed tunnel `atius-k3s-portainer`.
- Tunnel token supplied only in the shell as `CLOUDFLARE_TUNNEL_TOKEN`.
- Human approval to write `/etc/rancher/k3s/config.yaml` and install K3s.
- PTP fallback full-mesh design before declaring production-ready.

## Portainer Exposure Shape

Portainer CE LTS is configured as `ClusterIP`, pinned to `atius-srv-2` via
`nodeSelector`, with `enterpriseEdition.enabled=false` and
`trusted_origins=portainer.atius.com.br`. Public access must come through
Cloudflare Tunnel and Access, not NodePort or LoadBalancer.

The srv2 placement preserves one 500m scheduling unit on `atius-srv-1` for
node-pinned production workloads such as `router-ai-atius` without weakening
the cluster `system-reserved` CPU margin.

For the same capacity contract, Alertmanager is pinned to `atius-srv-2` and
Grafana to `atius-srv-3`; their `local-path` PVCs must remain on the matching
nodes and use reclaim policy `Retain` after migration.

Prometheus/Grafana are planned through `kube-prometheus-stack` in namespace
`monitoring`. Grafana uses a Kubernetes Secret for admin credentials and may be
published only through Cloudflare Access. Prometheus and Alertmanager remain
internal. Alertmanager should signal Omni Fleet; it must not execute host
commands directly.

## Non-secret Install Shape

```bash
sudo install -d -m 700 /etc/rancher/k3s
sudo sh -c 'umask 077; openssl rand -hex 32 > /etc/rancher/k3s/cluster-token'
sudo install -m 600 modules/k3s-ha-portainer-oci/k3s/config-srv1.example.yaml /etc/rancher/k3s/config.yaml
sudo python3 - <<'PY'
from pathlib import Path
cfg = Path("/etc/rancher/k3s/config.yaml")
token = Path("/etc/rancher/k3s/cluster-token").read_text().strip()
cfg.write_text(cfg.read_text().replace("<K3S_CLUSTER_TOKEN>", token))
PY
curl -sfL https://get.k3s.io | INSTALL_K3S_CHANNEL=stable sh -
```

Do not copy the token into git, vault notes or command logs.
