# Phase 48: Codex OAuth and Wayland Remote ACP Convergence - Research

**Researched:** 2026-07-12
**Domain:** Native Codex OAuth, local/remote ACP lifecycle validation, and Wayland runtime convergence before Headroom
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Run Codex as user `ubuntu` with `CODEX_HOME=/home/ubuntu/.codex`.
- Require a renewable ChatGPT login; any upstream 401, 403 or invalidated token blocks completion.
- Do not reuse the Router's temporary access token as a permanent fallback.
- Require a real prompt response after login, not only ACP initialize/session-new.
- Publish the remote agent at `wss://codex-acp.atius.com.br/gateway`.
- Authenticate with a Bearer token sourced from Vault profile `codex-acp`; never persist secret values in docs, Git or logs.
- Route SRV-1 `10.11.1.11` to SRV-3 `10.13.1.13` over OCI/DRG.
- Keep `10.100.100.0/24` as reserve fallback only.
- Default Codex permission remains `danger-full-access`.
- Derive enabled Codex models account-aware from `codex debug models`; do not maintain a stale static picker.
- Keep Model, Effort, Speed and Advanced/Power in one menu.
- Keep only Codex and Hermes Agent as runtime agents; GSD entries remain slash/`$` commands.
- Validate local and remote prompt, approval, cancel, resume and reconnect with sanitized evidence.
- Phase 49 remains blocked until native OAuth and the complete ACP matrix pass. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

### the agent's Discretion
- Exact test decomposition, temporary worktree layout and sanitized evidence format may follow existing repo conventions. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
- Headroom canary and integration belong exclusively to Phase 49.
- Atius-wide SSO closeout remains Phase 50. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WAC-01 | Router Phase 32 e auditada em shell funcional sem sobrescrever mudancas concorrentes e possui testes deterministas para metadata, refresh, regenerate, probe e upstream auth. | Ownership and CPU-capped Router test slice are called out as remaining work; stale checkpoint claims are reconciled. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-02 | `token_invalidated`, `refresh_token_invalidated`, `invalid_api_key`, 401 e 403 upstream sao distintos da autenticacao interna do Router. | Human OAuth gate and renewable OAuth proof explicitly separate Router auth from upstream native Codex failures. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-03 | Credencial Codex nativa funciona antes de qualquer Headroom, com refresh/regeneration e health persistido sem tokens em logs/respostas. | Native OAuth is the primary blocker; proof requires real prompt completion and renewable login evidence. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-04 | Catalogo final de modelos e reasoning effort passa no Codex CLI e no Wayland sem expectativas antigas de GPT-5.6. | Model/config UI is already live; remaining work is proof reuse after native OAuth recovery, not UI reimplementation. [VERIFIED: user-provided verified facts] |
| WAC-05 | `codex-acp` local passa initialize, session/new, prompt, tool, approval, cancel, resume e shutdown. | Local lifecycle matrix defines the exact behaviors still needing end-to-end proof. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-06 | ACP remoto/ACPX/OpenClaw passa Upgrade auth, gateway auth, approvals e reconnect sem reduzir o contrato local. | Remote matrix keeps auth and lifecycle parity as mandatory after local passes. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-07 | Wayland preserva `Wayland -> codex-acp -> codex`, sem converter GSD skills em runtime agents. | Runtime chain and agent boundary remain fixed; only validation and OAuth repair remain. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
| WAC-08 | Ownership, backup, rollback e validacao live estao registrados antes de liberar Phase 49. | Security/rollback section and stop conditions keep Headroom blocked until evidence is complete. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- Builds, heavy tests, container builds, bundlers, and equivalent CPU-heavy work must stay at or below 20% of total host CPU, preferably through the repo guard/wrapper; if containment cannot be verified, stop before starting the build. [CITED: AGENTS.md]
- Secrets remain in HashiCorp Vault; document only Vault paths, profiles, variable names, and validation evidence, never secret values. [CITED: AGENTS.md]
- Codex MCP endpoints stay canonical and tokenized through Vault-backed `ATIUS_MCP_TOKEN`; no secret material belongs in Git, docs, logs, Obsidian, or GBrain. [CITED: AGENTS.md]
- Repo identity stays DRG-first with `10.11.1.11` as the primary private/DRG service path and `10.100.100.1` reserve fallback only. [CITED: AGENTS.md]

