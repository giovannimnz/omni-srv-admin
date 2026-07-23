---
phase: 09
padded: 09
slug: mission-guardian
name: Mission Guardian
date: 2026-06-11
method: inline
status: complete
---

# Phase 09: Mission Guardian — Research

## Context

Mission 4h ATIUS-SRV-1 (2026-06-11 06:23 BRT) foi a primeira missão de monitoramento
ativo do SRV-1. Durante ~1h47min de operação, os gaps abaixo foram identificados
e PARCIALMENTE corrigidos no commit `eaad0cc` (resource-governor: inviolable services).
Esta fase encapsula o **sistema permanente** que vai garantir que o servidor NUNCA
mais trave silenciosamente, e que vai treinar um agente DevOps/Redes para assistir.

## Method

Inline research (skill `gsd-plan-phase` §1.6 shortcut). Researcher subagent
delegado falhou com HTTP 503 do provider MiniMax em tentativas anteriores nesta
sessão. Manual research em 8 probes paralelos via `execute_code` cobriu o
escopo equivalente em <1s.

## Findings (probes paralelos)

### Probe 1 — Estado atual do servidor

- **Mission 4h running:** PID 189673 (`srv1-monitor-mission.sh`), 30+ ciclos GREEN
- **Watchdog:** PID 261444 (resource-governor-watchdog.py) — 1047+ cycles, agora com
  hysteresis de 5 cycles
- **Patcher:** PID 381406 (resource-governor-patcher.py) — 68 inviolable patterns
- **Inviolable watchdog:** systemd user timer, 30s cycle, 14+ services protected
- **Cgroups omni-***: 5 (builds, generic, interactive, protected, transfers)

### Probe 2 — Estado do repo GSD

- `omni-srv-admin` é GSD-managed
- 11 phases, 1 completed (Phase 1), 5/11 plans completed
- Active milestone: M002 (fork-sync)
- 38 requirements em REQUIREMENTS.md
- Próximo phase number livre: 09

### Probe 3 — Files de srv1-ops existentes

```
resource-governor-patcher.py    (587 lines, 68 inviolable patterns, 5 cgroups)
resource-governor-watchdog.py   (444 lines, hysteresis, 5s poll)
resource-governor-snapshot.py
resource-governor-audit.py
resource-governor-status.py
server-analysis.py
backup-dangling-to-gdrive.py
```

### Probe 4 — Services systemd user existentes (deduplicados)

```
atius-router-docs, atius-web, atius-web-healthcheck, ats-pm2
backup-smb-daily, backup-srv1-daily
cleanup-daily-fleet, cleanup-local-weekly
gdrive-mount, rclone-gdrive-mount
hermes-os-webapp, hermes-sessions-cleanup, hermes-telegram, hermes-ws-gateway
horistic-pm2, inviolable-watchdog, keyboard-abnt2
obsidian-git-sync, offload-dotbackups-to-gdrive, offload-retired-artifacts-to-gdrive
resource-governor-{audit,cgroup-init,patcher,snapshot,watchdog}
server-analysis, ws-cleanup, ws-gateway-http-trigger
```

### Probe 5 — Crons ativos

- `*/5 * * * *` — sync-vault.sh (obsidian-vault auto-sync)
- `*/30 * * * *` — disk-alert.sh
- `0 3 * * *` — cleanup-daily-fleet.sh
- `0 7,8 * * *` — fork-sync (manuals list, aionui sync)
- `0 13 * * *` — browser automation (BR-13 schedule)
- `@reboot` — horistic start

### Probe 6 — Vault obsidian (60-LOGS)

Logs já existentes da missão 4h:
- `2026-06-11-srv1-mission-4h-config-tuning.md`
- `2026-06-11-srv1-inviolable-services.md`
- `2026-06-11-srv1-inviolable-services-v2.md`
- `server-analysis-2026-06-11.md`

## Gaps identificados durante a missão 4h

1. **Cobertura de medição incompleta** — monitor mede load, mem, disk, PSI, top procs.
   NÃO mede: tcp socket count, fd usage, network rate (rx/tx), cpu.stat nr_throttled,
   journald blocking, dmesg OOM count, disk I/O latency.
2. **Ações reativas, não preditivas** — thresholds YELLOW/RED disparam quando já está
   ruim. Sem correlação temporal de eventos (ex: "ram subiu X% em Y min → alerta cedo").
3. **Auto-balanceamento parcial** — patcher move procs para omni-* mas não detecta
   drift de slices de processos pesados (se um cargo build começa a 2 cores, patcher
   só age quando CPU > 3%, mas pode já ter saturado o slice).
