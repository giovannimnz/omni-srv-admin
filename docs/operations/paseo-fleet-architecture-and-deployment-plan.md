---
title: Plano Arquitetural - Instalação, Configuração Multi-Host e Publicação do Paseo na Frota ATIUS
date: 2026-11-02
status: planned
tags:
  - paseo
  - fleet
  - landscape
  - apache
  - drg
  - plan
---

# PLAN.md: Instalação, Configuração Multi-Host e Publicação do Paseo na Frota ATIUS (srv-1 a 4)

**Status:** APROVAÇÃO PENDENTE (Plan-Only Gate)  
**Autoridade:** Orquestrador Central Soberano (`1db8d421-5cba-48c9-a245-ba475f0899cb`)  
**Worker Executor:** Sessão Paseo (`f597aebd-1392-487b-9818-0cd127a72117`)  
**Domínios Alvo:** `https://paseo.atius.io` e `https://paseo.atius.com.br`  
**Hub Central:** `atius-srv-4` (`10.4.0.14:37845`)

---

## 1. Topologia de Rede OCI DRG e Matriz de Portas Dedicadas

O runtime do Paseo será distribuído de forma padronizada em todos os 4 servidores principais da frota, com isolamento estrito de portas locais para evitar colisões e permitir controle granular via Landscape:

| Host | IP DRG Primário (Fase 46) | IP DRG Secundário / Legado | IP Público | Porta Paseo | Papel no Cluster Paseo |
|---|---|---|---|---|---|
| **`atius-srv-1`** | `10.1.0.11` | `10.11.1.11` | `137.131.190.161` | **`37815`** | Node Local + Edge Gateway Apache (Proxy Reverso / TLS / WebSocket) |
| **`atius-srv-2`** | `10.2.0.12` | `10.12.1.12` | `129.148.47.32` | **`37825`** | Node Local / Compute Host (Antigravity Desktop & Browser Headless) |
| **`atius-srv-3`** | `10.3.0.13` | `10.13.1.13` | `150.230.71.10` | **`37835`** | Node Local / Control Host (Vault & Landscape Server) |
| **`atius-srv-4`** | `10.4.0.14` | `10.14.1.14` | `164.152.48.22` | **`37845`** | **Paseo Central Server (Hub Principal / Backend Alvo / Relay)** |

---

## 2. Cronograma de Execução por Ondas (Waves GSD)

### Wave 1: Pré-Requisitos, Governança & Contenção de Recursos
- CPU Guardrail Mandatório ($\le 20\%$ total host CPU).
- Invariantes de `/etc/hosts` e Resolução DRG (`10.3.0.13`/`10.13.1.13 landscape.atius.com.br landscape.atius.io`).
- Verificação de conectividade simultânea via Landscape (`omni landscape computers`).

### Wave 2: Automação em Lote via Landscape Control-Plane (srv-1 a 4)
- Script versionado `modules/landscape-control-plane/scripts/fleet-paseo-install.sh` e registro no `manifest.json`.
- Bootstrap do Node.js 24 LTS via `fnm`.
- Instalação dos pacotes npm globais (`@getpaseo/cli@0.14.0`, `@getpaseo/server@0.14.0`, `paseo-agy-acp@2.7.2`).
- Sincronização do catálogo de skills (`~/.agents/skills` e `~/.paseo/skills` apontando para `~/.gemini/config/skills`).

### Wave 3: Parametrização dos Daemons & Systemd Units (Portas Customizadas)
- Arquivo `~/.paseo/config.json` parametrizado por host:
  - srv-1: porta 37815
  - srv-2: porta 37825
  - srv-3: porta 37835
  - srv-4: porta 37845 (Hub com CORS aberto para `paseo.atius.io`, `paseo.atius.com.br` e `app.paseo.sh`)
- Aplicação dos 3 patches de estabilidade v0.14.0 (`sessions.ts`, `identity.js`, `proxy.js`).
- Provisionamento das units systemd `paseo-daemon.service` com user `ubuntu`.

### Wave 4: Edge Gateway Apache & Paridade Dual-Domain (`atius-srv-1`)
- Criação e habilitação de `paseo.atius.io.conf` atendendo `paseo.atius.io` e alias `paseo.atius.com.br`.
- ProxyPass HTTP e WebSocket (`ws://10.4.0.14:37845/$1`) para o Hub Central.
- Headers canônicos: `RequestHeader set Origin "paseo://app"`, `X-Forwarded-Proto "https"`.
- Certificado TLS Wildcard Cloudflare DNS-01.

### Wave 5: Matriz de Verificação, Homologação & Rollback
- Testes locais com `curl` e `nc` nas portas dedicadas.
- Validação CLI: `paseo status` e `paseo provider ls`.
- Probes E2E em `https://paseo.atius.io` e `https://paseo.atius.com.br`.
- Procedimento documentado de rollback imediato por nó.
