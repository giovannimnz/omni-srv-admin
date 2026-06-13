# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-13 after M005 observability/control-loop plan update

## Project Reference

See: .planning/ROADMAP.md (M005 — K3s HA Cluster + Portainer + Observability)
See also: .planning/MILESTONES.md (branch/milestone matrix)

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M005 K3s HA Cluster + Portainer + Observability, Phase 13 execution stopped before live mutation; K3s install remains gated by OCI snapshots/backups per OCI account, OCI/host firewall and human approval. Cloudflare token/DNS gates UI publication. M004 Fleet Control Plane remains in its separate branch.

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | Omni Fleet Control Plane (Phase 12, branch `codex/omni-fleet-control-plane-m004`) | Contract implemented |
| M005 | K3s HA Cluster + Portainer + Observability (Phase 13) | Execution checkpoint blocked before live mutation |

## M001 Completion

### Completed Phases
- Phase 1: Preparação do Host ✅ (2026-04-19)
- Phase 2: Migração Apache2 ✅ (2026-04-19)

### Backlog (Phases 3-7)
- Phase 3: FreeIPA Server Container — planejamento pendente
- Phase 4: Samba Domain Member — depende Phase 3
- Phase 5: Migração WireGuard + CoreDNS — depende Phase 3
- Phase 6: Keycloak SSO — depende Phase 3
- Phase 7: Coexistência e Client Enrollment — depende Phase 3

## M002 Result Summary

| MH | Descrição | Status |
|---|---|---|
| MH-1 | Repo renamed: atius-srv → omni-srv-admin | ✅ |
| MH-2 | Remote atualizado | ✅ |
| MH-3 | Rebrand textual (14+ arquivos) | ✅ |
| MH-4 | .gitmodules com fork-sync | ✅ |
| MH-5 | modules/fork-sync/ populado (69 files) | ✅ |
| MH-6 | fork-sync repo arquivado | ✅ |
| MH-7 | Vault notes criadas | ✅ |
| MH-8 | Working tree limpo | ✅ |
| MH-9 | 9 commits claros | ✅ |

## M005 Preflight Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `codex/k3s-portainer-oci-plan` | ✅ |
| Phase | `.planning/phases/13-k3s-ha-portainer-oci/` | ✅ |
| CONTEXT | Decisões travadas para 3 nos K3s server+worker, SRV-1 em 24.04, Portainer em `portainer.atius.com.br` | ✅ |
| RESEARCH | PDF + docs oficiais K3s/Portainer/Cloudflare/OCI/Ubuntu + repo/vault local | ✅ |
| PLAN | `13-01-PLAN.md` human-gated para bootstrap K3s HA + Portainer + Cloudflare Tunnel | ✅ |
| PREFLIGHT | `13-PREFLIGHT-2026-06-13.md` registra leitura dos 3 nós, limpeza segura de logs e gates restantes | ✅ |
| EXECUTION CHECKPOINT | `13-EXECUTION-CHECKPOINT-2026-06-13.md` registra validacao live read-only, WireGuard `wg0`, Ubuntu 24.04.4 nos 3 hosts e bloqueio antes da Task 5 | ✅ |
| PTP Fallback | `13-02-PLAN.md` define desenho de fallback PTP full-mesh SRV-1/SRV-2/SRV-3 antes de production-ready | Planned |
| Observability | `13-03-PLAN.md` define Prometheus/Grafana + Alertmanager -> Omni Fleet control loop (`OBS-01`..`OBS-03`) | Planned |
| Templates | `modules/k3s-ha-portainer-oci/` com configs K3s, Portainer values, kube-prometheus-stack values, cloudflared deployment e logrotate | ✅ |
| Prerequisite | M004 Fleet Control Plane tratado em branch separada | Open until accepted/merged |
| Blocker | Não instalar K3s enquanto snapshots/backup OCI, firewall OCI/host por conta OCI e aprovação humana não forem confirmados | Open |
| UI publication gate | Não publicar Portainer/Grafana enquanto Cloudflare Tunnel token/DNS/Access não estiverem confirmados | Open |
| Production gate | Não declarar cluster production-ready enquanto fallback PTP e observability/control-loop não tiverem desenho e validação de failover/rollback | Open |

## M005 Phase Breakdown

| Phase | Descrição | Status |
|---|---|---|
| 13 | K3s HA + Portainer + Observability Milestone Plan | Execution checkpoint blocked before live mutation |

## Backup GDrive

- **Mount:** ~/GDrive/ RW via systemd (rclone-gdrive-mount.service)
- **Auth:** OAuth pessoal giovannimunizds@gmail.com
- **Timer:** backup-srv1-daily.timer (04:00 BRT, random 0-30min)
- **Destino:** ATIUS-SRV/SRV-1/backups/snapshot-YYYY-MM-DD_HHMMSS/
- **Script:** ~/.local/bin/backup-srv1-to-gdrive.sh
- **Throttle:** 75MB/s, transfers=1, checkers=1
- **Rotação:** 14 snapshots

## Notes

- YOLO mode ativado
- Push policy: fork push livre após audit
- GDrive quota: 5TB total, ~144GB usado, ~4.7TB livre
