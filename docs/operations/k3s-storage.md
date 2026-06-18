# K3s Storage Decision — M005 Observability + RWX

Status: decided 2026-06-18

## Decision

Manter `local-path` por agora.

Não implementar RWX live nesta fase.

## Opções consideradas

### 1. NFS em SRV-1

Prós:
- simples
- barato
- operacionalmente conhecido
- entrega RWX rápido

Contras:
- single point of failure em SRV-1
- adiciona mount/network/debug path novo
- não resolve bem quorum/distribuição

### 2. Longhorn distributed

Prós:
- nativo de K3s
- snapshots/replicação
- caminho mais "cloud-native"

Contras:
- mais complexo
- mais moving parts
- mais risco operacional para a necessidade atual
- overkill para o uso presente

### 3. local-path (atual)

Prós:
- já está live
- simples
- sem rollout extra
- suficiente para Prometheus/Loki/Grafana/Alertmanager com PVC RWO

Contras:
- sem RWX
- workloads que exigirem escrita compartilhada precisarão de nova decisão

## Critério de decisão

Necessidade atual real:
- observability stack
- Portainer
- Jenkins/K3s auxiliares

Nenhum deles exige RWX imediato para fechar M005.

## Decisão final

Ficar em `local-path` nesta fase.

Gatilhos para revisitar:
- Gitea no K3s
- Postgres/MySQL no K3s
- workload multi-pod que precise volume compartilhado RWX
- retenção/disaster-recovery que justifique storage distribuído

## Impacto

- Phase 17 fecha a parte de decisão arquitetural de RWX
- a implementação live de RWX fica deferida
- sem mutação desnecessária no cluster agora

## Próximo passo quando RWX virar necessidade real

Reabrir como phase específica:
1. benchmark NFS vs Longhorn
2. escolher storage class
3. smoke com PVC RWX
4. rollout controlado com rollback documentado
