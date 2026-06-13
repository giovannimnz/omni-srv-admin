---
phase: 13
name: k3s-ha-portainer-oci
created: 2026-06-13
method: self-discuss + official-doc research
generator: gsd-discuss-phase adapted to Codex
status: locked
---

# Phase 13 — K3s HA + Portainer on OCI ARM64

## Objective

Planejar a criacao de um cluster K3s de alta disponibilidade nos servidores
`ATIUS-SRV-1`, `ATIUS-SRV-2` e `ATIUS-SRV-3`, com os tres nos atuando como
`server` + `worker`, embedded etcd, exposicao administrativa via
`portainer.atius.com.br`, e sem expor Kubernetes API, etcd, Flannel ou Portainer
diretamente para a internet.

## Locked Decisions

### D-01: Branch de trabalho criada no inicio

**Decisao:** A branch desta phase e `codex/k3s-portainer-oci-plan`.

**Status:** executado antes da escrita dos artefatos GSD.

### D-02: Topologia inicial com 3 server nodes

**Decisao:** Usar 3 nos K3s `server` com embedded etcd. Todos tambem aceitam
workloads, sem workers dedicados na primeira montagem.

**Nos:**
- `atius-srv-1` / `ATIUS-SRV-1` — `10.1.1.1`, public `137.131.190.161`
- `atius-srv-2` / `ATIUS-SRV-2` — `10.1.1.2`, public `129.148.47.32`
- `atius-srv-3` / `ATIUS-SRV-3` — `10.1.1.7`, public `136.248.126.12`

**Rationale:** 3 servidores e o minimo correto para quorum etcd com tolerancia
a perda de 1 no. O PDF anexado recomenda exatamente esse desenho.

### D-03: Todos os nos no Ubuntu 24.04 antes da montagem real

**Decisao:** Nao instalar K3s enquanto algum dos 3 nos estiver fora do Ubuntu
24.04 LTS. Em 2026-06-13, o checkpoint de execucao confirmou `ATIUS-SRV-1`,
`ATIUS-SRV-2` e `ATIUS-SRV-3` em Ubuntu 24.04.4 LTS.

**Rationale:** O usuario informou que a montagem real aconteceria ja em 24.04.
Como os tres servidores ja foram atualizados, a instalacao pode exigir uma base
homogenea e reduzir variaveis de debug.

### D-04: Canal K3s estavel, nunca `latest`

**Decisao:** Instalar via `INSTALL_K3S_CHANNEL=stable` ou minor fixado apos
preflight. Nao usar `latest`.

**Rationale:** Em 2026-06, Kubernetes/K3s tem multiplas minors ativas. `latest`
pode pular para uma minor nova demais; `stable` reduz surpresa operacional.

### D-05: Inter-node somente pela WireGuard `wg0` / `10.1.1.0/24`

**Decisao:** K3s deve anunciar e usar `10.1.1.x` como `node-ip` e
`advertise-address`, e o Flannel deve ser fixado em `flannel-iface: wg0`.
O checkpoint de 2026-06-13 confirmou `wg0` nos tres hosts:
`10.1.1.1/32`, `10.1.1.2/24`, `10.1.1.7/32`.

**Rationale:** API, etcd, kubelet e Flannel nao devem usar IP publico. Os IPs
OCI VCN `10.0.0.x` existem, mas nao sao a rede canonica deste K3s v1. OCI
NSG/Security List deve impedir exposicao publica; a permissao inter-node do
K3s acontece pela VPN/host firewall em `wg0`.

### D-06: Desabilitar Traefik e ServiceLB no v1

**Decisao:** Instalar K3s com `--disable=traefik --disable=servicelb`.

**Rationale:** O servidor atual ja tem Apache/Portainer/servicos em portas
sensiveis. O Traefik padrao do K3s com ServiceLB pode tentar ocupar 80/443 nos
hosts. O v1 deve ser zero-conflito com Apache, Docker e Podman existentes.

### D-07: Portainer novo em `portainer.atius.com.br`

**Decisao:** O Portainer CE do cluster sera instalado no namespace obrigatorio
`portainer`, via Helm chart LTS, e exposto por Cloudflare Tunnel em
`https://portainer.atius.com.br`.

**Nao fazer:** reaproveitar `docker.atius.com.br` ou abrir NodePort/LoadBalancer
publico. O Portainer antigo em `docker.atius.com.br` ja foi parado/desabilitado
em trabalho operacional anterior; M005 nao deve depender dele nem ressuscita-lo.

### D-08: Cloudflare Tunnel em vez de OCI Load Balancer

**Decisao:** Expor Portainer via Cloudflare Tunnel remoto, com 2 ou 3 replicas
`cloudflared` no cluster, token em Kubernetes Secret criado manualmente e nunca
commitado.

**Rationale:** Evita Load Balancer pago, evita portas publicas, e alinha com o
PDF anexado. Replicas do tunnel dao alta disponibilidade de conector; nao sao
load-balancer interno.

### D-09: Storage do Portainer v1 e node-local

