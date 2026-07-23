# Phase 28: G18 Ubuntu Pro/ESM Fleet Gates - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Mode:** Operator-approved milestone scope, no external research

<domain>
## Phase Boundary

Phase 28 prepares the G18 live operation but does not execute the live apt upgrade. It must consolidate Ubuntu Pro/ESM state for SRV-1, SRV-2 and SRV-3, verify token/account/attach status, inspect apt sources and ESM availability, and produce a per-host upgrade gate checklist with backup/snapshot/checkpoint requirements.

The next phase (29) is responsible for controlled apt upgrade execution, Microsoft RDP validation and Landscape SaaS validation after the Phase 28 gates are satisfied.

</domain>

<decisions>
## Implementation Decisions

### D-01 | Safety | No live apt upgrade in Phase 28
Phase 28 is read-only/prep by default. It may generate commands, scripts, manifests, and runbooks, but it must not run live `apt upgrade`, restart XRDP/RDP, restart PM2, or mutate Landscape enrollment without an explicit operator gate.

### D-02 | Scope | Fleet hosts
The required live hosts for G18 are SRV-1, SRV-2 and SRV-3. Any extra host discovered during inventory can be reported, but it is not required for Phase 28 completion.

### D-03 | Secrets | No token leakage
Ubuntu Pro token/account data, API keys, Cloudflare tokens, Landscape credentials and webhook secrets must not be copied into git, docs, logs, summaries or planning files. Store only paths, presence/absence, mode/owner, redacted IDs and verification outcomes.

### D-04 | Landscape | SaaS first
Landscape SaaS validation is part of G18. Self-hosted Landscape remains a later governance/fallback path and must not be deployed in Phase 28.

### D-05 | RDP | Preserve remote access
Any RDP/XRDP validation plan must preserve current working display/session setup and include rollback references. No restart is allowed in Phase 28.

### the agent's Discretion
The planner may choose whether Phase 28 is one or two plans, but it must keep read-only inventory separate from any gated upgrade preparation if that improves auditability.

</decisions>

<code_context>
## Existing Code Insights

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` records G18 operator next steps: authorize apt upgrade, validate Microsoft RDP post-upgrade on 3 SRVs, confirm Landscape SaaS UI with SRV-1/2/3 online.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` maps Phase 28 to requirements G18-01 and G18-02.
- Prior Phase 18 context contains XRDP/RDP display fixes and Ubuntu Pro/ESM rescope.
- Prior Phase 15 provides OCI snapshot workflow and runbook context.
- Prior Phase 17 provides observability/runbook context for post-upgrade checks.

</code_context>

<specifics>
## Specific Ideas

- Produce a redacted per-host G18 inventory table.
- Include preflight commands for `pro status`, apt sources, held packages, reboot-required state, disk space, service status, and Landscape agent state when present.
- Include backup/snapshot prerequisites before Phase 29 can mutate hosts.
- Include an explicit operator checkpoint format for Phase 29.
- Include acceptance criteria that prove no live mutation happened during Phase 28.

</specifics>

<deferred>
## Deferred Ideas

- Live apt upgrade execution is deferred to Phase 29.
- Microsoft RDP post-upgrade validation is deferred to Phase 29.
- Landscape SaaS online confirmation after mutation is deferred to Phase 29.
- Landscape self-hosted deployment is deferred to governance/fallback phases.

</deferred>
