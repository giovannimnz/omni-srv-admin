---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Runtime Trust and Codex Delivery Convergence
current_phase: 47.1
current_phase_name: Internal DNS Authority and FreeIPA Convergence
status: executing
stopped_at: "Phase 47.1 planned and independently verified: 8 plans in 8 waves; execute 47.1-01 next and keep Phase 48 plan 48-03 blocked until the release gate passes"
last_updated: "2026-07-22T08:36:38.181Z"
last_activity: 2026-07-22
last_activity_desc: Phase 47.1 research, Nyquist validation, 8-plan revision and independent plan-check completed
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 18
  completed_plans: 2
  percent: 11
---

# State: Omni Srv Admin (omni-srv-admin)

**Last updated:** 2026-07-22 after Phase 47.1 planning verification
**Last activity:** 2026-07-22 — Phase 47.1 research, Nyquist validation, 8-plan revision and independent plan-check completed

## Project Reference

See: `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md`
See also: .planning/MILESTONES.md

**Core value:** Gestão centralizada de servidores, aplicações GitHub e containers
**Current focus:** Phase 47.1 — Internal DNS Authority and FreeIPA Convergence; Phase 48 plans 48-01/48-02 remain an independent execution lane

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
| M011 | Local AI Embeddings and Semantic Retrieval (Phase 41) | ✅ DONE 2026-07-04 |
| M012 | Atius-wide SSO and Login (Phase 42) | HISTORICAL PARTIAL - 42-01/42-02 retained; continuation moved to Phase 50 |
| M013 | Codex Runtime and MCP Bootstrap Reliability (Phase 43) | ✅ DONE 2026-07-05 |
| M014 | Internal Service PKI and Fleet Trust (Phase 44) | HISTORICAL PARTIAL - continuation completed by Phase 47 |
| M015 | Internal DNS and DRG Canonicalization (Phase 45) | DONE 2026-07-10 - OCI/DRG DNS, resolver, drift and edge closeout verified |
| M016 | Runtime Trust and Codex Delivery Convergence (Phases 46-50) | CURRENT - Phases 46-47 complete; Phase 48 executing; 49-50 queued |

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
- Host firewall guard: ✅ `atius-k3s-firewall.service` active on SRV-1/SRV-2/SRV-3/horistic-srv.
- Critical local backups: ✅ created under `~/.backups/k3s-preflight/`.
- Etcd post-bootstrap snapshot: ✅ saved on SRV-1.

| OCI snapshot IDs | follow-up for formal cloud rollback record |
| Cloudflare Access policy | ⚠️ code shipped 2026-06-17 (`cli/omni/edge.py` + runbook + validation script) — live cutover **blocked** on Cloudflare dashboard "Enable Access" click; see `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/16-m005-cloudflare-access/16-SUMMARY.md` |
| Observability stack | ⚠️ code/artifacts shipped 2026-06-18 (`cli/omni/observability.py`, dashboards, rules, scripts, RWX decision doc); live closeout still blocked on production gate + missing `~/.hermes/secrets/alert-webhook.json` + Grafana dashboard provisioning; see `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/17-m005-observability-rwx/17-SUMMARY.md` |
| **Tailscale ACL** | ✅ **closed 2026-06-16** — see `13-ACL-CLOSURE-2026-06-16.md` and vault `60-LOGS/2026-06-16/` |

- M006 live execution must not stop PM2 daemons, trading processes, XRDP, or stale user jobs without an explicit gate and current process snapshot.
- M006 14-01 found current live stuck jobs: `default.target`, `ats-pm2.service`, `horistic-pm2.service`; these remain gated for 14-02/14-03.
- M006 14-01 found `pm2-ubuntu.service` still references `/home/ubuntu/ecosystem.atius.js`; this remains gated for 14-02.

## M005 Live Bootstrap Summary

| Item | Descrição | Status |
|---|---|---|
| Branch | `docs/m005-k3s-live-bootstrap` | ✅ |
| Phase | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/13-k3s-ha-portainer-oci/13-LIVE-BOOTSTRAP-2026-06-14.md` | ✅ |
| K3s | 3 nodes `Ready`: SRV-1/SRV-2/SRV-3/horistic-srv, all `control-plane,etcd` | ✅ |
| Network | K3s historical bootstrap used legacy WireGuard node IPs; Phase 45 makes OCI/DRG private IPs canonical and treats `wg100` only as reserve fallback | ✅ |
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
| Plan 14-01 | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-01-SUMMARY.md` | ✅ |
| Plan 14-05 | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-05-PLAN.md` (Jenkins + servicos orfaos de Docker) | ✅ |
| Plan 14-06 | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-06-PLAN.md` (Jenkins agent on K3s, M005 extension) | ready |
| Governor services | Moved to `timers.target` (out of `default.target`); install dry-run + status coverage; direct cgroup patcher reads `resource-governor.env` | ✅ |
| Inviolable watchdog | Timer-triggered service, no direct Install target | ✅ |
| PM2 stale-ref detection | `resource-governor status` reports `pm2-ubuntu.service` → `ecosystem.atius.js` (gated for 14-02) | ✅ |
| Jenkins docker-deps cleanup | `container-jenkins.service` active (running); removed `/var/run/docker.sock` + `/usr/bin/docker` mounts; validated on `https://jenkins.atius.com.br/` (x-jenkins 2.541.3) | ✅ |
| Next | 14-02 PM2 boot canonicalization, 14-03 boot/login-linger + cgroup validation, 14-04 rollback/runbook | Open |

