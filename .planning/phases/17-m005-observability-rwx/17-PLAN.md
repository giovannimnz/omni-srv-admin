---
phase: 17
padded: 17
slug: m005-observability-rwx
name: M005 Observability + RWX
date: 2026-06-15
status: ready
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - OBS-01
  - OBS-02
  - OBS-03
  - RWX-01
  - RWX-02
---

# Phase 17: M005 Observability + RWX

## Goal

Deploy Prometheus + Grafana + Loki stack para scraping K3s control
plane + workers + PM2 daemons + Jenkins + GDrive health, com alert
routing pra canal preferido de Giovanni. Decidir e implementar RWX
storage para K3s (NFS em SRV-1 ou Longhorn distributed).

## Motivation

M005 live, mas observability tá faltando: edge watchdog de K3s existe
mas é read-only; não há histórico de métricas, não há alerting
proativo, não há dashboard unificado. Quando um node cai, o usuário
descobre via SSH manual, não via alert.

RWX storage é pendente desde M005: sem RWX, qualquer StatefulSet
(Jenkins agent state, futuras databases) precisa de um pod per node,
o que é ineficiente. Decidir e implementar.

## Tasks

### Task 1: kube-prometheus-stack via Helm

```bash
# Add helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set prometheus.prometheusSpec.retention=30d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi
```

After install, validate:
- `kubectl -n monitoring get pods` — all Running
- Prometheus UI accessible via port-forward
- Grafana UI accessible via port-forward (default credentials admin / prom-operator)
- ServiceMonitor for kube-state-metrics auto-detected

### Task 2: Loki + Promtail for PM2 + Jenkins logs

Deploy Loki as a single-binary stateful set with 30d retention.
Promtail as a DaemonSet scraping systemd journals from each node
(PM2, jenkins controller, GDrive mount).

```bash
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set promtail.enabled=true
```

Loki datasource in Grafana auto-added.

### Task 3: Grafana dashboards

Create 4 dashboards (provisioned as ConfigMaps):
- **K3s HA**: control plane + worker CPU/mem, etcd quorum size, pod count per node, network IO
- **Portainer**: container count, container status (running/exited/created)
- **PM2 daemons**: app count online/errored/stopped, memory per app, restart count
- **Jenkins + GDrive health**: jenkins job queue, jenkins agent connectivity, GDrive quota

JSON manifests in `modules/k3s-ha-portainer-oci/monitoring/dashboards/`.

### Task 4: alert routing to Telegram/Hermes

AlertManager config:
- Route: group_by=['alertname', 'cluster'], group_wait=30s, group_interval=5m
- Receiver: `telegram` (or `hermes-webhook` if user prefers the in-house alternative)
- Webhook URL stored in `~/.hermes/secrets/alert-webhook.json` (mode 600)

Alert rules (Grafana-managed or PrometheusRule):
- KubePodCrashLooping (5min)
- KubeEtcdNoLeader (1min)
- PM2AppOffline > 5min (custom exporter or cron-checked)
- GDrive quota > 80% (custom check via `rclone about gdrive: --json`)
- Disk > 85% (node-exporter standard)

### Task 5: RWX storage decision

Compare:
- **NFS server on SRV-1**: simple, well-understood, single point of failure, can be made HA via DRBD
- **Longhorn distributed**: K3s-native, RAID across nodes, snapshot support, but more complex
- **local-path** (default): no RWX, only RWO, what we're using now

Decision criterion: cost vs. complexity vs. what we actually need. For
now, M005 is the only consumer of K3s storage (Jenkins agents have
emptyDir, Portainer is stateless). Recommend: stay with `local-path`
for now, revisit when adding a database (Gitea, Postgres-on-K8s).

Document decision in `docs/operations/k3s-storage.md`.

### Task 6: `omni srv observability status`

Add CLI command to report the health of each monitoring component:
- Prometheus: targets count, last scrape time
- Grafana: dashboard count, datasource count
- Loki: ingestion rate (last 1h)
- AlertManager: alert count by severity

Output: `omni srv observability status` → table with each component and
its current state.

## Success Criteria

- [ ] kube-prometheus-stack deployed, all pods Running
- [ ] Loki + Promtail deployed, scraping PM2 + Jenkins + GDrive logs
- [ ] 4 Grafana dashboards provisioned
- [ ] Alert routing tested: simulate crash loop, receive alert in Telegram/Hermes within 5min
- [ ] RWX decision documented in `docs/operations/k3s-storage.md`
- [ ] `omni srv observability status` returns green for all 4 components

## Risks

- **Helm chart values complexity:** kube-prometheus-stack has 100+ values; we use a minimal subset. Document the full values in `modules/k3s-ha-portainer-oci/monitoring/values.yaml`.
- **Storage class:** K3s default `local-path` works for monitoring stack as long as we set `reclaimPolicy: Delete`. For 30d retention + 50Gi, ensure enough disk on each node.
- **AlertManager false positives:** noisy alerts erode trust. Set thresholds conservatively (5min not 1min for app offline; 85% not 70% for disk).
- **Telegram bot token** in `~/.hermes/secrets/`: must be created via @BotFather before this phase. If user hasn't done it, use Hermes webhook instead (built-in).

## Out of Scope

- Distributed tracing (Jaeger / Tempo) — defer to M008
- Application Performance Monitoring (APM) — defer
- Cost analysis / FinOps — defer
- Multi-cluster observability — defer (we have 1 cluster)

## Next Phase Readiness

After 17, M005 is fully closed. M006 (resource governance) was v1.0. M007 is v1.1 close. Next: M008 (TBD — could be observability expansion, FreeIPA backlog, or new direction).
