---
phase: 23
title: "Omni Fleet Governance com Landscape complementar"
date: 2026-06-24
status: context
depends_on:
  - phase 12
  - phase 16
  - phase 17
  - phase 18
  - phase 20
  - phase 22
requirements:
  - GOV-01
  - GOV-02
  - GOV-03
  - GOV-04
  - GOV-05
  - GOV-06
  - GOV-07
  - GOV-08
  - GOV-09
  - GOV-10
  - GOV-11
---

# Phase 23 — Omni Fleet Governance com Landscape complementar

## Decisao de direcao

Implementar Landscape self-hosted como camada complementar de administracao das
maquinas Ubuntu, porque o consumo esperado cabe na infra e traz controle
operacional adicional. O alvo e usar:

- Cockpit como console web por host, apenas para operacao interativa e break-glass.
- Landscape como painel oficial/complementar para administracao de maquinas
  Ubuntu, pacotes, updates, security/compliance pratico e visibilidade de frota.
- Omni Fleet Control Plane como sistema central de inventario, programas,
  desired state, update plans, auditoria, agentes locais e integracao com o
  estado do Landscape.
- Portainer/K3s como camada de administracao do cluster e workloads.
- Prometheus/Grafana/Loki/Portainer/K3s/fork-sync como camadas ja
  implementadas ou planejadas para observability, containers e versionamento.

## Pergunta original

Com a infra ja montada no `omni-srv-admin`, Cockpit + Omni consegue substituir
100% do que Landscape faria para gestao de programas, versionamento coletivo,
updates e afins?

Resposta atualizada: Cockpit sozinho nao. Cockpit + Omni cobrem boa parte da
paridade pratica, mas a decisao mudou para tambem operar Landscape self-hosted.
Landscape entra para dar mais seguranca no controle das maquinas Ubuntu; Omni
continua sendo o contrato proprio de automacao/auditoria e K3s/Portainer seguem
responsaveis pelo cluster.

## Estado local relevante

- Phase 12 criou `DbOmniFleet`, `TbHosts`, `TbNodes`, `TbPrograms`,
  `TbVersions`, `TbUpdatePlans`, `TbAuditEvents`, `TbNodeTelemetry`,
  `TbFleetCommands` e o modelo de agent local.
- `docs/fleet/control-plane.md` define que update execution deve passar por
  `queue-update` e pelo `omni fleet agent` local do host alvo.
- `cli/omni/fleet.py` ja expoe `programs`, `update-plan`, `queue-update`,
  `agent heartbeat/once/loop`, `monitor hosts` e `audit`.
- `cli/omni/managed_apps.py` + `modules/managed-apps/configs/programs.json`
  ja modelam `programs`, `repositories`, `policies` e `customizations` para
  Chromium/Firefox/Bitwarden, incluindo force-install do Bitwarden e policy
  `chromium-google-browser-defaults` para busca Google/homepage
  `https://google.com.br`; com validacao local e probe remoto de fleet, essa
  superficie deve ser tratada como seed reutilizavel, nao como trabalho paralelo
  descartavel.
- Phase 16 ja tem Cloudflare Access planejado para admin edges, mas o live
  cutover ainda depende do dashboard Cloudflare.
- Auditoria antiga aponta Cockpit como risco quando exposto na porta `9090`
  sem SSO/Access.
- Phase 17 fornece a direcao de observability central.
- Phase 18 cobre Ubuntu Pro/ESM, mas o watchdog/documentacao final ainda
  precisa ser consolidado.
- `fork-sync` cobre parte do versionamento coletivo de repos/forks.
- Documentacao oficial atual de Landscape self-hosted descreve quickstart,
  manual, Juju e LXD; Podman/K3s entram como alvo de empacotamento da nossa
  infra com gate de validacao e fallback para LXD/VM/Juju se necessario.

## Fora de escopo

- Reimplementar internals do Landscape ou criar clone de Landscape.
- Assumir suporte Canonical, SLA, compliance formal ou multi-tenant SaaS.
- Usar Cockpit como control plane central.
- Usar Landscape como orquestrador primario de workloads Kubernetes.
- Executar mutacoes live sem approval, snapshot/preflight quando aplicavel e
  auditoria.

## Gates

- G23-1: Cockpit nao deve ficar acessivel publicamente sem Access/SSO/VPN.
- G23-2: Qualquer update fleet-wide deve continuar local ao host alvo via
  allowlist e update plan aprovado.
- G23-3: Secrets de Ubuntu Pro, Cloudflare, DB, tokens ou licencas ficam fora
  de git, `.planning`, logs e vault.
- G23-4: A phase deve produzir matriz de responsabilidades documentada:
  Landscape para maquinas Ubuntu, Omni Fleet para governanca/auditoria propria,
  Cockpit para break-glass, K3s/Portainer para cluster/workloads.
- G23-5: Deploy Landscape em Podman/K3s exige gate de recursos, portas 80/443,
  certificado, Ubuntu Pro/licenca, registro de clientes, backup/rollback e
  fallback suportado se o empacotamento nao ficar estavel.