## M001 Completion

### Completed Phases

- Phase 1: Preparação do Host ✅ (2026-04-19)
- Phase 2: Migração Apache2 ✅ (2026-04-19)
- Phase 16: M005 Cloudflare Access — code shipped 2026-06-17 (`cli/omni/edge.py` + `docs/operations/edge-auth.md` + `scripts/validate-edge-auth.py`, 16/16 tests passing, live pre-cutover state confirmed); live cutover ⛔ blocked on Cloudflare dashboard "Enable Access" click — see `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/16-m005-cloudflare-access/16-SUMMARY.md`
- Phase 17: M005 Observability + RWX — code/artifacts shipped 2026-06-18 (`cli/omni/observability.py`, monitoring dashboards/rules/scripts, `docs/operations/k3s-storage.md`, 43/43 tests passing); live closeout ⛔ blocked on production gate + missing alert webhook + dashboard provisioning — see `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/17-m005-observability-rwx/17-SUMMARY.md`

### Legacy Domain Backlog (superseded)

- Phase 3: FreeIPA Server Container — planejamento pendente
- Legacy stage 4: Samba Domain Member — superseded by Phase 35
- Legacy stage 5: WireGuard + CoreDNS — superseded by Phases 34 and 45
- Legacy stage 6: Keycloak SSO — superseded by Phases 36 and 50
- Legacy stage 7: coexistence/client enrollment — superseded by Phases 34-36

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

