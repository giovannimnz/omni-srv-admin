---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: M005 Follow-ups + M007-ext (Ubuntu Pro ESM Apps) + M008 (Fleet Standardization)
status: planning
last_updated: "2026-06-17T20:20:00-03:00"
last_activity: 2026-06-17 — Phase 22 started: horistic-srv-1 renamed to horistic-srv (host, inventory, DB, VPN, vault, gbrain); rust/cargo-binstall/zellij + node-exporter installed
progress:
  total_phases: 20
  completed_phases: 8
  total_plans: 36
  completed_plans: 25
  percent: 19
---

# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-06-16 after Phase 18 added (Ubuntu Pro ESM Apps)
**Last activity (prior):** 2026-06-15 — Phase 14 / 14-01 execution and main alignment with origin/main

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
| M007-ext | Ubuntu Pro ESM Apps — Phase 18 (Phase 18) | 18-01..18-05 closed; 18-06..18-09 pending G18-1 gate |
| M008 | Fleet Standardization — hostnames + chromium + dark theme (Phase 19) | ✅ DONE 2026-06-17 (commit on main) |
| M008-b | Podman Networking Standardization (Phase 20) | ✅ DONE 2026-06-17 (commit on main) |
| M009 | MT5 KVM Fleet Onboarding (Phase 21) | ✅ DONE 2026-06-17 (commit on main) |
| M010 | Horistic rename + rust/zellij (Phase 22) | ✅ DONE 2026-06-17 (commit on main) |

## Active Branch Results

| Milestone | Branch | Result |
|---|---|---|
| M004 | `codex/omni-fleet-control-plane-m004` | Live repo rollout, central `omni_fleet` DB, DB-backed ops/config/slash registry, CLI dry-run commands, schema/config docs, pytest/offline/live validation, PgBouncer private endpoint guard |
| M005 | `docs/m005-k3s-live-bootstrap` | Live K3s HA cluster, Portainer CE, Apache/Cloudflare endpoint validation, post-bootstrap docs |
| M006 | `codex/phase14-resource-governor-14-01` | 14-01 committed: governor/inviolable versioning, install/status coverage, PM2 stale-ref detection |
| M007-ext | TBD (Phase 18) | `18-PLAN.md` + `18-06-AUDIT-2026-06-16.md` written; 18-01..18-05 (RDP scope) closed; 18-06 detach+reattach blocked on D18-06-A/B/C clarifications + gate |

## Live Gates

- K3s HA live gate: ✅ closed on 2026-06-14.
- Portainer live gate: ✅ closed on 2026-06-14.
- Host firewall guard: ✅ `atius-k3s-firewall.service` active on SRV-1/SRV-2/SRV-3.
- Critical local backups: ✅ created under `~/.backups/k3s-preflight/`.
- Etcd post-bootstrap snapshot: ✅ saved on SRV-1.
| OCI snapshot IDs | follow-up for formal cloud rollback record |
| Cloudflare Access policy | ⚠️ code shipped 2026-06-17 (`cli/omni/edge.py` + runbook + validation script) — live cutover **blocked** on Cloudflare dashboard "Enable Access" click; see `.planning/phases/16-m005-cloudflare-access/16-SUMMARY.md` |
| Observability stack | follow-up from M005 observability plan |
| **Tailscale ACL** | ✅ **closed 2026-06-16** — see `13-ACL-CLOSURE-2026-06-16.md` and vault `60-LOGS/2026-06-16/` |
- M006 live execution must not stop PM2 daemons, trading processes, XRDP, or stale user jobs without an explicit gate and current process snapshot.
- M006 14-01 found current live stuck jobs: `default.target`, `ats-pm2.service`, `horistic-pm2.service`; these remain gated for 14-02/14-03.
- M006 14-01 found `pm2-ubuntu.service` still references `/home/ubuntu/ecosystem.atius.js`; this remains gated for 14-02.

