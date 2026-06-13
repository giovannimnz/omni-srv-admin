---
phase: 12
padded: 12
slug: k3s-ha-portainer-oci
name: K3s HA + Portainer on OCI ARM64
date: 2026-06-13
status: ready
wave: 1
depends_on: []
autonomous: false
files_modified:
  - .planning/phases/12-k3s-ha-portainer-oci/12-CONTEXT.md
  - .planning/phases/12-k3s-ha-portainer-oci/12-RESEARCH.md
  - .planning/phases/12-k3s-ha-portainer-oci/12-01-PLAN.md
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

# Phase 12 — Master Plan

## Goal

Montar, em fase posterior de execucao, um cluster K3s HA nos tres servidores
OCI ARM64 e publicar o Portainer do cluster em `portainer.atius.com.br`, sem
quebrar o Portainer antigo, Apache, Docker/Podman ou os servicos atuais.

## Scope

Esta phase e de planejamento. A execucao real deve ser uma phase separada ou a
execucao do plano `12-01` apos o SRV-1 estar em Ubuntu 24.04.

## Architecture

```
portainer.atius.com.br
  -> Cloudflare Edge
  -> Cloudflare Tunnel remote connector
  -> cloudflared pods in K3s
  -> Portainer ClusterIP service
  -> Portainer Server pod pinned to atius-srv-1

K3s HA:
  atius-srv-1 10.1.1.1 server+worker+etcd
  atius-srv-2 10.1.1.2 server+worker+etcd
  atius-srv-3 10.1.1.7 server+worker+etcd
```

## Plans

| ID | Name | Status | Notes |
|---|---|---|---|
| 12-01 | K3s HA bootstrap + Portainer exposure | ready | Single executable runbook with human checkpoints |

## Hard Gates

- SRV-1 must be Ubuntu 24.04 before K3s install.
- Backups/snapshots of all 3 nodes must exist before mutating servers.
- `10.1.1.0/24` connectivity must be stable from every node to every node.
- OCI/host firewall must restrict K3s ports to private node traffic only.
- No public exposure of 6443, 2379-2380, 8472, 10250, Portainer NodePort.
- Cloudflare Tunnel token must never be committed.

## Acceptance

- `kubectl get nodes -o wide` shows all 3 nodes Ready, `arm64`.
- `kubectl get --raw /readyz?verbose` returns ok.
- `kubectl -n kube-system get pods` all Ready.
- `kubectl -n portainer get deploy,svc,pvc` healthy.
- `kubectl -n cloudflared get deploy,pods` healthy with >=2 ready replicas.
- `https://portainer.atius.com.br` opens Portainer initial setup/login through Cloudflare.
- `docker.atius.com.br` old Portainer still works until explicit cutover.