## Executive Summary

Phase 48 is no longer a feature-build phase for Wayland UI, model/config menus, fork-sync protection, or public WSS gateway publication. Those pieces are already implemented and live in the pinned Wayland and `codex-acp` forks, and the public authenticated gateway health is already green. [VERIFIED: user-provided verified facts]

The remaining Phase 48 scope is now narrower and stricter: recover native Codex OAuth for the `ubuntu` runtime, prove that the login is renewable, and then run the full lifecycle contract across local `codex-acp`, remote ACP gateway, and Wayland Chromium headless without introducing Headroom. A successful ACP initialize or `session/new` is not enough; the decisive gate is a real prompt completion without upstream `401 token_expired` or revoked refresh state. [VERIFIED: user-provided verified facts]

The implementation order must stay Router Phase 32 evidence reconciliation -> native Codex OAuth recovery/proof -> local ACP lifecycle proof -> remote ACP lifecycle proof -> Wayland lifecycle proof. Phase 49 Headroom remains blocked throughout. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md]

**Primary recommendation:** Treat Phase 48 as an auth-recovery-and-proof phase, not as a UI or gateway implementation phase. [VERIFIED: user-provided verified facts]

## Stale Assumptions

| Stale assertion | Corrected fact | Execution impact |
|-----------------|----------------|------------------|
| Phase 48 still needs Wayland menu/model/config implementation. | Model/config UI and related Wayland/codex-acp convergence work are already implemented and live. [VERIFIED: user-provided verified facts] | Do not reopen UI work; only reuse it during validation. |
| Phase 48 still needs public remote ACP gateway bring-up. | Public WSS gateway health is already passing. [VERIFIED: user-provided verified facts] | Remote scope is lifecycle/auth proof, not gateway publication. |
| GPT-5.6 catalog parity is still the central blocker. | Account-aware model/config behavior is already implemented; the real blocker is native OAuth prompt failure under revoked refresh state and upstream `401 token_expired`. [VERIFIED: user-provided verified facts] | Do not spend more time on catalog UI unless parity regresses after OAuth recovery. |
| Router Phase 32 OAuth and native Codex OAuth are the same gate. | Router Phase 32 OAuth is separate; native Codex prompt failure is the live blocker for this phase. [VERIFIED: user-provided verified facts] | Keep Phase 32 evidence reconciliation scoped to distinctions required by WAC-01/WAC-02; do not substitute Router token flow for native login. |
| Headroom can be used as a workaround if native OAuth remains unstable. | Headroom must remain blocked until all Phase 48 gates pass. [VERIFIED: user-provided verified facts] | Any attempt to proxy around native failure is out of scope and invalidates completion. |
| `10.100.100.0/24` is an acceptable active path for this phase. | DRG is canonical; `10.100.100.0/24` stays reserve only. [VERIFIED: user-provided verified facts] | Remote ACP and Wayland proof must cite DRG endpoints and reserve fallback only as rollback context. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Native Codex OAuth and renewable login proof | API / Backend | Frontend Server (SSR) | Upstream auth state and refresh validity are owned by the Codex runtime, not by Wayland UI. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |
| Local ACP lifecycle contract | API / Backend | Browser / Client | `codex-acp` owns initialize/prompt/tool/approval/cancel/resume/shutdown semantics; clients only exercise the contract. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Remote ACP gateway auth and reconnect | API / Backend | CDN / Static | OpenClaw gateway and WSS auth boundaries are server-side; the browser observes upgrade/reconnect behavior. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Wayland model/effort/runtime UX | Browser / Client | API / Backend | Wayland must preserve the `Wayland -> codex-acp -> codex` chain and reflect account-aware models already exposed upstream. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |
| DRG routing and reserve fallback discipline | Database / Storage | API / Backend | Inventory/roadmap canonize DRG/private addressing and treat reserve networking as fallback metadata, not active runtime selection. [CITED: AGENTS.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] |

## Standard Stack

### Core

