---
phase: 14
padded: 14
slug: resource-governor-pm2-boot-hardening
name: Resource Governor + PM2 Boot Hardening
date: 2026-06-13
status: ready
wave: 1
depends_on: []
requirements_addressed:
  - RGP-01
  - RGP-02
  - RGP-03
  - RGP-04
  - RGP-05
  - RGP-06
  - RGP-07
  - RGP-08
  - RGP-09
  - RGP-10
  - M005-JENKINS-PODMAN
  - M005-JENKINS-AGENT
---

# Phase 14: Resource Governor + PM2 Boot Hardening

## Goal

Fechar as pendencias de boot, cgroup, PM2 e runbook deixadas apos a correcao
live de 2026-06-13 no ATIUS-SRV-1, mantendo apps, bots, SSHD e XRDP
operacionais durante a execucao. Tambem fecha a limpeza de dependencias
Docker-orfas em servicos que ja migraram para Podman (Jenkins) e estende
M005 com Jenkins agent rodando no cluster K3s.

## Waves

- **Wave 1:** `14-01` consolida artefatos versionados e status/install.
- **Wave 2:** `14-02` e `14-03` podem rodar em paralelo apos `14-01`.
- **Wave 3:** `14-04` fecha runbook, rollback e documentacao depois de
  `14-02` e `14-03`.
- **Wave 4:** `14-05` finaliza a remocao de dependencias Docker-orfas em
  servicos que ja migraram (Jenkins) e amarra o ciclo de validacao externa
  em `jenkins.atius.com.br`.
- **Wave 5:** `14-06` estende M005 com Jenkins agent Deployment no cluster
  K3s (substitui DinD por build pods efêmeros via Kubernetes plugin).

## Plans

| ID | Name | Wave | Depends On | Status |
|----|------|------|------------|--------|
| [14-01](14-01-PLAN.md) | Versionar governor/inviolable e status/install coverage | 1 | - | complete |
| [14-02](14-02-PLAN.md) | PM2 boot canonicalization e stale jobs | 2 | 14-01 | ready |
| [14-03](14-03-PLAN.md) | Boot/login-linger, cgroups e XRDP-safe cleanup | 2 | 14-01 | ready |
| [14-04](14-04-PLAN.md) | Runbook, rollback e verificacao pos-boot | 3 | 14-02, 14-03 | ready |
| [14-05](14-05-PLAN.md) | Jenkins + servicos orfaos: remover deps Docker e validar em dominio publico | 4 | 14-01 | complete |
| [14-06](14-06-PLAN.md) | Jenkins agent on K3s (M005 extension) | 5 | 14-05, M005-live | ready |

## Cross-Cutting Constraints

- Criar snapshot de estado antes de qualquer mudanca live.
- Declarar impacto antes de mexer em PM2, XRDP ou jobs systemd presos.
- Qualquer acao que possa derrubar RDP ou trading exige gate humano explicito.
- Preferir dry-run, status e patch versionado antes de enable/restart.
- Nao gravar secrets em logs, `.planning`, repo ou vault.
- Preservar o backup de rollback:
  `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`.
- Servicos que ja migraram para Podman nao podem manter bind mounts para
  `/var/run/docker.sock` ou `/usr/bin/docker` (Docker foi desinstalado);
  esses paths causam exit 125 (statfs ENOENT) no systemd.

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
- `https://jenkins.atius.com.br/` responde `x-jenkins: 2.541.3` e login form
  carrega o theme dark da marca.
- Runbook e rollback documentados em repo e Obsidian.