4. **Sem agente de plantão** — quando missão 4h termina, ninguém fica olhando.
   Servidor pode degradar gradualmente e só ser notado quando sshd para de responder.
5. **Disco a 81%** — fill rate atual ~1%/dia. Sem previsão de quando vai saturar.
6. **logrotate do syslog quebrado** — `/var/log` perm 775 (syslog group writable)
   bloqueia rotação. 850MB+ atualmente.
7. **Cleanup script timeout** — `cleanup-local.sh` deu rc=124 (timeout 3s) 2x.
8. **Sem treinamento de agente DevOps** — Giovanni quer treinar um agente para
   "ser o DevOps/Redes". Precisa: persona, base de conhecimento, skill de
   monitoramento, skill de resposta a incidentes, skill de tuning.

## Requirements (propostos)

NOVOS — não cobertos por REQUIREMENTS.md existente:

- **MGR-01**: Mission Guardian daemon que roda 24/7 com auto-tuning contínuo
- **MGR-02**: Predição de disk fill (forecasting 7/30 dias)
- **MGR-03**: Auto-balanceamento proativo (ajustar cpu.weight por classe baseado em
  demanda observada)
- **MGR-04**: Correlação temporal de eventos (alert se load subiu 50% em 5min
  mesmo abaixo do YELLOW)
- **MGR-05**: Agente DevOps/Redes treinado com skill dedicada, on-call automático
- **MGR-06**: Incident response playbook codificado (cada tipo de evento →
  ação automatizada)
- **MGR-07**: Métricas históricas em SQLite/Postgres para dashboard e forecast
- **MGR-08**: Integration com inviolable-watchdog para escalation

## Decisões locked

- **D-01**: Mission Guardian roda como systemd user service `mission-guardian.service`
  com timer 60s (mesma cadência do monitor 4h, mas permanente)
- **D-02**: Banco de dados: SQLite local em `~/.local/state/omni/mission-guardian.db`
  (zero infra, suficiente para 30 dias de histórico @ 60s = 43k registros)
- **D-03**: Agente DevOps tem persona = "HoristicOps" (combina Horistic + Ops).
  Skills: `monitoring`, `incident-response`, `tuning`, `at-front-protection`
- **D-04**: Predição disk fill usa regressão linear simples (slope dos últimos 7
  dias) — sem dependência externa
- **D-05**: Auto-balanceamento usa window deslizante de 6h de cpu.weight efetivo
  por slice. Ajusta proativamente a cada 1h.
- **D-06**: Incident response é via systemd + Telegram (hermes-telegram é
  inviolable, já está no ar). Severidade RED → Telegram imediato; YELLOW →
  log + checkpoint; GREEN → silencioso.
- **D-07**: Cleanup rc=124 fix: aumentar timeout do `run_cmd` para 8s em
  cleanup tasks (era 3s) + watchdog monitora se cleanup > 30s
- **D-08**: logrotate fix: criar `chmod 755 /var/log` no fork-bootstrap (idempotente
  com `stat` guard) e configurar logrotate com `su syslog adm` + `create 0640`

## Sources / Inspiration

- `~/.hermes/skills/devops/control-loop-hysteresis/` — pattern de hysteresis
  (já aplicado no watchdog)
- `~/.hermes/skills/devops/process-supervisor/` — pattern de watchdog
  (já aplicado no inviolable-watchdog)
- `~/.hermes/skills/devops/srv1-local-cleanup-automation/` — cleanup patterns
- commit `c6288b1` (fix/resource-governor-pid1-incident) — base resource-governor
- commit `eaad0cc` (mesmo branch) — inviolable v1 + v2 + hysteresis

## Out of scope

- Auto-reboot (decisão humana, não daemon)
- Migration para cluster (single-node continua)
- ML-based anomaly detection (overkill para 4 vCPUs)
- Grafana/Prometheus stack (overhead, missão é < 100MB de daemon)

## Estimated effort

- Daemon core: ~400 lines Python (similar ao watchdog/patcher)
- Agente DevOps: 1 skill em `~/.hermes/skills/devops/mission-guardian/`
  (~500 lines docs + scripts)
- Auto-tune logic: ~150 lines
- Cleanup timeout fix: 3 line patch no watchdog
- logrotate fix: 1 script idempotente
- Teste E2E: 1 missão 4h em modo "guarded"

Total: 5 plans, 1 wave (todos independentes exceto cleanup/logrotate que
podem ser wave 1.5).
