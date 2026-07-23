---
phase: 23
plan: 00
type: index
wave: 0
depends_on: []
files_modified: []
autonomous: false
padded: 23
slug: omni-fleet-governance-cockpit-sem-landscape
name: Omni Fleet Governance com Landscape complementar
date: 2026-06-24
status: ready
plans: 5
requirements:
  - GOV-01
  - GOV-02
  - GOV-03
  - GOV-04
  - GOV-05
  - GOV-06
  - GOV-07
  - GOV-08
  - GOV-09
  - GOV-10
  - GOV-11
must_haves:
  truths:
    - "Landscape self-hosted entra como camada complementar de administracao das maquinas Ubuntu."
    - "Cockpit fica restrito a console por host e break-glass."
    - "Omni Fleet e o control plane central para inventario, programas, versoes, desired state, update plans, auditoria e agentes locais."
    - "K3s/Portainer continuam responsaveis por administracao do cluster e workloads."
    - "Collectors locais reportam versoes reais e security findings sem executar updates."
    - "managed-apps Chromium/Firefox/Bitwarden e seed operacional reutilizavel e precisa mapear para perfis de governanca ou compatibility links sem divergencia."
    - "Mutacoes fleet-wide continuam passando por TbUpdatePlans aprovados, omni fleet agent local e command allowlist."
    - "Deploy Landscape em Podman/K3s exige gate de recursos, portas 80/443, certificados, Pro/licenca, registro de clientes, backup/rollback e fallback LXD/VM/Juju."
  artifacts:
    - path: "docs/operations/cockpit-edge.md"
      provides: "Runbook e gate de exposicao Cockpit por Access/auth/VPN."
    - path: "cli/omni/fleet_collectors.py"
      provides: "Collectors locais read-only de programas, pacotes, servicos e containers."
    - path: "modules/fleet-control-plane/migrations/0004_governance_profiles.sql"
      provides: "Schema de desired state, repository profiles, security findings, drift e update profiles."
    - path: "modules/fleet-control-plane/tools/import_managed_apps_seed.py"
      provides: "Adapter dry-run/import para converter managed-apps seed em perfis de governanca."
    - path: "docs/fleet/landscape-parity.md"
      provides: "Matriz Landscape vs Omni/Cockpit/K3s e modelo operacional hibrido."
    - path: "docs/operations/landscape-self-hosted.md"
      provides: "Runbook de deploy Landscape self-hosted em Podman/K3s com fallback suportado."
  key_links:
    - from: "cli/omni/fleet.py"
      to: "cli/omni/fleet_collectors.py"
      via: "agent collect-programs"
      pattern: "collect-programs"
    - from: "cli/omni/fleet.py"
      to: "TbUpdatePlans"
      via: "queue-update and agent once/loop"
      pattern: "queue-update|agent once|TbUpdatePlans"
    - from: "modules/fleet-control-plane/tools/validate_m023.py"
      to: "GOV-01..GOV-11"
      via: "offline coverage validation"
      pattern: "GOV-01|GOV-11"
    - from: "modules/managed-apps/configs/programs.json"
      to: "modules/fleet-control-plane/tools/import_managed_apps_seed.py"
      via: "managed-apps seed compatibility"
      pattern: "chromium|firefox|bitwarden"
---

# Phase 23: Omni Fleet Governance com Landscape complementar

<objective>
Implementar governanca hibrida da frota: Landscape self-hosted entra como
camada complementar de administracao das maquinas Ubuntu; Cockpit fica como
console web por host e break-glass; Omni Fleet continua como control plane
proprio de inventario, programas, versoes, desired-state profiles, update
plans, auditoria, agentes locais e security reporting; K3s/Portainer seguem
como administracao do cluster e workloads.

Purpose: ganhar seguranca operacional com Landscape sem transformar Cockpit ou
Landscape em orquestrador do cluster e sem criar caminho generico de mutacao
remota fora dos gates auditaveis.
Output: cinco PLAN.md executaveis, em ondas, cobrindo Cockpit edge hardening,
collectors, governanca/update profiles/security reporting, matriz de
responsabilidades e deploy Landscape self-hosted em Podman/K3s com fallback.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-CONTEXT.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-RESEARCH.md
@docs/fleet/control-plane.md
@modules/fleet-control-plane/README.md
@cli/omni/fleet.py
@modules/fleet-control-plane/migrations/0001_fleet_control_plane.sql
@modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql
@.planning/codebase/CONCERNS.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/16-m005-cloudflare-access/16-SUMMARY.md
</context>

## Locked Direction

These labels trace the locked context decisions from `23-CONTEXT.md`:

- D-01: Landscape self-hosted is implemented as a complementary Ubuntu machine management layer.
- D-02: Cockpit is a per-host console for interactive operation and break-glass only.
- D-03: Omni Fleet is the central governance/control plane.
- D-04: Live mutation requires explicit approval, preflight/snapshot when applicable and audit.
- D-05: Remote execution remains local to the target host through `TbUpdatePlans`, `omni fleet agent` and command allowlists; no generic SSH apply.
- D-06: Secrets stay out of git, `.planning`, logs and vault.
- D-07: K3s/Portainer remain the cluster/workload administration layer; Landscape manages Ubuntu machines, not Kubernetes workloads.
- D-08: Podman/K3s Landscape packaging requires validation and fallback to LXD/VM/Juju if it is not stable.