| Component | Version / Pin | Purpose | Why Standard |
|-----------|----------------|---------|--------------|
| Wayland fork | `a6fd31aac` | Live Wayland surface with unified menu, account-aware startup cache, and remote ACP transport. | This is the pinned implementation already carrying the required UX/runtime behavior. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [VERIFIED: user-provided verified facts] |
| `codex-acp` fork | `9bfb36b` | ACP runtime exposing model, effort, service tier, Power, and agent-profile options. | This is the pinned ACP side already aligned with Wayland UI needs. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [VERIFIED: user-provided verified facts] |
| Native Codex runtime | `/home/ubuntu/.codex` under user `ubuntu` | Authoritative upstream auth and prompt execution path. | Phase completion is defined by native Codex success before any proxy layer. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |
| OpenClaw WSS gateway | `wss://codex-acp.atius.com.br/gateway` | Authenticated remote ACP transport. | This is the locked remote endpoint for gateway validation. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| Vault profile `codex-acp` | Supplies Bearer auth for remote ACP without persisting secrets. | Use for gateway auth and validation probes only. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [CITED: AGENTS.md] |
| Router Phase 32 evidence lane | Distinguishes Router-owned auth states from native Codex upstream auth states. | Use only to clear WAC-01/WAC-02 proof gaps. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-01-PLAN.md] [VERIFIED: user-provided verified facts] |
| CPU guard wrapper | Constrains focused Go verification to the project CPU budget. | Mandatory for Router deterministic tests and any heavy rebuild/test attempt. [CITED: AGENTS.md] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Model catalog parity | Static model picker or hard-coded GPT expectation tables | Account-aware `codex debug models` derived catalog already implemented in the pinned forks | Static catalogs go stale and are explicitly forbidden by the phase context. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |
| Secret distribution | `.env` copies, inline bearer tokens, or doc-embedded secrets | Vault profiles and variable-name-only evidence | AGENTS and validation both forbid token leakage. [CITED: AGENTS.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Phase bypass | Headroom proxy workaround for native auth failure | Native Codex OAuth recovery first, Headroom only in Phase 49 | The roadmap and context explicitly block Headroom until Phase 48 passes. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md] [VERIFIED: user-provided verified facts] |

**Key insight:** The remaining risk is not missing code surface; it is false-positive validation that proves session setup while native prompt execution is still broken. [VERIFIED: user-provided verified facts]

## Exact Remaining Execution Slices

1. **Slice A - Reconcile Router Phase 32 evidence without conflating auth domains**
   - Goal: Clear WAC-01/WAC-02 by updating stale Router-owned evidence so it reflects the distinction between Router internal auth states and native Codex upstream failures. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md] [VERIFIED: user-provided verified facts]
   - Output: Sanitized evidence set for metadata, refresh, regenerate, probe, and upstream auth classification.
   - Stop condition: Any attempt to treat Router access-token flow as permanent native fallback fails the slice. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

2. **Slice B - Human native OAuth recovery on the real `ubuntu` Codex home**
   - Goal: Replace the revoked native refresh state with a renewable ChatGPT login for `/home/ubuntu/.codex`, then prove a real prompt response. [VERIFIED: user-provided verified facts]
   - Output: Sanitized proof that upstream prompt execution succeeds without `401 token_expired`.
   - Stop condition: ACP initialize/session success without prompt completion does not count. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

3. **Slice C - Local `codex-acp` lifecycle proof**
   - Goal: Run initialize, `session/new`, prompt, tool, approval, cancel, resume, and shutdown locally against the recovered native runtime. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
   - Output: Sanitized transcript proving the full local contract.
   - Stop condition: Any local step that succeeds only because auth degradation or cached stale session is reused fails the slice. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]

4. **Slice D - Remote ACP gateway lifecycle proof**
   - Goal: Repeat the local contract through authenticated WSS upgrade, gateway auth, approval flow, reconnect, and clean error propagation. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
   - Output: Upgrade/auth/reconnect evidence over the live public gateway.
   - Stop condition: Remote parity that weakens auth or approval semantics fails the slice. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]

5. **Slice E - Wayland Chromium headless lifecycle proof**
   - Goal: Prove model selection, effort, streaming, approval, cancel/resume, and reconnect through the shipped Wayland UI without changing runtime-agent boundaries. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
   - Output: Headless browser console/network snapshot plus lifecycle evidence.
   - Stop condition: Any fix that introduces Headroom, changes agent inventory, or bypasses `Wayland -> codex-acp -> codex` fails the slice. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

