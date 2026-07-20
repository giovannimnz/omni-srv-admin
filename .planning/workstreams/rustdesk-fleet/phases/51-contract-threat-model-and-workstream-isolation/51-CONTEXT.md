# Phase 51: Contract, Threat Model and Workstream Isolation - Context

**Source:** PRD Express Path (`51-PRD.md`)

<domain>
## Phase Boundary

Produce only governance, security, scope, validation, and evidence-contract artifacts. Do not install software, hydrate secret values, modify host runtime, change DNS/firewalls, or decommission existing access tools in this phase.
</domain>

<decisions>
## Decisions

### Fleet and coexistence
- **D-01:** Include exactly `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, and `GIOVANNI-W11-PC`; WSL and `GIOVANNI-S23` are excluded from every mutation and evidence path. `[SCP-01]`
- **D-02:** RustGuac, XRDP, AnyDesk, NoMachine, and noVNC remain installed and independently usable; this milestone contains no decommission scope. `[SCP-01]`

### Product and transport boundary
- **D-03:** RustDesk Server OSS is acceptable only for a single operator after explicit acceptance of missing mandatory SSO/OIDC, RBAC, MFA, centralized API/device policy, and human-attributed audit; any mandatory control makes the decision `NO-GO` until Pro is selected. `[SCP-02]`
- **D-04:** Production policy is direct-first. Forced relay is allowed only for controlled validation and proven fallback and cannot be the default fleet setting. `[SCP-03]`

### Secrets, identity, and permissions
- **D-05:** Treat the server private key, distributed server public key, five distinct permanent target passwords, RustDesk client IDs, permission profiles, and recovery authority as separate assets. Only names and Vault paths may appear in versioned or documented artifacts.
- **D-06:** Define least-privilege `admin-maintenance` and `support-observe` permission profiles. Any OSS limitation preventing centralized enforcement is an explicit compensating-control risk, not a claimed capability.
- **D-07:** Evidence validators reject secret-looking values and command/process/screenshot leakage. No secret value may enter repo files, Markdown, logs, fixtures, Obsidian, GBrain, or evidence manifests.

### GSD isolation and proof
- **D-08:** Every RustDesk lifecycle command explicitly supplies `--ws rustdesk-fleet`; the active marker alone is not authority. Shared `PROJECT.md`, `MILESTONES.md`, and Graphify writers are serialized. `[SCP-05]`
- **D-09:** Capture a Phase 48 integrity baseline from `runtime-trust-codex-delivery-convergence` and verify it after each lifecycle transition. Any unexplained drift blocks advancement. `[SCP-05]`
- **D-10:** Requirement acceptance is evidence-addressed: every requirement maps to current machine-readable proof, and summary-only PASS text never closes a gate.

### the agent's Discretion
- Exact file names and implementation language for small validators, provided they follow existing repo patterns and run without heavy builds.
- Exact normalized schema for evidence manifests and permission tables, provided it is deterministic, redacted, and extensible through Phase 58.
</decisions>

<canonical_refs>
## Canonical References

### Project rules and workstream truth
- `AGENTS.md` — CPU, Vault, Graphify, multi-agent, writer-serialization, and documentation requirements.
- `.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md` — milestone requirements and traceability.
- `.planning/workstreams/rustdesk-fleet/ROADMAP.md` — phase goal, risks, success criteria, and advance gate.
- `.planning/workstreams/rustdesk-fleet/STATE.md` — active workstream state.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/` — preserved Phase 48 workstream whose integrity must be proved.

### RustDesk research
- `.planning/research/rustdesk-fleet/SUMMARY.md` — synthesized architecture and rollout gates.
- `.planning/research/rustdesk-fleet/FEATURES.md` — OSS/Pro and functional boundary.
- `.planning/research/rustdesk-fleet/ARCHITECTURE.md` — trust boundaries, direct/relay, evidence model, and rollout ordering.
- `.planning/research/rustdesk-fleet/PITFALLS.md` — concrete failure modes and verification requirements.
</canonical_refs>

<specifics>
## Specific Ideas

- Validators should make excluded-host and secret-leak failures easy to reproduce with fixtures.
- The ledger should reserve stable evidence IDs for all 36 requirements even though Phase 51 implements only the contract and skeleton.
- The Phase 48 baseline should use deterministic hashes/manifests over the authoritative preserved artifacts, excluding transient/generated noise explicitly.
</specifics>

<deferred>
## Deferred Ideas

- Runtime server placement and capacity gate: Phase 52.
- DNS, ports, server containers, client installs, live sessions, DR, rollback, and UAT: Phases 52-58.
- RustDesk Server Pro implementation: deferred unless D-03 returns `NO-GO` for OSS.
</deferred>

<scope_fence>
## Scope Fence

No package installation, service mutation, secret-value retrieval, network exposure, DNS change, client configuration, display-manager change, or legacy-tool removal is authorized by Phase 51.
</scope_fence>

---

*Phase: 51-contract-threat-model-and-workstream-isolation*
*Context gathered: 2026-07-19 via PRD Express Path*
