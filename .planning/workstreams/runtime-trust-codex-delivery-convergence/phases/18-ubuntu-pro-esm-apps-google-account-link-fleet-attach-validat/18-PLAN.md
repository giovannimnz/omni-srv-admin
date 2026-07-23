---
phase: 18
milestone: M007-ext
title: "Ubuntu Pro ESM Apps - Google account link, fleet attach validation, regression watchdog"
date: 2026-06-16
status: planning
depends_on: phase 17
plans: 4
gates:
  - id: G18-1
    desc: "apt upgrade esm-apps+infra (live mutation, gated)"
  - id: G18-2
    desc: "Microsoft RDP funcional nos 3 SRVs pós-upgrade"
  - id: G18-3
    desc: "Google account link clarificado (UI step ou já feito)"
---

# Phase 18 — Ubuntu Pro ESM Apps + Fleet attach + Watchdog

## Goal

Garantir que os 3 SRVs (ATIUS-SRV-1, ATIUS-SRV-2, ATIUS-SRV-3) estão
attached ao Ubuntu Pro com `esm-apps` + `esm-infra` enabled, sources
em formato `.sources` (DEB822), account giovannimunizds@gmail.com,
e protegidos por watchdog de regressão (cron que valida attach +
esm-services e alerta se algo sair do estado desejado).

## Contexto

A Phase 18 começou emaranhada com o escopo XRDP/port pool
(18-01..18-05 = RDP/x11vnc/port collision fixes, todas concluídas
2026-06-16 com Microsoft RDP funcional nos 3 SRVs — ver
`18-XRDP-CLOSURE-2026-06-16.md`). Os planos 18-06..18-09 são
o escopo "puro" ESM Apps.

Contexto herdado do Phase 13 (K3s HA):
- `13-CONTEXT.md` L134-163 definiu gate ESM Apps.
- SRV-1/2 estavam attached, SRV-3 não (naquele momento). 2026-06-16
  confirmou que SRV-3 JÁ está attached (free personal subscription).
- Subscription ID canônico: `cAXjb3pG50fBZTE05MHBl78XOuMqbtLzN5YPUxYNK7RM`.
- Account SSO atual nos 3: `munizgiovanni@hotmail.com` (id
  `aAH_y4bKKPBfZzQvmD6ZNQm3bs92bg531e_dBe469s5A`).
- Alvo do plano: account `giovannimunizds@gmail.com` (gmail pessoal
  do Giovanni, canônico para rclone, Camofox, etc).

## Plans

| Plan | Status | Descrição |
|------|--------|-----------|
| 18-01 | ✅ DONE (RDP) | Diagnóstico RDP + x11vnc collision |
| 18-02 | ✅ DONE (RDP) | Fix RDP SRV-1 |
| 18-03 | ✅ DONE (RDP) | Limpar x11vnc.service legacy SRV-1 + websockify 6080 |
| 18-04 | ✅ DONE (RDP) | Auditar SRV-2 RDP pré-upgrade + x11vnc WAN |
| 18-05 | ✅ DONE (RDP) | KILL x11vnc SRV-2 (port 5900 WAN) + cleanup |
| 18-06 | ⏳ BLOCKED-parcial | Token + detach+reattach SRV-1/2/3 com conta giovannimunizds@gmail.com + converter `.list` → `.sources` |
| 18-07 | ⏸ GATED | apt upgrade (esm-apps+infra) live mutation — gate G18-1 |
| 18-08 | ⏸ GATED | Validar pós-upgrade RDP/Microsoft nos 3 SRVs — gate G18-2 |
| 18-09 | ✅ PARTIAL | Atualizar STATE + GATE-REVIEW + vault log (pode rodar em paralelo) |

## Estado atual (2026-06-16 — baseline 18-06-AUDIT)

| Item | SRV-1 | SRV-2 | SRV-3 |
|------|-------|-------|-------|
| `pro` version | 37.2ubuntu~24.04 | 37.2ubuntu~24.04 | 37.2ubuntu~24.04 |
| `attached` | true | true | true |
| `account.name` | munizgiovanni@hotmail.com | munizgiovanni@hotmail.com | munizgiovanni@hotmail.com |
| `account.id` | aAH_y4bKKPBfZzQvmD6ZNQm3bs92bg531e_dBe469s5A | (same) | (same) |
| `contract.id` | cAXjb3pG50fBZTE05MHBl78XOuMqbtLzN5YPUxYNK7RM | (same) | (same) |
| `esm-apps` | enabled | enabled | enabled |
| `esm-infra` | enabled | enabled | enabled |
| `ubuntu-esm-apps.*` | `.list` (legacy) | `.list` (legacy) | `.sources` (DEB822) |
| `ubuntu-esm-infra.*` | `.list` (legacy) | `.list` (legacy) | `.sources` (DEB822) |
| `~/secrets/ubuntu-pro-token.txt` | exists (mode 600, 30 bytes) | ? | ? |
| `apt update` clean? | needs check | needs check | needs check |

