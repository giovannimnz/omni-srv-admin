# Phase 48: Codex OAuth and Wayland Remote ACP Convergence - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Make native Codex OAuth, account-aware model discovery, local codex-acp and
authenticated remote ACP reliable in Wayland before any Headroom proxy is
introduced. The phase ends only with real prompt completion and lifecycle
proof; session initialization alone is insufficient.

</domain>

<decisions>
## Implementation Decisions

### Native Codex OAuth
- Run Codex as user `ubuntu` with `CODEX_HOME=/home/ubuntu/.codex`.
- Require a renewable ChatGPT login; any upstream 401, 403 or invalidated token blocks completion.
- Do not reuse the Router's temporary access token as a permanent fallback.
- Require a real prompt response after login, not only ACP initialize/session-new.

### Remote ACP
- Publish the remote agent at `wss://codex-acp.atius.com.br/gateway`.
- Authenticate with a Bearer token sourced from Vault profile `codex-acp`; never persist secret values in docs, Git or logs.
- Route SRV-1 `10.11.1.11` to SRV-3 `10.13.1.13` over OCI/DRG.
- Keep `10.100.100.0/24` as reserve fallback only.
- Default Codex permission remains `danger-full-access`.

### Catalog, UI and Validation
- Derive enabled Codex models account-aware from `codex debug models`; do not maintain a stale static picker.
- Keep Model, Effort, Speed and Advanced/Power in one menu.
- Keep only Codex and Hermes Agent as runtime agents; GSD entries remain slash/`$` commands.
- Validate local and remote prompt, approval, cancel, resume and reconnect with sanitized evidence.
- Phase 49 remains blocked until native OAuth and the complete ACP matrix pass.

### the agent's Discretion
- Exact test decomposition, temporary worktree layout and sanitized evidence format may follow existing repo conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Wayland fork commit `a6fd31aac` contains the unified menu, account-aware startup cache and remote ACP transport.
- codex-acp fork commit `9bfb36b` exposes model, reasoning effort, service tier, Power and agent-profile options.
- OpenClaw Gateway is active on SRV-3 and the public authenticated health call returns `ok=true`.
- Omni fork-sync `origin/main` protects both forks and passes dry-run with no stale or unprotected conflicts.

### Established Patterns
- Heavy validation and builds run under the global 20 percent host CPU cap.
- Secrets are referenced only by Vault profile/path and variable name.
- OCI/DRG addresses are canonical; wg100 is never selected while DRG works.
- Dirty concurrent worktrees are preserved and reconciled through isolated worktrees.

### Integration Points
- Wayland runtime: `/home/ubuntu/GitHub/wayland`, system units `wayland.service` and `wayland-https-proxy.service`.
- Codex ACP runtime: `/home/ubuntu/GitHub/codex-acp` and `/home/ubuntu/.local/bin/codex-acp-atius`.
- Remote gateway: `openclaw-codex-acp.service` and the public WSS domain.
- Router Phase 32 remains an external OAuth dependency and must not be conflated with native Codex login.

</code_context>

<specifics>
## Specific Ideas

Match the Codex desktop interaction model while keeping the Wayland surface
compact. Treat a visible `Internal error` caused by revoked refresh credentials
as failed end-to-end validation even when ACP capabilities and model options
load successfully.

</specifics>

<deferred>
## Deferred Ideas

- Headroom canary and integration belong exclusively to Phase 49.
- Atius-wide SSO closeout remains Phase 50.

</deferred>
