---
phase: 09
padded: 09
slug: mission-guardian
name: Mission Guardian
date: 2026-06-11
status: ready
wave: 1
depends_on: []
autonomous: true
files_modified:
  - modules/srv1-ops/scripts/mission-guardian.py
  - modules/srv1-ops/configs/mission-guardian.env
  - modules/srv1-ops/scripts/resource-governor-watchdog.py
  - modules/srv1-ops/scripts/mission-guardian-tune.sh
  - modules/srv1-ops/scripts/mission-guardian-cleanup-rotate.sh
  - .config/systemd/user/mission-guardian.service
  - .config/systemd/user/mission-guardian.timer
  - .config/systemd/user/inviolable-watchdog.service
  - modules/srv1-ops/scripts/inviolable-watchdog.sh
requirements_addressed:
  - MGR-01
  - MGR-02
  - MGR-03
  - MGR-04
  - MGR-05
  - MGR-06
  - MGR-07
  - MGR-08
must_haves:
  truths:
    - Mission Guardian daemon roda 24/7 com timer 60s, persiste histórico em SQLite
    - Auto-tuning ajusta cpu.weight por classe omni-* baseado em janela 6h
    - Disk fill forecasting com slope linear emite alerta 7/30 dias antes
    - Cleanup rc=124 resolvido (timeout 3s→8s, watchdog monitora > 30s)
    - logrotate /var/log/syslog funciona (permissão 755 + su syslog)
    - Agente DevOps "HoristicOps" tem skill registrada em ~/.hermes/skills/devops/mission-guardian/
  artifacts:
    - mission-guardian.py existe em modules/srv1-ops/scripts/
    - mission-guardian.db criado em ~/.local/state/omni/
    - 5 plans criados: 09-01 a 09-05
  gates:
    - python3 -c "import ast; ast.parse(open('modules/srv1-ops/scripts/mission-guardian.py').read())" exits 0
    - systemctl --user is-active mission-guardian.timer returns "active"
    - sqlite3 ~/.local/state/omni/mission-guardian.db "SELECT count(*) FROM samples" > 0 after 5min
---

# Phase 09: Mission Guardian — Master Plan

## Goal

Servidor ATIUS-SRV-1 NUNCA mais trava silenciosamente. Sistema de
monitoramento + auto-tuning + incident response + agente DevOps de plantão
roda 24/7, previne degradação antes de virar travamento, e responde a
incidentes em <60s.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  24/7 MONITORING (60s cycle)                                │
│                                                              │
│  mission-guardian.timer  ──►  mission-guardian.service       │
│      (systemd user)              (oneshot)                   │
│                                          │                   │
│                                          ▼                   │
│                              mission-guardian.py             │
│                              ┌──────────────────┐            │
│                              │ sampler:         │            │
│                              │  - load,memory   │            │
│                              │  - disk,PSI      │            │
│                              │  - tcp,fds,net   │            │
│                              │  - cpu.throttled │            │
│                              │  - dmesg OOM     │            │
│                              │  - journald      │            │
│                              └────────┬─────────┘            │
│                                       │                      │
│                              ┌────────▼─────────┐            │
│                              │ SQLite DB        │            │
│                              │ (history 30d)    │            │
│                              └────────┬─────────┘            │
│                                       │                      │
│                              ┌────────▼─────────┐            │
│                              │ analyzers:       │            │
│                              │  - correlation   │            │
│                              │  - disk forecast │            │
│                              │  - auto-tune     │            │
│                              │  - incident det. │            │
│                              └────────┬─────────┘            │
│                                       │                      │
│                              ┌────────▼─────────┐            │
│                              │ responders:      │            │
│                              │  - log           │            │
│                              │  - cgroup tune   │            │
│                              │  - telegram      │            │
│                              │  - inviolable-wd │            │
│                              └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

## Waves

- **Wave 1** (sequential, builds foundation): 09-01 → 09-02 → 09-03
- **Wave 2** (parallel after wave 1): 09-04 ∥ 09-05

## Plans in this phase

| ID | Name | Wave | Status |
|----|------|------|--------|
| [09-01](09-01-PLAN.md) | Mission Guardian daemon (core) | 1 | ready |
| [09-02](09-02-PLAN.md) | Disk fill forecasting + correlation analyzer | 1 | ready |
| [09-03](09-03-PLAN.md) | Auto-tune omni-* cpu.weight (predictive) | 1 | ready |
| [09-04](09-04-PLAN.md) | Cleanup timeout fix + logrotate /var/log | 2 | ready |
| [09-05](09-05-PLAN.md) | HoristicOps agent (DevOps on-call) | 2 | ready |

## Cross-cutting constraints

- **Idempotência absoluta** — toda config/script rodável múltiplas vezes sem
  side-effect negativo (regra GSD + memory)
- **Backup antes de destrutivo** — qualquer mudança em /var/log, /etc/logrotate.d,
  cgroup config → backup em /home/ubuntu/.logs/resource-governor/backups/
  com timestamp
- **Documentar no vault** — cada fix → entry em 60-LOGS/ e decision em
  21.03-Decisoes-Arquitetura.md
- **Não quebrar inviolable v2** — qualquer mudança tem que preservar 68 patterns
  + 5 cgroups + 8 unit files hardened

## Acceptance gate (final)

- [ ] Mission Guardian daemon ativo, sample count > 0 após 5min
- [ ] Disk forecast: comando CLI mostra previsão 7d/30d
- [ ] Auto-tune: cpu.weight de omni-* muda em janela de 6h
- [ ] Cleanup rc=124 não acontece mais em 24h
- [ ] logrotate syslog rotaciona
- [ ] Skill mission-guardian em ~/.hermes/skills/devops/ + agente
      invocável via "ask horistic-ops" no chat
- [ ] Documentação em 60-LOGS/ completa
