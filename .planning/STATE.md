# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-15 after Phase 14 / 14-01 execution

## Project Reference

See: .planning/ROADMAP.md (M004/M005 branch matrix + M006 resource-governor/PM2 hardening)
See also: .planning/MILESTONES.md

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M006 Resource Governor + PM2 Boot Hardening is in progress. Plan 14-01 versioned the governor/inviolable artifacts, install dry-run and status coverage. Next up: 14-02 PM2 boot canonicalization and 14-03 boot/login-linger + cgroup validation, both gated before live PM2/XRDP mutation.

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | Omni Fleet Control Plane (Phase 12, branch `codex/omni-fleet-control-plane-m004`) | Live implemented / validated |
| M005 | K3s HA Cluster + Portainer (Phase 13, branch `codex/k3s-portainer-oci-plan`) | Execution checkpoint; blocked before live mutation |
| M006 | SRV-1 Resource Governance + PM2 Hardening (Phase 14) | In progress; 14-01 complete |

## Active Branch Results

| Milestone | Branch | Result |
|---|---|---|
| M004 | `codex/omni-fleet-control-plane-m004` | Fleet Control Plane live foundation, central DB/PgBouncer node path, DB-backed ops/config/slash registry, local agent executor, fleet monitoring |
| M005 | `codex/k3s-portainer-oci-plan` | K3s/Portainer execution checkpoint, preflight, network port map, safe log cleanup, non-secret templates, vault notes |
| M006 | `codex/phase14-resource-governor-14-01` | 14-01 committed: governor/inviolable versioning, install/status coverage, PM2 stale-ref detection |

## Live Gates

- M005 still requires OCI snapshots/backups for all 3 nodes.
- M005 still requires OCI public-ingress closure in each OCI account plus host firewall rules for private K3s ports over `wg0`.
- M005 still requires Cloudflare Tunnel token supplied outside git/log/vault.
- M005 still requires PTP fallback mesh design/validation before production-ready.
- M006 live execution must not stop PM2 daemons, trading processes, XRDP, or stale user jobs without an explicit gate and current process snapshot.
- M006 14-01 found current live stuck jobs: `default.target`, `ats-pm2.service`, `horistic-pm2.service`; these remain gated for 14-02/14-03.
- M006 14-01 found `pm2-ubuntu.service` still references `/home/ubuntu/ecosystem.atius.js`; this remains gated for 14-02.

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
