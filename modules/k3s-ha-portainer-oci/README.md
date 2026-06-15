# K3s HA + Portainer + Observability — ATIUS

## Estado live

- K3s `v1.35.5+k3s1` em SRV-1/SRV-2/SRV-3.
- 3 nodes `Ready`, todos `control-plane,etcd`.
- Portainer CE em `portainer` namespace.
- kube-prometheus-stack em `monitoring` namespace.
- Grafana público: `https://grafana.atius.com.br`.
- Portainer público: `https://portainer.atius.com.br` e `https://docker.atius.com.br`.
- Edge protegido por Apache Basic Auth enquanto Cloudflare Access e validado sem custo na conta.

## Arquivos versionados

| Arquivo | Origem live |
|---|---|
| `k8s/kube-prometheus-stack-values.yaml` | Helm values da observability stack |
| `scripts/atius-k3s-watchdog.sh` | `/home/ubuntu/scripts/atius-k3s-watchdog.sh` |
| `scripts/collect-network-map.sh` | coleta snapshot read-only de rede, portas, Podman e K3s dos 3 SRVs |
| `scripts/backup-local-path-pvcs.sh` | gera bundle crash-consistent de etcd + PVCs `local-path` no SRV-1 |
| `scripts/promote-network-map-to-fleet-db.sh` | promove o snapshot operacional M005 para `DbOmniFleet/TbConfigItems` via PgBouncer |
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

## Operação M005

```bash
modules/k3s-ha-portainer-oci/scripts/collect-network-map.sh > .planning/phases/13-k3s-ha-portainer-oci/13-NETWORK-MAP-YYYY-MM-DD.md
modules/k3s-ha-portainer-oci/scripts/backup-local-path-pvcs.sh
modules/k3s-ha-portainer-oci/scripts/promote-network-map-to-fleet-db.sh
```

Último bundle executado:

- `/home/ubuntu/.backups/k3s-local-path/20260614-150944`
- Inclui `pv-pvc.yaml`, `workloads.yaml`, `helm-list.txt`, snapshot etcd `m005-pvc-backup-20260614-150944`, arquivos `.tgz` dos PVCs `local-path` e `SHA256SUMS`.
- Observação: o PVC do Prometheus pode registrar warning de WAL mutando durante leitura; o bundle continua válido como backup crash-consistent.
- Snapshot operacional promovido ao DB: `TbConfigItems.key = m005.cluster_operational_snapshot` em `scope_id=srv1-ops`, `host_id=atius-srv-1`.

## Runbooks

- Network map: `.planning/phases/13-k3s-ha-portainer-oci/13-NETWORK-MAP-2026-06-14.md`
- Restore drill: `.planning/phases/13-k3s-ha-portainer-oci/13-RESTORE-DRILL-2026-06-14.md`
- OCI rollback path superseded for M005 by GDrive DR decision: `.planning/phases/13-k3s-ha-portainer-oci/13-OCI-ROLLBACK-PATH-2026-06-14.md`
- PTP/direct-IP fallback review: `.planning/phases/13-k3s-ha-portainer-oci/13-FALLBACK-PTP-2026-06-14.md`
- No-cost release plan: `.planning/phases/13-k3s-ha-portainer-oci/13-01-PLAN.md`

## Pendências

- Cloudflare Access: selecionado se free/available; manter Basic Auth ate validacao.
- GDrive DR: substitui snapshots OCI no M005 para evitar custo; exige bundle, checksum e restore drill validado.
- HA storage Portainer/Grafana/Prometheus/Alertmanager: `local-path` + GDrive backup/restore aceito para M005; Longhorn/RWX fica diferido.
- Fallback de transporte: Tailscale sera fallback operacional de gestao; K3s/flannel/etcd continuam dependentes de WireGuard no M005.
- Jenkins: corrigir `container-jenkins.service` para Podman socket/CLI; estado atual retorna Apache 503 porque `/var/run/docker.sock` nao existe.
- Ubuntu Pro/ESM Apps: validar `pro status` e habilitar `esm-apps` nos 3 SRVs sem registrar token.
