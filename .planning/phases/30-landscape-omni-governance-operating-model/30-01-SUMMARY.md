---
phase: 30-landscape-omni-governance-operating-model
plan: 01
status: complete
completed_at: 2026-06-25
requirements_addressed:
  - GOV-01
  - GOV-02
  - GOV-07
---

# Phase 30 / Plan 30-01 — Summary

## Outcome

Phase 30 is complete as a governance/operating-model phase.

The durable decision is:

- Omni Fleet remains the source of truth for reviewed inventory, governance, audit and approved automation.
- Landscape self-hosted is the durable Ubuntu machine-management endpoint for the four managed servers.
- Landscape SaaS remains a fallback/reference path, not the durable endpoint.
- Cockpit remains host-level break-glass only.
- K3s/Portainer remain the workload and container administration plane.
- Observability remains a read-only signal plane and does not execute repairs automatically.

## Artifacts

| Artifact | Purpose |
|---|---|
| `docs/fleet/landscape-omni-governance.md` | Canonical matrix, access model, operating rules, fallback model and validation commands |
| `docs/fleet/control-plane.md` | Updated with the Landscape/Omni governance section and pointer to the canonical doc |
| `.planning/REQUIREMENTS.md` | GOV-01, GOV-02 and GOV-07 marked complete |
| `.planning/ROADMAP.md` | Phase 30 marked complete and Phase 31 remains next |
| `.planning/STATE.md` | Current phase advanced to 31 |

## Validation

No live mutation was required for this phase. The document uses the already-validated Phase 29 baseline:

- Landscape self-hosted installed on SRV3 LXD.
- Public `landscape.atius.com.br` edge active through SRV1.
- Four hosts registered to self-hosted account `standalone`.
- Landscape secrets client fixed through local Vault.
- `http://landscape.atius.com.br/ping` serves client heartbeat.
- K3s, Portainer and RDP remained green at Phase 29 closeout.

## Follow-up

Proceed to Phase 31:

- Implement or consolidate collectors for programs, packages, repositories, policies and customizations.
- Model desired-state profiles and update-plan approval/audit flow.

