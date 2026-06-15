# Omni Srv Admin (omni-srv-admin)

## What This Is

Repositório central de configuração e provisionamento do servidor Atius (10.1.1.1 Oracle Cloud). Contém scripts de instalação padrão, configurações de rede (iptables, WireGuard), antiviral, tema desktop, e o módulo de Infraestrutura de Domínio Linux (FreeIPA + Keycloak + Samba) para autenticação centralizada e SSO web.

## Core Value

Servidor Atius sempre provisionado, documentado e operante — com identidade centralizada para login unificado de todas as máquinas Linux e SSO web funcionando em paralelo.

## Requirements

### Validated

- ✓ **SRV-01**: Script `setup.sh` executa provisionamento base do servidor — tooling, usuários, permissões
- ✓ **SRV-02**: Regras iptables salvas e restauráveis em `/etc/iptables/`
- ✓ **SRV-04**: ~25 containers Docker rodando (Portainer, Plane, n8n, Open WebUI, Paperclip, Jenkins)
- ✓ **SRV-05**: PostgreSQL 17 (porta 8745) e MongoDB (porta 27017) operacionais
- ✓ **SRV-06**: PM2 gerenciando API, frontend, webhooks e bots de trading
- ✓ **CLI-01**: `omni` CLI instalado via pip editable (`cli/`)
- ✓ **CLI-02**: `fork-sync` integrado como subcomando `omni fork-sync`
- ✓ **CLI-03**: `fork-sync` lib-only (sem entry point próprio)
- ✓ **CLI-04**: 9 forks gerenciados via `omni fork-sync projects list`

### Active

#### M007: M005 Follow-ups (Phase 15-17)
- [ ] **OBS-01**: Observability stack live (Prometheus + Grafana + Loki) scraping K3s control plane + worker nodes
- [ ] **OBS-02**: Dashboards for K3s HA, Portainer, PM2 daemons, Jenkins, GDrive backup health
- [ ] **OBS-03**: Alert routing to Giovanni's preferred channel (Telegram/Hermes) for: pod CrashLoopBackOff, etcd quorum loss, PM2 app offline, GDrive quota >80%, disk >85%
- [ ] **CFL-01**: Cloudflare Access policy configured for `portainer.atius.com.br` and `docker.atius.com.br` (replaces Apache Basic Auth)
- [ ] **CFL-02**: Service token issued for omni-cli automation that needs to bypass Access
- [ ] **CFL-03**: Apache Basic Auth retained as fallback if Access is unavailable, with documented cutover
- [ ] **OCI-01**: OCI snapshot script for SRV-1/2/3 — `preflight` creates snapshot before risky ops; `routine` weekly snapshots to ATIUS-SRV-OCI bucket
- [ ] **OCI-02**: Snapshot ID registered in `inventory/hosts/<srv>.yaml` and `DbOmniFleet` for rollback traceability
- [ ] **OCI-03**: Restore drill validated from snapshot (start a stopped node and verify K3s rejoins)
- [ ] **RWX-01**: RWX storage decision for K3s: NFS server on SRV-1 or Longhorn distributed
- [ ] **RWX-02**: PVC backup ops for any StatefulSet using RWX

#### Módulo: Domain Infrastructure (domain-infrastructure/)
- [ ] **FIPA-01**: FreeIPA instalado e configurado no servidor 10.1.1.1 (LDAP + Kerberos + CA) — container AlmaLinux 9
- [ ] **FIPA-02**: Máquinas Linux ingressam no domínio FreeIPA (ipa-client-install)
- [ ] **FIPA-03**: Usuários centrais gerenciados no FreeIPA com grupos e permissões
- [ ] **FIPA-04**: DNS interno do FreeIPA integrado com rede WireGuard (10.1.1.0/24)
- [ ] **KKEY-01**: Keycloak instalado no OS em 10.1.1.1, federado no LDAP do FreeIPA
- [ ] **KEY-02**: Login SSO funcional via OIDC em `auth.atius.com.br`
- [ ] **SAM-01**: Samba configurado com autenticação via FreeIPA/Kerberos
- [ ] **SAM-02**: Compartilhamentos de arquivos acessíveis por máquinas no domínio
- [ ] **MIG-01**: WireGuard migrado de 10.1.1.2 para 10.1.1.1
- [ ] **MIG-02**: Samba migrado de 10.1.1.2 para 10.1.1.1
- [ ] **COEX-01**: SSO existente no Apache2 (~/GitHub/Atius-Capital/ats) NÃO é afetado durante implementação
- [ ] **COEX-02**: Ambos SSO (Apache2 e Keycloak) coexistem sem conflito

