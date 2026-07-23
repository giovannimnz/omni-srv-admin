---
phase: 23
title: "Validation Architecture — Omni Fleet Governance com Landscape complementar"
date: 2026-06-24
status: planned
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
---

# Phase 23 Validation Architecture

## Validation Goal

Provar que o modelo hibrido cobre a operacao da frota: Landscape como camada
complementar de administracao das maquinas Ubuntu, Omni Fleet como governanca e
auditoria propria, Cockpit como break-glass e K3s/Portainer como administracao
do cluster, sem expor superficies administrativas sem gate e sem criar caminho
generico de mutacao remota.

## Requirement Matrix

| Requirement | Evidence | Primary validation |
|---|---|---|
| GOV-01 | Cockpit bloqueado/restrito ou publicado por Access/auth/SSO/WireGuard | `python3 scripts/validate-cockpit-edge.py --expect gated` + `PYTHONPATH=cli pytest cli/omni/tests/test_cockpit_edge.py -q` |
| GOV-02 | Matriz Landscape vs Omni/Cockpit/K3s | `python3 modules/fleet-control-plane/tools/validate_m023.py` checks `docs/fleet/landscape-parity.md` |
| GOV-03 | Collectors reais read-only | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_collectors.py -q` |
| GOV-04 | Program/version desired/current/policy/drift | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_collectors.py modules/fleet-control-plane/tests/test_m023_governance.py -q` + managed-apps seed adapter dry-run |
| GOV-05 | Desired-state profiles | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` |
| GOV-06 | Update profiles e rollout gates | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` + `python3 modules/fleet-control-plane/tools/validate_m023.py` |
| GOV-07 | Repository/source profiles sem secrets | `python3 modules/fleet-control-plane/tools/validate_m023.py` |
| GOV-08 | CVE/USN/security reporting | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py -q` |
| GOV-09 | Execucao via `TbUpdatePlans` + local agent allowlist; sem SSH apply generico | `PYTHONPATH=cli pytest modules/fleet-control-plane/tests/test_m023_governance.py modules/fleet-control-plane/tests/test_m004_contract.py -q` + `python3 modules/fleet-control-plane/tools/validate_m023.py` |
| GOV-10 | Papel do Landscape no modelo operacional hibrido | `python3 modules/fleet-control-plane/tools/validate_m023.py` checks docs decision text |
| GOV-11 | Deploy Landscape self-hosted em Podman/K3s com gates e fallback | `python3 scripts/validate-landscape-deployment.py --docs-only` + endpoint/resource validation after approved deploy + `python3 modules/fleet-control-plane/tools/validate_m023.py` |

## Plan Gates

| Plan | Gate | Pass condition |
|---|---|---|
| 23-01 | Cockpit exposure gate | Validator reports gated/blocked/private exposure; live mutation requires explicit operator approval. |
| 23-02 | Read-only collector gate | Collectors never execute update/install/remove commands and missing tools degrade to warnings. |
| 23-03 | Governance mutation gate | Remediation creates or renders `TbUpdatePlans`; execution remains local to target host agent. |
| 23-04 | Responsibility matrix gate | Docs declare Landscape/Omni/Cockpit/K3s responsibilities without conflating their roles. |
| 23-05 | Landscape deployment gate | Operator-approved target/resources/edge/licensing/rollback are recorded; live deploy is executed and endpoint/rollback evidence is validated. If approval is withheld, the phase is blocked. |

## Minimum Automated Suite

```bash
PYTHONPATH=cli pytest \
  cli/omni/tests/test_cockpit_edge.py \
  modules/fleet-control-plane/tests/test_m023_collectors.py \
  modules/fleet-control-plane/tests/test_m023_governance.py \
  modules/fleet-control-plane/tests/test_m004_contract.py \
  -q

python3 modules/fleet-control-plane/tools/validate_m023.py
python3 modules/fleet-control-plane/tools/import_managed_apps_seed.py --source modules/managed-apps/configs/programs.json --dry-run --json
python3 scripts/validate-cockpit-edge.py --expect gated
python3 scripts/validate-landscape-deployment.py --docs-only
node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status
```

## Acceptable Pre-Execution State

Before implementation, some files named in this validation architecture do not
exist yet. That is expected. The acceptance gate for planning is that every
GOV requirement has an explicit planned validation command and owner plan.

## Non-Negotiable Failures

- Public anonymous direct Cockpit `:9090` remains open after 23-01 live gate.
- Any collector executes `apt upgrade`, `snap refresh`, package installs or
  package removals.
- Any governance remediation path runs generic SSH apply from the requester.
- Managed-apps Chromium/Firefox/Bitwarden seed cannot be loaded into governance
  profiles or explicit compatibility links without divergence.
- Landscape deploy/register-client runs without G23-5 approval, or Phase 23 is marked complete while Landscape was not deployed.
- Docs imply Landscape replaces K3s/Portainer for Kubernetes workloads or replaces
  Omni Fleet audit/governance contracts.
- Any doc, test, log or `.planning` file stores real tokens, passwords, DB
  credentials, Cloudflare service tokens or Ubuntu Pro tokens.
- Final Graphify status is stale or `commit_stale=true` after code, docs or
  planning changes.
