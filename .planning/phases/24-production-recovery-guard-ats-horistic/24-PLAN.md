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
name: ATS/Horistic Production Recovery Guard
date: 2026-06-24
status: ready
plans: 4
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
  - PRG-06
  - PRG-07
  - PRG-08
  - PRG-09
  - PRG-10
must_haves:
  truths:
    - "ATS e Horistic estao em producao; nenhuma acao da fase pode derrubar trading, RDP/XRDP ou Apache sem gate explicito."
    - "pm2-ubuntu.service e o unico boot owner de PM2 para ATS e Horistic."
    - "Namespaces PM2 canonicos sao atius e horistic; default e wrong namespace sao findings."
    - "waiting restart so e healthy para launchers one-shot se houver ciclo recente e sem fatal error."
    - "Horistic proxy Apache vive no host remoto horistic-srv; SRV-1 roda apps."
    - "Repair e dry-run por default, snapshot-first, sem pm2 kill."
    - "Renomeio de pasta/host/repo deve ser detectado e proposto, nao aplicado automaticamente."
  artifacts:
    - path: "modules/srv1-ops/scripts/production_guard.py"
      provides: "Read-only status/doctor and gated repair engine for ATS/Horistic production guard."
    - path: "modules/srv1-ops/configs/production-guard.yaml"
      provides: "Declarative baseline for PM2 apps, namespaces, ports, endpoints, remote Apache and rename drift."
    - path: "cli/omni/tests/test_srv1_production_guard.py"
      provides: "Tests for PM2/dump/ecosystem/namespace/repair contracts."
    - path: "modules/srv1-ops/systemd/production-guard.service"
      provides: "Boot/login verification unit."
    - path: "docs/operations/production-guard.md"
      provides: "Runbook for validation, repair, rollback and session-start protocol."
  key_links:
    - from: "modules/srv1-ops/scripts/production_guard.py"
      to: "modules/srv1-ops/configs/production-guard.yaml"
      via: "baseline-driven validation"
      pattern: "atius|horistic|pm2-ubuntu|apache|rename"
    - from: "cli/omni/srv1_ops.py"
      to: "modules/srv1-ops/scripts/production_guard.py"
      via: "production-guard command group"
      pattern: "production-guard|status|repair"
---

# Phase 24: ATS/Horistic Production Recovery Guard

<objective>
Criar um guard operacional versionado para ATS e Horistic em producao,
cobrindo boot PM2, namespaces, ecosystems, dump/resurrect, reverse proxy remoto,
containers/servicos/timers, protocolo reboot/login e drift de renomeio.

Purpose: transformar as correcoes manuais recentes em verificacao e reparo
reproduziveis dentro do `omni-srv-admin`, sem depender de memoria de sessao.
Output: quatro PLANs executaveis com CLI, config, tests, systemd units e docs.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/phases/24-production-recovery-guard-ats-horistic/24-CONTEXT.md
@.planning/phases/24-production-recovery-guard-ats-horistic/24-RESEARCH.md
@.planning/REQUIREMENTS.md
@docs/operations/pm2-canonical.md
@docs/operations/srv1-ops.md
@modules/srv1-ops/scripts/inviolable-watchdog.sh
@modules/srv1-ops/systemd/pm2-ubuntu.service
@cli/omni/srv1_ops.py
</context>

## Wave Structure

| Wave | Plans | Why |
|---|---|---|
| 1 | `24-01` | Build read-only truth before any repair. |
| 2 | `24-02` | Add gated repair only after validator exists. |
| 3 | `24-03` | Wire boot/login protocol after status/repair contracts. |
| 4 | `24-04` | Add remote Apache + rename drift and final docs after status, repair and boot/login contracts are stable. |

## Plans

| Plan | Objective | Requirements | Wave | Autonomous |
|---|---|---|---:|---|
| `24-01` | PM2 boot, namespace and ecosystem validator | PRG-01, PRG-02, PRG-03, PRG-04, PRG-05 | 1 | yes |
| `24-02` | Guarded repair engine for PM2, services and containers | PRG-06 | 2 | no, repair apply gate |
| `24-03` | Boot/login protocol, timers and operator runbook | PRG-07, PRG-10 | 3 | no, live install gate |
| `24-04` | Horistic remote Apache and rename drift detector | PRG-08, PRG-09, PRG-10 | 4 | yes, remote checks read-only |

