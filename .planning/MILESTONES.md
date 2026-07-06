# Milestone Branch Matrix

## v1.3 Local AI Embeddings and Semantic Retrieval (Shipped: 2026-06-26)

**Phases completed:** 1 phases, 1 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v1.3 Local AI Embeddings and Semantic Retrieval (Completed: 2026-06-26)

**Phases completed:** 1 phase, 1 plan

**Goal:** Local embeddings via `https://router.atius.com.br/v1`, New API gateway, TEI backend on k3s in `horistic-srv`, and a stable `embedding-gte-v1` contract for GBrain, Obsidian and Graphify.

**Key planned deliverables:**

- TEI service in namespace `ai-search`, internal only, serving `Alibaba-NLP/gte-multilingual-base` on private `horistic-srv` URL `http://10.1.1.4:3115`.
- New API channel/alias mapping `embedding-gte-v1` -> `embedding-gte-v1`.
- External smoke tests for OpenAI-compatible `/v1/models` and `POST /v1/embeddings` passed.
- Migration runbook for GBrain/Obsidian/Graphify with 768-dimensional contract and reindex rules.

**Guardrails:**

- No New API key can be written into shell history, Git, `.planning`, Obsidian or logs.
- New API channel base URL must point to `http://10.1.1.4:3115`, never back to `https://router.atius.com.br/v1`.
- Any future alias backend change requires same model/digest/quantization/dimension/normalization or a full reembed/reindex.

---

## v1.1 M005 Follow-ups (Shipped: 2026-06-24)

**Phases completed:** 3 phases, 3 plans, 0 tasks

**Key accomplishments:**

- OCI snapshot workflow versionado para os hosts `oracle-oci`, com CLI `omni srv oci`, runbook e dry-run validado.
- Cloudflare Access client/runbook versionados para os admin edges, mantendo Basic Auth como fallback e registrando o live cutover como gate externo de dashboard.
- Observability/RWX bundle entregue com CLI, dashboards/rules/scripts e decisão documentada de storage K3s.

**Known live gates:**

- Live OCI restore drill depende de `oci` CLI + API key no host.
- Cloudflare Access depende do botão "Enable Access" no dashboard.
- Observability live closeout depende de gate de produção, alert webhook secret e provisioning final de dashboards.

---

## v1.0 v1.0 (Shipped: 2026-06-15)

**Phases completed:** 7 phases, 23 plans, 28 tasks

**Key accomplishments:**

- FQDN resolution for FreeIPA, NTP synchronization via chrony, working certbot v5.5.0, and comprehensive port inventory audit
- Migrate Apache2 from ports 80/443 to 9080/9444 across 54+ vhosts with certbot webroot fallback
- systemd-resolved stub disabled on port 53 for FreeIPA BIND, Cloudflare Origin Rules investigated, full Phase 1 validation complete
- Resource governor and inviolable watchdog guardrails versioned with install dry-run, status drift reporting and default.target-independent critical units.
- Canonical PM2 boot path documented. Repo version of pm2-ubuntu.service updated. Live apps preserved (no gated mutation applied).
- Read-only validation. All governor/inviolable units active. Cgroup profile consistent. No XRDP/SSHD leftover in watchdog cgroup. No live mutation required.
- Jenkins migrado 100% para Podman. Bind mounts Docker-orfaos removidos. Validado externamente em https://jenkins.atius.com.br/ (x-jenkins 2.541.3).
- Jenkins agent Deployment deployed live in K3s HA cluster. 2/2 pods Running. JNLP reachable via wg0. Foundation for Kubernetes plugin integration.
- All 6 plans complete. M006 closed. Live state preserved (no PM2/XRDP restart performed).

---

## v1.0 v1.0 (Shipped: 2026-06-15)

**Phases completed:** 7 phases, 23 plans, 28 tasks

**Key accomplishments:**

- FQDN resolution for FreeIPA, NTP synchronization via chrony, working certbot v5.5.0, and comprehensive port inventory audit
- Migrate Apache2 from ports 80/443 to 9080/9444 across 54+ vhosts with certbot webroot fallback
- systemd-resolved stub disabled on port 53 for FreeIPA BIND, Cloudflare Origin Rules investigated, full Phase 1 validation complete
- Resource governor and inviolable watchdog guardrails versioned with install dry-run, status drift reporting and default.target-independent critical units.
- Canonical PM2 boot path documented. Repo version of pm2-ubuntu.service updated. Live apps preserved (no gated mutation applied).
- Read-only validation. All governor/inviolable units active. Cgroup profile consistent. No XRDP/SSHD leftover in watchdog cgroup. No live mutation required.
- Jenkins migrado 100% para Podman. Bind mounts Docker-orfaos removidos. Validado externamente em https://jenkins.atius.com.br/ (x-jenkins 2.541.3).
- Jenkins agent Deployment deployed live in K3s HA cluster. 2/2 pods Running. JNLP reachable via wg0. Foundation for Kubernetes plugin integration.
- All 6 plans complete. M006 closed. Live state preserved (no PM2/XRDP restart performed).

