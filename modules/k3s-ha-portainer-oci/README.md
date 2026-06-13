# k3s-ha-portainer-oci

Execution package for M005 / Phase 13.

This module keeps the K3s HA + Portainer setup reproducible without committing
tokens or live kubeconfig files. The current branch is ready up to preflight and
template generation. Live installation remains gated by OCI snapshots,
OCI/host firewall confirmation and the out-of-band Cloudflare Tunnel token.
The K3s node network is explicitly WireGuard `wg0` / `10.1.1.0/24`.

## Contents

| Path | Purpose |
|---|---|
| `k3s/config-srv1.example.yaml` | First K3s server config template |
| `k3s/config-srv2.example.yaml` | Join config template for SRV-2 |
| `k3s/config-srv3.example.yaml` | Join config template for SRV-3 |
| `k8s/portainer-values.yaml` | Helm values for Portainer CE LTS |
| `k8s/cloudflared-deployment.yaml` | Cloudflare Tunnel deployment without token |
| `logrotate/docker-json-containers` | Docker JSON log rotation installed during preflight on SRV-2/SRV-3 |

## Still Required Before Install

- OCI snapshots or equivalent backups for all three instances/block volumes.
- OCI NSG/Security List rules restricting K3s ports to private node traffic.
- Cloudflare remotely-managed tunnel `atius-k3s-portainer`.
- Tunnel token supplied only in the shell as `CLOUDFLARE_TUNNEL_TOKEN`.
- Human approval to write `/etc/rancher/k3s/config.yaml` and install K3s.

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
