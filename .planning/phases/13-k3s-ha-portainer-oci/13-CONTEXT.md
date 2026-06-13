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

### D-03: SRV-1 no Ubuntu 24.04 antes da montagem real

**Decisao:** Nao instalar K3s no SRV-1 enquanto ele ainda estiver em 22.04. A
montagem real so com SRV-1 ja atualizado para Ubuntu 24.04 LTS. SRV-2 e SRV-3
podem entrar inicialmente em 22.04 se os preflights passarem; upgrades deles
ficam para fase posterior e sequencial.

**Rationale:** O usuario informou que este servidor sera atualizado antes, e os
demais so depois. O plano precisa aceitar essa transicao sem bloquear o cluster.

### D-04: Canal K3s estavel, nunca `latest`

**Decisao:** Instalar via `INSTALL_K3S_CHANNEL=stable` ou minor fixado apos
preflight. Nao usar `latest`.

**Rationale:** Em 2026-06, Kubernetes/K3s tem multiplas minors ativas. `latest`
pode pular para uma minor nova demais; `stable` reduz surpresa operacional.

### D-05: Inter-node somente pela rede privada `10.1.1.0/24`

**Decisao:** K3s deve anunciar e usar `10.1.1.x` como `node-ip` e
`advertise-address`. Antes da instalacao, validar se essa rede e VCN privada,
WireGuard ou outra interface. Se `10.1.1.x` estiver instavel, parar.

**Rationale:** API, etcd, kubelet e Flannel nao devem usar IP publico.

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
publico. O Portainer antigo em `docker.atius.com.br` permanece ate cutover
explicito.

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
- `60-LOGS/2026-06-12-ubuntu2404-express-prep.md` no vault — preparo do upgrade
  SRV-1 para 24.04.

## Deferred Ideas

- Longhorn ou OCI CSI para storage distribuido.
- Traefik/Ingress oficial para apps publicas.
- GitOps com Argo CD/Flux.
- Upgrade SRV-2/SRV-3 para Ubuntu 24.04.
- Migrar apps existentes para K3s.
- Desativar o Portainer antigo em `docker.atius.com.br`.
