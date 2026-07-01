---
phase: 27
plan: 27-PLAN.md
status: complete
completed_by: codex
completed_at: 2026-06-24
source:
  - .planning/phases/27-production-guard-horistic-remote-rename-drift/27-01-SUMMARY.md
---

# Phase 27: Production Guard - Horistic Remote Apache + Rename Drift

## Status: COMPLETE

Fase 27 concluída com checks remotos de estado Apache e detecção de drift de rename sem mutação.

## Entregas

- Adicionado check read-only de Apache remoto (SSH) para estado do serviço, portas 80/443, `sites-enabled` e `apache2ctl -S`.
- Adicionado detector de drift de rename para referências legadas `horistic-srv-1` em runtime PM2 e vhosts remotos, com severidade controlada (`warn`/`block`).
- Novo endpoint de saúde `horistic-webhook-health` (`HEAD`) na baseline de produção.

## Resultado de execução

- `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "apache or remote or rename or drift or webhook"` executado com sucesso.
- Comandos operacionais `status --json` e `doctor --json` executam e reportam o novo check remoto + rename-drift, porém o resultado global permanece `block` por bloqueios já existentes no ambiente (PM2/unit, parse de ecosystems e alguns serviços/containeres).