**Decisao:** Usar a StorageClass local default do K3s no v1 e fixar o pod
Portainer em `atius-srv-1` por `nodeSelector`.

**Rationale:** Portainer exige persistencia; a StorageClass local-path do K3s e
node-local. Sem Longhorn/OCI CSI ainda, mover o pod para outro no criaria banco
vazio. Cluster HA nao depende do Portainer estar sempre disponivel.

### D-10: Backup/snapshot antes de qualquer mutacao real

**Decisao:** Antes de instalar K3s ou alterar OCI firewall/NSG, criar snapshot
OCI ou backup equivalente dos 3 servidores e backup local de `/etc`,
`/var/lib/rancher`, configs Docker/Podman/Apache e GDrive map. Backups rclone
devem ser seriais, nunca paralelos.

**Rationale:** Ha precedente de rate limit no GDrive com backups paralelos, e
SRV-1/SRV-3 estao com disco pressionado.

### D-11: Tokens nunca em argumentos de processo

**Decisao:** Substituicoes de `K3S_CLUSTER_TOKEN` e criacao do Secret do
Cloudflare Tunnel devem usar arquivo com permissao `0600` ou stdin. Nao usar
`sed`/`kubectl --from-literal` com token expandido em `argv`.

**Rationale:** Tokens em argumentos de processo podem aparecer em `ps`, logs de
auditoria ou historico de shell.

### D-12: Fallback PTP full-mesh alem do WireGuard

**Decisao:** Adicionar um subplano `13-02` para desenhar uma malha PTP de
fallback entre as tres pontas: SRV-1 <-> SRV-2, SRV-1 <-> SRV-3 e
SRV-2 <-> SRV-3.

**Regra critica:** O K3s v1 continua anunciando `10.1.1.x` em `wg0`. Um fallback
transparente precisa preservar a alcançabilidade desses IPs canonicos via
roteamento/failover, ou entao deve ser tratado apenas como caminho emergencial
de administracao/DR. Nao mudar `node-ip`, `advertise-address` ou peers etcd em
producao sem plano separado de migracao e rollback.

**Rationale:** O WireGuard `wg0` e a rede canonica do v1, mas o cluster HA perde
valor se uma falha da malha VPN derruba a comunicacao entre control-plane/etcd.
Uma malha PTP secundaria reduz o risco, desde que nao introduza split-brain,
rotas assimetricas ou exposicao publica de portas Kubernetes.

### D-13: Os 3 servidores estao em contas OCI/OC1 diferentes

**Decisao:** Planejar M005 assumindo que SRV-1, SRV-2 e SRV-3 pertencem a contas
OCI/OC1 diferentes. Nao assumir VCN compartilhada, NSG compartilhado, Security
List unica ou permissao cross-account automatica.

**Implicacao:** Cada conta precisa de seu proprio snapshot/backup, auditoria de
ingresso publico e regras de firewall OCI. A comunicacao K3s inter-node deve
acontecer por overlay criptografado (`wg0` agora, PTP/fallback depois), nao por
dependencia em rede privada OCI comum.

**Rationale:** NSG/VCN e Security Lists sao limites administrativos da conta/
tenancy. Como os 3 servidores estao em contas diferentes, o plano tem que tratar
OCI como underlay publico/independente e usar overlays para trafego privado.

## Canonical References

- `planejamento_cluster_k3s_portainer_oci.pdf` — blueprint fornecido pelo usuario.
- `inventory/hosts/atius-srv-1.yaml` — IPs e papel do SRV-1.
- `inventory/hosts/atius-srv-2.yaml` — IPs e papel do SRV-2.
- `inventory/hosts/atius-srv-3.yaml` — IPs e papel do SRV-3.
- `docs/operations/atius-fleet-specs.md` — recursos, disco e I/O dos 3 servidores.
- `docs/operations/Atius-Spec-Servers.md` — regra operacional de 50% por recurso.
- `docs/CLOUDFLARE.md` — padrao atual do dominio `atius.com.br` no Cloudflare.
- `61-Incidents/2026-06-12-podman-cutover-srv1-portainer-cuts.md` no vault —
  estado atual do Portainer antigo.
- `60-LOGS/2026-06-13-containers-portainer-mailcow-gitlab-fixes.md` no vault —
  Portainer antigo parado e vhost `portainer.atius.com.br` apontando para `127.0.0.1:9005`.
- `60-LOGS/2026-06-12-ubuntu2404-express-prep.md` no vault — preparo do upgrade
  SRV-1 para 24.04.
- `60-LOGS/2026-06-13-m005-oci-separate-accounts.md` no vault — registro da
  premissa de contas OCI/OC1 separadas.

## Deferred Ideas

- Longhorn ou OCI CSI para storage distribuido.
- Traefik/Ingress oficial para apps publicas.
- GitOps com Argo CD/Flux.
- Fallback PTP full-mesh SRV-1/SRV-2/SRV-3 conforme `13-02-PLAN.md`.
- Migrar apps existentes para K3s.
- Limpar ou reaproveitar explicitamente o legado `docker.atius.com.br`.
