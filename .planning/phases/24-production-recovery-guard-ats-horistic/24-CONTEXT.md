---
phase: 24
title: "Context — ATS/Horistic Production Recovery Guard"
date: 2026-06-24
status: ready-for-planning
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
---

# Phase 24 Context

## Phase Boundary

Implementar uma protecao operacional versionada no `omni-srv-admin` para ATS
e Horistic em producao.

Escopo incluido:

- Validar boot automatico via `pm2-ubuntu.service`.
- Validar que PM2 vivo, dump e ecosystems batem.
- Validar isolamento de namespaces `atius` e `horistic`.
- Validar ports/endpoints criticos sem disparar mensagens reais para Telegram
  ou ATS.
- Validar Apache remoto do Horistic no host `horistic-srv`.
- Criar guard read-only e repair gateado para PM2, services e containers.
- Criar protocolo de verificacao no reboot e no inicio de login/session.
- Detectar rename drift de pasta/host/repo/vhost antes que PM2/Apache quebrem.

Fora de escopo:

- Alterar logica de trading do ATS/Horistic.
- Reiniciar PM2, RDP/XRDP, Apache remoto ou containers sem gate explicito.
- Enviar POST real para webhooks de trading ou Telegram.
- Corrigir bugs internos dos repos `Atius-Capital/ats` ou
  `Atius-Capital/horistic`; esta fase cria guard/diagnostico/reparo no
  `omni-srv-admin`.

## Locked Decisions

- D24-01: `pm2-ubuntu.service` e o unico boot owner para ATS + Horistic.
- D24-02: O baseline atual esperado e `atius: 12`, `horistic: 5`.
- D24-03: `atius` e `horistic` sao namespaces separados; `default` e namespace
  errado sao findings bloqueantes para apps desses sistemas.
- D24-04: `waiting restart` so e aceitavel para launchers one-shot se o ultimo
  ciclo teve `[CYCLE_SUMMARY]` recente e sem erro fatal; nao pode ser tratado
  como healthy de forma cega.
- D24-05: Repair automatico deve ser dry-run por default, snapshot-first e sem
  `pm2 kill`.
- D24-06: Apache dos sites Horistic vive no host remoto `horistic-srv`; o SRV-1
  roda backend/frontend/webhooks.
- D24-07: Renomeios de host/pasta precisam ser detectados automaticamente antes
  de corrigir: cwd/script inexistente, vhost antigo, GDrive path antigo,
  symlink pendente, inventory `rename_from`.
- D24-08: Checks podem rodar no reboot/login; mutacoes live continuam gateadas
  por escopo e impacto.
- D24-09: Saidas devem ser JSON + resumo PT-BR, sem secrets.

## Current Validation Snapshot

Coletado em 2026-06-24, sem reiniciar servicos:

- `pm2-ubuntu.service`: `enabled`, `active`, `Type=oneshot`,
  `RemainAfterExit=yes`, `NeedDaemonReload=no`.
- Live PM2: `atius: 12`, `horistic: 5`.
- `/home/ubuntu/.pm2/dump.pm2`: `atius: 12`, `horistic: 5`.
- `missing_in_dump`: none.
- `missing_live`: none.
- `wrong_namespace_live`: none.
- Legacy user PM2 units: `ats-pm2.service` disabled/inactive,
  `horistic-pm2.service` disabled/inactive.
- Critical local ports open: 3015, 8015, 3050, 8050, 8099, 8199.
- Public checks returned 200:
  `dashboard.horistic.com/login`, `trade.horistic.com/login`,
  `backtest.horistic.com/login`, `painel.horistic.com/login`,
  `api.horistic.com/v1/health`, `webhook.horistic.com/`,
  `dashboard.atius.com.br/login`, `api.atius.com.br/v1/health`,
  `webhook.atius.com.br/`.
- `horistic-srv`: Apache unit padrao em `/usr/lib/systemd/system/apache2.service`,
  `enabled`, `active`, sem drop-ins, ouvindo em 80/443.

## Observed Gaps

- `atius-unified-bot-launcher` e `horistic-unified-bot-launcher` aparecem como
  `waiting restart` com milhares de restarts. Logs indicam modo one-shot
  esperado, mas o guard atual nao valida recencia/sucesso de `[CYCLE_SUMMARY]`.
- `inviolable-watchdog` aceita `waiting restart` para launchers. Isso deve ser
  substituido por contrato explicito.
- `inviolable-watchdog` relanca containers `atius-router-containers` com
  frequencia. A Phase 24 deve reportar isso como finding estruturado, nao so
  log solto.
- `systemctl --user list-jobs` ainda mostrou `default.target` em `start waiting`
  e jobs longos nao relacionados diretamente a PM2. O novo guard deve separar
  risco critico de ruido aceitavel.
- Renomeios anteriores (`horistic-srv-1` -> `horistic-srv`) deixaram refs
  operacionais antigas em algumas areas. O novo detector deve listar e classificar
  isso antes de qualquer rename live.

## Canonical References

- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`
- `.planning/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md`
- `.planning/phases/14-resource-governor-pm2-boot-hardening/14-04-PLAN.md`
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
