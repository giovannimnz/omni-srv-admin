---
phase: 24
plan: 00
type: index
wave: 0
depends_on: []
files_modified: []
autonomous: false
padded: 24
slug: production-recovery-guard-ats-horistic
name: Production Guard Foundation - PM2 Status/Doctor
date: 2026-06-24
status: ready
plans: 1
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
must_haves:
  truths:
    - "Phase 24 e read-only; nao aplica repair, pm2 save, restart ou mutate."
    - "pm2-ubuntu.service e o unico boot owner de PM2 para ATS e Horistic."
    - "Namespaces canonicos sao atius e horistic; default/wrong namespace bloqueiam."
    - "waiting restart so e healthy para launchers one-shot com ciclo recente e sem fatal error."
    - "Status/doctor cobre PM2, dump, ecosystems, portas, endpoints GET/HEAD, containers, timers e jobs."
    - "Webhook validation nao envia POST real para ATS/Horistic/Telegram."
  artifacts:
    - path: "modules/srv1-ops/configs/production-guard.yaml"
      provides: "Baseline declarativo de PM2/apps/ports/endpoints/containers/timers/jobs."
    - path: "modules/srv1-ops/scripts/production_guard.py"
      provides: "Status/doctor read-only com JSON e resumo PT-BR."
    - path: "cli/omni/tests/test_srv1_production_guard.py"
      provides: "Tests de PM2/dump/ecosystem/namespace/launcher/container/timer/job."
---

# Phase 24: Production Guard Foundation - PM2 Status/Doctor

<objective>
Criar a fundacao read-only do `production-guard` para ATS/Horistic.

Purpose: provar em um comando que boot PM2, live/dump parity, namespace
separation, ecosystem contract, portas, endpoints GET/HEAD, containers, timers
e jobs estao coerentes antes de qualquer repair futuro.

Output: um PLAN executavel por Spark, com CLI/config/testes e validacao final
por `$gsd-verify-work 24`.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/phases/24-production-recovery-guard-ats-horistic/24-CONTEXT.md
@.planning/phases/24-production-recovery-guard-ats-horistic/24-RESEARCH.md
@.planning/phases/24-production-recovery-guard-ats-horistic/24-VALIDATION.md
@.planning/REQUIREMENTS.md
@docs/operations/pm2-canonical.md
@docs/operations/srv1-ops.md
@modules/srv1-ops/scripts/inviolable-watchdog.sh
@modules/srv1-ops/systemd/pm2-ubuntu.service
@cli/omni/srv1_ops.py
</context>

## Execution Envelope

| Field | Value |
|---|---|
| Target executor | `gpt-5.3-codex-spark` |
| Context target | 75k-95k tokens |
| Plans | 1 |
| Live mutation | Forbidden in Phase 24 |
| Final gate | `$gsd-verify-work 24` after automated validation |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `24-01` | PM2 boot, namespace, ecosystem, container/timer/job validator | PRG-01, PRG-02, PRG-03, PRG-04, PRG-05 | 1 | yes, read-only |

<tasks>

<task type="auto">
  <name>Task 1: Execute Phase 24 foundation plan</name>
  <files>.planning/phases/24-production-recovery-guard-ats-horistic/24-01-PLAN.md</files>
  <action>Execute only the read-only foundation plan. Do not run repair, `pm2 save`, `pm2 kill`, PM2 restarts, RDP/XRDP restarts, Apache mutation or webhook POST tests.</action>
  <verify>
    <automated>node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure .planning/phases/24-production-recovery-guard-ats-horistic/24-01-PLAN.md</automated>
  </verify>
  <done>Child plan parses and remains scoped to read-only status/doctor.</done>
</task>

</tasks>

## Source Coverage Audit

| Source | ID | Feature/Requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| REQ | PRG-01 | PM2 boot owner contract | 24-01 | COVERED | systemd unit validation. |
| REQ | PRG-02 | PM2 live/dump/ecosystem parity | 24-01 | COVERED | baseline-driven validator. |
| REQ | PRG-03 | PM2 namespace isolation | 24-01 | COVERED | wrong namespace blocks. |
| REQ | PRG-04 | ecosystem contract | 24-01 | COVERED | cwd/script/autorestart/restart policy/env/ports/redaction. |
| REQ | PRG-05 | CLI status/doctor | 24-01 | COVERED | PM2 plus containers/timers/jobs. |

<verification>
Run the ordered battery in `24-VALIDATION.md`, then run:

- `$gsd-verify-work 24`
</verification>

<success_criteria>
Phase 24 is complete when ATS/Horistic have a reproducible read-only guard in
`omni-srv-admin` proving PM2 boot resilience, namespace separation,
ecosystem/dump parity, critical port/endpoint visibility and timer/job/container
classification without secrets or live mutation.
</success_criteria>

<output>
Create `.planning/phases/24-production-recovery-guard-ats-horistic/24-SUMMARY.md`
when `24-01` completes and `$gsd-verify-work 24` passes.
</output>
