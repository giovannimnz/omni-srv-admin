---
phase: 14
padded: 14
slug: resource-governor-pm2-boot-hardening
name: Resource Governor + PM2 Boot Hardening
date: 2026-06-13
method: local-note-and-repo-inspection
status: complete
---

# Phase 14: Research

## Method

Research local baseada na nota live de 2026-06-13, leitura dos artefatos
`.planning`, grep de arquivos `srv1-ops`, docs operacionais e estado de
requirements. Nao houve consulta web porque o escopo e operacional/local.

## Source Note Findings

- A causa operacional principal foi combinacao de `default.target` bloqueado
  por jobs antigos, units PM2 inconsistentes e services do governor que ainda
  dependiam indiretamente de boot/login user target.
- `resource-governor-cgroup-init.service` falhava quando dependia de snapshot
  nao ativo.
- `resource-governor-patcher.py` e `resource-governor-cgroup-init.sh` divergiam
  do `resource-governor.env`; isso foi corrigido live e precisa permanecer
  versionado.
- `inviolable-watchdog.service` como `oneshot` com kill behavior padrao era
  perigoso para processos em background; `KillMode=process` virou decisao.
- `inviolable-watchdog.sh` relancava apps por units quebrados e precisava usar
  ecosystems reais.
- `pm2-ubuntu.service` apontava para `/home/ubuntu/ecosystem.atius.js`, arquivo
  inexistente.
- Dois PM2 daemons estavam presentes, e jobs user antigos ainda podiam prender
  `default.target`.

## Repo Findings

- `cli/omni/srv1_ops.py` ja reconhece scripts e units do governor/inviolable.
- `docs/operations/resource-governor.md` e `docs/operations/srv1-ops.md` sao os
  runbooks naturais para consolidar o fix.
- `modules/srv1-ops/systemd/` contem units versionadas para governor, slices e
  inviolable watchdog.
- `.planning/phases/09-mission-guardian/` ja tratava `resource-governor` e
  `inviolable-watchdog` como base operacional permanente; Phase 14 e uma fase
  de hardening/fechamento apos incidente, nao substitui Mission Guardian.

## Gaps to Close

1. **Boot graph:** garantir que governor/inviolable sobem mesmo se
   `default.target` estiver preso por PM2 ou backup antigo.
2. **PM2 canonical path:** declarar e implementar um unico caminho suportado
   para subir ATS/Horistic no boot.
3. **Stale jobs:** drenar ou substituir `ats-pm2.service`,
   `horistic-pm2.service` e `pm2-ubuntu.service` sem matar processos live.
4. **XRDP cgroup:** limpar leftover sem derrubar RDP, ou deixar documentado que
   exige janela.
5. **Status command:** `omni srv1 resource-status` deve apontar claramente
   divergencias entre slices, cgroups, PM2 jobs e runtime override.
6. **Runbook/rollback:** comandos de abort, restore e validacao precisam ficar
   em docs e vault.

## Risk Classification

- **High:** `pm2 kill`, `systemctl --user stop ats-pm2.service`,
  `systemctl --user stop horistic-pm2.service`, restart de `xrdp.service`,
  reboot do host.
- **Medium:** `systemctl --user daemon-reload`, enable/disable de units user,
  restart de services do governor/inviolable, alteracao de `pm2-ubuntu.service`
  com backup.
- **Low:** leitura de status, dry-run de installer, `bash -n`, `py_compile`,
  `git diff --check`, leitura de cgroups, geracao de runbook.

## Requirements Proposed

- RGP-01 a RGP-07 foram adicionados a `.planning/REQUIREMENTS.md` e mapeados
  para Phase 14 / M006.

## Planning Choice

Quatro planos:

- `14-01`: consolidar artefatos versionados e cobertura de status/install.
- `14-02`: canonizar PM2 e drenar jobs presos com gate.
- `14-03`: validar boot/login-linger, cgroups e cleanup XRDP-safe.
- `14-04`: runbook, rollback, pos-boot e documentacao Obsidian.
