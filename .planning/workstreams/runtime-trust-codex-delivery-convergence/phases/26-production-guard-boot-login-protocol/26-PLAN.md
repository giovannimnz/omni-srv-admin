---
phase: 26
plan: 00
type: index
wave: 0
depends_on:
  - 25
files_modified: []
autonomous: false
padded: 26
slug: production-guard-boot-login-protocol
name: Production Guard Boot/Login Protocol
date: 2026-06-24
status: ready
plans: 1
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
requirements:
  - PRG-07
  - PRG-10
must_haves:
  truths:
    - "Boot/login checks sao read-only por default."
    - "Live install de units/timers exige gate."
    - "RDP/XRDP nao pode ser reiniciado."
    - "Repair automatico so usa politicas da Phase 25."
    - "Auditoria sem secrets e obrigatoria."
  artifacts:
    - path: "modules/srv1-ops/systemd/production-guard.service"
      provides: "read-only boot verification unit."
    - path: "modules/srv1-ops/systemd/production-guard.timer"
      provides: "scheduled verification timer."
    - path: "modules/srv1-ops/systemd/production-guard-login.service"
      provides: "login/session verification unit or template."
    - path: "docs/operations/production-guard.md"
      provides: "boot/login protocol runbook."
---

# Phase 26: Production Guard Boot/Login Protocol

<objective>
Versionar o protocolo de verificacao no reboot e no inicio de login/session.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-CONTEXT.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-RESEARCH.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-VALIDATION.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-SUMMARY.md
@docs/operations/production-guard.md
</context>

## Execution Envelope

| Field | Value |
|---|---|
| Target executor | `gpt-5.3-codex-spark` |
| Context target | 75k-95k tokens |
| Plans | 1 |
| Live mutation | Unit/timer install gated; default is repo-only validation |
| Final gate | `$gsd-verify-work 26` after automated validation |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `26-01` | Boot/login read-only verification units and runbook | PRG-07, PRG-10 | 1 | no, live install gate |

<tasks>

<task type="auto">
  <name>Task 1: Execute Phase 26 boot/login plan</name>
  <files>.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-01-PLAN.md</files>
  <action>Execute the repo-side boot/login plan after Phase 25 is complete. Validate units and docs, but do not enable/install live units without the explicit live gate.</action>
  <verify>
    <automated>node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-01-PLAN.md</automated>
  </verify>
  <done>Child plan parses and live install remains gated.</done>
</task>

</tasks>

<verification>
Run the ordered battery in `26-VALIDATION.md`, then run:

- `$gsd-verify-work 26`
</verification>

<success_criteria>
Phase 26 is complete when boot/login verification is versioned, systemd-verified,
documented, read-only by default and safe for RDP/XRDP.
</success_criteria>

<output>
Create `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-SUMMARY.md`
when `26-01` completes and `$gsd-verify-work 26` passes.
</output>