## Wave Structure

| Wave | Plans | Why |
|---|---|---|
| 1 | `23-01`, `23-02` | Cockpit edge validation and read-only collectors touch separate files. |
| 2 | `23-03` | Consumes collector contracts from `23-02` and extends DB governance. |
| 3 | `23-04` | Documents the hybrid operating model before live Landscape deployment. |
| 4 | `23-05` | Deploys Landscape after the model, gates and fallback are explicit. If approval is withheld, the phase blocks instead of succeeding from docs-only readiness. |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `23-01` | Cockpit edge hardening and access model | GOV-01 | 1 | no, live exposure gate |
| `23-02` | Fleet package/program/version collectors | GOV-03, GOV-04, GOV-08 | 1 | yes |
| `23-03` | Desired-state profiles, update profiles, security reporting and execution gates | GOV-04, GOV-05, GOV-06, GOV-07, GOV-08, GOV-09 | 2 | yes |
| `23-04` | Landscape/Omni/Cockpit/K3s responsibility matrix and operating model | GOV-02, GOV-10 plus final GOV audit | 3 | yes |
| `23-05` | Self-hosted Landscape deployment on Podman/K3s | GOV-11 | 4 | no, live deployment gate |

<tasks>

<task type="auto">
  <name>Task 1: Executar plans em ondas</name>
  <files>.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-01-PLAN.md, .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-02-PLAN.md, .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-03-PLAN.md, .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-04-PLAN.md, .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-05-PLAN.md</files>
  <action>Execute `23-01` and `23-02` first because they do not share implementation files. Execute `23-03` only after `23-02` creates the collector contract. Execute `23-04` before live Landscape work because it defines the responsibility matrix. Execute `23-05` only after the operator approves the deployment target and resource/certificate/licensing gate. If the operator does not approve the Landscape deploy, mark the phase blocked rather than complete. Preserve D-01 through D-08 throughout the phase.</action>
  <verify>
    <automated>for f in .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-{01,02,03,04,05}-PLAN.md; do gsd-tools query verify.plan-structure "$f" >/dev/null || exit 1; done</automated>
  </verify>
  <done>All five per-plan files parse as GSD plan structures and are executable in the listed wave order.</done>
</task>

<task type="auto">
  <name>Task 2: Manter gates de mutacao live explicitos</name>
  <files>.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-01-PLAN.md, .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-03-PLAN.md</files>
  <action>Ensure Cockpit exposure changes require a blocking checkpoint before live firewall, Apache or Cockpit socket mutation, and ensure update execution remains only through approved `TbUpdatePlans` plus local `omni fleet agent` allowlisted commands per D-04 and D-05.</action>
  <verify>
    <automated>grep -R "checkpoint:human-verify\\|TbUpdatePlans\\|command allowlist\\|sem SSH apply generico" .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-*-PLAN.md</automated>
  </verify>
  <done>Plan text makes Cockpit and package/update mutation gates explicit, and no plan introduces generic SSH apply.</done>
</task>

</tasks>

## Source Coverage Audit

