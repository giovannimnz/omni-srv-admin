---
phase: 13
padded: 13
slug: k3s-ha-portainer-oci
name: K3s HA + Portainer on OCI ARM64
date: 2026-06-13
method: pdf + repo/vault inspection + official docs + Context7
status: complete
---

# Phase 13 — Research

## Executive Summary

O caminho recomendado e criar um cluster K3s HA de 3 nos `server` com embedded
etcd, usando apenas os IPs privados `10.1.1.1`, `10.1.1.2` e `10.1.1.7` para
trafego interno. O K3s deve ser instalado com Traefik e ServiceLB desabilitados
para nao ocupar portas de host e nao quebrar Apache/Portainer/servicos atuais.
Portainer CE deve entrar via Helm LTS, namespace `portainer`, Service interno e
Cloudflare Tunnel publicado como `portainer.atius.com.br`.

O maior risco nao e Kubernetes em si; e o estado operacional: discos cheios em
SRV-1/SRV-3, historico de rate limit no GDrive, Portainer antigo rodando em
Podman rootless, Apache com muitos vhosts, e incerteza sobre a estabilidade real
da rede `10.1.1.0/24`. A instalacao real precisa ser precedida por snapshot OCI,
limpeza de disco e preflight de rede/firewall.

## Local Evidence

### Fleet

Fonte local: `docs/operations/atius-fleet-specs.md` e
`docs/operations/Atius-Spec-Servers.md`.

- Todos os 3 servidores sao Oracle OCI Ampere A1 ARM64.
- Shape comum: 4 vCPU, ~23.42 GiB RAM, 10 GiB swap, disco real ~186 GiB.
- Regra operacional local: nenhum processo/container deve consumir mais de 50%
  dos recursos da maquina.
- IPs:
  - SRV-1: public `137.131.190.161`, private/VPN `10.1.1.1`
  - SRV-2: public `129.148.47.32`, private/VPN `10.1.1.2`
  - SRV-3: private/VPN `10.1.1.7`, public em docs `136.248.126.12`
- Disco documentado: SRV-1 e SRV-3 ja estiveram entre 95-99%.

### Portainer atual

Fonte vault:
- `61-Incidents/2026-06-12-podman-cutover-srv1-portainer-cuts.md`
- `60-LOGS/2026-06-13-containers-portainer-mailcow-gitlab-fixes.md`

- Portainer antigo foi migrado para Podman rootless no SRV-1.
- Em 2026-06-13, o Portainer antigo foi parado/desabilitado de proposito.
- Proxy Apache atual: `portainer.atius.com.br -> 127.0.0.1:9005`, reservado
  para o novo Portainer/K3s.
- `docker.atius.com.br` pode retornar 503 enquanto o Portainer antigo estiver
  intencionalmente desligado.
- `docker.sock` nao esta montado no Portainer rootless; UI funciona, mas nao
  gerencia Docker local pelo socket antigo.
- M005 nao deve depender de `docker.atius.com.br`; o novo hostname e
  `portainer.atius.com.br`.

### Ubuntu 24.04

Fonte vault:
- `60-LOGS/2026-06-12-ubuntu2404-express-prep.md`
- `60-LOGS/srv2-srv3-upgrade-22.04-to-24.04-kamikaze-batch-20260613-FINAL.md`
- `13-EXECUTION-CHECKPOINT-2026-06-13.md`

- SRV-1/SRV-2/SRV-3 estao em Ubuntu 24.04.4 LTS no checkpoint de execucao.
- Kernel atual nos 3 hosts: `6.17.0-1016-oracle`.
- Ubuntu 24.04 traz Podman mais novo nos repos oficiais que a base 22.04.

## Official Docs Findings

### K3s HA embedded etcd

Fontes:
- https://docs.k3s.io/datastore/ha-embedded
- https://docs.k3s.io/installation/requirements
- https://docs.k3s.io/installation/configuration
- https://docs.k3s.io/cli/server

