---
phase: 26
title: "Context - Production Guard Boot/Login Protocol"
date: 2026-06-24
status: ready-for-execution
requirements:
  - PRG-07
  - PRG-10
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
depends_on:
  - Phase 25
---

# Phase 26 Context

## Phase Boundary

Versionar o protocolo de verificacao no reboot e no inicio de login/session.

Escopo desta fase:

- Criar units/timers read-only para rodar `production-guard status/doctor`.
- Registrar findings e audit sem secrets.
- Documentar runbook de boot/login, impacto, rollback e troubleshooting.
- Gatear qualquer live install de units/timers.
- Garantir que o protocolo nao reinicia PM2, RDP/XRDP, Apache ou trading.

Fora desta fase:

- Reparos automaticos novos alem dos scopes permitidos pela Phase 25.
- Remote Apache deep validation e rename drift; isso fica para Phase 27.
- Reboot real obrigatorio.

## Locked Decisions

- D26-01: Boot/login protocol e read-only por default.
- D26-02: Units/timers versionadas podem ser instaladas so com gate live.
- D26-03: Qualquer repair acionado a partir do protocolo precisa reutilizar as
  politicas da Phase 25.
- D26-04: RDP/XRDP nao pode ser reiniciado por este protocolo.

## Inputs From Phase 25

- `production-guard status/doctor`
- `production-guard repair --dry-run`
- runbook inicial `docs/operations/production-guard.md`
- audit redaction tests
