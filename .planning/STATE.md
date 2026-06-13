# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-13 after Phase 12 K3s HA Portainer planning

## Project Reference

See: .planning/ROADMAP.md (M004 — K3s HA Cluster + Portainer)

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M004 K3s HA Cluster + Portainer, starting with Phase 12 planning and Phase 13 SRV-1 Ubuntu 24.04/preflight

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | K3s HA Cluster + Portainer (Phases 12-16) | Active |

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

## M004 Planning Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `codex/k3s-portainer-oci-plan` criada | ✅ |
| Phase | `.planning/phases/12-k3s-ha-portainer-oci/` | ✅ |
| CONTEXT | Decisões travadas para 3 nos K3s server+worker, SRV-1 em 24.04, Portainer em `portainer.atius.com.br` | ✅ |
| RESEARCH | PDF + docs oficiais K3s/Portainer/Cloudflare/OCI/Ubuntu + repo/vault local | ✅ |
| PLAN | `12-01-PLAN.md` human-gated para bootstrap K3s HA + Portainer + Cloudflare Tunnel | ✅ |
| Blocker | Não instalar enquanto SRV-1 não estiver em Ubuntu 24.04 e SRV-3 sem folga de disco | Open |

## M004 Phase Breakdown

| Phase | Descrição | Status |
|---|---|---|
| 12 | K3s HA + Portainer Milestone Plan | Planned |
| 13 | SRV-1 Ubuntu 24.04 + Fleet Preflight | Pending |
| 14 | K3s HA Bootstrap | Pending |
| 15 | Portainer CE + Cloudflare Tunnel | Pending |
| 16 | K3s Backup, DR and Acceptance | Pending |

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