Findings:

- K3s HA com embedded etcd requer 3 ou mais server nodes.
- etcd em HA precisa de numero impar; em 3 servidores, quorum e 2.
- Server nodes rodam Kubernetes API/control plane e tambem hospedam o datastore.
- K3s suporta ARM64.
- Portas internas necessarias:
  - TCP 6443: K3s supervisor / Kubernetes API, acessivel pelos nos.
  - TCP 2379-2380: etcd entre server nodes.
  - UDP 8472: Flannel VXLAN entre todos os nos.
  - TCP 10250: kubelet metrics/API entre todos os nos.
  - UDP 51820/51821: somente se usar Flannel WireGuard backend.
- A porta UDP 8472 nao deve ficar exposta publicamente.
- Configuracao pode ser por flags, environment ou `/etc/rancher/k3s/config.yaml`.
- O install script aceita `INSTALL_K3S_CHANNEL=stable` e `INSTALL_K3S_EXEC`.

Implications:

- Usar Flannel VXLAN default no v1, mas liberar UDP 8472 apenas entre nos.
- Instalar via config file em cada servidor para evitar comandos gigantes e
  facilitar auditoria/rollback.
- Usar `--node-ip` e `--advertise-address` com `10.1.1.x`.
- Configurar `--tls-san` com IP privado e nome interno, nao com hostname publico
  do Portainer.

### Portainer CE on Kubernetes

Fontes:
- https://docs.portainer.io/start/install-ce/server/kubernetes/baremetal
- Context7 `/portainer/portainer-docs`, version 2.39 LTS docs.

Findings:

- Portainer em Kubernetes tem Portainer Server + Portainer Agent.
- Requisitos: cluster Kubernetes funcional, Helm ou kubectl, Cluster Admin,
  RBAC, namespace `portainer`, StorageClass default.
- Portainer requer persistencia.
- O proprio doc alerta que hostPath/local storage em multi-node pode deixar os
  dados para tras se o pod for reagendado em outro no; workaround e `nodeSelector`.
- Helm e recomendado; exemplo LTS:
  `helm upgrade --install --create-namespace -n portainer portainer portainer/portainer --set tls.force=true --set image.tag=lts`
- Para Ingress, chart suporta `service.type=ClusterIP`, `ingress.enabled=true`,
  `ingress.ingressClassName`, `ingress.hosts[0].host`.

Implications:

- No v1, usar Helm LTS, namespace `portainer`, default StorageClass local-path,
  `nodeSelector.kubernetes.io/hostname=atius-srv-1`.
- Nao usar NodePort/LoadBalancer para Portainer.
- Expor via Cloudflare Tunnel para o Service interno.

### Cloudflare Tunnel on Kubernetes

Fonte:
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/deployment-guides/kubernetes/

Findings:

- Cloudflare recomenda rodar `cloudflared` como deployment separado ao lado das
  aplicacoes.
- Uma mesma Tunnel pode ter multiplas replicas `cloudflared`; nao e necessario
  criar tunnel por pod.
- Replicas sao para alta disponibilidade, nao para load balancing. Downscale
  pode quebrar conexoes existentes.
- `cloudflared` usa token de tunnel remoto guardado em Kubernetes Secret.
- O deployment oficial usa `cloudflare/cloudflared`, `--no-autoupdate`,
  metrics em `0.0.0.0:2000` e liveness probe `/ready`.
- Se o firewall de saida for restritivo, validar acesso a Cloudflare na porta
  7844.

Implications:

- Criar tunnel remoto `atius-k3s-portainer` no dashboard/Cloudflare API.
- Guardar token como Secret no namespace `cloudflared`.
- Usar `replicas: 3` ou `replicas: 2` com anti-affinity; evitar autoscaling.
- Public hostname: `portainer.atius.com.br -> https://portainer.portainer.svc.cluster.local:9443`
  ou `http://portainer.portainer.svc.cluster.local:9000`, dependendo do TLS
  interno escolhido no Helm.
