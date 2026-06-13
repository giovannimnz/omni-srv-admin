---
phase: 13
padded: 13
slug: k3s-ha-portainer-oci
name: K3s HA + Portainer on OCI ARM64
date: 2026-06-13
status: execution-blocked-live-gates
wave: 1
depends_on: []
autonomous: false
files_modified:
  - .planning/phases/13-k3s-ha-portainer-oci/13-CONTEXT.md
  - .planning/phases/13-k3s-ha-portainer-oci/13-RESEARCH.md
  - .planning/phases/13-k3s-ha-portainer-oci/13-01-PLAN.md
  - .planning/phases/13-k3s-ha-portainer-oci/13-PREFLIGHT-2026-06-13.md
  - .planning/phases/13-k3s-ha-portainer-oci/13-EXECUTION-CHECKPOINT-2026-06-13.md
  - modules/k3s-ha-portainer-oci/
requirements_addressed:
  - K3S-01
  - K3S-02
  - K3S-03
  - K3S-04
  - K3S-05
  - PRT-01
  - PRT-02
  - CFL-01
  - SEC-01
---

# Phase 13 — Master Plan

## Goal

Montar, em fase posterior de execucao, um cluster K3s HA nos tres servidores
OCI ARM64 e publicar o Portainer do cluster em `portainer.atius.com.br`, sem
quebrar o Portainer antigo, Apache, Docker/Podman ou os servicos atuais.

## Scope

Esta phase agora tem planejamento, preflight, templates seguros e checkpoint de
execucao read-only. A execucao real do plano `13-01` continua bloqueada antes
de qualquer mutacao ate snapshots/backup OCI, firewall OCI/host, token
Cloudflare Tunnel e aprovacao humana serem confirmados fora do repo.

## Architecture

```
portainer.atius.com.br
  -> Cloudflare Edge
  -> Cloudflare Tunnel remote connector
  -> cloudflared pods in K3s
  -> Portainer ClusterIP service
  -> Portainer Server pod pinned to atius-srv-1

K3s HA:
  atius-srv-1 wg0 10.1.1.1 server+worker+etcd
  atius-srv-2 wg0 10.1.1.2 server+worker+etcd
  atius-srv-3 wg0 10.1.1.7 server+worker+etcd
```

## Plans

| ID | Name | Status | Notes |
|---|---|---|---|
| 13-01 | K3s HA bootstrap + Portainer exposure | blocked before live mutation | Single executable runbook with human checkpoints |

## Hard Gates

- SRV-1/SRV-2/SRV-3 must be Ubuntu 24.04 before K3s install. Passed on
  2026-06-13: all three are Ubuntu 24.04.4 LTS.
- Backups/snapshots of all 3 nodes must exist before mutating servers.
- WireGuard `wg0` / `10.1.1.0/24` connectivity must be stable from every node to every node.
- OCI/host firewall must restrict K3s ports to `wg0` private node traffic only.
- No public exposure of 6443, 2379-2380, 8472, 10250, Portainer NodePort.
- Cloudflare Tunnel token must never be committed.
- SRV-1 swap must be disabled and persisted off before K3s starts.

## Preflight Status

`13-PREFLIGHT-2026-06-13.md` records read-only node checks and the safe log
cleanup performed on SRV-2/SRV-3. `13-EXECUTION-CHECKPOINT-2026-06-13.md`
records the current execution attempt: all three hosts are now Ubuntu 24.04.4,
K3s is absent, K3s ports are closed as expected pre-install, and live install
remains blocked by OCI snapshots/firewall, Cloudflare token and human approval.

## Acceptance

- `kubectl get nodes -o wide` shows all 3 nodes Ready, `arm64`.
- `kubectl get --raw /readyz?verbose` returns ok.
- `kubectl -n kube-system get pods` all Ready.
- `kubectl -n portainer get deploy,svc,pvc` healthy.
- `kubectl -n cloudflared get deploy,pods` healthy with >=2 ready replicas.
- `https://portainer.atius.com.br` opens Portainer initial setup/login through Cloudflare.
- Legacy `docker.atius.com.br` state is documented and not used as an M005 dependency.