<tasks>

<task type="auto">
  <name>Task 1: Execute Phase 24 plans in order</name>
  <files>.planning/phases/24-production-recovery-guard-ats-horistic/24-01-PLAN.md, .planning/phases/24-production-recovery-guard-ats-horistic/24-02-PLAN.md, .planning/phases/24-production-recovery-guard-ats-horistic/24-03-PLAN.md, .planning/phases/24-production-recovery-guard-ats-horistic/24-04-PLAN.md</files>
  <action>Execute plans in wave order. Do not run live repair, install timers, restart PM2, restart XRDP/RDP, restart Apache or mutate remote Horistic without the explicit checkpoints in the child plans. Preserve Phase 14 single-boot-owner decision.</action>
  <verify>
    <automated>for f in .planning/phases/24-production-recovery-guard-ats-horistic/24-{01,02,03,04}-PLAN.md; do node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure "$f" >/dev/null || exit 1; done</automated>
  </verify>
  <done>All child plans parse and are executable in wave order.</done>
</task>

<task type="auto">
  <name>Task 2: Preserve production safety gates</name>
  <files>.planning/phases/24-production-recovery-guard-ats-horistic/24-02-PLAN.md, .planning/phases/24-production-recovery-guard-ats-horistic/24-03-PLAN.md</files>
  <action>Verify that repair apply and live systemd install are checkpoint-gated, dry-run by default and explicitly ban `pm2 kill`, RDP/XRDP restarts and ungated Apache mutation.</action>
  <verify>
    <automated>rg -n "pm2 kill|checkpoint|dry-run|XRDP|RDP|Apache|repair --apply" .planning/phases/24-production-recovery-guard-ats-horistic/24-*-PLAN.md</automated>
  </verify>
  <done>Plan text enforces dry-run-first production guard behavior and live mutation gates.</done>
</task>

</tasks>

## Source Coverage Audit

| Source | ID | Feature/Requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| REQ | PRG-01 | PM2 boot owner contract | 24-01 | COVERED | systemd unit validation. |
| REQ | PRG-02 | PM2 live/dump/ecosystem parity | 24-01 | COVERED | baseline-driven validator. |
| REQ | PRG-03 | PM2 namespace isolation | 24-01, 24-02 | COVERED | wrong namespace blocks repair save. |
| REQ | PRG-04 | ecosystem.config.js contract | 24-01 | COVERED | cwd/script/autorestart/restart policy. |
| REQ | PRG-05 | CLI status/doctor | 24-01 | COVERED | `production-guard status`. |
| REQ | PRG-06 | guarded repair | 24-02 | COVERED | dry-run/apply gates. |
| REQ | PRG-07 | boot/login protocol | 24-03 | COVERED | systemd units/timer and runbook. |
| REQ | PRG-08 | remote Horistic Apache | 24-04 | COVERED | SSH read-only and endpoint probes. |
| REQ | PRG-09 | rename drift detector | 24-04 | COVERED | path/host/vhost/GDrive refs. |
| REQ | PRG-10 | audit/docs/no secrets | 24-03, 24-04 | COVERED | JSON output and runbook. |

<verification>
Run:

- `for f in .planning/phases/24-production-recovery-guard-ats-horistic/24-{01,02,03,04}-PLAN.md; do node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" verify plan-structure "$f"; done`
- `rg -n "PRG-01|PRG-10|production-guard|pm2-ubuntu|horistic-srv|rename" .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/phases/24-production-recovery-guard-ats-horistic`
- `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
</verification>

<success_criteria>
Phase 24 is complete when ATS/Horistic have a reproducible guard in
`omni-srv-admin` that proves boot resilience, PM2 namespace separation,
ecosystem/dump parity, remote Horistic proxy health, boot/login verification and
safe repair rules without exposing secrets or performing ungated production
mutations.
</success_criteria>

<output>
Create `.planning/phases/24-production-recovery-guard-ats-horistic/24-SUMMARY.md` when all four plans complete.
</output>
