# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-13 after M004 Fleet Control Plane planning

## Project Reference

See: .planning/ROADMAP.md (M004 — Omni Fleet Control Plane)

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M004 Omni Fleet Control Plane

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | Omni Fleet Control Plane (Phase 12) | Active |

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
| Branch | `codex/omni-fleet-control-plane-m004` ativa | ✅ |
| Phase | `.planning/phases/12-omni-fleet-control-plane/` | ✅ |
| CONTEXT | Decisões travadas para server/node, inventário, DB central, PgBouncer, agents, licenças, auditoria e contrato Podman/K3s | ✅ |
| RESEARCH | Repo/vault local + PostgreSQL dump/restore + PgBouncer como pooler obrigatório | ✅ |
| PLAN | `12-01-PLAN.md` para Fleet Control Plane Foundation | ✅ |
| Blocker | Execução real depende de aprovar storage de secrets/licenças fora do git/log/vault | Open |

## M004 Phase Breakdown

| Milestone | Phase | Descrição | Status |
|---|---:|---|---|
| M004 | 12 | Fleet Control Plane Foundation | Planned |

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
