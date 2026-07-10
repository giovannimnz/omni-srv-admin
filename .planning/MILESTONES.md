# Milestone Branch Matrix

**Last updated:** 2026-07-06

This file is the shared milestone index for `main`, planning branches, and
cross-session resumes. It should answer three questions quickly:

1. Which milestone is the current operator focus?
2. Which milestones are already shipped?
3. Which phase artifacts are the canonical source for each milestone?

## Current Delivery Order

| Milestone | Phase span | Theme | Canonical artifacts | Status |
|---|---|---|---|---|
| v1.4 | 42 | Atius-wide SSO and Login | `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/` | In progress: 2/3 plans complete |
| v1.5 | 43 | Codex Runtime and MCP Bootstrap Reliability | `.planning/phases/43-codex-mcp-bootstrap-hardening/` | Shipped: 2/2 plans complete |
| v1.6 | 44 | Internal Service PKI and Fleet Trust | `.planning/phases/44-internal-service-pki-and-fleet-trust/` | In progress: 1/3 plans complete |

## Shipped Milestones

### v1.3 Local AI Embeddings and Semantic Retrieval

**Shipped:** 2026-07-04
**Canonical phase:** 41

**Delivered:**

- TEI backend on `horistic-srv` using `Alibaba-NLP/gte-multilingual-base`.
- Private router-facing endpoint `http://10.1.1.4:3115`.
- Public alias `embedding-gte-v1` via `https://router.atius.com.br/v1`.
- k3s runtime moved to namespace `ebeddings-local`.
- GBrain/Obsidian/Graphify migration contract documented.

**Guardrails:**

- No New API token or secret material in Git, `.planning`, Obsidian, GBrain,
  logs, or shell history.
- Router channel must point to the private TEI endpoint, never loop back to the
  public router URL.
- Any future model or dimension drift requires explicit reembed/reindex.

### v1.1 M005 Follow-ups

**Shipped:** 2026-06-24
**Canonical phases:** 15-17

**Delivered:**

- OCI snapshot workflow and runbook.
- Cloudflare Access client/runbook with gated live cutover.
- Observability/RWX docs, CLI, dashboards, and storage decision.

**Deferred live gates:**

- Real OCI restore drill still depends on `oci` CLI + API key on host.
- Cloudflare Access still depends on dashboard-side enablement.
- Observability live closeout still depends on production gate and alerting
  secrets.

### v1.0 Fleet Governance / Domain Foundation Base

**Shipped:** 2026-06-15
**Canonical phases:** 12-14

**Delivered:**

- Omni Fleet control-plane live implementation.
- K3s HA + Portainer base rollout.
- Resource governor / PM2 hardening / Jenkins K3s agent foundation.

## Historical Dependency Chain

| Milestone | Phase | Name | Canonical branch or surface | Status |
|---|---:|---|---|---|
| M004 | 12 | Omni Fleet Control Plane | `codex/omni-fleet-control-plane-m004` | Shipped |
| M005 | 13 | K3s HA Cluster + Portainer | `codex/k3s-portainer-oci-plan` | Shipped |
| M006 | 14 | SRV-1 Resource Governance + PM2 Hardening | `codex/phase14-resource-governor-14-01` | Shipped |
| M007 | 15-17 | M005 follow-ups | `main` + `.planning/phases/{15,16,17}-*/` | Shipped procedurally |
| M011 | 41 | Local AI Embeddings Gateway on `horistic-srv` | `.planning/phases/41-local-ai-embeddings-gateway-horistic-srv/` | Shipped |
| M012 | 42 | Atius-wide SSO Login | `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/` | In progress |
| M013 | 43 | Codex MCP Bootstrap Hardening | `.planning/phases/43-codex-mcp-bootstrap-hardening/` | Shipped |
| M014 | 44 | Internal Service PKI and Fleet Trust | `.planning/phases/44-internal-service-pki-and-fleet-trust/` | In progress |

## Separation Rules

- `main` carries the operator-facing roadmap, requirements, state, and current
  milestone index.
- Phase directories remain the canonical source for plan, summary, validation,
  and verification artifacts.
- A milestone is only "shipped" here when its roadmap status, requirements
  traceability, and phase summaries agree.
- Out-of-order shipping is allowed when operationally justified; Phase 43 is a
  valid example because the Windows Codex bootstrap was hardened before Phase 42
  edge publication closed.

## Current Operator Queue

1. Close Phase 42 with `42-03` and promote v1.4 to shipped.
2. Resume Phase 44 from `44-02` after explicit live mutation approval.
3. Keep v1.3 and v1.5 as reference milestones, not active focus.