## M005 Live Bootstrap Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `docs/m005-k3s-live-bootstrap` | ✅ |
| Phase | `.planning/phases/13-k3s-ha-portainer-oci/13-LIVE-BOOTSTRAP-2026-06-14.md` | ✅ |
| K3s | 3 nodes `Ready`: SRV-1/SRV-2/SRV-3, all `control-plane,etcd` | ✅ |
| Network | Node IPs on WireGuard: `10.1.1.1`, `10.1.1.2`, `10.1.1.3`; flannel `wg0`; SRV-3 keeps `10.1.1.7` as etcd compatibility alias | ✅ |
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
- Phase 16: M005 Cloudflare Access — code shipped 2026-06-17 (`cli/omni/edge.py` + `docs/operations/edge-auth.md` + `scripts/validate-edge-auth.py`, 16/16 tests passing, live pre-cutover state confirmed); live cutover ⛔ blocked on Cloudflare dashboard "Enable Access" click — see `.planning/phases/16-m005-cloudflare-access/16-SUMMARY.md`

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
- 2026-06-16 (cont): Phase 18 scoped up. (a) RDP login SRV-1 broken — root cause: x11vnc (camofox in :97) holding 5910, collides with xrdp-sesman display :10. (b) SRV-2 incident parallel — x11vnc 0.0.0.0:5900 exposed WAN, pid 1678706, bots hammering since 2025-10. (c) Doc canônico unificado criado: `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` (+ mirror `30-RECURSOS/operations/` no vault, indexed in gbrain pages=877 chunks=2670). (d) Decisão: pool de displays `:5..9` = headless helpers; VNC=5900+N, noVNC=6080+N. Camofox migra `:97→:5` (VNC 5905, noVNC 6085). (e) ESM Apps re-scoped: token em `~/secrets/ubuntu-pro-token.txt` em cada SRV; target .sources (DEB822) + account giovannimunizds@gmail.com. Phase 18 re-numerada 18-01..18-09. Gate explícito: restart xrdp-sesman + smoke test RDP + apt upgrade ainda pendentes.
- 2026-06-16 (Codex resume): `ATIUS-FLEET-NETWORK-PORT-MAP.md` bumped to v1.1.0: reserva baixa `:1..14`, pool headless `:15..30`, xrdp `:31..60`, overflow `:61+`. Live `/etc/xrdp/sesman.ini` changed on SRV-1/2/3 from `X11DisplayOffset=1` to `31` with backups, `xrdp`/`xrdp-sesman` restarted, stale `:1/:2/:10` XRDP sessions removed, and `xfreerdp` probes reached `sesman` on all 3 with expected `AUTHFAIL` for fake user. Human Microsoft RDP retry still pending.
- 2026-06-16 (Codex follow-up): human login on SRV-1 with offset 31 accepted password and created `Xvnc :31`, but `/var/log/xrdp.log` showed `VNC error 1 after security negotiation` / `Error connecting to user session`. Per operator request, SRV-1 only was forced back to `X11DisplayOffset=1`; stale `X1/X31` sockets and session `:31` were removed; backup is `/etc/xrdp/sesman.ini.codex-bak-20260616-190844-force-display1`.
- 2026-06-16 (Codex fix): SRV-1 XRDP root cause isolated to the `xrdp/libvnc.so -> Xvnc` handoff on display `:1`: the session authenticated, but VNC negotiation needed explicit `SecurityTypes None`, `Protocol3.3`, and XRDP socket `/run/xrdp/sockdir/xrdp_display_1`. Final live config: `X11DisplayOffset=1`, `lib=libvnc.so`, `port=-1`, `code=0`, `delay_ms=6000`, `Xvnc -SecurityTypes None -Protocol3.3 -rfbunixpath /run/xrdp/sockdir/xrdp_display_1 -rfbunixmode 432`. Local `xfreerdp` smoke with temp user reached `VNC connection complete, connected ok` on display `:1`; temp user/session/sockets removed. Port map bumped to v1.1.1 with SRV-1 override `XRDP primary :1`; `:31..60` is expansion/overflow for SRV-1.
- 2026-06-16 (Codex fleet fix): Operator confirmed SRV-1 Microsoft RDP works on `:1`. SRV-2/SRV-3 still had `X11DisplayOffset=31`; SRV-2 real login hit `:31` then `startwm.sh` exited in 0s, and SRV-3 real login/reconnect hit `:31` then `VNC error 1`. Applied SRV-1 working XRDP/Xvnc profile to SRV-2/SRV-3: `X11DisplayOffset=1`, `code=0`, `delay_ms=6000`, `SecurityTypes None`, `Protocol3.3`, `xrdp_display_1`, custom LXDE `startwm.sh` with no 1366 watcher. Disabled SRV-2 `xvfb.service` because it pinned `Xvfb :1`. Removed SRV-1 `xrdp-display-1366x768.sh --watch`; live SRV-1 session returned to `1920x1080` from the RDP client. Smoke `xfreerdp` OK on SRV-2 and SRV-3: display `:1`, geometry `1280x720`, `VNC connection complete, connected ok`. Port map bumped to v1.1.2. Final rule: `:1..14` XRDP humano with resolution controlled by RDP client; `:15..30` headless/Camofox/noVNC may use fixed resolution; `:31..60` legacy/overflow only.
- 2026-06-16 (Codex closure): Operator confirmed Microsoft RDP success on SRV-2 and SRV-3 as well, closing the XRDP adjustment across the fleet. Status is now operator-confirmed on SRV-1/SRV-2/SRV-3, port map bumped to v1.1.3, and the remaining open scope of Phase 18 returns to Ubuntu Pro / `esm-apps`, Google account link, fleet attach validation, and regression watchdog.

