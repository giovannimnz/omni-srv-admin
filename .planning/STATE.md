---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: M005 Follow-ups
status: planning
last_updated: "2026-06-15T12:25:00Z"
last_activity: 2026-06-15 — M007 (v1.1) planning started: M005 follow-ups
progress:
  total_phases: 14
  completed_phases: 1
  total_plans: 27
  completed_plans: 12
  percent: 7
---

# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-15 after Phase 14 / 14-01 execution and main alignment with origin/main

## Project Reference

See: .planning/ROADMAP.md (M004/M005 branch matrix + M006 resource-governor/PM2 hardening)
See also: .planning/MILESTONES.md

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** M007 (v1.1) planning — M005 follow-ups: OCI snapshot workflow, Cloudflare Access policy, observability stack (Prometheus + Grafana + Loki), RWX storage decision. M004/M005/M006 closed (v1.0 shipped 2026-06-15).

## Milestones

| Milestone | Description | Status |
|---|---|---|
| M001 | Domain Foundation (Phases 1-2) | ✅ Done |
| M002 | Fork Sync Integration (Phase 8) | ✅ Done |
| M003 | Omni CLI Expansion (Phases 9-11) | ✅ Done |
| M004 | Omni Fleet Control Plane (Phase 12, branch `codex/omni-fleet-control-plane-m004`) | Live implemented; repos, central DB and DB-backed ops/config/slash registry validated |
| M005 | K3s HA Cluster + Portainer (Phase 13) | K3s HA + Portainer + observability live; edge Basic Auth active; OCI snapshot IDs/RWX strategy pending |
| M006 | SRV-1 Resource Governance + PM2 Hardening (Phase 14, branch `codex/phase14-resource-governor-14-01`) | ✅ Closed (v1.0 shipped 2026-06-15) |
| M007 | M005 Follow-ups: OCI snapshots, Cloudflare Access, observability, RWX (Phases 15-17) | Planning |

## Active Branch Results

| Milestone | Branch | Result |
|---|---|---|
| M004 | `codex/omni-fleet-control-plane-m004` | Live repo rollout, central `omni_fleet` DB, DB-backed ops/config/slash registry, CLI dry-run commands, schema/config docs, pytest/offline/live validation, PgBouncer private endpoint guard |
| M005 | `docs/m005-k3s-live-bootstrap` | Live K3s HA cluster, Portainer CE, Apache/Cloudflare endpoint validation, post-bootstrap docs |
| M006 | `codex/phase14-resource-governor-14-01` | 14-01 committed: governor/inviolable versioning, install/status coverage, PM2 stale-ref detection |

## Live Gates

- K3s HA live gate: ✅ closed on 2026-06-14.
- Portainer live gate: ✅ closed on 2026-06-14.
- Host firewall guard: ✅ `atius-k3s-firewall.service` active on SRV-1/SRV-2/SRV-3.
- Critical local backups: ✅ created under `~/.backups/k3s-preflight/`.
- Etcd post-bootstrap snapshot: ✅ saved on SRV-1.
- OCI snapshot IDs: follow-up for formal cloud rollback record.
- Cloudflare Access policy: follow-up before broad Portainer sharing.
- Observability stack: follow-up from M005 observability plan.
- M006 live execution must not stop PM2 daemons, trading processes, XRDP, or stale user jobs without an explicit gate and current process snapshot.
- M006 14-01 found current live stuck jobs: `default.target`, `ats-pm2.service`, `horistic-pm2.service`; these remain gated for 14-02/14-03.
- M006 14-01 found `pm2-ubuntu.service` still references `/home/ubuntu/ecosystem.atius.js`; this remains gated for 14-02.

## M005 Live Bootstrap Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `docs/m005-k3s-live-bootstrap` | ✅ |
| Phase | `.planning/phases/13-k3s-ha-portainer-oci/13-LIVE-BOOTSTRAP-2026-06-14.md` | ✅ |
| K3s | 3 nodes `Ready`: SRV-1/SRV-2/SRV-3, all `control-plane,etcd` | ✅ |
| Network | Node IPs on WireGuard: `10.1.1.1`, `10.1.1.2`, `10.1.1.7`; flannel `wg0` | ✅ |
| Smoke | DaemonSet one pod per node + DNS resolution to `kubernetes.default` | ✅ |
| Portainer | Portainer CE `2.39.3` deployed via Helm, ClusterIP + local port-forward | ✅ |
| Edge | `docker.atius.com.br` and `portainer.atius.com.br` return Portainer API status | ✅ |
| Backups | Critical local backups + etcd post-bootstrap snapshot | ✅ |
| Gate review | `13-GATE-REVIEW-2026-06-14.md` + `13-FALLBACK-PTP-2026-06-14.md` + `13-OCI-ROLLBACK-PATH-2026-06-14.md` + `13-RESTORE-DRILL-2026-06-14.md` | ✅ (docs/m005-gate-review-20260614) |
| Follow-up | Observability, Cloudflare Access, formal OCI snapshot IDs | Open |

## M006 Progress Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `codex/phase14-resource-governor-14-01` | ✅ |
| Plan 14-01 | `.planning/phases/14-resource-governor-pm2-boot-hardening/14-01-SUMMARY.md` | ✅ |
| Plan 14-05 | `.planning/phases/14-resource-governor-pm2-boot-hardening/14-05-PLAN.md` (Jenkins + servicos orfaos de Docker) | ✅ |
| Plan 14-06 | `.planning/phases/14-resource-governor-pm2-boot-hardening/14-06-PLAN.md` (Jenkins agent on K3s, M005 extension) | ready |
| Governor services | Moved to `timers.target` (out of `default.target`); install dry-run + status coverage; direct cgroup patcher reads `resource-governor.env` | ✅ |
| Inviolable watchdog | Timer-triggered service, no direct Install target | ✅ |
| PM2 stale-ref detection | `resource-governor status` reports `pm2-ubuntu.service` → `ecosystem.atius.js` (gated for 14-02) | ✅ |
| Jenkins docker-deps cleanup | `container-jenkins.service` active (running); removed `/var/run/docker.sock` + `/usr/bin/docker` mounts; validated on `https://jenkins.atius.com.br/` (x-jenkins 2.541.3) | ✅ |
| Next | 14-02 PM2 boot canonicalization, 14-03 boot/login-linger + cgroup validation, 14-04 rollback/runbook | Open |

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
- 2026-06-15: main local aligned with origin/main via merge. 5 docs/m005-* branches ready for archival. M006 stays in-progress on phase14 branch.

## Current Position

Phase: Milestone v1.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-06-15 — Milestone v1.0 completed and archived

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
