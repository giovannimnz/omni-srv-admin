---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-14
status: observability-watchdog-live
---

# Phase 13 Observability + Watchdog — 2026-06-14

## Resultado

Observability stack instalada e validada.

Edge admin protegido com Apache Basic Auth porque Cloudflare Access API retornou `access.api.error.not_enabled`.

## Observability

| Componente | Namespace | Status |
|---|---|---|
| Prometheus | `monitoring` | Running, `2/2` |
| Alertmanager | `monitoring` | Running, `2/2` |
| Grafana | `monitoring` | Running, `3/3` |
| kube-state-metrics | `monitoring` | Running |
| prometheus-node-exporter | `monitoring` | 3/3 nodes |
| prometheus-operator | `monitoring` | Running |

Helm release:

- `omni-monitoring`
- chart `kube-prometheus-stack-86.2.3`
- app `v0.91.0`

## Grafana

- Local port-forward: `127.0.0.1:3005 -> svc/omni-monitoring-grafana:80`.
- Systemd service: `k3s-grafana-portforward.service`.
- Public domain: `grafana.atius.com.br`.
- Public no-auth: `401`.
- Public with edge auth: `302 /login`.
- Grafana API auth: `GET /api/org` returned `ORG 1 Main Org.`.
- Password path: `/home/ubuntu/.secrets/grafana-admin-password` (`0600`).

## Edge protection

Cloudflare Access attempt:

- Endpoint: `/accounts/<account>/access/apps`.
- Result: HTTP 403.
- Error: `access.api.error.not_enabled`.

Fallback applied:

- Apache Basic Auth on:
  - `docker.atius.com.br`
  - `portainer.atius.com.br`
  - `grafana.atius.com.br`
- User: `giovanni`.
- Password path: `/home/ubuntu/.secrets/edge-admin-password` (`0600`).
- htpasswd path: `/etc/apache2/auth/atius-edge.htpasswd` (`0640`, `root:www-data`).

Validation:

| Domain | No auth | With Basic Auth |
|---|---:|---:|
| `docker.atius.com.br` | 401 | 200 |
| `portainer.atius.com.br` | 401 | 200 |
| `grafana.atius.com.br` | 401 | 302 `/login` |

## Watchdog

- Script: `/home/ubuntu/scripts/atius-k3s-watchdog.sh`.
- Timer: `atius-k3s-watchdog.timer` (systemd user, every 60s).
- Log: `/home/ubuntu/.logs/atius-k3s-watchdog.log`.
- Validated log: `OK ready_nodes=3/3 notready_pods=0`.

Checks:

- local `k3s` service.
- remote `k3s` service on SRV-2/SRV-3.
- `atius-k3s-firewall.service`.
- `k3s-portainer-portforward.service`.
- `k3s-grafana-portforward.service`.
- node readiness 3/3.
- pod container readiness.
- Portainer local + public HTTP with edge Basic Auth.
- Grafana local + public HTTP with edge Basic Auth.
- Watchdog public checks use `/home/ubuntu/.secrets/edge-admin-password`; no password is logged or committed.

## OCI snapshots

Formal OCI snapshot IDs were not recorded.

Blocker:

- `oci` CLI absent locally and on SRV-1/SRV-2/SRV-3.
- `~/.oci` config absent.
- Oracle Cloud Agent logs exist but do not expose snapshot creation capability or snapshot IDs.

Rollback currently available:

- etcd snapshot: `atius-pre-observability-20260614-002029-atius-srv-1-1781407230`.
- critical local backups under `~/.backups/k3s-preflight/`.

## Pendências restantes

- Enable Cloudflare Access in dashboard, then replace Apache Basic Auth or keep both.
- Add formal OCI snapshot IDs through Oracle console/API.
- Decide RWX storage / PVC backup strategy for Portainer+Grafana HA.