- 2026-07-06: Reconciled the planning surface so `ROADMAP.md`, `REQUIREMENTS.md`, `PROJECT.md`, `MILESTONES.md`, and phase summaries agree on the current state: Phase 37 is complete, Phase 41 is complete with `embedding-gte-v1` on namespace `ebeddings-local`, Phase 42 is in progress with `42-01` and `42-02` complete, Phase 43 is complete, and Phase 44 is in progress with `44-01` complete.
- 2026-07-05: Phase 43 effectively closed on `GIOVANNI-W11-PC`. The Codex bootstrap now defaults to a lean MCP baseline, heavy MCPs moved to opt-in profiles, and cold-start smoke is documented and repeatable without printing secrets.
- 2026-07-05: Phase 44 `44-01` closed. `omni fleet trust-pki` exists as a versioned dry-run resource surface with inventory SAN rendering, onboarding/reconcile/rotate flows, allowlisted command shapes, and focused tests. Live CA/trust rollout remains gated in `44-02`.
- 2026-06-26: Phase 35 closed. Samba moved from `atius-srv-2` to `atius-srv-1`; `srv1` joined `ATIUS.INTERNAL`, `ipa-client-samba` configured the member server, `smbd` and `winbind` are active on `srv1`, `nmbd` remains intentionally disabled, `/srv/Shared` holds the copied `8.8G` share data, `/home/ubuntu/Shared_smb` is now a local bind mount, and Kerberos access passed with `smbclient -k -U ATIUS\\giovanni`. The old Samba service on `srv2` is disabled.
- 2026-07-06: TEI namespace moved from `ai-search` to `ebeddings-local`. The old namespace was deleted after `ebeddings-local/tei-gte` reached `1/1 Running`; current router-facing private endpoint is `10.21.1.21:3115`, with `10.100.100.4:3115` retained only as reserve fallback until Phase 45 validation closes. A direct embedding smoke returned one 768-dimensional vector with `error=null`. The manifest now pins TEI CPU request/limit at `500m`, binds TEI to `0.0.0.0` for Kubelet health on the K3s node InternalIP, and carries an explicit toleration for `horistic-srv` manual-only taint.
- 2026-06-26: Phase 36 closed. Keycloak 26.6.3 runs on `atius-srv-1` with Java 21 and private listener `127.0.0.1:8180`; Apache proxies `auth.atius.com.br` locally for controlled smoke; the realm `atius` has LDAP federation to FreeIPA and imported `giovanni`; OIDC password grant passed through client `phase36-smoke`; the legacy Apache/JWT auth path remained unchanged.
- 2026-06-26: Phases 37-40 were canonized from the already-shipped Production Guard implementation. `status/doctor` foundation, guarded repair dry-run/apply gate, boot/login read-only protocol, and Horistic remote/rename/webhook-safe checks now have canonical phase artifacts and verification under the new roadmap numbering.
- 2026-07-04: Phase 41 live port migration completed. TEI `Alibaba-NLP/gte-multilingual-base` is running in k3s on `horistic-srv`; the canonical private router-facing URL after DRG readdress is `http://10.21.1.21:3115`; `router-ai-atius` channel `TEI - GTE Embeddings` exposes alias `embedding-gte-v1`; public `POST https://router.atius.com.br/v1/embeddings` smoke returned 2 vectors, 768 dimensions, `error=null`; unauthenticated `/v1/models` remains 401. Tokens were loaded only in an ephemeral shell and no token values were written.
- 2026-06-26: Phase 34 closed with real-host FreeIPA pilot. CoreDNS forwarding for `atius.internal` now needs Phase 45 reconciliation to SRV-3 OCI/DRG private IP `10.13.1.13`; `atius-srv-3` privately gateways FreeIPA to the container at `10.89.53.10`; `atius-srv-3` joined `ATIUS.INTERNAL` as `atius-srv-3.atius.internal`; `kinit admin`, `ipa ping`, `getent`, `id`, and `sudo -l -U admin` passed. `horistic-srv` enrollment remains deferred to the next controlled step.
- 2026-06-26: Started v1.3 Local AI Embeddings and Semantic Retrieval as a separate milestone. Phase 41 plans TEI/GTE in k3s on `horistic-srv`, New API alias `embedding-gte-v1`, public OpenAI-compatible entrypoint `https://router.atius.com.br/v1`, 768-dimension contract, no router self-loop, and GBrain/Obsidian/Graphify migration runbooks without secrets in docs/logs/history.
- 2026-06-25: Landscape self-hosted became the operator-facing control plane for Atius fleet administration. The Landscape secrets UI OOPS was patched inside LXD `landscape`; the internal Landscape Vault now stores approved break-glass entries for dedicated HashiCorp Vault root token, unseal key, Omni AppRole role/secret ID, and Vaultwarden admin token. No secret values were written to repo docs. Snapshot: `/root/landscape-vault-breakglass-20260626T001545Z.snap` inside LXD `landscape`.
- 2026-06-18: Phase 15 (M005 OCI Snapshots) closed procedurally. CLI `omni srv oci {status, snapshot preflight, snapshot routine, restore drill}` shipped; inventory dos 4 hosts `oracle-oci` tem bloco `oci:` com `pending-...` (offline); `docs/operations/oci-snapshots.md` é o runbook. 12/12 testes verdes. Live OCI (drill real em SRV-1) bloqueado: `oci` CLI e `~/.oci/config` não estão instalados no host. Próxima janela: provisionar API key + rodar preflight/routine em cada host + drill real.
- 2026-06-15: main local aligned with origin/main via merge. 5 docs/m005-* branches ready for archival. M006 stays in-progress on phase14 branch.
- 2026-06-16 (cont): Phase 18 scoped up. (a) RDP login SRV-1 broken — root cause: x11vnc (camofox in :97) holding 5910, collides with xrdp-sesman display :10. (b) SRV-2 incident parallel — x11vnc 0.0.0.0:5900 exposed WAN, pid 1678706, bots hammering since 2025-10. (c) Doc canônico unificado criado: `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` (+ mirror `30-RECURSOS/operations/` no vault, indexed in gbrain pages=877 chunks=2670). (d) Decisão: pool de displays `:5..9` = headless helpers; VNC=5900+N, noVNC=6080+N. Camofox migra `:97→:5` (VNC 5905, noVNC 6085). (e) ESM Apps re-scoped: token em `~/secrets/ubuntu-pro-token.txt` em cada SRV; target .sources (DEB822) + account giovannimunizds@gmail.com. Phase 18 re-numerada 18-01..18-09. Gate explícito: restart xrdp-sesman + smoke test RDP + apt upgrade ainda pendentes.
- 2026-06-16 (Codex resume): `ATIUS-FLEET-NETWORK-PORT-MAP.md` bumped to v1.1.0: reserva baixa `:1..14`, pool headless `:15..30`, xrdp `:31..60`, overflow `:61+`. Live `/etc/xrdp/sesman.ini` changed on SRV-1/2/3 from `X11DisplayOffset=1` to `31` with backups, `xrdp`/`xrdp-sesman` restarted, stale `:1/:2/:10` XRDP sessions removed, and `xfreerdp` probes reached `sesman` on all 3 with expected `AUTHFAIL` for fake user. Human Microsoft RDP retry still pending.
- 2026-06-16 (Codex follow-up): human login on SRV-1 with offset 31 accepted password and created `Xvnc :31`, but `/var/log/xrdp.log` showed `VNC error 1 after security negotiation` / `Error connecting to user session`. Per operator request, SRV-1 only was forced back to `X11DisplayOffset=1`; stale `X1/X31` sockets and session `:31` were removed; backup is `/etc/xrdp/sesman.ini.codex-bak-20260616-190844-force-display1`.
- 2026-06-16 (Codex fix): SRV-1 XRDP root cause isolated to the `xrdp/libvnc.so -> Xvnc` handoff on display `:1`: the session authenticated, but VNC negotiation needed explicit `SecurityTypes None`, `Protocol3.3`, and XRDP socket `/run/xrdp/sockdir/xrdp_display_1`. Final live config: `X11DisplayOffset=1`, `lib=libvnc.so`, `port=-1`, `code=0`, `delay_ms=6000`, `Xvnc -SecurityTypes None -Protocol3.3 -rfbunixpath /run/xrdp/sockdir/xrdp_display_1 -rfbunixmode 432`. Local `xfreerdp` smoke with temp user reached `VNC connection complete, connected ok` on display `:1`; temp user/session/sockets removed. Port map bumped to v1.1.1 with SRV-1 override `XRDP primary :1`; `:31..60` is expansion/overflow for SRV-1.
- 2026-06-16 (Codex fleet fix): Operator confirmed SRV-1 Microsoft RDP works on `:1`. SRV-2/SRV-3 still had `X11DisplayOffset=31`; SRV-2 real login hit `:31` then `startwm.sh` exited in 0s, and SRV-3 real login/reconnect hit `:31` then `VNC error 1`. Applied SRV-1 working XRDP/Xvnc profile to SRV-2/SRV-3: `X11DisplayOffset=1`, `code=0`, `delay_ms=6000`, `SecurityTypes None`, `Protocol3.3`, `xrdp_display_1`, custom LXDE `startwm.sh` with no 1366 watcher. Disabled SRV-2 `xvfb.service` because it pinned `Xvfb :1`. Removed SRV-1 `xrdp-display-1366x768.sh --watch`; live SRV-1 session returned to `1920x1080` from the RDP client. Smoke `xfreerdp` OK on SRV-2 and SRV-3: display `:1`, geometry `1280x720`, `VNC connection complete, connected ok`. Port map bumped to v1.1.2. Final rule: `:1..14` XRDP humano with resolution controlled by RDP client; `:15..30` headless/Camofox/noVNC may use fixed resolution; `:31..60` legacy/overflow only.
- 2026-06-16 (Codex closure): Operator confirmed Microsoft RDP success on SRV-2 and SRV-3 as well, closing the XRDP adjustment across the fleet. Status is now operator-confirmed on SRV-1/SRV-2/SRV-3/horistic-srv, port map bumped to v1.1.3, and the remaining open scope of Phase 18 returns to Ubuntu Pro / `esm-apps`, Google account link, fleet attach validation, and regression watchdog.

