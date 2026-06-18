---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-14
status: runbook-ready-no-destructive-restore
branch: docs/m005-restore-drill-20260614
mode: read-only-plan
---

# Phase 13 Restore Drill — 2026-06-14

## Objetivo

Formalizar o restore de Portainer, Grafana, Prometheus e Alertmanager para M005 usando o bundle atual de PVCs `local-path` + snapshot etcd do K3s, sem executar restore destrutivo no cluster live.

Este documento descreve o procedimento real de rollback para o estado capturado em `2026-06-14 15:09:44 -03:00`.

## 2026-06-15 M005 Decision

O M005 aceita `local-path` + backup GDrive + restore drill como estrategia de
storage/rollback sem custo. GDrive substitui snapshots OCI como gate de
rollback deste milestone.

Novo criterio de fechamento:

1. gerar bundle local com `SHA256SUMS`;
2. copiar o bundle para GDrive via `rclone copy`, nao por escrita pesada no
   mount `~/GDrive`;
3. validar listagem/checksum material no GDrive;
4. registrar o path GDrive no gate review e, quando seguro, em
   `DbOmniFleet/TbConfigItems`.

## Artefatos confirmados

Bundle validado em SRV-1:

- Diretório: `/home/ubuntu/.backups/k3s-local-path/20260614-150944`
- Snapshot etcd lógico no bundle: `m005-pvc-backup-20260614-150944`
- Arquivo real do snapshot local K3s: `/var/lib/rancher/k3s/server/db/snapshots/m005-pvc-backup-20260614-150944-atius-srv-1-1781460585`
- Checksums: `/home/ubuntu/.backups/k3s-local-path/20260614-150944/SHA256SUMS`
- Warning registrado: `tar-warnings.log` indica mutação live no PVC do Prometheus durante o backup

PVCs e arquivos associados:

| App | Namespace | PVC | PV | Path live em SRV-1 | Arquivo do bundle |
|---|---|---|---|---|---|
| Portainer | `portainer` | `portainer` | `pvc-f0a94018-f4e7-4001-9fd0-1e13bc0cb814` | `/var/lib/rancher/k3s/storage/pvc-f0a94018-f4e7-4001-9fd0-1e13bc0cb814_portainer_portainer` | `pvc-f0a94018-f4e7-4001-9fd0-1e13bc0cb814__portainer__portainer.tgz` |
| Grafana | `monitoring` | `omni-monitoring-grafana` | `pvc-fdb97914-ccba-4d22-8261-71534be0f67b` | `/var/lib/rancher/k3s/storage/pvc-fdb97914-ccba-4d22-8261-71534be0f67b_monitoring_omni-monitoring-grafana` | `pvc-fdb97914-ccba-4d22-8261-71534be0f67b__monitoring__omni-monitoring-grafana.tgz` |
| Prometheus | `monitoring` | `prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0` | `pvc-5ecc69dc-5d54-4a22-8b90-e6e9d5ef48d4` | `/var/lib/rancher/k3s/storage/pvc-5ecc69dc-5d54-4a22-8b90-e6e9d5ef48d4_monitoring_prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0` | `pvc-5ecc69dc-5d54-4a22-8b90-e6e9d5ef48d4__monitoring__prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0.tgz` |
| Alertmanager | `monitoring` | `alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0` | `pvc-0acadfd3-899b-4adb-9c1e-fa8aae8f104b` | `/var/lib/rancher/k3s/storage/pvc-0acadfd3-899b-4adb-9c1e-fa8aae8f104b_monitoring_alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0` | `pvc-0acadfd3-899b-4adb-9c1e-fa8aae8f104b__monitoring__alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0.tgz` |

## Quando usar este restore

Use este runbook quando pelo menos um destes cenários ocorrer:

1. Corrupção lógica do estado Kubernetes e necessidade de voltar o cluster inteiro para o snapshot de `2026-06-14 15:09`.
2. Perda/corrupção do conteúdo `local-path` em SRV-1 para Portainer/Grafana/Prometheus/Alertmanager.
3. Falha operacional após mudança live em charts/Secrets/ConfigMaps/CRDs relacionada a M005, com necessidade de rollback completo.

