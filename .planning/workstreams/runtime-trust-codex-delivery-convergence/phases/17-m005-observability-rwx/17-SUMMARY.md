---
phase: 17
plan: 17-PLAN.md
status: partial
completed_by: hermes-agent
completed_at: 2026-06-18
---

# Phase 17 — M005 Observability + RWX — SUMMARY

## Resultado

Code/artifacts shipped.
Live rollout parcial já existe no cluster.
Fechamento 100% da phase ficou bloqueado por gate de produção + webhook ausente + dashboards ainda não provisionados como ConfigMaps no Grafana.

## O que foi entregue

- `cli/omni/observability.py`
  - `omni srv observability status`
  - `omni srv observability status --json`
  - `omni srv observability validate`
  - `omni srv observability dry-run`
  - `omni srv observability config`
- `cli/omni/tests/test_observability.py`
- `modules/k3s-ha-portainer-oci/monitoring/alertmanager/values.yaml`
- `modules/k3s-ha-portainer-oci/monitoring/loki/values.yaml`
- `modules/k3s-ha-portainer-oci/monitoring/prometheus-rules/omni-rules.yaml`
- `modules/k3s-ha-portainer-oci/monitoring/dashboards/{k3s-ha,portainer,pm2-fleet,jenkins-gdrive}.json`
- `modules/k3s-ha-portainer-oci/monitoring/scripts/{install-prometheus-stack,install-loki,uninstall-monitoring}.sh`
- `docs/operations/k3s-storage.md`

## Validação real

- `python3 -m pytest cli/omni/tests/ -q` → `43 passed`
- `python3 -m pytest cli/omni/tests/test_observability.py -q` → `15 passed`
- `PYTHONPATH=cli:. python3 -m omni srv observability status`
  - `k3s`: green
  - `prometheus`: yellow (`21/23 targets up, 8 firing`)
  - `loki`: green (`1/1 running`)
  - `alertmanager`: green (`1/1 running`)
  - `prometheus-rules`: green (`35 rule(s) loaded`)
  - `dashboards`: yellow (dashboards files existem, mas ConfigMaps ainda não provisionados no Grafana)
- `sudo -n` validado OK
- `ALERT_WEBHOOK_MISSING` confirmado em `~/.hermes/secrets/alert-webhook.json`

## RWX decision

Decisão arquitetural fechada: manter `local-path` por agora.
NFS e Longhorn foram avaliados e deferidos até existir workload com necessidade real de RWX.
Ver `docs/operations/k3s-storage.md`.

## Blockers para marcar DONE

1. Gate explícito para mutação live final em produção
2. `~/.hermes/secrets/alert-webhook.json` ausente
3. Provisioning final dos dashboards como ConfigMaps para o Grafana
4. Teste real de alert routing (Hermes webhook / Telegram) ainda não executado

## Estado final honesto

- Observability stack: parcialmente live / parcialmente instrumentada
- CLI/status/testes/docs: shipped
- Phase 17: não 100% DONE ainda