## Current Position

Phase: 47.1 (Internal DNS Authority and FreeIPA Convergence) — PLANNING; Phase 48 plans 48-01/48-02 may continue independently
Plans: Phase 47.1 planning in progress; existing Phase 48 plans remain preserved
Status: Ready to execute
Last activity: 2026-07-19 — owner-local research/spikes completed; plans 48-03..48-06 passed the independent checker after three revision cycles

## Operator Next Steps

- Continue the active Phase 48 task without overlapping its Wayland/codex-acp runtime files; Headroom remains absent.
- Reconcile Router Phase 32 evidence and finish the CPU-capped Go verification plus native/local/remote ACP lifecycle matrix.
- Execute 48-03 only after 48-02: repair FreeIPA/host-key trust and activate encrypted FQDN multiplexing without changing NFS or legacy fleet aliases.
- Execute 48-04..48-06 in order: protect the fork before edits, add ACP stdio-over-SSH, enable only per-conversation owner-local routing, then prove fork-sync/headless/fleet/rollback parity. Keep NFS for discovery/picker/light read-diff/compatibility/fallback.
- Treat the Wayland GUID effort-selector repair as a Phase 48 regression fix, not as Phase 49 Headroom work.
- Execute Phase 49 only after every Phase 48 validation and stop condition is green.
- Execute Phase 50 after Phase 49, reusing 42-01/42-02 as historical evidence rather than reopening Phase 42.

## Session Continuity (resumed + closed 2026-06-17)

- **Last session:** 2026-06-28T08:44:21.517Z
  - Skill: `~/.hermes/skills/devops/podman-fleet-standardize/` (12 files)
  - Module: `~/GitHub/omni-srv-admin/modules/fleet/podman-network/` (12 files, commit `c0543a9de`)
  - CLI: `omni podman-network {drift,apply,smoke,standard}` registered in cli/omni/cli.py
  - Doc: `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.2.0
  - **Drift check result: 6/6 PASS** on all 4 servidores

- **Discovered gaps:**
  1. Phase 19 PLAN marked `status: complete` but no SUMMARY.md exists (procedural gap)
  2. Podman networking standardization was done as a one-off, not yet reflected in .planning/
  3. Phase 20 candidate: "M008-b podman networking standardization" (formalize the work done in 2026-06-16)

- **Operator next steps (unchanged from STATE pre-resume):**
  - [ ] Authorize G18-1 (apt upgrade esm-apps+infra nos 4 servidores)
  - [ ] Validate G18-2 (Microsoft RDP login pós-upgrade nos 4 servidores)
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

## Phase 23 — Omni Fleet Governance com Landscape complementar

Status: PLANNING (2026-06-24)

| Item | Direcao |
|---|---|
| Decisao atual | Implementar Landscape self-hosted como camada complementar de administracao das maquinas Ubuntu, porque o consumo estimado cabe na infra e aumenta controle operacional |
| Cockpit | Console web por host, protegido por Access/SSO/VPN; nao e control plane central |
| Omni Fleet | Control plane central para inventario, programas, versoes, desired state, update plans, auditoria e agentes locais |
| Landscape | Deploy planejado em Podman e/ou K3s com gate de recursos, portas 80/443, certificado, Pro/licenca, registro dos clientes e rollback; fallback documentado para LXD/VM/Juju se Podman/K3s nao ficar suportavel |
| K3s/Portainer | Continuam responsaveis por administracao do cluster e workloads; Landscape administra maquinas Ubuntu e pacotes, nao substitui Portainer/Kubernetes |
| Gaps | collectors reais de versao, desired-state profiles, repository profiles, CVE/USN reporting, matriz de responsabilidades Landscape/Omni/Cockpit/K3s |
| Fundacao existente | `managed-apps` agora cobre `programs`, `repositories`, `policies` e `customizations` para Chromium/Firefox/Bitwarden, incluindo Bitwarden force-install e browser defaults Google/homepage; validado localmente por `manifest`, `status`, `verify`, `config-status` e `config-verify` e remotamente por `fleet-config-status`; reutilizar como seed de governanca da Phase 23 |
| Worktree | Ainda ha mudancas paralelas fora da Phase 23 em `managed-apps`, `srv1-ops`, `fork-sync`, `dark-theme` e Graphify outputs; deixadas intocadas |
| Proximo | Planejar e executar `23-01..23-05` |

## Phase 34 — FreeIPA DNS + client enrollment

Status: IN PROGRESS (2026-06-25)

| Item | Resultado |
|---|---|
| 34-01 | Disposable AlmaLinux client gate passed on `atius-srv-3` |
| DNS | `ipa.atius.internal @10.89.53.10` returned `10.89.53.10` inside `freeipa-client-test` |
| Enrollment | `ipa-client-install` to `ATIUS.INTERNAL` passed in disposable container |
| Auth smoke | `kinit admin` plus `ipa ping` passed |
| Real hosts | `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv` not enrolled |
| Remaining | `34-02` must implement WireGuard/CoreDNS forwarding and first real host enrollment with rollback |

## Secrets vault deployment — 2026-06-25

| Item | Resultado |
|---|---|
| Vaultwarden | Live at `https://vault.atius.com.br`, Apache edge on SRV1, container on SRV3 |
| HashiCorp Vault | Live private at `https://10.13.1.13:8202`, raft storage, TLS, KV v2, AppRole and audit enabled |
| DNS | Cloudflare `A vault.atius.com.br -> 137.131.190.161`, DNS-only |
| Backups | Vaultwarden `.tgz` and HashiCorp raft snapshot timers installed |
| Docs | `docs/security/atius-secrets-vaults.md` and Obsidian infra note created |
| Seeded KV | Cloudflare API, Landscape SaaS API, FreeIPA bootstrap and Vaultwarden admin token mirrored into `kv/atius/*` |
| Helper | `/home/ubuntu/.local/bin/atius-vault-env` loads selected profiles from Vault on demand |
| Landscape secrets UI | OOPS fixed in LXD `landscape` by patching `list-secrets.pt`; durable APT hook installed and reference secrets seeded |

