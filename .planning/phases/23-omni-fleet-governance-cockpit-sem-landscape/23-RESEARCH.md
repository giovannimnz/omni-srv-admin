# Phase 23: Omni Fleet Governance Cockpit sem Landscape - Research

**Researched:** 2026-06-24  
**Domain:** Ubuntu fleet governance, Cockpit hardening, Landscape parity, Omni Fleet control plane  
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Nao instalar/habilitar Landscape como dependencia operacional primaria agora.
O alvo e usar:

- Cockpit como console web por host, apenas para operacao interativa e break-glass.
- Omni Fleet Control Plane como sistema central de inventario, programas,
  desired state, update plans, auditoria, agentes locais e monitoramento.
- Prometheus/Grafana/Loki/Portainer/K3s/fork-sync como camadas ja
  implementadas ou planejadas para observability, containers e versionamento.

### the agent's Discretion
Pesquisar a paridade pratica Landscape vs Cockpit + Omni, recomendar lacunas concretas de schema/collector/CLI/docs, e manter execucao remota restrita ao `omni fleet agent` local.

### Deferred Ideas (OUT OF SCOPE)
- Reimplementar Landscape SaaS inteiro.
- Assumir suporte Canonical, SLA, compliance formal ou multi-tenant SaaS.
- Usar Cockpit como control plane central.
- Executar mutacoes live sem approval, snapshot/preflight quando aplicavel e
  auditoria.
</user_constraints>

## Summary