## Current Position

Phase: 19 (Fleet Standardization — M008) — 19-02 desktop shortcuts hotfix DONE
Plan: 19-01 (hostnames+PPA+chromium+theme) + 19-02 (atalhos LXDE/XRDP via `xrdp-launch`) + 19-05 (cron cleanup) — DONE
Status: Atalho fix final aplicado. Root cause final: `.desktop` inválido com `Exec=env "DISPLAY=:1" "XAUTHORITY=*** ...` e aspas sem fechamento. Fix definitivo: wrapper `~/.local/bin/xrdp-launch` + `Exec=<home>/.local/bin/xrdp-launch <app>`, sem `env` inline, sem glob e validado por `desktop-file-validate`. PCManFM já foi recarregado nos 3 ATIUS; não há pendência de logout/login para atalhos. G18-1 (apt upgrade ESM) e G18-2 (RDP validation) ainda gates.
Last activity: 2026-06-17 — 19-04 tentativa anterior documentada como superseded: aspas duplas em `env` não eram suficientes porque os arquivos gravados ficaram com `***` literal e quote aberto.
Cron desativados (19-05): `@reboot sudo systemctl start horistic` + `*/5 * * * * /home/ubuntu/.hermes/cron/atius-phase7-monitor.sh` comentados. Backup: `~/.backups/crontab-pre-hermes-disable-2026-06-17.txt`. Entrada AionUi 23:55:32Z removida do daily note 2026-06-16.md.
Last activity: 2026-06-17 — 19-06 hotfix real dos atalhos: root cause final era `.desktop` inválido (`Exec=env "DISPLAY=:1" "XAUTHORITY=*** ...` com aspas sem fechamento). Substituído por wrapper `~/.local/bin/xrdp-launch`; atalhos Chromium/Firefox/Obsidian/Hermes/Sublime reescritos ou removidos quando sem binário; Obsidian real copiado para SRV-2; `chromium-browser` transitional purgado do SRV-3/HORISTIC; `google-chrome.desktop` quebrado removido do SRV-1; handler vazio `claude-code-url-handler.desktop` removido; PCManFM recarregado nos 3 ATIUS sem reiniciar XRDP.
Last activity: 2026-06-17 — gsd-resume-work triggered session resumption. Audit `omni podman-network drift` 6/6 PASS. Phase 19 closed (SUMMARY created). Phase 20 created (PLAN + SUMMARY), commits on main. M008 + M008-b both closed procedurally.

## Operator Next Steps

- [ ] Authorize G18-1 (apt upgrade esm-apps+infra nos 3 SRVs) — eu rodo serial 5min cooldown.
- [ ] Validate G18-2 (Microsoft RDP login pós-upgrade nos 3 SRVs) — você valida nos 3.
- [ ] Confirmar no Landscape SaaS UI que SRV-1, SRV-2, SRV-3 estão todos online (e não só SRV-2/3 como antes).
- Decisões já tomadas + executadas:
  - D18-06-A = (a) Dashboard transfer gmail → EXECUTED
  - D18-06-B = (1) pro refresh suave + fallback detach → EXECUTED (caminho detach+reattach funcionou; D18-06-B sub-decisão "auto-habilita esm-* no attach" — confirmado em pro 37.2)
  - D18-06-C = paralelo via subagent nos 3 SRVs → EXECUTED (3 subagentes parallel, 134-253s cada)