## Phases 24-27 — ATS/Horistic Production Recovery Guard

Status: PLANNING (2026-06-24)

| Item | Estado validado / direcao |
|---|---|
| PM2 boot owner | `pm2-ubuntu.service` live esta `enabled`, `active`, `Type=oneshot`, `RemainAfterExit=yes`, sem `PIDFile`, restaurando de `/home/ubuntu/.pm2/dump.pm2` |
| PM2 live vs dump | PM2 vivo e dump batem: `atius: 12`, `horistic: 5`; nenhum `missing_in_dump`, nenhum `missing_live`, nenhum processo em namespace errado |
| Namespaces | ATS em namespace `atius`; Horistic em namespace `horistic`; legacy `ats-pm2.service` e `horistic-pm2.service` continuam disabled/inactive |
| Ecosystems | `ecosystem.config.js` de ATS e Horistic tem `autorestart: true`, `restart_delay`, `max_restarts`, cwd/script canonicos e namespaces corretos para apps base |
| Portas e dominios | Portas locais 3015, 8015, 3050, 8050, 8099, 8199 abertas; `dashboard/trade/backtest/painel/api/webhook.horistic.com` e `dashboard/api/webhook.atius.com.br` responderam 200 no check de 2026-06-24 |
| Horistic Apache | `horistic-srv` remoto: `apache2.service` padrao do Ubuntu, `enabled`, `active`, sem drop-ins, ouvindo em 80/443 |
| Incidente PM2 | Em 2026-06-21, `pm2-ubuntu.service` falhava por `Type=forking` + `PIDFile`; a correcao canonica e `Type=oneshot`, `RemainAfterExit=yes`, sem `PIDFile`, com `pm2 save --force` apenas quando live/dump estao coerentes |
| Incidente Horistic Apache | Em 2026-06-21, sites Horistic quebraram porque o Apache remoto usava unit custom chamando `/usr/sbin/apache2 -k start`; o guard deve verificar unit padrao do pacote, `apache2ctl -S`, portas 80/443 e vhosts no `horistic-srv`, nao no SRV-1 |
| Incidente Horistic webhook | O webhook scalp deve manter split Telegram de entrada dupla com 500ms e suprimir Circuit Breaker apenas no Telegram, ainda encaminhando ao ATS; validacoes do guard nao podem disparar POST real para Telegram/ATS |
| Lacuna principal | `atius-unified-bot-launcher` e `horistic-unified-bot-launcher` rodam em modo one-shot com PM2 `waiting restart`; isso e esperado pelo launcher, mas o volume de restarts torna necessario um health contract explicito em vez de aceitar `waiting restart` cegamente |
| Guard existente | `inviolable-watchdog` ja repara ATS/Horistic PM2 e containers, mas precisa de validator/repair versionado, output JSON, checks de dump/ecosystem/namespace, remote Apache, renomeios e protocolo boot/login |
| Replanejamento Spark | PRG dividido em fases 24-27, cada uma com target de contexto 75k-95k tokens e executor planejado `gpt-5.3-codex-spark` |
| Fechamento por fase | Cada fase termina com bateria automatizada ordenada por custo/complexidade e execucao obrigatoria de `$gsd-verify-work <fase>` |
| Sequencia | 24 foundation status/doctor -> 25 repair engine -> 26 boot/login protocol -> 27 Horistic remote Apache + rename drift + webhook-safe validation |
| Worktree | Mudancas paralelas em `managed-apps`, `srv1-ops`, `fork-sync`, `dark-theme` e Graphify outputs permanecem fora de escopo para esta revisao ate serem integradas por plano/commit seletivo |
| Proximo | Executar Phase 24 primeiro com Spark; fases 25-27 seguem em cadeia, sem restart live automatico de PM2/RDP |

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 28 P02 | 18m | 2 tasks | 4 files |
| Phase 42 P01 | 24 min | 2 tasks | 6 files |

