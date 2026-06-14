# K3s HA + Portainer + Observability — ATIUS

## Estado live

- K3s `v1.35.5+k3s1` em SRV-1/SRV-2/SRV-3.
- 3 nodes `Ready`, todos `control-plane,etcd`.
- Portainer CE em `portainer` namespace.
- kube-prometheus-stack em `monitoring` namespace.
- Grafana público: `https://grafana.atius.com.br`.
- Portainer público: `https://portainer.atius.com.br` e `https://docker.atius.com.br`.
- Edge protegido por Apache Basic Auth porque Cloudflare Access ainda não está habilitado na conta.

## Arquivos versionados

| Arquivo | Origem live |
|---|---|
| `k8s/kube-prometheus-stack-values.yaml` | Helm values da observability stack |
| `scripts/atius-k3s-watchdog.sh` | `/home/ubuntu/scripts/atius-k3s-watchdog.sh` |
| `systemd/atius-k3s-watchdog.service` | user service SRV-1 |
| `systemd/atius-k3s-watchdog.timer` | user timer SRV-1 |
| `systemd/k3s-portainer-portforward.service` | system service SRV-1 |
| `systemd/k3s-grafana-portforward.service` | system service SRV-1 |

## Secrets locais — não commitar

| Secret | Path SRV-1 |
|---|---|
| Portainer admin | `/home/ubuntu/.secrets/portainer-admin-password` |
| Grafana admin | `/home/ubuntu/.secrets/grafana-admin-password` |
| Edge Basic Auth | `/home/ubuntu/.secrets/edge-admin-password` |
| Apache htpasswd | `/etc/apache2/auth/atius-edge.htpasswd` |

## Comandos de validação

```bash
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pods -A -o wide
sudo env KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm list -A
curl -skI https://portainer.atius.com.br/
curl -skI https://grafana.atius.com.br/
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user status atius-k3s-watchdog.timer
```

## Pendências

- Cloudflare Access: bloqueado porque a conta retorna `access.api.error.not_enabled`.
- OCI snapshot IDs: bloqueado porque OCI CLI/config não existe localmente nem nos 3 hosts.
- HA storage Portainer/Grafana: hoje `local-path` + nodeSelector em SRV-1. Produção HA real exige RWX storage ou backup/restore explícito dos PVCs.