## Session Continuity (resumed + closed 2026-06-17)

- **Last session:** 2026-06-17 — Phase 21 + 22 merged; M009/M010 closed.
  - Skill: `~/.hermes/skills/devops/podman-fleet-standardize/` (12 files)
  - Module: `~/GitHub/omni-srv-admin/modules/fleet/podman-network/` (12 files, commit `c0543a9de`)
  - CLI: `omni podman-network {drift,apply,smoke,standard}` registered in cli/omni/cli.py
  - Doc: `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.2.0
  - **Drift check result: 6/6 PASS** on all 3 SRVs

- **Discovered gaps:**
  1. Phase 19 PLAN marked `status: complete` but no SUMMARY.md exists (procedural gap)
  2. Podman networking standardization was done as a one-off, not yet reflected in .planning/
  3. Phase 20 candidate: "M008-b podman networking standardization" (formalize the work done in 2026-06-16)

- **Operator next steps (unchanged from STATE pre-resume):**
  - [ ] Authorize G18-1 (apt upgrade esm-apps+infra nos 3 SRVs)
  - [ ] Validate G18-2 (Microsoft RDP login pós-upgrade nos 3 SRVs)
  - [ ] Confirmar Landscape SaaS UI com SRV-1/2/3 online

- **Next decision:** user chooses between (a) close phase 19 procedurally + create phase 20, (b) advance to G18-1, (c) something else.


## Phase 21 — MT5 KVM Fleet Onboarding

Status: ✅ DONE (2026-06-17)

| Item | Resultado |
|---|---|
| Graphify | fresh; Codex + Hermes runtimes retornam `commit_stale=false` |
| KVM-1 | `atius-mt5-kvm-1`; zsh default; rustc 1.96.0; cargo-binstall 1.20.0; zellij 0.44.3; port 9001 preservado |
| KVM-2 | `atius-mt5-kvm-2`; zsh default; rustc 1.96.0; cargo-binstall 1.20.0; zellij 0.44.3; port 9002 preservado |
| K3s | explicitamente fora do escopo por enquanto |
| Inventário/DB | `inventory/hosts/atius-mt5-kvm-{1,2}.yaml` OK; `TbHosts/TbNodes/TbPrograms/TbNodeTelemetry` OK; `omni fleet monitor hosts --json` source=database |
| VPN/docs | CoreDNS `custom_hosts` lowercase + compat uppercase; `peer_aliases.json` lowercase; `wg-quick strip wg0` OK |
| Docs | network map repo+vault, mt5-arm docs e session log vault atualizados |
| Pendência | Graphify final pós-mudanças + commit/push |


## Phase 22 — Horistic rename + rust/zellij

Status: ✅ DONE (2026-06-17)

| Item | Resultado |
|---|---|
| Host | horistic-srv-1 -> horistic-srv (aarch64, Ubuntu 24.04) sem reboot |
| WireGuard | chave/PSK/IP preservados; /etc/wireguard/wg0.conf nao tocado |
| Tailscale | rename aplicado |
| Toolchain | rustup 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3 |
| Monitoramento | prometheus-node-exporter ativo em :9100 |
| Inventario omni | inventory/hosts/horistic-srv-1.yaml -> horistic-srv.yaml |
| DB | horistic-srv em TbHosts/TbNodes/TbNodeTelemetry; horistic-srv-1 removido |
| VPN/CoreDNS | alias lowercase canonical; SRV-1/2/3/Horistic /etc/hosts atualizado |
| Network map | v1.4.0 (repo + vault mirror) |
| gbrain | sincronizado (sem embed, MiniMax 1 RPM) |
| Pendencia | vhost Apache remote.horistic-srv-1.atius.com.br.conf e pasta GDrive ainda com nome antigo (operacional) |