## Decisions

- [Phase 28]: Phase 28 Plan 02 kept G18 upgrade preparation docs-only: no apt mutation, service restart, Landscape mutation, webhook POST, or PM2/XRDP action.
- [Phase 28]: Phase 29 G18 mutation now requires one approval record per host with report path, snapshot ID or exception, backup path, package scope, posture, and signed timestamp.
- [Phase 28]: pending-* OCI snapshot IDs are blockers for live mutation unless the operator signs a no-OCI-restore exception.
- [Phase 42]: Wave 0 keeps ATS RBAC in the DB: OIDC may identify the user, but permissions.js remains authoritative. — The Phase 42 context locks authorization compatibility until a later phase proves an authorization migration.
- [Phase 42]: Phase 42 runtime auth smoke now requires explicit SSO/ADMIN env vars and never falls back to embedded credentials. — Wave 0 must fail closed without secrets or implicit live credential usage.
- [Phase 42]: Phase 42 edge validation remains assertion-driven and dry-run-safe until sso.atius.com.br is published. — The edge contract must be locally verifiable before any DNS, Cloudflare, Apache reload, or Keycloak publication step.

## Scope addendum - 2026-06-24

- Active managed fleet for G18 is now 4 hosts: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`.
- `horistic-srv` is already expected to appear in Landscape web/SaaS at least temporarily.
- Landscape self-hosted remains required in the governance track; SaaS/web is only the temporary control-plane validation layer.
- Phase 29 Task 1 must be rerun/refreshed before any live apt upgrade approval because the existing checkpoint was generated for the previous 3-host fleet.

## Phase 29 checkpoint refresh - 2026-06-25T01:36:00Z

- `29-01-G18-FRESH-INVENTORY.md` was regenerated read-only for 4 hosts: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`.
- `29-01-G18-GO-NOGO.md` was refreshed and the fleet remains `BLOCK` for live apt mutation.
- Common blockers: Ubuntu Pro token file absent at approved paths and Landscape local registration check returns `no` on all 4 hosts.
- Additional blockers: disk warnings on `atius-srv-1` and `atius-srv-2`; role confirmation needed for missing `pm2-ubuntu` on `atius-srv-3` and `horistic-srv`, and missing `k3s` on `horistic-srv`.
- No live mutation, restart, reboot, Landscape mutation, Pro attach/detach, or webhook POST was executed.

## Accumulated Context

## Phase 44 planning - 2026-07-05

- Created Phase 44 for `Internal Service PKI and Fleet Trust`.
- Scope: `omni-srv-admin` managed internal service PKI for `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv`.
- Planning decision: each server gets its own leaf certificate/key, but trust stores receive the internal CA chain, not peer leaf certificates as trusted roots.
- Live read-only SSH preflight passed on all four hosts: SSH, `sudo -n`, OpenSSL 3.0.13, `update-ca-certificates`, NTP synchronized, and `/etc/omni-srv-admin/tls` absent.
- Artifacts: `.planning/spikes/001-fleet-service-pki-trust-matrix/README.md`, `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/44-internal-service-pki-and-fleet-trust/44-CONTEXT.md`, `44-RESEARCH.md`, `44-VALIDATION.md`, and `44-01..03-PLAN.md`.
- No CA, private key, trust-store mutation, service restart, port change, or router channel change was executed in this planning step.

### Roadmap Evolution

- Phase 47.1 inserted after Phase 47: Internal DNS Authority and FreeIPA Convergence (URGENT)
- Phase 47.1 planned after Phase 47: 8 verified plans for authoritative DNS and FreeIPA convergence before Phase 48 plan 48-03

## Phase 44-01 execution - 2026-07-05

- Implemented the `omni fleet trust-pki` CLI resource surface.
- Added `onboard-host` for the new-server flow: resolve host from inventory/DbOmniFleet, render SANs/paths, and optionally queue the PKI sequence in `TbUpdatePlans`.
- Added `reconcile-host` and `rotate-host` for IP/SAN drift detection and leaf rotation when a registered server changes address.
- Added allowlisted `omni.trust-pki.*` command templates locally and in migration `0008_internal_service_pki_commands.sql`.
- Added `modules/fleet-pki` docs/templates and `docs/operations/internal-service-pki.md`.
- Validation passed: 24 focused pytest checks, `trust-pki preflight`, `trust-pki plan`, `trust-pki onboard-host`, `validate-inventory`, `py_compile`, and `git diff --check`.
- Live mutating runner remains blocked until Phase 44-02 installs remote CA/key/cert scripts.

## Phase 42 planning - 2026-06-28T04:57:11-0300

- Created Phase 42 for Atius-wide SSO login on `sso.atius.com.br`, promoting `SSO-MIG-01` into `SSO-01`..`SSO-06`.
- Research, UI, validation, patterns, and 3 executable plans are ready under `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br/`.
- Plan set: `42-01` Wave 0 validation/secret hygiene, `42-02` ATS SSO facade/OIDC bridge/RBAC-compatible session, `42-03` edge/Keycloak/app-host header/manual publication gate.
- Plan checker passed with no blockers or warnings. Next action: run `$gsd-execute-phase 42`.