## Human OAuth Gate

Phase 48 contains one explicit human gate: the native Codex login for user `ubuntu` must be renewed in the real runtime home and must produce a real upstream prompt response. The checkpoint and verified facts agree that the live blocker is revoked refresh state with upstream `401 token_expired`, not missing Wayland or gateway code. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md] [VERIFIED: user-provided verified facts]

**Human gate definition**

| Gate | Why human | Required evidence |
|------|-----------|-------------------|
| Renewable ChatGPT login as `ubuntu` using `/home/ubuntu/.codex` | The login must be real, renewable, and cannot be substituted by Router temporary access tokens. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] | Sanitized proof of successful login plus prompt completion, with no token material. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Prompt proof after login | Session initialization alone is explicitly insufficient. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] | Successful real prompt response from native Codex. [VERIFIED: user-provided verified facts] |
| Re-run after refresh boundary | The phase requires renewable, not one-shot, auth. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] | Second sanitized prompt success after refresh/restart boundary. |

## Renewable OAuth Proof

WAC-03 should be considered complete only when all of the following are true:

| Proof item | Pass condition | Failure condition |
|-----------|----------------|------------------|
| Native prompt after login | Real prompt completes successfully in native Codex running as `ubuntu`. [VERIFIED: user-provided verified facts] | Upstream `401`, `403`, `token_invalidated`, or `refresh_token_invalidated`. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Prompt after refresh or restart boundary | A second prompt succeeds after the credential is exercised across a fresh process/session boundary. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] | Success depends on a stale cached session that cannot renew. |
| Sanitized health persistence | Evidence records success/failure classification without persisting token material in logs or docs. [CITED: AGENTS.md] | Any token, refresh secret, or raw auth payload appears in artifacts. |
| Separation from Router OAuth | Native proof stands on its own and does not depend on Router temporary access token reuse. [VERIFIED: user-provided verified facts] | Native proof is inferred only from Router evidence. |

## Local/Remote Lifecycle Test Matrix

| Behavior | Local `codex-acp` | Remote gateway | Wayland headless | Required proof |
|----------|-------------------|----------------|------------------|----------------|
| Initialize | Must pass against recovered native Codex. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must pass through authenticated gateway. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must surface a healthy ready state in UI. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Sanitized protocol transcript. |
| `session/new` | Must create session locally. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must create session remotely after WSS auth. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must map to a visible Wayland conversation/session. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Transcript plus UI/network snapshot. |
| Prompt | Must complete a real prompt, not only open session state. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] | Must complete a real prompt through gateway. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must stream/show prompt completion in Chromium headless. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Successful completion evidence. |
| Approval | Must preserve approval semantics locally. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must preserve approval semantics remotely without weakening controls. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must show approval UX and action path. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Approval request/response trace. |
| Cancel | Must cancel an active turn cleanly. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must cancel remotely with clean propagation. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must expose cancel behavior in UI. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Turn-cancel trace. |
| Resume | Must resume after cancel/interruption locally. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must resume through gateway without auth drift. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Must resume in UI without session corruption. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Resume transcript. |
| Reconnect | Local process restart must reconnect cleanly to valid auth/session state. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | WSS reconnect must preserve auth and session semantics. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Browser reconnect must recover the same contract. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Reconnect transcript plus browser network evidence. |
| Shutdown | Local shutdown must be clean and repeatable. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Remote path must close cleanly after lifecycle completion. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | UI must survive clean shutdown/reload cycle. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | Final cleanup evidence. |

## Common Pitfalls

### Pitfall 1: Mistaking session setup for end-to-end success
**What goes wrong:** Initialize or `session/new` passes, but the first real prompt still fails upstream. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [VERIFIED: user-provided verified facts]
**Why it happens:** Cached or partial auth state masks revoked refresh credentials until a real model turn begins. [VERIFIED: user-provided verified facts]
**How to avoid:** Require prompt completion in every lifecycle lane before marking success. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
**Warning signs:** Upstream `401 token_expired`, repeated unauthorized turn failures, or success that disappears after restart. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md] [VERIFIED: user-provided verified facts]