## Gaps vs target

1. **Account email mismatch**: hotmail.com vs gmail.com (giovannimunizds)
2. **Sources format**: SRV-1/2 em legacy `.list`, SRV-3 já em DEB822 `.sources`
3. **Watchdog regression**: NÃO existe (cron/script que valide ESM
   services + sources format + account email)
4. **Token distribution**: SRV-2/3 podem não ter `~/secrets/ubuntu-pro-token.txt`

## Sub-tasks

### 18-06 — Account + sources + token

Pré-requisitos:
- [ ] User clarifica o que significa "Google account link"
      (a) criar nova subscription sob giovannimunizds@gmail.com
          no dashboard Ubuntu Pro + transferir/atachar;
      (b) já existe a subscription sob giovannimunizds e o attach
          é só re-bind (token novo);
      (c) SSO Google → Ubuntu Pro dashboard.

Ações (idempotentes, read-mostly):
- [ ] Copiar `~/secrets/ubuntu-pro-token.txt` para SRV-2/SRV-3
      (mode 600, mesmo hash).
- [ ] SRV-1/2: converter `ubuntu-esm-{apps,infra}.list` → `.sources`
      (DEB822). Idempotente: `pro refresh && pro enable esm-apps
      esm-infra` reconstrói o sources.
- [ ] Decidir detach+reattach vs só `pro refresh` (gate implícito
      em re-attach — verificar com user).
- [ ] Criar `omni srv pro status --fleet` (CLI) que retorna a tabela
      de estado dos 3 SRVs.

### 18-07 — apt upgrade esm-apps+infra (GATED)

Pré-flight (read-only, pode rodar):
- [ ] `apt list --upgradable` filtrado por pacotes `esm-apps`/`esm-infra`.
- [ ] Listar CVEs cobertos pelos upgrades: `pro cves` + `pro cve <id>`.
- [ ] Backup pre-upgrade: snapshot OCI + `dpkg --get-selections` salvo
      em `~/.backups/phase-18/<srv>-<date>/`.

Gated (gate G18-1):
- [ ] User autoriza "pode dar apt upgrade".
- [ ] `sudo apt upgrade -y` em cada SRV (sequencial, 1 por vez, com
      cooldown 5min entre — mesma lição do rclone rate limit).
- [ ] Validar `pro status` pós-upgrade.

### 18-08 — Validar pós-upgrade (GATED G18-2)

- [ ] Microsoft RDP login nos 3 SRVs (gate de aceitação: usuário
      confirma que consegue logar).
- [ ] `pro status` pós-upgrade mostra esm-apps+infra enabled.
- [ ] `apt list --upgradable` pós-upgrade mostra 0 pacotes esm pendentes.

### 18-09 — Documentação + watchdog (pode rodar em paralelo)

- [ ] Criar `docs/operations/ubuntu-pro-fleet.md` (canônica
      operação/attach/upgrade/rollback).
- [ ] Criar `modules/srv1-pro-watchdog/` (systemd timer que roda
      `omni srv pro status --fleet` a cada 6h, alerta se algo sair
      do target).
- [ ] Vault log: `60-LOGS/2026-06-16-phase-18-esm-apps-audit.md`.
- [ ] Atualizar STATE.md.

## Cross-refs

- `13-CONTEXT.md` L134-163 (gate ESM original)
- `13-GATE-REVIEW-2026-06-14.md` L64/L109 (gate review)
- `30-RECURSOS/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` §7.4
- `18-HANDOFF-RDP.md` (handoff histórico da sessão RDP)
- `18-XRDP-CLOSURE-2026-06-16.md` (closure XRDP)
- `60-LOGS/2026-06-16-port-pool-rdp-camofox-network-doc.md` (sessão
  onde o phase foi re-numerado 18-01..18-09)

## Rollback

- 18-06 detach+reattach: reversível (`pro detach` + attach com token
  anterior; o token atual está em `~/secrets/ubuntu-pro-token.txt`).
- 18-07 apt upgrade: reversível com `apt-get -V package=version`
  por pacote. Snapshot OCI pré-upgrade disponível (gate 13-oci-rollback).
- 18-08 não é destrutivo.
- 18-09 é só docs.