### Roadmap Evolution

- Phase 29.1 inserted after Phase 29: Obsidian ARM64 AppImage pilot without Snap on atius-srv-1 (URGENT)
- Phase 29.1 edited: filled goal requirements risk canonical refs and success criteria
- Phase 29.1 edited: locked official Obsidian arm64.AppImage source and live-verified v1.12.7 sha256
- Phase 29.1 planned: created RESEARCH and 1 executable PLAN for Obsidian official arm64.AppImage local pilot

## Landscape API reconciliation - 2026-06-25T02:50Z

- Landscape SaaS API read-only validation passed for all 4 managed hosts: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`.
- Evidence artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-02-LANDSCAPE-API-EVIDENCE.md`.
- Local `landscape-config --is-registered` as non-root is now considered permission-limited because `/etc/landscape/client.conf` is unreadable by the invoking user.
- Phase 29 fleet remains `BLOCK` for live apt mutation due to remaining non-Landscape blockers.

## Landscape API tooling note - 2026-06-25T02:55Z

- Tried `ppa:landscape/latest-stable` for an `apt`-based `landscape-api` install after operator approval.
- Result: no `landscape-api` package is available from that PPA on this Noble/ARM64 host; only Landscape server/client/dashboard packages were visible.
- The PPA was removed immediately to avoid changing future `apt upgrade` candidates, especially `landscape-client`, during Phase 29.
- Landscape SaaS API validation is currently performed through a local Python stdlib HMAC client using `LANDSCAPE_API_URI`, `LANDSCAPE_API_KEY`, and `LANDSCAPE_API_SECRET` from `~/.zshrc`.

## Cloudflare DNS for Landscape self-hosted - 2026-06-25T03:21:29Z

- Created Cloudflare DNS record `A landscape.atius.com.br -> 137.131.190.161`.
- Record is DNS-only (`proxied=false`) with TTL 300 to avoid Cloudflare proxy interference with Landscape self-hosted web/API/client flows.
- Evidence artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-02-CLOUDFLARE-DNS-EVIDENCE.md`.
- This prepares the active Landscape self-hosted target using `ppa:landscape/self-hosted-26.04`; it does not install or expose Landscape yet.

## Landscape Cloudflare proxy repair - 2026-07-04T21:50Z

- Symptom: Brave blocked `https://landscape.atius.com.br/` with `net::ERR_CERT_AUTHORITY_INVALID` under HSTS.
- Root cause: the Cloudflare record was still DNS-only and the Apache site was no longer enabled, so SNI for `landscape.atius.com.br` fell through to the default `admin.atius.com.br` vhost and exposed a Cloudflare Origin CA certificate directly to browsers.
- Fix: backed up `/etc/apache2/sites-available/landscape.atius.com.br.conf` to `/home/ubuntu/.backups/apache-landscape-enable-20260704T214537Z`, re-enabled the Apache site with `a2ensite`, passed `apache2ctl configtest`, reloaded Apache, then patched Cloudflare DNS record `7eedc66a6420a7beb1f5cb9abb84a94c` to `proxied=true`, `ttl=1`.
- Cloudflare before/after API evidence: `/home/ubuntu/.backups/cloudflare-landscape-proxy-20260704T214747Z`.
- Validation: DNS now returns Cloudflare IPs; `curl -I https://landscape.atius.com.br/` returns `302` with `Server: cloudflare`; `/new_dashboard/overview` returns `200 text/html`; `/assets/atius-dark.css` returns `200 text/css`; `http://landscape.atius.com.br/ping` returns `200`; edge certificate is issued by Google Trust Services for Cloudflare.
- Residual: `137.131.190.161:6554` still accepts raw TCP, but `landscape.atius.com.br:6554` does not work while the hostname is orange-cloud proxied. If Landscape raw TCP clients ever require hostname-based 6554, use a separate DNS-only hostname, direct origin IP, or Cloudflare Spectrum before relying on that path.
- Evidence artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-12-LANDSCAPE-CLOUDFLARE-PROXY-20260704.md`.

## Landscape classic UI default - 2026-07-04T22:39Z

- Requirement: default Landscape login flow must land on the classic UI because the Vault/secrets administrator is there, not in the modern `/new_dashboard/` UI.
- Fix: backed up `/etc/apache2/sites-available/landscape.atius.com.br.conf` to `/home/ubuntu/.backups/apache-landscape-classic-default-20260704T223757Z` and `/home/ubuntu/.backups/apache-landscape-classic-query-20260704T223905Z`; changed the HTTPS root redirect from `/new_dashboard/` to `/account/standalone/secrets`; added `RewriteCond %{QUERY_STRING} ^$` so Landscape login callbacks like `/?next_url=/account/standalone/secrets` are proxied to the classic login page instead of being redirected again.
- Validation: `https://landscape.atius.com.br/` returns `302` to `/account/standalone/secrets`; following redirects ends at `/?next_url=%2Faccount%2Fstandalone%2Fsecrets` with `200 text/html;charset=utf-8`; `/new_dashboard/overview` remains available at `200`; `/ping` remains `200`.
- Evidence artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-13-LANDSCAPE-CLASSIC-DEFAULT-20260704.md`.

## Session

**Last session:** 2026-06-25T03:25:13.517Z
**Stopped at:** Phase 47.1 planned and independently verified: 8 plans in 8 waves; execute 47.1-01 next and keep Phase 48 plan 48-03 blocked until the release gate passes
**Resume file:** None

## Phase 29 inventory probe correction - 2026-06-25T03:32:16Z

- Updated `scripts/g18-pro-esm-inventory.py` so unreadable `/etc/landscape/client.conf` is reported as `permission-limited` instead of a false local `no` registration result.
- Regenerated `29-01-G18-FRESH-INVENTORY.md` for all 4 managed hosts.
- Rewrote `29-01-G18-GO-NOGO.md`: Landscape SaaS/API remains PASS; local Landscape probe is permission-limited; fleet still BLOCK for non-Landscape blockers.
- No live server mutation was executed.

## Phase 29 controlled apt mutation - 2026-06-25T04:08Z

- Operator approved apt mutation for all 4 managed hosts and confirmed all are Ubuntu Pro/ESM through Landscape SaaS.
- Executed controlled host-by-host `apt-get update && apt-get -y upgrade` on `horistic-srv`, `atius-srv-3`, `atius-srv-2`, and `atius-srv-1`.
- No host reports `reboot-required` after upgrade.
- Landscape SaaS API post-upgrade validation passed for all 4 hosts.
- Post-upgrade inventory artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-POST-UPGRADE-INVENTORY.md`.
- Landscape post-upgrade API artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-POST-UPGRADE-LANDSCAPE-API.md`.
- Execution artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-03-G18-UPGRADE-EXECUTION.md`.
- Remaining Phase 29 gates: human RDP validation, decision on deferred service restarts, decision on phased packages left on `atius-srv-2`.