### Pitfall 2: Using Router OAuth evidence as proof of native Codex health
**What goes wrong:** Router Phase 32 progress is treated as if native Codex OAuth were fixed. [VERIFIED: user-provided verified facts]
**Why it happens:** Both lanes touch auth terminology, but the phase context explicitly separates them. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]
**How to avoid:** Keep WAC-01/WAC-02 as evidence-reconciliation slices and require independent native prompt proof for WAC-03. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md]
**Warning signs:** Any plan step that proposes Router temporary token reuse as permanent native fallback. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

### Pitfall 3: Reopening already-shipped UI/gateway work
**What goes wrong:** Time is spent re-implementing menus, model selectors, or public gateway health that are already live. [VERIFIED: user-provided verified facts]
**Why it happens:** Older checkpoint language can look like missing implementation instead of missing proof. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md]
**How to avoid:** Limit execution to auth recovery, lifecycle parity, and evidence. [VERIFIED: user-provided verified facts]
**Warning signs:** Any new task that starts with UI redesign, WSS publication, or Headroom enablement. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md]

## Security and Rollback

### Security

- Native and remote auth evidence must stay sanitized; no access token, refresh token, or bearer secret can appear in repo artifacts, logs, or validation notes. [CITED: AGENTS.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
- Remote ACP must keep Bearer auth sourced from Vault profile `codex-acp`; secret handling remains Vault-only. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] [CITED: AGENTS.md]
- DRG/private routing is canonical for runtime proof; reserve networking belongs only to fallback/rollback discussion. [VERIFIED: user-provided verified facts]
- CPU-capped wrappers are mandatory for any focused Go verification or rebuild attempt. [CITED: AGENTS.md]

### Rollback

