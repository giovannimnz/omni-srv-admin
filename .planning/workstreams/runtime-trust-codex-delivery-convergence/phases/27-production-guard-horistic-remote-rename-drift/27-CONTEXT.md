---
phase: 27
title: "Context - Horistic Remote Apache, Rename Drift and Webhook Safety"
date: 2026-06-24
status: ready-for-execution
requirements:
  - PRG-08
  - PRG-09
  - PRG-10
  - PRG-11
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
depends_on:
  - Phase 26
---

# Phase 27 Context

## Phase Boundary

Completar o `production-guard` com checks read-only para o Horistic remoto,
rename drift e webhook-safe validation.

Escopo desta fase:

- Validar Apache remoto no `horistic-srv`, sem assumir que Apache vive no SRV-1.
- Checar unit padrao, drop-ins, portas 80/443, `apache2ctl -S`,
  `sites-enabled`, vhosts, proxy targets e endpoints publicos.
- Detectar drift de renomeio de host/pasta/repo/vhost/GDrive/symlink, incluindo
  `horistic-srv-1` -> `horistic-srv`.
- Garantir que checks de webhook/trading sao GET/HEAD por default e nao fazem
  POST real para Horistic/ATS/Telegram.
- Registrar como contrato externo que Horistic scalp split e Circuit Breaker
  suppression devem ser preservados.

Fora desta fase:

- Mutar Apache remoto.
- Renomear pastas/repos/vhosts.
- Criar symlinks corretivos.
- Enviar POST real de teste.
- Alterar codigo do repo `/home/ubuntu/GitHub/Atius-Capital/horistic`.

## Locked Decisions

- D27-01: Horistic Apache vive no host remoto `horistic-srv`; backend/frontend
  e webhooks rodam no SRV-1.
- D27-02: Remote checks sao read-only e usam SSH apenas para status/config dump.
- D27-03: Rename detector propoe correcao; nao aplica automaticamente.
- D27-04: Public endpoint validation usa GET/HEAD apenas.
- D27-05: Webhook/scalp behavior atual e contrato externo:
  - entrada dupla vira duas mensagens Telegram separadas por 500ms;
  - Circuit Breaker scalp nao envia Telegram;
  - Circuit Breaker scalp ainda encaminha payload ao ATS.

## Incident Context To Preserve

- Apache incident, 2026-06-21: unit custom remota chamava
  `/usr/sbin/apache2 -k start` e falhava com `DefaultRuntimeDir`; a unit correta
  e a padrao do pacote Ubuntu.
- Horistic sites foram validados com 200 em:
  `dashboard.horistic.com/login`, `trade.horistic.com/login`,
  `backtest.horistic.com/login`, `painel.horistic.com/login`,
  `api.horistic.com/v1/health`, `webhook.horistic.com/`.
- O teste POST em webhook real dispara Telegram/ATS; validacoes devem evitar
  isso por padrao.

## External Contract References

- `/home/ubuntu/GitHub/Atius-Capital/horistic/backend/indicators/webhook/scalpMessageSplitter.js`
- `/home/ubuntu/GitHub/Atius-Capital/horistic/backend/indicators/webhook/webhookSignals.js`
- `/home/ubuntu/GitHub/Atius-Capital/horistic/tests/unit/backend/test_scalp_message_splitter.test.js`