Cockpit deve ser tratado como console interativo por host, nao como substituto central do Landscape. Ele cobre login administrativo, shell, systemd/services e updates por host via PackageKit, mas nao entrega sozinho inventory central, desired state, compliance de profiles, rollout serial/staggered, CVE/USN correlation ou auditoria fleet-wide. [CITED: https://cockpit-project.org/guide/latest/system-softwareupdates.html] [CITED: https://cockpit-project.org/guide/latest/cockpit.conf.5.html]

Omni Fleet ja tem a base correta para substituir a dependencia operacional primaria de Landscape nesta frota: `DbOmniFleet`, `TbPrograms`, `TbVersions`, `TbUpdatePlans`, `TbAuditEvents`, `TbNodeTelemetry`, `TbFleetCommands`, PgBouncer privado e execucao por agent local allowlisted. [VERIFIED: docs/fleet/control-plane.md] [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql] [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql] [VERIFIED: cli/omni/fleet.py]

**Primary recommendation:** implementar Phase 23 como extensao incremental do Omni Fleet: harden Cockpit exposure, adicionar collectors reais, criar migration `0004_governance_profiles.sql`, expor comandos `omni fleet governance/*`, e documentar matriz "Landscape omitido agora; Landscape opcional se precisar SaaS/UI/compliance/suporte Canonical". [VERIFIED: .planning/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-CONTEXT.md]

## Project Constraints (from AGENTS.md)

- Repo: `omni-srv-admin`, display `Omni Srv Admin`, dominio preservado `atius.com.br`, host principal `10.1.1.1`. [VERIFIED: AGENTS.md]
- Projeto e GSD-managed; usar artefatos `.planning` e respeitar fluxo GSD. [VERIFIED: AGENTS.md]
- Instrucoes globais fornecidas pelo usuario exigem PT-BR com Giovanni, comunicacao direta e pratica, sem secrets em docs/logs/planning. [VERIFIED: user-provided AGENTS.md]
- Graphify e obrigatorio quando `.planning/config.json` tem `graphify.enabled: true`; status atual esta fresco no commit `ad8b4b6`, sem `stale` ou `commit_stale`. [VERIFIED: graphify status 2026-06-24]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GOV-01 | Cockpit protegido por Access, Apache auth/SSO ou WireGuard; 9090 publico removido/bloqueado. | 23-01 deve bloquear porta direta e so publicar via gate autenticado. [VERIFIED: .planning/REQUIREMENTS.md] |
| GOV-02 | Matriz Landscape vs Omni/Cockpit com coberta/parcial/fora/pendente. | 23-04 deve gerar doc canonical de paridade. [VERIFIED: .planning/REQUIREMENTS.md] |
| GOV-03 | Agent coleta versoes reais de dpkg/apt, snap, pip/uv, npm/pnpm, cargo, PM2, systemd e containers. | 23-02 deve substituir `current_version=unknown` por collectors locais best-effort. [VERIFIED: cli/omni/fleet.py] |
| GOV-04 | `TbPrograms`/`TbVersions` representam atual/desejada/origem/tipo/policy/drift. | 23-03 deve estender schema atual, que ainda tem campos basicos. [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql] |
| GOV-05 | Desired-state profiles: required, forbidden, pinned, held, manual. | 23-03 deve criar tabelas de profiles e avaliador de drift. [VERIFIED: .planning/REQUIREMENTS.md] |
| GOV-06 | Update profiles: janelas, serial/staggered, security-only/all, approval, rollback_ref, audit. | 23-03 deve estender `TbUpdatePlans`; `rollback_ref` ja existe desde migration 0003. [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql] |
| GOV-07 | Repository/source profiles para APT `.sources`, PPAs, Ubuntu Pro ESM, sem secrets. | 23-03 deve adicionar source profiles e redaction. [VERIFIED: .planning/REQUIREMENTS.md] |
| GOV-08 | CVE/USN/security reporting central por pacote/origem/host. | 23-02/23-03 devem coletar `pro security-status`, `pro cves` e APT security origin. [CITED: https://documentation.ubuntu.com/pro-client/en/v32/references/commands/] |
| GOV-09 | Execucao remota continua via agent local, allowlist e `TbUpdatePlans`; sem SSH apply generico. | 23-03 deve preservar `queue-update` + `agent once/loop`. [VERIFIED: docs/fleet/control-plane.md] |
| GOV-10 | Docs declaram quando Landscape ainda e necessario. | 23-04 deve declarar tradeoffs de SaaS, UI, compliance e suporte Canonical. [CITED: https://documentation.ubuntu.com/landscape/] |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Cockpit break-glass console | Browser / host service | Edge auth | Cockpit e sessao administrativa por host; edge decide quem chega nele. [CITED: https://cockpit-project.org/guide/latest/cockpit-ws.8.html] |
| Fleet inventory/program versions | Local agent | Database / CLI | Versoes reais precisam ser coletadas no host alvo e persistidas no `DbOmniFleet`. [VERIFIED: docs/fleet/control-plane.md] |
| Desired state and drift | Database / Backend | CLI | Profiles sao contratos centrais avaliados contra observacoes de agent. [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql] |
| Update execution | Local agent | Database queue | Mutacao deve acontecer no host alvo, claimando `TbUpdatePlans` aprovado. [VERIFIED: cli/omni/fleet.py] |
| Security/CVE reporting | Local agent | Database / CLI docs | Ubuntu Pro/APT sabem CVEs localmente; Omni centraliza por host. [CITED: https://documentation.ubuntu.com/pro-client/en/v32/references/commands/] |

## Landscape vs Cockpit + Omni Parity

| Landscape Capability | Cockpit Coverage | Omni Current Coverage | Phase 23 Action |
|----------------------|------------------|-----------------------|-----------------|
| Per-machine admin console | Covered for individual hosts. [CITED: https://cockpit-project.org/guide/latest/] | Not a UI console. [VERIFIED: docs/fleet/control-plane.md] | Keep Cockpit for break-glass only. |
| Package list and host updates | Partial; per-host PackageKit software updates. [CITED: https://cockpit-project.org/guide/latest/system-softwareupdates.html] | Partial; `programs`, `update-plan`, `queue-update` exist but current versions are placeholder/inventory-based. [VERIFIED: cli/omni/fleet.py] | Add real collectors and write DB observations. |
| Package profiles/compliance | Not a Cockpit fleet feature. [CITED: https://cockpit-project.org/guide/latest/] | Missing. [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql] | Add desired-state profiles and drift report. |
| Repository/source profiles | Not a Cockpit fleet feature. [CITED: https://cockpit-project.org/guide/latest/] | Missing. [VERIFIED: rg migrations/docs 2026-06-24] | Add APT source/Ubuntu Pro source profiles without tokens. |
| Upgrade profiles and schedules | Cockpit updates are interactive per host. [CITED: https://cockpit-project.org/guide/latest/system-softwareupdates.html] | Partial; queue and approval exist, windows/stagger/security-only missing. [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql] | Extend `TbUpdatePlans` or add `TbUpdateProfiles`. |
| CVE/USN reporting | Not central fleet reporting. [CITED: https://cockpit-project.org/guide/latest/] | Missing central view. [VERIFIED: .planning/REQUIREMENTS.md] | Collect Ubuntu Pro security-status/cves + apt security metadata. |
| SaaS UI, Canonical support, formal compliance reports | Not provided by Cockpit. [CITED: https://cockpit-project.org/guide/latest/] | Out of scope by context. [VERIFIED: 23-CONTEXT.md] | Document Landscape optional for these needs. |

## What Cockpit Can Cover / Cannot Cover

**Can cover**
- Host-level web console, authenticated through the host and reachable on Cockpit's web service. [CITED: https://cockpit-project.org/guide/latest/cockpit-ws.8.html]
- Interactive shell, service inspection, logs and host-local administration when an operator deliberately opens a host. [CITED: https://cockpit-project.org/guide/latest/]
- Host-local software updates through Cockpit's software updates page backed by PackageKit. [CITED: https://cockpit-project.org/guide/latest/system-softwareupdates.html]

**Cannot cover for Phase 23**
- Fleet desired-state profiles, repository profiles, rollout windows, CVE/USN central correlation and Landscape-like compliance matrix are not Cockpit's documented control-plane model. [CITED: https://cockpit-project.org/guide/latest/] [CITED: https://documentation.ubuntu.com/landscape/]
- Public direct exposure of port `9090` is not acceptable here because historical audit identified Cockpit as admin surface with shell/service/user-management impact. [VERIFIED: .planning/codebase/CONCERNS.md]
- Cockpit should not become the place that decides fleet-wide changes; execution stays in Omni `TbUpdatePlans` and local agent. [VERIFIED: docs/fleet/control-plane.md]

## What Omni Already Covers

- Reviewed inventory source of truth remains `inventory/hosts/*.yaml`; PostgreSQL is runtime state, not unreviewed identity source. [VERIFIED: docs/fleet/control-plane.md]
- `DbOmniFleet` has `TbHosts`, `TbNodes`, `TbPrograms`, `TbVersions`, `TbUpdatePlans`, `TbAuditEvents`, `TbFleetCommands`, `TbNodeTelemetry` and related tables. [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql] [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql]
- PgBouncer is the required node/client database endpoint at `10.1.1.1:6432`; direct PostgreSQL from nodes is blocked by design. [VERIFIED: docs/fleet/control-plane.md]
- `omni fleet queue-update` writes executable plans; target hosts execute locally via `omni fleet agent once/loop`. [VERIFIED: cli/omni/fleet.py]
- Existing Phase 16 edge-auth code and docs provide Cloudflare Access + Basic Auth fallback machinery, but live Access remains blocked until dashboard enablement. [VERIFIED: .planning/phases/16-m005-cloudflare-access/16-SUMMARY.md]

## Concrete Missing Work

### Collectors

- Add `agent collect-programs --db --json` that emits a normalized list with `host_id`, `name`, `install_type`, `current_version`, `source`, `manager`, `observed_at`, `raw_ref`, `confidence`. [VERIFIED: GOV-03 in .planning/REQUIREMENTS.md]
- Implement collectors with stdlib subprocess wrappers and timeouts: `dpkg-query`, `apt-cache policy`, `snap list`, `python -m pip list`, `uv pip list` if present, `npm ls -g --depth=0`, `pnpm list -g --depth=0`, `cargo install --list` if present, `pm2 jlist`, `systemctl list-units`, and `podman ps/images`/`docker ps/images` if present. [VERIFIED: environment audit 2026-06-24]
- Treat missing tools as collector warnings, not phase failures; local audit found `cargo` and `cloudflared` absent from PATH during research. [VERIFIED: environment audit 2026-06-24]

### Schema

- Add migration `0004_governance_profiles.sql` with `TbDesiredStateProfiles`, `TbDesiredStateRules`, `TbRepositoryProfiles`, `TbRepositorySources`, `TbProgramObservations`, `TbDriftFindings`, `TbSecurityFindings`, `TbUpdateProfiles`. [VERIFIED: current migrations lack these tables via rg 2026-06-24]
- Extend or view `TbPrograms`/`TbVersions` to represent `desired_version`, `source`, `install_type`, `policy`, `drift_status`, and `profile_id` per host/program. [VERIFIED: modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql]
- Keep raw secrets out: repository profiles may store source URLs, suites/components, enabled state and `secret_ref`, but not Ubuntu Pro tokens, Cloudflare secrets or DB passwords. [VERIFIED: modules/fleet-control-plane/README.md]

### CLI

- Add `omni fleet governance collect --host <id> --db --json`, `drift --host/all`, `profiles list/show/apply --dry-run`, `security report --host/all`, and `landscape-parity --json`. [VERIFIED: current `cli/omni/fleet.py` lacks these subcommands via rg 2026-06-24]
- Preserve `queue-update` as the only mutation entry point for update execution; do not add generic SSH apply. [VERIFIED: GOV-09 in .planning/REQUIREMENTS.md]
- Tests should use Click `CliRunner`, temp host data, monkeypatched subprocess output and temp DB-env paths, matching current fleet and edge tests. [VERIFIED: modules/fleet-control-plane/tests/test_m004_contract.py] [VERIFIED: cli/omni/tests/test_edge.py]

### Docs

- Update `docs/fleet/control-plane.md` with a "Governance without Landscape" section and the new profile/report command contracts. [VERIFIED: docs/fleet/control-plane.md]
- Add `docs/fleet/landscape-parity.md` with the parity matrix and final decision: "Landscape omitted as operational dependency for this fleet; optional for Canonical SaaS/support/compliance UI." [VERIFIED: 23-CONTEXT.md]
- Update `modules/fleet-control-plane/README.md` safe commands and validation list. [VERIFIED: modules/fleet-control-plane/README.md]

## Security Gates for Cockpit Exposure

1. Inventory current Cockpit listeners and vhosts before mutation: `ss -tlnp`, `systemctl status cockpit.socket`, Apache sites, Cloudflare DNS/proxy state. [VERIFIED: .planning/codebase/CONCERNS.md]
2. Direct public `:9090` must be blocked or bound to private/VPN only before declaring GOV-01 complete. [VERIFIED: GOV-01 in .planning/REQUIREMENTS.md]
3. Preferred publication order: Cloudflare Access if Phase 16 dashboard blocker is resolved; otherwise Apache Basic Auth/SSO or WireGuard-only access. [VERIFIED: .planning/phases/16-m005-cloudflare-access/16-SUMMARY.md]
4. If reverse proxying Cockpit, configure allowed origins/proxy headers deliberately and do not trust spoofable `X-Forwarded-*` from direct clients. [CITED: https://cockpit-project.org/guide/latest/cockpit.conf.5.html]
5. Keep Cockpit `LoginTo=false` when exposed through a public-facing web service so the login page cannot pivot to arbitrary hosts. [CITED: https://cockpit-project.org/guide/latest/cockpit.conf.5.html]
6. Validate no secrets enter `.planning`, docs, logs or command output. [VERIFIED: modules/fleet-control-plane/README.md]

## Standard Stack

| Component | Version / Status | Purpose | Why Standard |
|-----------|------------------|---------|--------------|
| Python CLI + Click | Existing repo pattern | Fleet commands and tests | `cli/omni/fleet.py` and `cli/omni/edge.py` already use it. [VERIFIED: cli/omni/fleet.py] |
| PostgreSQL `DbOmniFleet` | Live contract | Central runtime state | Existing schema and PgBouncer contract are already validated. [VERIFIED: docs/fleet/control-plane.md] |
| PgBouncer | `10.1.1.1:6432` contract | Node/client DB access | Required endpoint; direct DB bypass is forbidden. [VERIFIED: docs/fleet/control-plane.md] |
| systemd user service | Existing `omni-fleet-agent.service` | Local node agent loop | Existing installer and service model. [VERIFIED: modules/fleet-control-plane/README.md] |
| Cockpit | Host console only | Break-glass/admin UI per host | Official Cockpit model is interactive Linux host administration. [CITED: https://cockpit-project.org/guide/latest/] |
| Ubuntu Pro Client | `pro 37.2ubuntu~24.04` local | CVE/USN/security status inputs | Official commands include `security-status`, `cves`, `cve`, `fix`. [VERIFIED: environment audit 2026-06-24] [CITED: https://documentation.ubuntu.com/pro-client/en/v32/references/commands/] |

**Installation:** no new external packages recommended for Phase 23 research; use stdlib subprocess collectors and existing repo test dependencies. [VERIFIED: environment audit 2026-06-24]

## Package Legitimacy Audit

No new external package install is recommended. [VERIFIED: Standard Stack above]  
Packages removed due to [SLOP] verdict: none. [VERIFIED: no package install recommendation]  
Packages flagged as suspicious [SUS]: none. [VERIFIED: no package install recommendation]

## Architecture Patterns

### Data Flow

```text
Host-local collectors
  -> omni fleet agent collect-programs/security
  -> local cache + DbOmniFleet through PgBouncer
  -> TbProgramObservations/TbSecurityFindings/TbDriftFindings
  -> CLI reports + docs parity matrix
  -> approved TbUpdatePlans only
  -> local target host agent executes allowlisted command
```

This preserves the existing local-agent execution boundary and adds governance as observation + policy evaluation before approved mutation. [VERIFIED: docs/fleet/control-plane.md]

### Recommended Project Structure

```text
modules/fleet-control-plane/migrations/0004_governance_profiles.sql
modules/fleet-control-plane/tools/validate_m023.py
modules/fleet-control-plane/tests/test_m023_governance.py
docs/fleet/landscape-parity.md
cli/omni/fleet.py
```

These paths match current module boundaries for schema, validation, tests, docs and CLI. [VERIFIED: modules/fleet-control-plane/README.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Host package truth | Custom parser of `/var/lib/dpkg/status` | `dpkg-query`/APT commands | Native tools expose package state and versions. [ASSUMED] |
| CVE metadata | Custom CVE scraper | `pro security-status`, `pro cves`, `pro cve`, `pro fix --dry-run` | Ubuntu Pro client knows local entitlement and CVE/USN applicability. [CITED: https://documentation.ubuntu.com/pro-client/en/v32/references/commands/] |
| Fleet-wide mutation | SSH loops from requester | `TbUpdatePlans` + local `omni fleet agent` | Existing safety model requires local execution and allowlists. [VERIFIED: docs/fleet/control-plane.md] |
| Admin edge auth | Raw public Cockpit port | Cloudflare Access, Apache auth/SSO, or WireGuard | GOV-01 explicitly forbids public direct 9090. [VERIFIED: .planning/REQUIREMENTS.md] |

## Common Pitfalls

### Pitfall 1: Treating Cockpit as Landscape
**What goes wrong:** planners put package compliance and rollout logic in Cockpit instead of Omni. [VERIFIED: 23-CONTEXT.md]  
**How to avoid:** Cockpit remains break-glass; all governance state lives in `DbOmniFleet`. [VERIFIED: docs/fleet/control-plane.md]

### Pitfall 2: Collectors become mutators
**What goes wrong:** a collector calls `apt upgrade` or `snap refresh`. [ASSUMED]  
**How to avoid:** `collect-*` commands are read-only; mutation must go through approved `queue-update`. [VERIFIED: cli/omni/fleet.py]

### Pitfall 3: Secrets in repository/source profiles
**What goes wrong:** Ubuntu Pro token, DB password or Cloudflare token is stored in DB/docs. [VERIFIED: modules/fleet-control-plane/README.md]  
**How to avoid:** store `secret_ref` only and redact command output. [VERIFIED: cli/omni/fleet.py]

### Pitfall 4: Security report overclaims compliance
**What goes wrong:** Omni report is described as formal Canonical compliance/SLA. [VERIFIED: 23-CONTEXT.md]  
**How to avoid:** document it as practical fleet governance; Landscape remains optional for official support/compliance workflows. [CITED: https://documentation.ubuntu.com/landscape/]

## Recommended 23-01..23-04 Plan Outline

### 23-01 - Cockpit edge hardening and access model
- Audit live Cockpit listener/vhost/DNS state; block direct public `:9090`; decide Access vs Apache auth/SSO vs WireGuard-only based on Phase 16 blocker. [VERIFIED: GOV-01] [VERIFIED: .planning/phases/16-m005-cloudflare-access/16-SUMMARY.md]
- Add validation command/runbook that proves anonymous public direct Cockpit access is closed. [VERIFIED: .planning/codebase/CONCERNS.md]

### 23-02 - Fleet package/program/version collectors
- Add read-only collectors and `agent collect-programs --db`; persist normalized observations and warnings. [VERIFIED: GOV-03]
- Add tests for parser normalization using monkeypatched command output; no live package mutation. [VERIFIED: modules/fleet-control-plane/tests/test_m004_contract.py]

### 23-03 - Desired-state profiles and approved update execution
- Add migration 0004 for desired-state, repository, security, drift and update profiles. [VERIFIED: current migrations]
- Add CLI `governance drift`, `profiles`, `security report`; preserve `queue-update` as the only execution path. [VERIFIED: GOV-05..GOV-09]

### 23-04 - Landscape parity matrix, runbook and deprecation decision
- Create `docs/fleet/landscape-parity.md`, update control-plane README/docs, and state: "Landscape omitted now; optional for SaaS/UI/compliance/suporte Canonical." [VERIFIED: GOV-02] [VERIFIED: GOV-10]
- Add validation script/report that maps GOV-01..GOV-10 to implemented commands/docs/tests. [VERIFIED: .planning/REQUIREMENTS.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `python3` | CLI/tests | yes | 3.12.3 | none |
| `pytest` | tests | yes | 7.4.4 | none |
| `psql` | DB validation | yes | 18.4 | offline SQL validation |
| `systemctl` | systemd collector | yes | 255 | collector warning |
| `dpkg-query` | dpkg collector | yes | 1.22.6 | collector warning |
| `apt-cache` | apt collector | yes | 2.8.3 | collector warning |
| `snap` | snap collector | yes | 2.75.2 | collector warning |
| `npm` | npm collector | yes | 11.8.0 | collector warning |
| `pnpm` | pnpm collector | yes | 10.33.0 | collector warning |
| `pm2` | PM2 collector | yes | 7.0.1 | collector warning |
| `podman` | container collector | yes | 4.9.3 | Docker collector if present |
| `pro` | Ubuntu Pro security collector | yes | 37.2ubuntu~24.04 | APT-only security origin report |
| `cargo` | cargo collector | no | - | collector warning |
| `cloudflared` | optional Access diagnostics | no | - | use existing Cloudflare API/edge validation |

**Missing dependencies with no fallback:** none for planning; all missing collector tools should degrade to warnings. [VERIFIED: environment audit 2026-06-24]

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 [VERIFIED: environment audit 2026-06-24] |
| Config file | none detected [VERIFIED: rg/find 2026-06-24] |
| Quick run command | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` |
| Existing baseline command | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m004_contract.py cli/omni/tests/test_edge.py -q` |

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GOV-01 | Cockpit direct public access blocked/gated | smoke/unit | `python3 scripts/validate-edge-auth.py --expect pre-cutover` plus new Cockpit probe | partial |
| GOV-02/GOV-10 | parity matrix and decision docs | docs test | `python3 modules/fleet-control-plane/tools/validate_m023.py` | no |
| GOV-03/GOV-04 | collectors populate observations | unit | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` | no |
| GOV-05/GOV-06/GOV-07/GOV-08/GOV-09 | profiles/security/update gates | unit/schema | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` | no |

**Wave 0 gaps**
- Add `modules/fleet-control-plane/tests/test_m023_governance.py`. [VERIFIED: no file exists 2026-06-24]
- Add `modules/fleet-control-plane/tools/validate_m023.py`. [VERIFIED: no file exists 2026-06-24]
- Add migration schema tests for `0004_governance_profiles.sql`. [VERIFIED: current test only checks M004 tables]

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Cloudflare Access, Apache auth/SSO or WireGuard gate for Cockpit. [VERIFIED: GOV-01] |
| V3 Session Management | yes | Let Cockpit/Access own sessions; Omni does not implement browser sessions in Phase 23. [CITED: https://cockpit-project.org/guide/latest/] |
| V4 Access Control | yes | `TbFleetCommands.allowed_host_ids`, approvals and command allowlists. [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql] |
| V5 Input Validation | yes | Click argument validation, JSON parsing guards and SQL literals already used; add parser tests. [VERIFIED: cli/omni/fleet.py] |
| V6 Cryptography | yes | Do not store raw tokens; use existing secret refs and Cloudflare token file mode 0600. [VERIFIED: cli/omni/tests/test_edge.py] |

| Threat Pattern | STRIDE | Standard Mitigation |
|----------------|--------|---------------------|
| Public Cockpit brute force/admin probing | Spoofing/Elevation | Block direct 9090 and require Access/auth/VPN. [VERIFIED: GOV-01] |
| Generic SSH fleet mutation | Tampering/Elevation | No generic apply; use `TbUpdatePlans` + local agent. [VERIFIED: GOV-09] |
| Secret leakage in reports | Information disclosure | Redaction and `secret_ref` only. [VERIFIED: cli/omni/fleet.py] |
| Duplicate or concurrent update execution | Tampering | lease/idempotency fields in `TbUpdatePlans`. [VERIFIED: modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Native package-manager CLIs are preferable to parsing raw status files. | Don't Hand-Roll | Collector implementation may need parser fallback if command output is insufficient. |
| A2 | Collector commands can remain read-only with subprocess timeouts and no extra packages. | Common Pitfalls / Standard Stack | If output formats are too divergent, planner may need a parser helper module, still without external install. |

## Open Questions

1. **Cloudflare Access for Cockpit**
   - What we know: Phase 16 is blocked on account-level Access dashboard enablement. [VERIFIED: .planning/phases/16-m005-cloudflare-access/16-SUMMARY.md]
   - What's unclear: whether Giovanni wants Cockpit behind Access now or WireGuard/Apache auth until Access is enabled. [ASSUMED]
   - Recommendation: plan 23-01 with fallback path; do not block GOV-01 on Access if Apache auth/SSO or WireGuard closes public 9090. [VERIFIED: GOV-01]

2. **Formal compliance requirement**
   - What we know: context excludes formal compliance/SLA and Landscape SaaS reimplementation. [VERIFIED: 23-CONTEXT.md]
   - What's unclear: whether future customer/audit needs will require Canonical Landscape reports. [ASSUMED]
   - Recommendation: document Landscape as optional trigger, not Phase 23 dependency. [VERIFIED: GOV-10]

## Sources

### Primary / Official
- Cockpit Guide - project documentation, web service, config, software updates. [CITED: https://cockpit-project.org/guide/latest/]
- Canonical Landscape documentation - package/security/repository/profile capability baseline. [CITED: https://documentation.ubuntu.com/landscape/]
- Ubuntu Pro Client command reference - `security-status`, `cves`, `cve`, `fix`. [CITED: https://documentation.ubuntu.com/pro-client/en/v32/references/commands/]
- Cloudflare Access self-hosted applications docs. [CITED: https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/self-hosted-public-app/]

### Repo-Verified
- `.planning/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-CONTEXT.md`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `docs/fleet/control-plane.md`
- `modules/fleet-control-plane/README.md`
- `modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql`
- `modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql`
- `cli/omni/fleet.py`
- `.planning/codebase/CONCERNS.md`
- `.planning/phases/16-m005-cloudflare-access/16-SUMMARY.md`
- `docs/operations/edge-auth.md`
- `cli/omni/tests/test_edge.py`
- `modules/fleet-control-plane/tests/test_m004_contract.py`

## Metadata

**Confidence breakdown:**
- Cockpit capability: MEDIUM - official docs checked, but no live Cockpit config mutation performed. [CITED: https://cockpit-project.org/guide/latest/]
- Landscape parity: MEDIUM - official Landscape docs checked, but Phase 23 intentionally implements practical subset, not SaaS clone. [CITED: https://documentation.ubuntu.com/landscape/]
- Omni current state: HIGH - repo docs, migrations and CLI read directly. [VERIFIED: docs/fleet/control-plane.md]
- Security gates: HIGH for repo constraints, MEDIUM for final Access path because Phase 16 remains dashboard-blocked. [VERIFIED: .planning/phases/16-m005-cloudflare-access/16-SUMMARY.md]

**Research date:** 2026-06-24  
**Valid until:** 2026-07-24 for repo-internal design; recheck official Cockpit/Landscape/Cloudflare docs before live exposure changes.