| Source | ID | Feature/Requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 23 | Hybrid governance with Landscape for Ubuntu machines, Cockpit break-glass, Omni Fleet governance and K3s/Portainer cluster administration | 23-01..23-05 | COVERED | D-01..D-08 traced in all plans. |
| REQ | GOV-01 | Cockpit protected by Access/auth/SSO/WireGuard; no direct public 9090 | 23-01 | COVERED | Blocking live gate included. |
| REQ | GOV-02 | Landscape vs Omni/Cockpit parity matrix | 23-04 | COVERED | `docs/fleet/landscape-parity.md`. |
| REQ | GOV-03 | Agent collects real versions from package managers, PM2, systemd and containers | 23-02 | COVERED | `fleet_collectors.py` and `agent collect-programs`. |
| REQ | GOV-04 | Program/version state includes current, desired, origin, install type, policy and drift | 23-02, 23-03 | COVERED | Collector output plus schema/view/drift findings and managed-apps seed adapter. |
| REQ | GOV-05 | Desired-state profiles required/forbidden/pinned/held/manual | 23-03 | COVERED | `TbDesiredStateProfiles` and `TbDesiredStateRules`. |
| REQ | GOV-06 | Update profiles windows, serial/staggered, security-only/all, approval, rollback_ref, audit | 23-03 | COVERED | `TbUpdateProfiles` plus `TbUpdatePlans` constraints. |
| REQ | GOV-07 | Repository/source profiles without secrets | 23-03 | COVERED | `TbRepositoryProfiles` and `TbRepositorySources` use `secret_ref`. |
| REQ | GOV-08 | CVE/USN/security reporting by package/origin/host | 23-02, 23-03 | COVERED | Security collector inputs plus `TbSecurityFindings`. |
| REQ | GOV-09 | Remote execution local via agent, allowlist, TbUpdatePlans; no SSH apply | 23-03 | COVERED | Explicit negative gate and validation. |
| REQ | GOV-10 | Docs state Landscape role in the operating model | 23-04 | COVERED | Hybrid responsibility matrix. |
| REQ | GOV-11 | Self-hosted Landscape deployment on Podman/K3s with resource/cert/licensing/client/rollback gates | 23-05 | COVERED | Approved live deployment plus fallback if Podman/K3s is unstable. |
| RESEARCH | R-01 | Cockpit is not Landscape/control plane | 23-01, 23-04 | COVERED | Break-glass-only model. |
| RESEARCH | R-02 | Add collectors and normalized observations | 23-02 | COVERED | Read-only collectors with warnings. |
| RESEARCH | R-03 | Add governance migration 0004 | 23-03 | COVERED | Desired/repo/security/drift/update profile tables. |
| RESEARCH | R-04 | Preserve PgBouncer-only DB and local agent execution | 23-02, 23-03 | COVERED | `_db_env` and existing agent model. |
| RESEARCH | R-05 | Add Landscape operating model doc and validator | 23-04 | COVERED | Docs plus `validate_m023.py`. |
| RESEARCH | R-06 | Validate Landscape self-hosted deployment path | 23-05 | COVERED | Podman/K3s target with LXD/VM/Juju fallback. |
| CONTEXT | D-01 | Landscape complementary machine-management layer | 23-05 | COVERED | Self-hosted deploy plan. |
| CONTEXT | D-02 | Cockpit per-host/break-glass only | 23-01, 23-04 | COVERED | No central Cockpit control plane. |
| CONTEXT | D-03 | Omni Fleet central governance/control plane | 23-02, 23-03 | COVERED | DB/CLI/schema extensions. |
| CONTEXT | D-04 | Explicit approval/audit before live mutation | 23-01, 23-03 | COVERED | Blocking Cockpit gate and approved update plans. |
| CONTEXT | D-05 | No generic SSH apply | 23-03 | COVERED | Validator and task acceptance enforce this. |
| CONTEXT | D-06 | No secrets in repo/planning/logs/vault | 23-01, 23-03, 23-04 | COVERED | Secret redaction and `secret_ref` only. |
| CONTEXT | D-07 | K3s/Portainer remain cluster/workload layer | 23-04, 23-05 | COVERED | Responsibility matrix. |
| CONTEXT | D-08 | Podman/K3s packaging needs validation and fallback | 23-05 | COVERED | Explicit deployment gate. |

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| browser-to-Cockpit | Public or VPN browser traffic reaches a host administration console. |
| browser-to-Landscape | Public or VPN browser traffic reaches Landscape's machine management UI. |
| CLI-to-DbOmniFleet | Operator and agents write/read runtime governance state through PgBouncer. |
| local-agent-to-host | `omni fleet agent` runs allowlisted commands on the target host. |
| collector-output-to-DB | Untrusted command output is normalized and persisted. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|---|---|---|---|---|
| T-23-01 | Spoofing/Elevation | Cockpit edge | mitigate | `23-01` blocks direct public 9090 and requires Access/auth/SSO/WireGuard. |
| T-23-02 | Tampering/Elevation | update execution | mitigate | `23-03` preserves `TbUpdatePlans`, approvals, leases and command allowlists; no SSH apply. |
| T-23-03 | Information Disclosure | repository/security reports | mitigate | `23-03` stores only `secret_ref` and redacts tokens/passwords/serials. |
| T-23-04 | Tampering | collector parsers | mitigate | `23-02` treats command output as untrusted, uses timeouts and JSON guards, and never mutates packages. |
| T-23-05 | Elevation/DoS | Landscape deployment | mitigate | `23-05` requires resource sizing, edge auth, certificates, client registration, backup/rollback and fallback before live deploy. |
| T-23-SC | Tampering | package installs | accept | Phase 23 plans no npm/pip/cargo dependency installs; no package legitimacy gate is needed. |
</threat_model>

<verification>
Run plan-structure validation for each per-plan file, then execute the plans by wave. After implementation, run:

- `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_collectors.py modules/fleet-control-plane/tests/test_m023_governance.py cli/omni/tests/test_cockpit_edge.py -q`
- `python3 modules/fleet-control-plane/tools/validate_m023.py`
- `python3 scripts/validate-cockpit-edge.py --expect gated`
- `python3 scripts/validate-landscape-deployment.py --docs-only`
- `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
</verification>

<success_criteria>
Phase 23 is complete when GOV-01..GOV-11 are covered by code, schema, validation or docs; Cockpit is not a primary control plane; Landscape self-hosted is deployed and validated as the complementary Ubuntu machine-management layer; K3s/Portainer remain responsible for cluster workloads; Graphify reports `stale=false` and `commit_stale=false`; and fleet-wide mutation remains limited to approved `TbUpdatePlans` executed by local agents or documented Landscape workflows with operator approval. If Landscape deployment approval is withheld, the phase remains blocked rather than complete.
</success_criteria>

<output>
Create `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/23-omni-fleet-governance-cockpit-sem-landscape/23-SUMMARY.md` when all five plans complete.
</output>