- Cloudflare Access deve proteger a UI administrativa.

### OCI networking

Fontes:
- https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm
- https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/network/security-list.html

Findings:

- Security Lists e NSGs funcionam como firewall virtual.
- OCI recomenda NSGs em vez de Security Lists quando possivel.
- NSGs permitem rules aplicadas a VNICs especificas e source/destination por NSG.
- OCI lembra que firewall do host tambem precisa estar coerente; nao basta abrir
  Security List/NSG.

Implications:

- Criar/usar NSG `atius-k3s-nodes` se a camada OCI precisar agrupar VNICs.
- Nao depender de NSG para liberar `10.1.1.0/24`: essa rede e WireGuard overlay.
- Nao abrir 6443, 2379-2380, 8472, 10250 para `0.0.0.0/0`.
- Host firewall deve permitir K3s apenas em `wg0`/`10.1.1.0/24`.
- Manter acesso externo ao Portainer apenas pelo Cloudflare Tunnel.

### Ubuntu 24.04

Fonte:
- https://documentation.ubuntu.com/release-notes/24.04/

Findings:

- Ubuntu 24.04 LTS tem manutencao de seguranca por 5 anos, ate 31 May 2029.
- Upgrade de 22.04 LTS para 24.04 LTS passou a ser oferecido apos 24.04.1.
- 24.04 inclui kernel 6.8 e systemd 255.x.

Implications:

- A exigencia do usuario de atualizar SRV-1 para 24.04 antes do cluster esta
  alinhada com suporte LTS.
- Plano precisa validar cgroups/systemd/containerd apos upgrade antes de K3s.

## Architecture Decision

```
Cloudflare Edge
  |
  | portainer.atius.com.br
  v
Cloudflare Tunnel (remote tunnel)
  |
  | outbound connectors, replicas 2-3
  v
cloudflared Deployment (namespace cloudflared)
  |
  v
Portainer Service (namespace portainer, ClusterIP)
  |
  v
Portainer Server Pod pinned to atius-srv-1
  |
  v
K3s API / Agent / RBAC inside cluster

K3s cluster:
  atius-srv-1 10.1.1.1  server+worker+etcd
  atius-srv-2 10.1.1.2  server+worker+etcd
  atius-srv-3 10.1.1.7  server+worker+etcd
```

## Preflight Gates

### Host readiness

- SRV-1/SRV-2/SRV-3 on Ubuntu 24.04 before install. Passed in the
  2026-06-13 execution checkpoint: all three hosts are Ubuntu 24.04.4 LTS.
- `df -h /` must show enough free space. Minimum for this phase: 25 GiB free
  on each node before installing. 2026-06-13 checkpoint: SRV-1 60G free,
  SRV-2 60G free, SRV-3 137G free.
