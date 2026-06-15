---
phase: 14
padded: 14
slug: resource-governor-pm2-boot-hardening
name: Resource Governor + PM2 Boot Hardening
date: 2026-06-13
status: ready
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - RGP-01
  - RGP-02
  - RGP-03
  - RGP-04
  - RGP-05
  - RGP-06
  - RGP-07
---

# Phase 14: Resource Governor + PM2 Boot Hardening

## Goal

Fechar as pendencias de boot, cgroup, PM2 e runbook deixadas apos a correcao
live de 2026-06-13 no ATIUS-SRV-1, mantendo apps, bots, SSHD e XRDP
operacionais durante a execucao.

## Waves

- **Wave 1:** `14-01` consolida artefatos versionados e status/install.
- **Wave 2:** `14-02` e `14-03` podem rodar em paralelo apos `14-01`.
- **Wave 3:** `14-04` fecha runbook, rollback e documentacao depois de
  `14-02` e `14-03`.

## Plans

| ID | Name | Wave | Depends On | Status |
|----|------|------|------------|--------|
| [14-01](14-01-PLAN.md) | Versionar governor/inviolable e status/install coverage | 1 | - | complete |
| [14-02](14-02-PLAN.md) | PM2 boot canonicalization e stale jobs | 2 | 14-01 | ready |
| [14-03](14-03-PLAN.md) | Boot/login-linger, cgroups e XRDP-safe cleanup | 2 | 14-01 | ready |
| [14-04](14-04-PLAN.md) | Runbook, rollback e verificacao pos-boot | 3 | 14-02, 14-03 | ready |

## Cross-Cutting Constraints

- Criar snapshot de estado antes de qualquer mudanca live.
- Declarar impacto antes de mexer em PM2, XRDP ou jobs systemd presos.
- Qualquer acao que possa derrubar RDP ou trading exige gate humano explicito.
- Preferir dry-run, status e patch versionado antes de enable/restart.
- Nao gravar secrets em logs, `.planning`, repo ou vault.
- Preservar o backup de rollback:
  `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`.

## Final Acceptance Gate

- `systemctl --user list-jobs` sem `ats-pm2.service`,
  `horistic-pm2.service` ou `default.target` presos.
- `systemctl --user is-active resource-governor-patcher.service` retorna
  `active`.
- `systemctl --user is-active resource-governor-watchdog.service` retorna
  `active`.
- `systemctl --user is-active inviolable-watchdog.timer` retorna `active`.
- `omni srv1 resource-status` mostra perfil base/conservador coerente entre
  runtime override, slices e cgroups diretos.
- PM2 principal usa ecosystems reais; nenhum unit suportado aponta para
  `/home/ubuntu/ecosystem.atius.js`.
- RDP nao cai durante a execucao normal da fase.
- Runbook e rollback documentados em repo e Obsidian.
