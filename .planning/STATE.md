# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-13 after M004 DB-backed ops/config/slash-command contract

## Project Reference

See: .planning/ROADMAP.md (M004 — Omni Fleet Control Plane)
See also: .planning/MILESTONES.md (branch/milestone matrix)

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M004 Omni Fleet Control Plane is live for its intended base: `~/GitHub/omni-srv-admin` exists on SRV1/SRV2/SRV3, SRV-1 owns central PostgreSQL database `omni_fleet`, and SRV-2/SRV-3 query it through PgBouncer on the private endpoint. `omni_fleet` is also the canonical `omni-srv-admin` DB for ops scopes, configs, runtime parameters and slash-command registry. M005 K3s HA Cluster + Portainer is queued in its separate branch.

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | Omni Fleet Control Plane (Phase 12, branch `codex/omni-fleet-control-plane-m004`) | Live implemented; repos, central DB and DB-backed ops/config/slash registry validated |
| M005 | K3s HA Cluster + Portainer (Phase 13, branch `codex/k3s-portainer-oci-plan`) | Planned |

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

## M004 Implementation Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `codex/omni-fleet-control-plane-m004` ativa | ✅ |
| Phase | `.planning/phases/12-omni-fleet-control-plane/` | ✅ |
| CONTEXT | Decisões travadas para server/node, inventário, DB central, PgBouncer, ops scopes, configs no DB, CLI-Anything slash commands, agents, licenças, auditoria e contrato Podman/K3s | ✅ |
| RESEARCH | Repo/vault local + PostgreSQL dump/restore + PgBouncer como pooler obrigatório | ✅ |
| PLAN | `12-01-PLAN.md` para Fleet Control Plane Foundation | ✅ |
| Docs | `docs/fleet/control-plane.md` criado com arquitetura, runbook e gates | ✅ |
| Module | `modules/fleet-control-plane/` criado com config exemplo, migration SQL inicial e migration `0002` para ops/config/slash commands | ✅ |
| CLI | `validate-inventory`, `install server/node`, `heartbeat`, `programs`, `update-plan`, `audit`, `status --all` | ✅ |
| Tests | pytest + offline validation harness + live SRV1/SRV2/SRV3 repo/DB probes | ✅ |
| Live network | SSH identity and VPN full-mesh passed across SRV1/SRV2/SRV3 | ✅ |
| Repo rollout | `~/GitHub/omni-srv-admin` exists on SRV1/SRV2/SRV3; SRV2/SRV3 track `main` with clean worktrees; SRV1 has local work preserved | ✅ |
| PostgreSQL | SRV-1 database `omni_fleet` exists with initial schema and seeded hosts/nodes/programs | ✅ |
| DB-backed ops/config | `0002_ops_config_slash_commands.sql` defines ops scopes, config items, slash commands and CLI-Anything bindings | ✅ |
| PgBouncer | SRV-1 PgBouncer is active on `127.0.0.1:6432` and `10.1.1.1:6432`; SRV-1/SRV-2/SRV-3 query `omni_fleet` via PgBouncer and direct node access to `8745` is blocked | ✅ |
| Remaining hardening | PgBouncer global auth is still `trust` for compatibility with existing services; move to stricter auth in a separate hardening task | Open |

## M004 Phase Breakdown

| Milestone | Phase | Descrição | Status |
|---|---:|---|---|
| M004 | 12 | Fleet Control Plane Foundation | Live implemented; repos, central DB and DB-backed ops/config/slash registry validated |

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