Este runbook assume restore do cluster inteiro para manter consistência entre:

- metadata em etcd;
- bindings PV/PVC;
- conteúdo em disco dos PVCs `local-path`.

## Limitações explícitas do backup atual

1. O bundle atual e o script `backup-local-path-pvcs.sh` são **crash-consistent**, não application-consistent.
2. O script **não** faz scale down, freeze, fsfreeze nem quiesce de Portainer/Grafana/Prometheus/Alertmanager.
3. O `tar-warnings.log` confirma escrita concorrente no PVC do Prometheus durante a coleta. Resultado esperado:
   - replay de WAL no startup;
   - perda dos samples mais recentes;
   - possível janela curta com gaps ou duplicação perto do timestamp do backup.
4. Grafana e Portainer podem conter estado parcialmente persistido no instante da captura:
   - dashboards alterados muito perto do backup podem voltar ao estado anterior;
   - sessões, tokens, preferências ou configurações salvas em janela de corrida podem não refletir o último write.
5. Alertmanager pode perder estado recente de silences, notification log e dedup cache.
6. Todos os PVCs estão em `local-path` + `RWO` + node affinity para `atius-srv-1`. Este backup **não** resolve HA real nem failover automático para SRV-2/SRV-3.
7. Não há OCIDs de snapshot OCI registrados no repo e eles não são mais gate do M005. Portanto este drill cobre rollback K3s/PVC e rebuild operacional via GDrive; não cobre rollback instantâneo de VM/disco.

## Pré-condições para um restore real

Antes de executar restore destrutivo:

1. Janela de manutenção aprovada.
2. Confirmação explícita de que o objetivo é voltar para o ponto de `2026-06-14 15:09:44 -03:00`.
3. Acesso shell sudo a SRV-1, SRV-2 e SRV-3.
4. Bundle local presente em SRV-1:
   - `/home/ubuntu/.backups/k3s-local-path/20260614-150944`
5. Token do cluster preservado:
   - `/var/lib/rancher/k3s/server/token`
6. Backup defensivo do estado imediatamente anterior ao restore:
   - `sudo k3s etcd-snapshot save --name pre-restore-$(date +%Y%m%d-%H%M%S)`
   - cópia de `/var/lib/rancher/k3s/server/token`
   - opcionalmente novo bundle `backup-local-path-pvcs.sh` se o cluster ainda estiver íntegro

## Pré-checks obrigatórios

Executar em SRV-1 antes de parar o cluster:

```bash
export BUNDLE=/home/ubuntu/.backups/k3s-local-path/20260614-150944
export SNAPSHOT=/var/lib/rancher/k3s/server/db/snapshots/m005-pvc-backup-20260614-150944-atius-srv-1-1781460585

test -d "$BUNDLE"
test -f "$SNAPSHOT"
sudo test -f /var/lib/rancher/k3s/server/token

(cd "$BUNDLE" && sha256sum -c SHA256SUMS)

sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pv,pvc -A -o wide
sudo k3s kubectl get pods -n portainer -o wide
sudo k3s kubectl get pods -n monitoring -o wide
sudo env KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm list -A
```

Se `sha256sum -c` falhar, abortar o restore.

## Sequência de restore recomendada

### 1. Congelar tráfego de borda e watchdog

Em SRV-1:

```bash
sudo systemctl stop k3s-portainer-portforward.service
sudo systemctl stop k3s-grafana-portforward.service
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user stop atius-k3s-watchdog.timer
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user stop atius-k3s-watchdog.service
```

Objetivo:

- evitar healthchecks gerando ruído;
- impedir tráfego administrativo durante o rollback.

### 2. Parar K3s em todos os servers

Em SRV-1, SRV-2 e SRV-3:

```bash
sudo systemctl stop k3s
sudo systemctl is-active k3s || true
```

Validar que nenhum processo do control plane permaneceu ativo:

```bash
sudo ps -ef | grep '[k]3s server' || true
```

### 3. Fazer backup defensivo do DB atual dos peers

Em SRV-2 e SRV-3, antes de apagar o DB antigo:

```bash
sudo mkdir -p /var/lib/rancher/k3s/server/db-pre-restore
sudo mv /var/lib/rancher/k3s/server/db /var/lib/rancher/k3s/server/db-pre-restore/db-$(date +%Y%m%d-%H%M%S)
```

Motivo: o upstream do K3s manda remover `server/db` dos peers para eles reentrarem no cluster restaurado. Aqui o procedimento preserva uma cópia local antes da remoção lógica.

### 4. Restaurar o snapshot etcd em SRV-1

Em SRV-1:

```bash
export SNAPSHOT=/var/lib/rancher/k3s/server/db/snapshots/m005-pvc-backup-20260614-150944-atius-srv-1-1781460585
sudo k3s server \
  --cluster-reset \
  --cluster-reset-restore-path="$SNAPSHOT"
```

Saída esperada no final:

```text
Managed etcd cluster membership has been reset, restart without --cluster-reset flag now.
```

Observações:

- O restore move o DB etcd atual para `etcd-old-*`.
- O restore reseta a membership do etcd para um único member.
- Ainda **não** subir os peers nesse momento.

### 5. Reidratar os PVCs `local-path` em SRV-1 antes do primeiro start pós-restore

Com K3s ainda parado em SRV-1:

```bash
export BUNDLE=/home/ubuntu/.backups/k3s-local-path/20260614-150944

sudo tar -C / -xzf "$BUNDLE/pvc-f0a94018-f4e7-4001-9fd0-1e13bc0cb814__portainer__portainer.tgz"
sudo tar -C / -xzf "$BUNDLE/pvc-fdb97914-ccba-4d22-8261-71534be0f67b__monitoring__omni-monitoring-grafana.tgz"
sudo tar -C / -xzf "$BUNDLE/pvc-5ecc69dc-5d54-4a22-8b90-e6e9d5ef48d4__monitoring__prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0.tgz"
sudo tar -C / -xzf "$BUNDLE/pvc-0acadfd3-899b-4adb-9c1e-fa8aae8f104b__monitoring__alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0.tgz"
```

Checar se os diretórios voltaram:

```bash
sudo ls -ld \
  /var/lib/rancher/k3s/storage/pvc-f0a94018-f4e7-4001-9fd0-1e13bc0cb814_portainer_portainer \
  /var/lib/rancher/k3s/storage/pvc-fdb97914-ccba-4d22-8261-71534be0f67b_monitoring_omni-monitoring-grafana \
  /var/lib/rancher/k3s/storage/pvc-5ecc69dc-5d54-4a22-8b90-e6e9d5ef48d4_monitoring_prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0 \
  /var/lib/rancher/k3s/storage/pvc-0acadfd3-899b-4adb-9c1e-fa8aae8f104b_monitoring_alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0
```

### 6. Subir SRV-1 sozinho

Em SRV-1:

```bash
sudo systemctl start k3s
sudo systemctl status --no-pager k3s
```

Esperar API e etcd estabilizarem:

```bash
until sudo k3s kubectl get nodes >/dev/null 2>&1; do sleep 5; done
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl get pv,pvc -A -o wide
sudo env KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm list -A
```

Resultado esperado neste ponto:

- SRV-1 visível;
- objetos do cluster restaurados para o timestamp do snapshot;
- PV/PVC ainda apontando para `atius-srv-1`;
- Portainer e stack `omni-monitoring` reaparecendo conforme o scheduler reconcilia.

### 7. Rejuntar SRV-2 e SRV-3

Em SRV-2 e depois em SRV-3:

```bash
sudo mkdir -p /var/lib/rancher/k3s/server
sudo rm -rf /var/lib/rancher/k3s/server/db
sudo systemctl start k3s
sudo systemctl status --no-pager k3s
```

Confirmar em SRV-1:

```bash
sudo k3s kubectl get nodes -o wide
```

Resultado esperado: `atius-srv-1`, `atius-srv-2`, `atius-srv-3` voltam como `Ready`.

### 8. Validar workloads e PVCs restaurados

Em SRV-1:

```bash
sudo k3s kubectl get pods -n portainer -o wide
sudo k3s kubectl get pods -n monitoring -o wide
sudo k3s kubectl describe pvc -n portainer portainer
sudo k3s kubectl describe pvc -n monitoring omni-monitoring-grafana
sudo k3s kubectl describe pvc -n monitoring prometheus-omni-monitoring-prometheus-db-prometheus-omni-monitoring-prometheus-0
sudo k3s kubectl describe pvc -n monitoring alertmanager-omni-monitoring-alertmanager-db-alertmanager-omni-monitoring-alertmanager-0
```

Esperado:

- `portainer` deployment `1/1`;
- `omni-monitoring-grafana` `3/3`;
- `prometheus-omni-monitoring-prometheus-0` `2/2`;
- `alertmanager-omni-monitoring-alertmanager-0` `2/2`.

### 9. Validar APIs e edge

Em SRV-1:

```bash
sudo systemctl start k3s-portainer-portforward.service
sudo systemctl start k3s-grafana-portforward.service
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start atius-k3s-watchdog.service
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start atius-k3s-watchdog.timer

curl -skI https://portainer.atius.com.br/
curl -skI https://grafana.atius.com.br/
curl -sk https://127.0.0.1:9443/api/system/status
curl -sk http://127.0.0.1:3000/api/health
```

Validação funcional mínima recomendada:

1. Login no Portainer e confirmar endpoint `atius-k3s` online.
2. Login no Grafana e abrir ao menos um dashboard default.
3. Confirmar targets do Prometheus via UI/API.
4. Confirmar em Alertmanager que a UI abre e não há crashloop.

## Critérios de sucesso

Considerar o restore bem-sucedido somente se todos abaixo passarem:

1. `kubectl get nodes` retorna os 3 servers `Ready`.
2. `helm list -A` mostra `portainer` e `omni-monitoring` como `deployed`.
3. Os 4 PVCs voltam `Bound` nos mesmos namespaces.
4. Portainer, Grafana, Prometheus e Alertmanager sobem sem `CrashLoopBackOff`.
5. `curl -skI https://portainer.atius.com.br/` e `curl -skI https://grafana.atius.com.br/` retornam `401` sem auth e `200` com auth válida.
6. Watchdog volta a reportar `OK ready_nodes=3/3 notready_pods=0`.

## Falhas esperadas e tratamento

### Prometheus demora a subir

Sintoma:

- startup lento;
- replay de WAL;
- readiness demorando vários minutos.

Ação:

- aguardar mais tempo antes de declarar falha;
- revisar logs:

```bash
sudo k3s kubectl logs -n monitoring prometheus-omni-monitoring-prometheus-0 -c prometheus --tail=200
```

### Portainer ou Grafana sobem, mas com estado anterior ao esperado

Isto é compatível com backup crash-consistent. Se o timestamp recuperado for funcional, tratar como comportamento esperado do ponto de restauração, não como erro do restore.

### Peer não volta ao cluster

Em SRV-2 ou SRV-3:

```bash
sudo journalctl -u k3s -n 200 --no-pager
sudo rm -rf /var/lib/rancher/k3s/server/db
sudo systemctl restart k3s
```

Se persistir, validar conectividade WireGuard e token/config em `/etc/rancher/k3s/config.yaml`.

## Drill futuro recomendado

Este documento ainda é um runbook validado por inspeção e evidência, não por restore destrutivo real. O próximo passo recomendado para fechar o risco M005 é:

1. clonar o bundle para um ambiente isolado;
2. executar restore real em janela de teste ou hosts descartáveis;
3. registrar tempo de recuperação (RTO) e perda observada (RPO);
4. decidir se `local-path` + crash-consistent backup continua aceitável ou se M005 exige RWX/replicação/snapshots de volume OCI.

## Referências

- K3s snapshot restore para embedded etcd HA: [docs.k3s.io/datastore/backup-restore](https://docs.k3s.io/datastore/backup-restore)
- CLI de restore/reset: [docs.k3s.io/cli/etcd-snapshot](https://docs.k3s.io/cli/etcd-snapshot)
- Token necessário para restaurar bootstrap data em novo host: [docs.k3s.io/cli/token](https://docs.k3s.io/cli/token)
