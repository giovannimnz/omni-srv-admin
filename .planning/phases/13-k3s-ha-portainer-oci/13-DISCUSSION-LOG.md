---
phase: 13
name: k3s-ha-portainer-oci
date: 2026-06-13
method: self-discussion requested by user
status: complete
---

# Phase 13 — Discussion Log

## Prompt do usuario

Usar `gsd plan phase`, fazer grande research e um discuss phase completo "consigo
mesmo". O cluster sera `ATIUS-SRV-1`, `ATIUS-SRV-2`, `ATIUS-SRV-3`; criar branch
nova no inicio; SRV-1 sera atualizado para Ubuntu 24.04 antes da montagem real;
Portainer deve ficar em `portainer.atius.com.br`.

## Areas discutidas internamente

### 1. Numero e papel dos nos

**Opcoes consideradas:**
- 3 server+worker com embedded etcd.
- 1 server + 2 workers.
- 3 servers + workers dedicados futuros.

**Decisao:** 3 server+worker agora. E o unico desenho HA real com exatamente 3
maquinas, preserva quorum 2/3 e aproveita os recursos existentes.

### 2. Upgrade Ubuntu 24.04

**Opcoes consideradas:**
- Exigir 24.04 nos 3 antes do cluster.
- Instalar misto 24.04/22.04.
- Instalar ja em 22.04 e migrar depois.

**Decisao original:** SRV-1 obrigatoriamente 24.04 antes da montagem; SRV-2/SRV-3
poderiam entrar depois com 22.04 se passassem preflight.

**Superseded em 2026-06-13:** SRV-1/SRV-2/SRV-3 ja estao em Ubuntu 24.04.4 LTS
no checkpoint de execucao. A montagem real agora exige os tres em 24.04.

### 3. Exposicao do Portainer

**Opcoes consideradas:**
- NodePort publico.
- OCI Load Balancer.
- Cloudflare Tunnel.
- Reaproveitar Apache do SRV-1.

**Decisao:** Cloudflare Tunnel para `portainer.atius.com.br`, sem NodePort publico
e sem OCI LB no v1. Isso evita custo e reduz superficie de ataque.

### 4. Traefik/ServiceLB

**Opcoes consideradas:**
- Manter default K3s.
- Desabilitar apenas ServiceLB.
- Desabilitar Traefik e ServiceLB.

**Decisao:** Desabilitar ambos no v1. O objetivo e montar cluster sem disputar
80/443/9443/9001 com Apache, Docker e Podman existentes.

### 5. Storage do Portainer

**Opcoes consideradas:**
- local-path com nodeSelector.
- Longhorn imediato.
- OCI Block Volume CSI imediato.

**Decisao:** local-path + nodeSelector em `atius-srv-1` para v1, com backup.
Longhorn/CSI vira fase posterior porque SRV-1/SRV-3 estao sem folga de disco.

### 6. Rede interna

**Opcoes consideradas:**
- Usar IP publico.
- Usar `10.1.1.0/24`.
- Criar nova rede overlay externa.

**Decisao:** usar WireGuard `wg0` / `10.1.1.0/24`, desde que preflight prove
estabilidade e interface correta. Se for WireGuard instavel, parar antes de
instalar.

### 7. Fallback PTP alem do WireGuard

**Pedido novo:** adicionar fallback PTP nas tres pontas, alem do WireGuard.

**Decisao:** criar `13-02-PLAN.md` para desenhar full-mesh SRV-1 <-> SRV-2,
SRV-1 <-> SRV-3 e SRV-2 <-> SRV-3. O fallback nao muda o bootstrap `wg0` do
K3s. Antes de production-ready, o projeto precisa decidir se o PTP sera apenas
admin/DR ou failover transparente que preserva `10.1.1.x`.

### 8. Contas OCI separadas

**Informacao nova:** os 3 servidores estao em contas OCI diferentes.

**Decisao:** nao assumir VCN/NSG/Security List compartilhado. Snapshots,
firewall OCI e auditoria de ingresso publico sao gates por conta. A rede privada
do K3s continua sendo overlay criptografado (`wg0`, e PTP depois), nao rede OCI
comum.

## Decisoes finais

- Branch: `codex/k3s-portainer-oci-plan`.
- Phase: `13-k3s-ha-portainer-oci`.
- K3s: 3 server nodes, embedded etcd, canal `stable`.
- K3s default ingress/LB: disabled.
- Portainer: Helm LTS, namespace `portainer`, `portainer.atius.com.br`.
- Cloudflare: Tunnel remoto com Secret, 2-3 replicas, Access recomendado.
- OCI/host firewall: manter ingresso publico fechado e liberar K3s apenas em `wg0`.
- Backups: serializados; snapshot antes de qualquer instalacao.
- Fallback PTP: subplano `13-02`, production-ready gate.
- OCI: gates por conta OCI; sem NSG unico compartilhado.

## Deferred

- Longhorn/OCI CSI.
- Traefik/Ingress publico.
- GitOps.
- Migracao de workloads.
- Implementacao do fallback PTP apos desenho `13-02`.