## Phase 29 runtime repair - 2026-06-25T04:44Z

- Resolved missing `pm2-ubuntu` on `atius-srv-3` and `horistic-srv`; both are now active/enabled with PM2 7.0.1.
- Installed `k3s-agent` on `horistic-srv`; the node joined the existing cluster as Ready worker and now uses OCI/DRG private identity `10.21.1.21` as the canonical service address.
- Did not add `horistic-srv` as fourth etcd/control-plane member to avoid even-numbered etcd quorum risk.
- Updated `scripts/g18-pro-esm-inventory.py` to check `k3s-agent` in addition to `k3s`.
- Updated host inventory YAML for `atius-srv-3` and `horistic-srv`.
- Post-repair inventory artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-POST-RUNTIME-REPAIR-INVENTORY.md`.
- Runtime repair artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-04-RUNTIME-REPAIR.md`.

## Landscape self-hosted hostname routing fix - 2026-06-25T04:48Z

- Fixed `landscape.atius.com.br` on `atius-srv-1`: Apache now has explicit port 80 and 443 vhosts for the hostname.
- Issued Let's Encrypt certificate for `landscape.atius.com.br`, expiring 2026-09-23.
- Prevented fallback to default `admin.atius.com.br` vhost.
- Current endpoint serves a static placeholder for all paths until Landscape self-hosted is installed.
- Remote Apache backup: `/home/ubuntu/.backups/apache-landscape-vhost-20260625T044645Z`.
- Evidence artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-05-LANDSCAPE-APACHE-VHOST.md`.

## Landscape self-hosted preflight - 2026-06-25

- `landscape.atius.com.br` is currently a valid TLS placeholder on `atius-srv-1`; Landscape Server is not installed yet.
- Checked Landscape PPA package availability: `ppa:landscape/self-hosted-26.04` does not publish `landscape-server` or `landscape-server-quickstart` for Noble ARM64, only for AMD64.
- Current ARM64 viable LTS path is `ppa:landscape/self-hosted-24.04`; `latest-stable` has ARM64 packages but is not preferred for production governance.
- Recommended path for current fleet: install Landscape 24.04 LTS on `horistic-srv` or provision AMD64 for strict 26.04 LTS.
- Artifact: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-06-LANDSCAPE-SELFHOSTED-PREFLIGHT.md`.

## Landscape and Vaultwarden legacy-upstream incident - 2026-07-11

- Resolved Apache 503 responses on `landscape.atius.com.br` and `vault.atius.com.br`.
- Root cause: both active vhosts on `atius-srv-1` still targeted retired address `10.1.1.3`.
- Landscape now uses `10.13.1.13:443/80`; Vaultwarden HTTP and WebSocket use `10.13.1.13:8088`.
- Backups were created before mutation; Apache config validation and reload passed.
- Public validation: Landscape HTTP 303 to login with `next_url`; Vaultwarden HTTP 200.
- Evidence: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-INCIDENT-LANDSCAPE-VAULT-503-20260711.md`.

## Public site DRG audit - 2026-07-11

- Audited every HTTPS vhost loaded by Apache on SRV-1 and active reverse-proxy configs on the other OCI hosts.
- Replaced the final active `10.1.1.2` upstreams with canonical SRV-2 address `10.12.1.12`; no enabled reverse-proxy config now references `10.1.1.x`.
- Recovered `router.zentrius.com.br`, `remote.atius-srv-1.atius.com.br`, `mail.atius.com.br`, `webmail.atius.com.br`, and `plane.atius.com.br` to HTTP 200.
- Made Mailcow and Plane boot-persistent through enabled user units.
- Classified 18 residual HTTP 503 names as missing deployments rather than network drift; no replacement service exists on the canonical OCI hosts.
- Evidence: `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-PUBLIC-SITE-DRG-AUDIT-20260711.md`.