- `timedatectl` synchronized on all nodes.
- Hostnames lowercase DNS-valid: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`.
- `swapoff` decision explicit. K3s/Kubernetes generally expects swap disabled
  unless kubelet configured for swap; v1 disables swap for simplicity.
  2026-06-13 checkpoint: SRV-1 still has `/swapfile` active; SRV-2/SRV-3 do not.

### Network readiness

Canonical K3s node network is WireGuard `wg0` / `10.1.1.0/24`.
`node-ip`, `advertise-address`, and `flannel-iface` must stay aligned to this
interface. OCI VCN `10.0.0.x` addresses are not the K3s v1 node identity.

Commands per node:

```bash
ip -br addr
ip -br addr show wg0
ip route get 10.1.1.1
ip route get 10.1.1.2
ip route get 10.1.1.7
ping -c 3 10.1.1.1
ping -c 3 10.1.1.2
ping -c 3 10.1.1.7
```

Port checks after firewall/NSG rules:

```bash
nc -vz 10.1.1.1 6443
nc -vz 10.1.1.1 2379
nc -vz 10.1.1.1 2380
nc -vu -z 10.1.1.1 8472
nc -vz 10.1.1.1 10250
```

### Firewall/OCI readiness

K3s inter-node traffic is allowed only over WireGuard `wg0` / `10.1.1.0/24`.
OCI NSG/Security List rules must not expose K3s ports publicly. Host firewall
rules must prevent the same ports from being reachable on public or OCI VCN
interfaces unless a later phase deliberately changes that.

| Protocol | Port | Source | Destination | Purpose |
|---|---:|---|---|---|
| TCP | 6443 | `wg0` / `10.1.1.0/24` | K3s nodes | Kubernetes API/supervisor |
| TCP | 2379-2380 | `wg0` K3s server nodes | K3s server nodes | embedded etcd |
| UDP | 8472 | `wg0` K3s nodes | K3s nodes | Flannel VXLAN |
| TCP | 10250 | `wg0` K3s nodes | K3s nodes | kubelet metrics/API |
| TCP/UDP egress | 7844 | K3s nodes | Cloudflare edge | Cloudflare Tunnel |

Explicitly not public:

- TCP 6443
- TCP 2379-2380
- UDP 8472
- TCP 10250
- Portainer service ports

## Installation Plan Outline

1. Create branch and GSD docs. Done in this planning phase.
2. Confirm all three nodes remain on Ubuntu 24.04.4 LTS.
3. Preflight all nodes: disk, time sync, OS, WireGuard network, current listeners.
4. Snapshot/backup all nodes before any firewall/NSG or K3s mutation. Rclone backups serial only.
5. Confirm OCI public ingress remains closed and configure host firewall for K3s ports on `wg0` only.
6. Disable swap where active and install K3s on SRV-1 with embedded etcd init, disabled Traefik/ServiceLB.
7. Join SRV-2 and SRV-3 as server nodes.
8. Validate etcd quorum, node readiness, CoreDNS, metrics-server.
9. Install Helm.
10. Install Portainer CE LTS with ClusterIP, local-path PVC, nodeSelector.
11. Create Cloudflare Tunnel, Secret, deployment, and route
    `portainer.atius.com.br`.
12. Protect Portainer via Cloudflare Access.
13. Configure etcd snapshots and backup export.
14. Document result in repo and Obsidian.

## Pitfalls

### Pitfall 1: Traefik/ServiceLB binds public host ports

Default K3s includes Traefik and ServiceLB. In this environment, that can bind
80/443 and break Apache/Cloudflare origins. Disable both in v1.

### Pitfall 2: Portainer data lost on reschedule

K3s local-path is node-local. If Portainer moves nodes, it starts with empty
data. Pin to SRV-1 and back up the PVC. Add distributed storage later.

### Pitfall 3: `10.1.1.x` is VPN-dependent

K3s v1 deliberately uses WireGuard `wg0`. If `10.1.1.x` is not stable between
all nodes, do not install K3s. Fix WireGuard first. Do not silently fall back to
public IPs or OCI VCN IPs without a new plan.

### Pitfall 4: GDrive rate limit during backups

Prior parallel backups broke the GDrive mount. All pre-K3s backups must be
serial with cooldown and `mountpoint ~/GDrive` checks.

### Pitfall 5: SRV-3 disk pressure

SRV-3 has been near 99% disk. K3s/containerd images and etcd snapshots need
space. Require 25 GiB free minimum before install.

### Pitfall 6: Public K8s API exposure

Opening 6443 to internet is unnecessary. Admin access should be via SSH/VPN or
Cloudflare Access/Tunnel in a later, explicit phase.

## Research Conclusion

Proceed with a conservative v1:

- K3s HA embedded etcd, 3 server+worker nodes.
- `stable` channel, config-file based install.
- WireGuard `wg0` private networking only.
- Traefik/ServiceLB disabled.
- Portainer CE LTS via Helm, pinned to SRV-1.
- Cloudflare Tunnel for `portainer.atius.com.br`.
- No workload migration, no distributed storage, no public Kubernetes API.