- Restore the last known-good Router/Wayland service artifacts from verified backups if a new validation attempt damages the live path. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
- Disable only the new remote ACP path if necessary; preserve native `codex-acp` and repeat the native smoke first. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
- Do not introduce Headroom or reserve-path routing as rollback substitutes for unresolved native auth failure. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md] [VERIFIED: user-provided verified facts]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Mixed proof harness: focused Router deterministic tests under CPU cap, native Codex smoke, ACP protocol transcripts, and Chromium headless smoke. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md] |
| Config file | `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| Quick run command | `./scripts/podman-admin.sh verify-profile && ./scripts/podman-admin.sh profile-run -- /usr/local/go/bin/go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/codex ./service ./relay -count=1` from `/home/ubuntu/GitHub/containers/router-ai-atius` on `atius-srv-1`. Live `verify-profile` proved `cpu.max=80000 100000` and `profile-run -- /usr/local/go/bin/go version` passed on 2026-07-12. |
| Full suite command | `TBD in execution: Phase 48 completion requires the full local + remote + Wayland lifecycle matrix, not a single suite command.` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WAC-01 | Router Phase 32 audit and deterministic shell/test evidence | focused deterministic + manual evidence | `./scripts/podman-admin.sh verify-profile && ./scripts/podman-admin.sh profile-run -- /usr/local/go/bin/go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/codex ./service ./relay -count=1` | ✅ |
| WAC-02 | Distinguish upstream auth failures from Router internal auth | live auth classification | `TBD - sanitized metadata/refresh/regenerate/probe sequence` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | ✅ |
| WAC-03 | Native renewable Codex OAuth | live prompt smoke | `TBD - native Codex prompt proof after login and after restart boundary` [VERIFIED: user-provided verified facts] | ✅ |
| WAC-04 | Model/effort parity in Codex CLI and Wayland | live smoke | `TBD - reuse shipped UI/runtime after OAuth recovery` [VERIFIED: user-provided verified facts] | ✅ |
| WAC-05 | Local ACP lifecycle | protocol lifecycle | `TBD - local initialize/session/prompt/tool/approval/cancel/resume/shutdown` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | ✅ |
| WAC-06 | Remote ACP lifecycle and reconnect | protocol lifecycle | `TBD - remote authenticated upgrade/auth/approval/reconnect` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | ✅ |
| WAC-07 | Wayland runtime chain preservation | headless browser smoke | `TBD - Chromium headless lifecycle pass` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] | ✅ |
| WAC-08 | Ownership, backup, rollback, live validation registration | evidence closeout | `TBD - finalize ownership/backup/rollback record before Phase 49` [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] | ✅ |

### Sampling Rate

- **Per task commit:** rerun the narrow slice that was changed, with CPU-capped Router verification if Router code or wrappers moved. [CITED: AGENTS.md] [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md]
- **Per wave merge:** rerun the full lifecycle proof for that lane: native, then local ACP, then remote ACP, then Wayland. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md]
- **Phase gate:** full local/remote/Wayland lifecycle green with sanitized evidence before Phase 49 is unblocked. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

### Wave 0 Gaps

- [x] Router deterministic command path resolved live on `atius-srv-1`: run `verify-profile` first, then invoke the focused Go suite directly through `profile-run`; do not nest it inside another resource-governor wrapper. The profile reported `cpu.max=80000 100000` on the 4-vCPU host.
- [ ] Native renewable OAuth proof artifact must be produced after human login recovery. [VERIFIED: user-provided verified facts]
- [ ] The single sanitized lifecycle evidence bundle format should be chosen before execution starts, per context discretion. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Renewable native Codex OAuth with distinct failure classification and no Router-token substitution. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md] [VERIFIED: user-provided verified facts] |
| V3 Session Management | yes | Reconnect/resume proof across local, remote, and Wayland lanes. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| V4 Access Control | yes | Bearer-gated remote ACP approvals must not be weakened relative to local ACP. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| V5 Input Validation | yes | Sanitized evidence and explicit auth-state classification prevent false proof and token leakage. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] [CITED: AGENTS.md] |
| V6 Cryptography | yes | Vault-backed secret handling and no secret persistence in repo/docs/logs. [CITED: AGENTS.md] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reusing temporary Router access token as native fallback | Spoofing | Explicitly forbidden by phase decisions; require real native login proof. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md] |
| Token leakage in validation artifacts | Information Disclosure | Sanitize all evidence and document only Vault paths/profile names. [CITED: AGENTS.md] |
| Remote gateway parity achieved by weakening approvals | Elevation of Privilege | Remote lane must preserve local approval semantics exactly. [CITED: .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md] |
| False-positive success from cached session state | Repudiation | Require prompt proof and restart-boundary renewable proof. [VERIFIED: user-provided verified facts] |

## Resolved Questions

1. **Final Router deterministic test invocation under the CPU wrapper**
   - On `atius-srv-1`, from `/home/ubuntu/GitHub/containers/router-ai-atius`, run `./scripts/podman-admin.sh verify-profile` and require `cpu.max=80000 100000` plus `profile limits OK`.
   - Then run `./scripts/podman-admin.sh profile-run -- /usr/local/go/bin/go test ./common ./controller ./service/modelcatalog ./relay/common ./relay/channel/codex ./service ./relay -count=1`.
   - Do not wrap `profile-run` inside `omni srv1-ops resources run builds`; the nested wrapper was the stale path associated with CGO/cache loss.

## Sources

### Primary
- User-provided verified facts - live status corrections for Wayland commit, `codex-acp` commit, WSS gateway health, model/config UI, fork-sync, native OAuth blocker, Router Phase 32 separation, DRG canon, Vault-only secrets, and CPU cap.

### Secondary
- `AGENTS.md` - project CPU, Vault, and DRG constraints.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` - WAC requirement contracts and milestone boundaries.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` - current phase ordering and Headroom block.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-CONTEXT.md` - locked decisions and phase stop conditions.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-01-PLAN.md` - execution intent and ownership/test lanes.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-EXECUTION-CHECKPOINT-2026-07-12.md` - stale assertions to reconcile and current test executor blocker.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md` - lifecycle proof contract, rollback, and completion evidence.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - pinned commits and endpoints are documented and partially reinforced by verified facts, but not re-validated live in this run.
- Architecture: HIGH - responsibility split and phase ordering are explicit in context, requirements, roadmap, and verified facts.
- Pitfalls: HIGH - the remaining auth/proof traps are directly stated by the verified facts and the phase validation contract.

**Research date:** 2026-07-12
**Valid until:** 2026-07-19