#### Módulo: Omni CLI Unificado
- [ ] **OMNI-01**: `omni admin` — comandos de administração do servidor (status, health, services)
- [ ] **OMNI-02**: `omni deploy` — deploy de projetos/containers (wrapping fork-sync deploy)
- [ ] **OMNI-03**: `omni backup` — backup e restore de dados/configs
- [ ] **OMNI-04**: Documentação e --help completos para todos subcomandos

#### Módulo: Server Setup (base)
- [ ] **SET-01**: `setup.sh` documentado e idempotente
- [ ] **SET-02**: Procedimento de rollback para cada alteração de configuração de rede

### Out of Scope

- Horistic (~/GitHub/Atius-Capital/horistic) — projeto separado com domínio próprio
- Migração de apps existentes para Keycloak — foco na infra primeiro
- Integração com Windows/Mac — ambiente 100% Linux
- FreeIPA nativo no Ubuntu — bug #1875114 impede; container é a solução

## Context

### Ambiente Atual

- **10.1.1.1** (este servidor): Atius apps (PM2: API, web, webhooks, bots, DIVAP), ~25 containers Docker, PostgreSQL 17, MongoDB, Apache2 com 60+ vhosts
- **10.1.1.2**: WireGuard VPN + CoreDNS + Samba existente (será migrado para 10.1.1.1)
- **10.1.1.3**: Apache2 para Horistic
- **Rede WireGuard**: 10.1.1.0/24
- **Domínio**: atius.com.br no Cloudflare

### Stack Existente

- Ubuntu 22.04 (Oracle Cloud Infrastructure, ARM64)
- Node.js 24 + Python 3.11 via NVM/uv
- Fastify (API port 8015) + Next.js (frontend port 3015)
- PM2 + Jest + Playwright
- Apache2 como reverse proxy com JWT SSO custom
- Docker + containerd

## Constraints

- **[Compatibilidade]**: SSO existente no Apache2 (~/GitHub/Atius-Capital/ats) NÃO pode ser afetado — coexistência obrigatória
- **[Portas]**: Apache2 movido para portas alternativas (9080/9444) para liberar 80/443 ao FreeIPA
- **[FreeIPA]**: Rodará em container Docker AlmaLinux 9 (não existe freeipa-server no Ubuntu)
- **[Hostname]**: FreeIPA requer FQDN — hostname deve ser `omni-srv-admin-1.atius.com.br`
- **[Rede]**: Todas as máquinas acessíveis via WireGuard 10.1.1.0/24
- **[DNS]**: CoreDNS existente precisa coexistir com DNS do FreeIPA (BIND interno)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FreeIPA no Docker (AlmaLinux 9) | `freeipa-server` não existe no Ubuntu 22.04 (bug #1875114) | — Pending |
| Keycloak nativo no OS (Java 21) | Instalação direta via apt, gerenciado por systemd | — Pending |
| FreeIPA como servidor de identidade | Login de máquina + Kerberos para Samba integrados | — Pending |
| Keycloak para SSO web federado no FreeIPA LDAP | SSO separado do Apache2, coexistência até migração completa | — Pending |
| Samba com auth via FreeIPA/Kerberos | Integração nativa com identidade centralizada | — Pending |
| Apache2 movido para 9080/9444 | FreeIPA precisa 80/443; 8080 já ocupado por Docker | ✓ Good |
| Horistic excluído do escopo | Domínio próprio, projeto independente | ✓ Good |
| domain-infrastructure como módulo do omni-srv-admin | Unificação do repositório servidor | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-06 after merge with domain-infrastructure .planning*
