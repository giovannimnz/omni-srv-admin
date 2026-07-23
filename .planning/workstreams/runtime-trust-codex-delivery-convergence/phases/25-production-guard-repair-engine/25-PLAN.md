---
phase: 25
plan: 00
type: index
wave: 0
depends_on:
  - 24
files_modified: []
autonomous: false
padded: 25
slug: production-guard-repair-engine
name: Production Guard Repair Engine
date: 2026-06-24
status: ready
plans: 1
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
requirements:
  - PRG-06
  - PRG-10
must_haves:
  truths:
    - "Repair depende do status/doctor read-only da Phase 24."
    - "Dry-run e default; apply exige checkpoint e escopo explicito."
    - "Snapshot vem antes de qualquer apply."
    - "pm2 kill, RDP/XRDP restart, Apache mutation e webhook POST sao proibidos."
    - "Auditoria machine-readable e resumo PT-BR sao obrigatorios."
  artifacts:
    - path: "modules/srv1-ops/scripts/production_guard.py"
      provides: "repair planner/apply checkpoint."
    - path: "cli/omni/tests/test_srv1_production_guard.py"
      provides: "tests de dry-run, allowlist, forbidden commands, audit redaction."
    - path: "docs/operations/production-guard.md"
      provides: "runbook de repair e rollback."
---

# Phase 25: Production Guard Repair Engine

<objective>
Adicionar repair seguro e auditavel ao `production-guard`.

Purpose: transformar findings da Phase 24 em planos de reparo seguros, sempre
dry-run por default, com apply limitado, checkpoint humano e auditoria.

Output: `repair --dry-run --json`, apply gateado, testes e runbook.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-CONTEXT.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-RESEARCH.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-VALIDATION.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/24-production-recovery-guard-ats-horistic/24-SUMMARY.md
@.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
@modules/srv1-ops/scripts/production_guard.py
@cli/omni/srv1_ops.py
</context>

## Execution Envelope

| Field | Value |
|---|---|
| Target executor | `gpt-5.3-codex-spark` |
| Context target | 75k-95k tokens |
| Plans | 1 |
| Live mutation | Apply gated; dry-run only unless operator explicitly approves |
| Final gate | `$gsd-verify-work 25` after automated validation |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `25-01` | Guarded repair planner and apply checkpoint | PRG-06, PRG-10 | 1 | no, apply gate |

<tasks>

<task type="auto">
  <name>Task 1: Execute Phase 25 repair plan</name>
  <files>.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-01-PLAN.md</files>
  <action>Execute the guarded repair plan after Phase 24 status/doctor exists. Keep dry-run as default and do not cross the apply checkpoint without explicit operator approval.</action>
  <verify>
    <automated>node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-01-PLAN.md</automated>
  </verify>
  <done>Child plan parses and repair remains dry-run-first with apply gated.</done>
</task>

</tasks>

<verification>
Run the ordered battery in `25-VALIDATION.md`, then run:

- `$gsd-verify-work 25`
</verification>

<success_criteria>
Phase 25 is complete when every repairable finding has a safe dry-run plan,
apply is impossible without explicit scope/checkpoint/snapshot, and forbidden
commands are blocked by tests and scanner.
</success_criteria>

<output>
Create `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-SUMMARY.md` when
`25-01` completes and `$gsd-verify-work 25` passes.
</output>
