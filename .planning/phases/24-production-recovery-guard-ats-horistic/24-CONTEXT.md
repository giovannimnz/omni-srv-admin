---
phase: 24
title: "Context - Production Guard Foundation"
date: 2026-06-24
status: ready-for-execution
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 24 Context

## Phase Boundary

Criar a fundacao read-only do `production-guard` para ATS/Horistic.

Escopo desta fase:

- Validar `pm2-ubuntu.service` como unico boot owner.
- Comparar PM2 vivo, `/home/ubuntu/.pm2/dump.pm2` e ecosystems.
- Validar namespaces PM2 `atius` e `horistic`.
- Validar contrato minimo de `ecosystem.config.js`: `cwd`, `script`, namespace,
  `autorestart`, `restart_delay`, `max_restarts`, env minima, portas e redacao.
- Validar portas locais, endpoints GET/HEAD, containers conhecidos, timers e
  jobs systemd com classificacao `pass`, `warn`, `block` ou `unknown`.
- Expor CLI read-only `omni srv1-ops production-guard status/doctor --json`.

Fora desta fase:

- Aplicar reparos ou `pm2 save`.
- Instalar units/timers de boot/login.
- Reiniciar PM2, RDP/XRDP, Apache remoto, containers ou trading.
- Fazer POST real para webhooks Horistic/ATS/Telegram.
- Corrigir Apache remoto Horistic ou rename drift; isso fica para Phase 27.

## Locked Decisions

- D24-01: `pm2-ubuntu.service` e o unico boot owner para ATS + Horistic.
- D24-02: O baseline atual esperado e `atius: 12`, `horistic: 5`.
- D24-03: Apps ATS devem ficar no namespace `atius`; apps Horistic no namespace
  `horistic`; `default` e namespace errado sao findings bloqueantes.
- D24-04: `waiting restart` so pode ser aceito para launchers one-shot quando o
  ultimo ciclo tiver `[CYCLE_SUMMARY]` recente e sem erro fatal.
- D24-05: Phase 24 e estritamente read-only; qualquer repair pertence a Phase 25.
- D24-06: Validacao de endpoint usa GET/HEAD por default; POST real contra
  webhook/trading/Telegram e proibido sem aprovacao explicita.
- D24-07: Saidas devem ser JSON + resumo PT-BR, sem secrets.

## Incident Context To Preserve

- PM2 boot incident, 2026-06-21: `pm2-ubuntu.service` estava como
  `Type=forking` + `PIDFile=/home/ubuntu/.pm2/pm2.pid`. O `pm2 resurrect`
  restaurava processos, mas o systemd marcava a unit como `failed (protocol)`.
  A correcao canonica e `Type=oneshot`, `RemainAfterExit=yes`, sem `PIDFile`.
- PM2 dump drift, 2026-06-21: vivo tinha 17 processos e dump tinha 6. O guard
  deve bloquear `pm2 save` quando live/dump/namespaces nao estiverem coerentes.
- Horistic Apache incident, 2026-06-21: sites quebraram porque o Apache remoto
  no `horistic-srv` usava unit custom que chamava `/usr/sbin/apache2 -k start`
  e falhava com `DefaultRuntimeDir`. A unit correta e a padrao do pacote.
- Horistic webhook/scalp: o split de mensagem dupla e a supressao Telegram-only
  do Circuit Breaker sao contratos externos. Esta fase so registra que checks
  de webhook devem ser nao invasivos; a validacao especifica fica na Phase 27.

## Current Validation Snapshot

Coletado em 2026-06-24, sem reiniciar servicos:

- `pm2-ubuntu.service`: `enabled`, `active`, `Type=oneshot`,
  `RemainAfterExit=yes`, `NeedDaemonReload=no`, sem `PIDFile`.
- Live PM2: `atius: 12`, `horistic: 5`.
- `/home/ubuntu/.pm2/dump.pm2`: `atius: 12`, `horistic: 5`.
- `missing_in_dump`: none.
- `missing_live`: none.
- `wrong_namespace_live`: none.
- Legacy user PM2 units: `ats-pm2.service` disabled/inactive,
  `horistic-pm2.service` disabled/inactive.
- Critical local ports open: 3015, 8015, 3050, 8050, 8099, 8199.
- Public checks returned 200 for Horistic and Atius GET endpoints.
- `horistic-srv`: Apache default package unit active on 80/443. Full remote
  Apache/vhost validation is Phase 27.

## Observed Gaps For Phase 24

- `atius-unified-bot-launcher` and `horistic-unified-bot-launcher` appear as
  PM2 `waiting restart`; the guard must validate recent successful cycles.
- `inviolable-watchdog` currently accepts `waiting restart` too broadly; Phase
  24 should report this as a structured finding, not mutate it.
- Repeated container relaunches and stuck user jobs must be classified without
  conflating noisy jobs with critical boot blockers.

## Canonical References

- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md`
- `docs/operations/pm2-canonical.md`
- `docs/operations/srv1-ops.md`
- `modules/srv1-ops/systemd/pm2-ubuntu.service`
- `modules/srv1-ops/scripts/inviolable-watchdog.sh`
- `modules/srv1-ops/configs/inviolable-services.env`
- `cli/omni/srv1_ops.py`
- `inventory/hosts/atius-srv-1.yaml`
- `inventory/hosts/horistic-srv.yaml`
- `/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js`
- `/home/ubuntu/GitHub/Atius-Capital/horistic/ecosystem.config.js`