---

**Last updated:** 2026-06-15

Este arquivo deve existir em `main` e nas branches de planejamento para deixar
clara a ordem dos milestones e onde cada plano completo vive.

## Correct Order

| Milestone | Phase | Name | Canonical branch | Full artifacts | Status |
|---|---:|---|---|---|---|
| M004 | 12 | Omni Fleet Control Plane | `codex/omni-fleet-control-plane-m004` | `.planning/phases/12-omni-fleet-control-plane/` | Live implemented; repos, central DB, PgBouncer node path and DB-backed ops/config/slash registry validated |
| M005 | 13 | K3s HA Cluster + Portainer | `codex/k3s-portainer-oci-plan` | `.planning/phases/13-k3s-ha-portainer-oci/` | Live: K3s HA + Portainer + observability live; edge Basic Auth active; OCI snapshot IDs/RWX strategy pending |
| M006 | 14 | SRV-1 Resource Governance + PM2 Hardening | `codex/phase14-resource-governor-14-01` | `.planning/phases/14-resource-governor-pm2-boot-hardening/` | ✅ Shipped in v1.0 (2026-06-15) |
| M007 | 15-17 | M005 Follow-ups: OCI snapshots, Cloudflare Access, observability, RWX | TBD | `.planning/phases/{15,16,17}-*/` | ✅ Shipped procedurally in v1.1 (2026-06-24); live gates deferred |
| M011 | 41 | Local AI Embeddings Gateway on horistic-srv | TBD | `.planning/phases/41-local-ai-embeddings-gateway-horistic-srv/` | Planned |

## Separation Rule

- Fleet branch contains the full M004/Phase 12 plan and only references K3s.
- K3s branch contains the full M005/Phase 13 plan and references Fleet as a prerequisite.
- Phase 14 branch contains the full M006 plan and references the live fix note `60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md` in the vault.
- `main` keeps the shared milestone/branch index and roadmap visibility; full plan artifacts should arrive via their canonical branches.

## Dependency

M004 comes before M005 because Fleet Control Plane defines the operational base:
inventory, server/node install contract, central PostgreSQL via PgBouncer,
per-host ops scopes, DB-backed configs/parameters, CLI-Anything slash-command
registry, program registry, versions/update plans, license metadata, audit logs
and the future contract consumed by Podman/K3s.

M005 must not be executed before:

- M004 live implementation remains healthy: repos on SRV1/SRV2/SRV3, central DB on SRV-1, nodes through PgBouncer.
- SRV-1 is upgraded to Ubuntu 24.04.
- Preflight for `ATIUS-SRV-1`, `ATIUS-SRV-2`, `ATIUS-SRV-3` passes.
- OCI snapshots/backups, public-ingress closure in each OCI account and host firewall rules for `wg0` are confirmed.
- Cloudflare Tunnel token is supplied out-of-band.
- Portainer exposure target remains `portainer.atius.com.br`.
- PTP fallback mesh is designed and validated before production-ready.

M006 depends on the live fix note and runs in parallel with M004/M005:

- Read: `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md`
- Backup pointer: `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`

## v1.1 v1.1 (In progress)

**Status:** M005 follow-ups + M007-ext + M008 + M008-b

### M008 — Fleet Standardization (Phases 18-19)

| Phase | Name | Status |
|------|------|--------|
| 18 | Ubuntu Pro ESM Apps + Google account link | D18-06-A/B/C done; G18-1 (apt upgrade) awaiting operator |
| 19 | Fleet Standardization (hostnames + chromium + dark theme) | ✅ DONE 2026-06-17 |

**Branch:** TBD (work committed to main as `c0543a9de` + `5077660c7`)

### M008-b — Podman Networking Standardization (Phase 20)

| Phase | Name | Status |
|------|------|--------|
| 20 | Podman Networking Standardization (containers.conf + netavark + aardvark) | ✅ DONE 2026-06-17 |

**Origin:** cutover plane-app v1.2.1 → v1.3.1 on SRV-1 (2026-06-16) surfaced 3 latent bugs (aardvark self-lookup NXDOMAIN, systemd-resolved missing on SRV-2 causing mailcow Exited 45h, containers.conf drift across fleet). Work consolidated into fleet-wide standard + skill + module + CLI.

**Artifacts:**

- `modules/fleet/podman-network/` (12 files, canonical)
- `~/.hermes/skills/devops/podman-fleet-standardize/` (12 files, vendored)
- `omni podman-network {drift,apply,smoke,standard}` (4 CLI subcommands)
- Commit `c0543a9de` on `origin/main` (16 files, 1741 insertions)
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.2.0 (cross-ref)

**Validation:** `omni podman-network drift` returns 6/6 PASS on all 3 SRVs.

### Operator next steps (unchanged)

- [ ] Authorize G18-1 (apt upgrade esm-apps+infra nos 3 SRVs)
- [ ] Validate G18-2 (Microsoft RDP login pós-upgrade nos 3 SRVs)
- [ ] Confirmar Landscape SaaS UI com SRV-1/2/3 online
