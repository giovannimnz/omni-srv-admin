---
phase: 27
plan: 27-01-PLAN.md
status: complete
completed_by: codex
completed_at: 2026-06-24
source:
  - modules/srv1-ops/scripts/production_guard.py
  - modules/srv1-ops/configs/production-guard.yaml
  - docs/operations/production-guard.md
  - cli/omni/tests/test_srv1_production_guard.py
---

# Phase 27 Plan 27-01 - SUMMARY

## Status: COMPLETE

Plan 27-01 executado com sucesso: adicionados checks remotos de Apache para o horistic e o detector de rename-drift sem mutações.

## Arquivos criados/atualizados

- `modules/srv1-ops/scripts/production_guard.py`
- `modules/srv1-ops/configs/production-guard.yaml`
- `docs/operations/production-guard.md`
- `cli/omni/tests/test_srv1_production_guard.py`

## Validação executada

- `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
- `rg -n "requests\\.post|urllib.*POST|curl .*POST|method=.*POST" modules/srv1-ops/scripts/production_guard.py modules/srv1-ops/configs/production-guard.yaml docs/operations/production-guard.md`
- `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "apache or remote or rename or drift or webhook"`
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
- `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`

## Segurança

- Nenhuma operação de mutação foi adicionada ao fluxo de `status/doctor`.
- Os novos checks de produção usam apenas leitura remota (`ssh` + comandos de inspeção).
- O novo endpoint `horistic-webhook-health` usa `HEAD`.
