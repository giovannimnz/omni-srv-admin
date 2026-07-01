# Phase 29: G18 Controlled Upgrade, RDP and Landscape SaaS Validation - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning
**Mode:** Derived from Phase 28 handoff; live mutation requires explicit operator gate

<domain>
## Phase Boundary

Phase 29 owns the controlled G18 live execution path: apt upgrade ESM Apps/infra, Microsoft RDP/XRDP validation on SRV-1/SRV-2/SRV-3/horistic-srv, Landscape SaaS online confirmation, and regression watchdog validation.

Phase 29 must consume Phase 28 outputs:
- `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md`
- `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md`
- `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md`
- `docs/operations/g18-ubuntu-pro-esm-inventory.md`
- `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md`

</domain>

<decisions>
## Implementation Decisions

### D-01 | Gate | Live upgrade is checkpointed
No live `apt upgrade`, `apt full-upgrade`, package install/remove/autoremove, or host mutation may run unless the plan creates a clear checkpoint and the operator explicitly approves the command set.

### D-02 | Host order | Per-host staged execution
Upgrade validation should be staged per host instead of fleet-wide blind execution. If the executor reaches a live mutation step, it must stop at a checkpoint before applying.

### D-03 | RDP | Remote access first-class
RDP/XRDP must be validated after upgrade, but restarts and session cleanup are not automatic. The plan must include rollback references from Phase 18 and require explicit gate before any RDP service restart.

### D-04 | Landscape | SaaS online validation
Landscape SaaS validation should confirm SRV-1/SRV-2/SRV-3/horistic-srv online if prerequisites are met. If Landscape registration is absent, the plan should document blocker/remediation, not silently mutate enrollment.

### D-05 | Regression | No destructive automated repair
Post-upgrade watchdog/regression checks should validate apt, ESM, RDP, Landscape, PM2, K3s, Apache edges and observability. It must not repair PM2, restart XRDP, or POST to trading/Telegram webhooks automatically.

### the agent's Discretion
The planner may split Phase 29 into gated pre-apply, live-apply checkpoint, post-upgrade validation, and blocker-remediation plans. The executor must be able to stop cleanly at operator checkpoints.

</decisions>

<code_context>
## Existing Code Insights

- Phase 28 found blockers for Phase 29: Ubuntu Pro token file absent in approved paths on the 4 servidores, Landscape registration check returned `no` on all 3, disk warning on SRV-1/SRV-2, and `pm2-ubuntu` absent/inactive on SRV-3.
- Phase 28 did not run live apt mutation and produced gate/runbook/handoff artifacts.
- Phase 18 contains RDP/XRDP display/session history and rollback considerations.
- Phase 15 OCI snapshots can provide rollback context for risky operations.
- Phase 17 observability can provide post-upgrade regression signals.

</code_context>

<specifics>
## Specific Ideas

- First plan should reconcile Phase 28 blockers and produce exact go/no-go matrix per host.
- Any live mutation plan must stop at checkpoint with command list, host order, expected downtime, rollback, and validation steps.
- Post-upgrade validation should include Microsoft RDP, Landscape SaaS, apt/pro status, reboot-required, PM2, K3s, Apache edges, disk, and observability smoke.
- If token/Landscape prerequisites remain absent, Phase 29 can produce a human-needed verification or blocker rather than forcing execution.

</specifics>

<deferred>
## Deferred Ideas

- Landscape self-hosted deployment is deferred to governance phases.
- Production Guard repair is deferred to Production Guard phases.
- Domain Infrastructure changes are deferred to Domain Infrastructure phases.

</deferred>

## Scope addendum - 2026-06-24

- `horistic-srv` is now part of the managed G18 fleet, making the current target 4 hosts: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`.
- The prior Phase 28 verification remains historical for the original 3-host scope. Phase 29 fresh inventory/go-no-go must supersede it before any live mutation.
- Landscape web/SaaS is the temporary onboarding and validation plane. Landscape self-hosted must stay in the v1.2 governance path for durable ownership.
