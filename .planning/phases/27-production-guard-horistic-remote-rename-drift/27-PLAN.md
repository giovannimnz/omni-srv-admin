---
phase: 27
plan: 00
type: index
wave: 0
depends_on:
  - 26
files_modified: []
autonomous: false
padded: 27
slug: production-guard-horistic-remote-rename-drift
name: Production Guard Horistic Remote + Rename Drift
date: 2026-06-24
status: ready
plans: 1
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
requirements:
  - PRG-08
  - PRG-09
  - PRG-10
  - PRG-11
must_haves:
  truths:
    - "Horistic Apache e remoto no horistic-srv."
    - "Remote checks sao read-only."
    - "Rename detector nao renomeia nem cria symlink automaticamente."
    - "Webhook/trading checks usam GET/HEAD; POST real e proibido por default."
    - "Horistic scalp split e Circuit Breaker suppression sao contratos externos."
  artifacts:
    - path: "modules/srv1-ops/configs/production-guard.yaml"
      provides: "Remote Apache, endpoint method and rename drift baseline."
    - path: "modules/srv1-ops/scripts/production_guard.py"
      provides: "Remote Apache checker, rename drift detector and webhook-safe validator."
    - path: "docs/operations/production-guard.md"
      provides: "Horistic remote Apache, rename drift and webhook safety runbook."
---

# Phase 27: Production Guard Horistic Remote + Rename Drift

<objective>
Completar o guard com validacao remota Horistic, detector de rename drift e
webhook-safe validation.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/phases/27-production-guard-horistic-remote-rename-drift/27-CONTEXT.md
@.planning/phases/27-production-guard-horistic-remote-rename-drift/27-RESEARCH.md
@.planning/phases/27-production-guard-horistic-remote-rename-drift/27-VALIDATION.md
@.planning/phases/26-production-guard-boot-login-protocol/26-SUMMARY.md
@docs/operations/production-guard.md
@inventory/hosts/horistic-srv.yaml
</context>

## Execution Envelope

| Field | Value |
|---|---|
| Target executor | `gpt-5.3-codex-spark` |
| Context target | 75k-95k tokens |
| Plans | 1 |
| Live mutation | Forbidden by default; remote checks read-only |
| Final gate | `$gsd-verify-work 27` after automated validation |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `27-01` | Remote Horistic Apache checks, rename drift detector and webhook-safe validation | PRG-08, PRG-09, PRG-10, PRG-11 | 1 | yes, read-only |

<tasks>

<task type="auto">
  <name>Task 1: Execute Phase 27 remote/rename/webhook plan</name>
  <files>.planning/phases/27-production-guard-horistic-remote-rename-drift/27-01-PLAN.md</files>
  <action>Execute read-only remote Apache checks, rename drift detector and webhook-safe validation after Phase 26 is complete. Do not mutate Apache, rename folders or send POST to trading/Telegram routes.</action>
  <verify>
    <automated>node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure .planning/phases/27-production-guard-horistic-remote-rename-drift/27-01-PLAN.md</automated>
  </verify>
  <done>Child plan parses and remote/webhook checks remain read-only.</done>
</task>

</tasks>

<verification>
Run the ordered battery in `27-VALIDATION.md`, then run:

- `$gsd-verify-work 27`
</verification>

<success_criteria>
Phase 27 is complete when Horistic remote proxy health, rename drift and
webhook-safe validation are visible in `production-guard` without remote
mutation, folder renames or live POST side effects.
</success_criteria>

<output>
Create `.planning/phases/27-production-guard-horistic-remote-rename-drift/27-SUMMARY.md`
when `27-01` completes and `$gsd-verify-work 27` passes.
</output>
