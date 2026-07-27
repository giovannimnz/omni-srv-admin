# Milestone Branch Matrix

**Last updated:** 2026-07-27

This file is the shared milestone index for `main`, planning branches, and
cross-session resumes. It should answer three questions quickly:

1. Which milestone is the current operator focus?
2. Which milestones are already shipped?
3. Which phase artifacts are the canonical source for each milestone?

## Current Delivery Order

| Milestone | Phase span | Theme | Canonical artifacts | Status |
|---|---|---|---|---|
| v1.9 | 51-58 | RustDesk Fleet Remote Access | `.planning/workstreams/rustdesk-fleet/` | Current parallel workstream: requirements/roadmap initialization |
| v1.8 | 46-50 | Runtime Trust and Codex Delivery Convergence | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/{46,47,48,49,50}-*/` | Current parallel workstream: Phases 46-47 complete; Phase 48 executing |
| Network lane | 54 | Horistic OCI/DRG readdress and BE3/WireGuard renumbering | `.planning/workstreams/network-horistic-readdress/` | Executing from preserved preflight; live migration remains gated |
| Local AI lane | 59 | Qwen3 embedding/rerank canary | `.planning/workstreams/qwen-local-ai/` | Planned; GTE remains titular |
| GBrain reliability lane | 60-65 | GBrain HTTP MCP recovery and hardening | `.planning/workstreams/gbrain-mcp-reliability/` | Fully planned; Phase 60 recovery foundation is next; all live changes remain gated |
| v1.7 | 45 | Internal DNS and DRG Canonicalization | `.planning/phases/45-internal-dns-drg-canonicalization/` | Shipped 2026-07-10 |
| v1.6 carry-over | 47 | Internal Service PKI listener/trust closeout | `.planning/phases/47-internal-service-pki-closeout/` | Shipped 2026-07-12 |
| Codex/Wayland lane | 48-49 | OAuth/ACP convergence then Headroom | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/{48,49}-*/` | Phase 48 executing; Phase 49 blocked until full Phase 48 validation |
| v1.4 carry-over | 50 | Atius-wide SSO publication closeout | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/50-atius-wide-sso-closeout/` | Queued after Phase 49; continues delivered 42-01/42-02 |

## Shipped Milestones

### v1.3 Local AI Embeddings and Semantic Retrieval

**Shipped:** 2026-07-04
**Canonical phase:** 41

**Delivered:**

- TEI backend on `horistic-srv` using `Alibaba-NLP/gte-multilingual-base`.
- Private router-facing endpoint `http://10.21.1.21:3115`, with `10.100.100.4:3115` reserve-only.
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
| M012 | 42 | Atius-wide SSO Login | `.planning/phases/42-atius-wide-sso-login-on-sso-atius-com-br/` | Historical partial; continues in Phase 50 |
| M013 | 43 | Codex MCP Bootstrap Hardening | `.planning/phases/43-codex-mcp-bootstrap-hardening/` | Shipped |
| M014 | 44 | Internal Service PKI and Fleet Trust | `.planning/phases/44-internal-service-pki-and-fleet-trust/` | Historical partial; continues in Phase 47 |
| M015 | 45 | Internal DNS and DRG Canonicalization | `.planning/phases/45-internal-dns-drg-canonicalization/` | Shipped 2026-07-10 |
| M016 | 46-50 + 47.1 | Runtime Trust and Codex Delivery Convergence | `.planning/workstreams/runtime-trust-codex-delivery-convergence/` | Current |

## Separation Rules

- `main` carries the shared project/milestone index; roadmap, requirements,
  state and phases are namespaced under `.planning/workstreams/<name>/`.
- Phase directories remain the canonical source for plan, summary, validation,
  and verification artifacts.
- A milestone is only "shipped" here when its roadmap status, requirements
  traceability, and phase summaries agree.
- Out-of-order shipping is allowed when operationally justified; Phase 43 is a
  valid example because the Windows Codex bootstrap was hardened before Phase 42
  edge publication closed.

## Current Operator Queue

1. Continue Phase 48: close Router evidence plus native/local/remote ACP validation without Headroom.
2. Execute Phase 49 only after every Phase 48 stop condition is green: isolated Headroom canary, ACP/Wayland promotion and rollback rehearsal.
3. Execute Phase 50 after Phase 49: close the remaining SSO publication/logout/RBAC gate using completed 42-01/42-02 evidence.
4. Execute RustDesk Phases 51-58 only through `rustdesk-fleet`; runtime changes on srv-1/srv-3 remain serialized against Phase 48 gates.
5. Continue the reenumerated network Phase 54 only through `network-horistic-readdress`, preserving the legacy Phase 52 receipts and their approval/hash scope.
6. Execute Qwen Phase 59 only through `qwen-local-ai`, after the authoritative network inventory is stable; GTE remains titular until every canary gate passes.
7. Execute GBrain Phases 60-65 only through `gbrain-mcp-reliability`; Phase 60 backup/restore PASS is prerequisite to every corpus, embedding, schema or PostgreSQL mutation.
