---
phase: 14
padded: 14
slug: resource-governor-pm2-boot-hardening
name: Resource Governor + PM2 Boot Hardening
date: 2026-06-13
source: /home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md
status: ready
---

# Phase 14: Context

## Goal

Transformar a correcao live de 2026-06-13 do `resource-governor`,
`inviolable-watchdog` e PM2 em estado versionado, boot-safe, verificavel e
operavel no ATIUS-SRV-1, sem derrubar ATS/Horistic, bots de trading, SSHD ou
XRDP.

## Incident Source

Nota canonica:

- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md`

Backup pre-live:

- `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`

## Live State Captured

- `resource-governor-watchdog.service`: ativo.
- `resource-governor-patcher.service`: ativo.
- `resource-governor-cgroup-init.service`: `active (exited)`.
- `inviolable-watchdog.timer`: ativo.
- `runtime_mode=base`, sem `resource-governor.runtime.env` ativo na leitura final.
- Cgroups diretos no perfil base:
  - builds: CPU `200%`, I/O `80M/40M`, `memory.max=8G`.
  - interactive: CPU `125%`, I/O `60M/30M`, `memory.max=6G`.
  - transfers: CPU `100%`, I/O `407M/90M`, `memory.max=2G`.
- PM2 apps principais online: `atius-web`, `horistic-api`, `atius-api`,
  `atius-webhook-signals`, `atius-divap-indicator`,
  `atius-unified-bot-launcher`, `atius-strategy-builder`,
  `atius-mexc-bridged-api-worker`.

## Open Risks

- `horistic-pm2.service` ainda podia aparecer `activating` com PM2 daemon antigo
  no cgroup.
- `ats-pm2.service` ainda podia ficar `waiting` por causa de `default.target`
  travado.
- `pm2-ubuntu.service` system-level apontava para
  `/home/ubuntu/ecosystem.atius.js`, arquivo inexistente.
- Havia dois PM2 daemons; consolidar sem matar processos de trading exige
  snapshot atual e gate.
- XRDP estava como leftover no cgroup antigo do `inviolable-watchdog`; limpar
  isso sem derrubar RDP exige migracao controlada ou janela explicita.

## Locked Decisions

- Nao parar `pm2`, `node`, `python`, bots de trading, ATS/Horistic ou XRDP sem
  snapshot atual e gate humano explicito.
- Nao usar `git checkout`, `git reset` ou troca de branch durante esta fase.
- Nao gravar secrets em git, logs, `.planning` ou vault.
- `resource-governor.env` e runtime override sao fontes de verdade para limites.
- Ecosystems reais conhecidos:
  - `/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js`
  - `/home/ubuntu/GitHub/Atius-Capital/horistic/ecosystem.config.js`
- PM2 binario observado:
  - `/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2`
- Mudancas de systemd devem preferir `daemon-reload`, dry-run/status e
  start/restart apenas dos units da fase, com declaracao de impacto.
- Qualquer cleanup de XRDP deve declarar uma das tres classes:
  - sem impacto na sessao;
  - pisca desktop;
  - derruba RDP e exige janela aprovada.

## Canonical Files

- `cli/omni/srv1_ops.py`
- `docs/operations/resource-governor.md`
- `docs/operations/srv1-ops.md`
- `modules/srv1-ops/configs/resource-governor.env`
- `modules/srv1-ops/scripts/inviolable-watchdog.sh`
- `modules/srv1-ops/scripts/resource-governor-cgroup-init.sh`
- `modules/srv1-ops/scripts/resource-governor-patcher.py`
- `modules/srv1-ops/scripts/resource-governor-status.py`
- `modules/srv1-ops/scripts/resource-governor-watchdog.py`
- `modules/srv1-ops/systemd/resource-governor-cgroup-init.service`
- `modules/srv1-ops/systemd/resource-governor-patcher.service`
- `modules/srv1-ops/systemd/resource-governor-watchdog.service`
- `modules/srv1-ops/systemd/inviolable-watchdog.service`
- `modules/srv1-ops/systemd/inviolable-watchdog.timer`
- `modules/srv1-ops/systemd/omni-builds.slice`
- `modules/srv1-ops/systemd/omni-interactive.slice`
- `modules/srv1-ops/systemd/omni-transfers.slice`

## Requirements

- RGP-01: Units user do governor/inviolable iniciam sem depender de
  `default.target` bloqueado.
- RGP-02: Limites ficam consistentes entre slices systemd e cgroups diretos.
- RGP-03: PM2 tem caminho canonico de boot sem service apontando para arquivo
  inexistente.
- RGP-04: Jobs PM2/default presos sao drenados/substituidos sem matar apps.
- RGP-05: `inviolable-watchdog` usa ecosystems reais, ignora servicos ausentes
  e nao prende novos filhos XRDP/SSHD no seu cgroup.
- RGP-06: Cleanup de XRDP/PM2 exige gate operacional explicito.
- RGP-07: Runbook, rollback e verificacao pos-boot ficam versionados.

## Out of Scope

- Migrar apps para K3s/Portainer.
- Trocar o gerenciador de processos de PM2 para outro runtime.
- Reboot real do SRV-1 sem janela aprovada.
- Restart de XRDP em sessao RDP ativa sem aprovacao explicita.
- Auditoria completa de storage nos 3 servidores; esta fase cobre o hardening
  SRV-1 do governor/PM2 decorrente da nota do incidente.
