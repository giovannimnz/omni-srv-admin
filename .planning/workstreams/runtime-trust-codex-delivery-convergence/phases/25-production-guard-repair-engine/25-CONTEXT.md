---
phase: 25
title: "Context - Production Guard Repair Engine"
date: 2026-06-24
status: ready-for-execution
requirements:
  - PRG-06
  - PRG-10
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
depends_on:
  - Phase 24
---

# Phase 25 Context

## Phase Boundary

Adicionar repair seguro ao `production-guard` depois que a Phase 24 entregar
status/doctor read-only.

Escopo desta fase:

- Implementar `production-guard repair --dry-run --json`.
- Implementar `repair --apply` apenas com `--scope`, `--target`, confirmacao
  explicita, snapshot primeiro e allowlist de acoes.
- Gerar audit log sem secrets.
- Bloquear repair se status/doctor da Phase 24 apontar live/dump/namespaces
  incoerentes.
- Planejar safe-starts para PM2 apps/stacks, containers conhecidos e systemd
  units permitidas.

Fora desta fase:

- Instalar protocolo boot/login.
- Corrigir Apache remoto Horistic.
- Renomear pastas/repos/vhosts.
- Reescrever dump PM2 automaticamente.
- Usar `pm2 kill`.
- Reiniciar RDP/XRDP ou derrubar trading.

## Locked Decisions

- D25-01: `repair` e dry-run por default.
- D25-02: `repair --apply` exige checkpoint humano e escopo especifico.
- D25-03: Snapshots precedem qualquer apply.
- D25-04: `pm2 save` so pode aparecer como proposta bloqueada quando live/dump
  e namespaces estiverem saudaveis; nao e acao automatica desta fase.
- D25-05: Todas as acoes precisam de audit event machine-readable e resumo PT-BR.

## Inputs From Phase 24

- `modules/srv1-ops/configs/production-guard.yaml`
- `modules/srv1-ops/scripts/production_guard.py`
- `omni srv1-ops production-guard status --json`
- `omni srv1-ops production-guard doctor --json`
- `cli/omni/tests/test_srv1_production_guard.py`

## Safety Constraints

- No `pm2 kill`.
- No RDP/XRDP restart.
- No Apache remote mutation.
- No webhook POST.
- No `pm2 save` while live/dump/namespaces are not fully healthy.
- No secrets in audit logs, JSON, docs or fixtures.
