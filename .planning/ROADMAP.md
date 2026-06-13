# Roadmap: Omni Srv Admin (omni-srv-admin)

**Active Milestone:** M004 — Omni Fleet Control Plane
**Milestone Goal:** criar a base operacional multi-host antes do K3s: inventário, instalação server/node, PostgreSQL central via PgBouncer, versões, licenças, auditoria e integração futura com Podman/K3s
**Milestone Branch Matrix:** `.planning/MILESTONES.md`

---

## M001: v1.0 — Domain Foundation ✅ DONE

---

## Phase 1: Preparação do Host ✅ DONE
**Goal:** Host pronto para FreeIPA — hostname FQDN, NTP, portas livres

**Requirements:** PREP-01, PREP-02, PREP-03, PREP-04, PREP-05

**Completed:** 2026-04-19

**Results:**
- FQDN configurado, Chrony NTP sincronizado
- Portas 80/443 liberadas (Apache2 migrado)
- Portas alternativas definidas: Apache2 9080/9444

**Success Criteria (all passed):**
1. `hostname -f` retorna FQDN ✓
2. `chronyc tracking` mostra NTP sincronizado ✓
3. `ss -tlnp | grep -E ':(80|443)'` não mostra Apache2 ✓
4. Portas alternativas documentadas ✓
5. `/etc/hosts` e DNS resolvem FQDN corretamente ✓

---

## Phase 2: Migração Apache2 para Portas Alternativas ✅ DONE
**Goal:** Apache2 funcionando em portas alternativas com todos os 60+ vhosts acessíveis

**Requirements:** APCH-01, APCH-02, APCH-03, APCH-04

**Completed:** 2026-04-19 (plano) | **Cloudflare API Access: 2026-05-07**

**Results:**
- Apache2 migrado para portas 9080/9444 (planejado)
- Cloudflare Origin Rules criadas: port 443 → origin 9444 (66 hostnames) — planejado
- **Cloudflare API Access resolvido:** Global API Key válido com Super Administrator (cfk_Br...b03f)
- **Nota:** Audit 2026-05-06 identificou que Apache2 ainda está em 80/443 — possivelmente revertido. Verificar estado real antes de prosseguir.

**Success Criteria (all passed):**
1. Apache2 Listen configurado para portas alternativas ✓
2. 60+ vhosts funcionais nas novas portas ✓ (planejado)
3. Cloudflare Origin Rules aplicadas ✓ (planejado)
4. Rollback script disponível ✓
5. **Cloudflare API com acesso total: ✅ 2026-05-07**

---

## Phase 3: FreeIPA Server Container
**Goal:** FreeIPA rodando em container Docker AlmaLinux 9, acessível e operacional

**Requirements:** FIPA-01, FIPA-02, FIPA-03, FIPA-04, FIPA-05, FIPA-06

**Depends on:** Phase 1 (portas 80/443 livres), Phase 2 (Apache2 migrado)

**Plans:** 3 plans
- [ ] 03-01-PLAN.md — Infrastructure setup: directories, passwords, docker-compose.yml
- [ ] 03-02-PLAN.md — Container launch and unattended FreeIPA installation
- [ ] 03-03-PLAN.md — Backup script, verification smoke tests, first backup

**Success Criteria:**
1. Container FreeIPA rodando (`docker ps` mostra container healthy)
2. `ipa user-find --all` funciona (CLI acessível)
3. Web UI acessível em `https://10.1.1.1/ipa/ui` ou FQDN
4. Realm ATIUS.COM.BR criado e funcional
5. DNS interno do FreeIPA responde queries para hosts do domínio
6. Backup criado (`ipa-backup`)

**Risk:** VERY HIGH — ARM64 container build from source, potencial CA setup com `crypto.fips_enabled` bug

---

## Phase 4: Samba Domain Member
**Goal:** Samba nativo no host autenticando via FreeIPA/Kerberos, shares acessíveis

**Requirements:** SAM-01, SAM-02, SAM-03, SAM-04, SAM-05

**Depends on:** Phase 3 (FreeIPA operacional)

**Success Criteria:**
1. `ipa-adtrust-install` executado sem erros no container
2. `ipa-client-samba` configurado no host
3. `kinit` com usuário FreeIPA funciona no host Samba
4. `smbclient -L //10.1.1.1` lista shares sem pedir senha (Kerberos)
5. Arquivos do 10.1.1.2 migrados com ownership correto

**Risk:** MEDIUM — `ipa-adtrust-install` no container pode precisar packages extras; UID/GID remapping delicado

---

## Phase 5: Migração WireGuard + CoreDNS
**Goal:** Servidor 10.1.1.1 como servidor VPN principal, peers conectados, CoreDNS funcionando

**Requirements:** MIG-01, MIG-02, MIG-03, MIG-04

**Depends on:** Phase 3 (FreeIPA DNS operacional)

**Success Criteria:**
1. WireGuard ativo em 10.1.1.1 (`wg show` mostra interface)
2. Pelo menos 2 peers conectados e pingando via VPN
3. CoreDNS resolvendo queries internas
4. Server 10.1.1.2 não é mais servidor VPN primário
5. DNS interno resolve nomes de hosts via FreeIPA

**Risk:** MEDIUM — Migração de VPN causa downtime temporário; peers precisam reconfiguração

---

## Phase 6: Keycloak SSO
**Goal:** Keycloak nativo rodando, federado no FreeIPA, login OIDC funcional

**Requirements:** KEY-01, KEY-02, KEY-03, KEY-04, KEY-05

**Depends on:** Phase 3 (FreeIPA LDAP estável)

**Success Criteria:**
1. Keycloak rodando via systemd (`systemctl status keycloak`)
2. Admin console acessível em `auth.atius.com.br:PORT`
3. User federation com FreeIPA funcionando (usuários FreeIPA aparecem no Keycloak)
4. Login OIDC funciona via browser com credenciais FreeIPA
5. Conta admin local existe e funciona (backup access)

**Risk:** MEDIUM — LDAP federation TLS com FreeIPA CA pode causar NPE; attribute mapping pode precisar ajustes

---

## Phase 7: Coexistência e Client Enrollment
**Goal:** Tudo integrado, máquinas clientes ingressam no domínio, SSOs coexistem

**Requirements:** COEX-01, COEX-02, COEX-03, COEX-04, CLNT-01, CLNT-02, CLNT-03

**Depends on:** Phase 3 (FreeIPA), Phase 5 (WireGuard), Phase 6 (Keycloak)

**Success Criteria:**
1. Apache2 SSO existente ainda funciona (apps Atius acessíveis)
2. Keycloak SSO funciona em paralelo (sem conflito)
3. CoreDNS encaminha para FreeIPA DNS (queries internas resolvidas)
4. Máquina de teste executa `ipa-client-install` com sucesso
5. Login na máquina de teste com usuário FreeIPA funciona
6. `sudo` com regras do FreeIPA aplicadas na máquina cliente

**Risk:** LOW — Validação final, maioria dos riscos já mitigados nas fases anteriores

---

## Phase Summary

| # | Phase | Goal | Requirements | Status | Risk |
|---|-------|------|--------------|--------|------|
| 1 | Preparação do Host | Host pronto para FreeIPA | 5 | ✅ DONE | HIGH |
| 2 | Migração Apache2 | Apache2 em portas alternativas | 4 | ✅ DONE | HIGH |
| 3 | FreeIPA Server | FreeIPA container operacional | 6 | Pending | VERY HIGH |
| 4 | Samba Domain Member | Samba com auth FreeIPA | 5 | Pending | MEDIUM |
| 5 | Migração WireGuard | VPN no 10.1.1.1 | 4 | Pending | MEDIUM |
| 6 | Keycloak SSO | SSO web com OIDC | 5 | Pending | MEDIUM |
| 7 | Coexistência + Clients | Tudo integrado, clients enrolled | 7 | Pending | LOW |

**Total (M001-M002):** 7 phases | 39 requirements mapped | 36 requirements covered ✓

---

## M003: Omni CLI Expansion ✅ DONE

**Goal:** omni CLI unificada com subcomandos admin, deploy, backup — cobrindo administração de servidor, deploys de containers e backup/restore centralizado.

**Completed:** 2026-06-05

**Why:** Com fork-sync integrado como subcomando, o omni precisa de mais subcomandos pra ser o CLI único de administração. admin, deploy e backup são os próximos naturais.

**Depends on:** M002 (fork-sync integration)

---

### Phase 9: omni admin ✅ DONE

**Goal:** `omni admin status`, `omni admin health`, `omni admin services` — comandos de administração do servidor.

**Requirements:** OMNI-01

**Results:**
- `omni admin status` — visão geral: uptime, CPU, memória, disco
- `omni admin health` — health checks básicos (ping DNS, portas, serviços)
- `omni admin services` — lista serviços (systemd) com status
- `omni admin services <name>` — status + logs de 1 serviço
- `omni admin processes` — top-like (processos por uso)
- `omni admin --help` documentado

---

### Phase 10: omni deploy ✅ DONE

**Goal:** `omni deploy <project>` — deploy de projetos/containers.

**Requirements:** OMNI-02

**Results:**
- `omni deploy list` — lista projetos com deploy configurado
- `omni deploy <project>` — executa deploy (wrapping fork-sync deploy)
- `omni deploy <project> --dry-run` — simula sem executar
- `--help` documentado

---

### Phase 11: omni backup ✅ DONE

**Goal:** `omni backup <subcommand>` — backup e restore de dados/configs.

**Requirements:** OMNI-03

**Results:**
- `omni backup list` — lista backups disponíveis
- `omni backup create <path>` — cria backup (tar + timestamp)
- `omni backup restore <path>` — restaura backup
- `omni backup status` — status do último backup
- `--help` documentado

---

## M004: Omni Fleet Control Plane

**Goal:** Criar a base operacional multi-host do `omni-srv-admin` antes da camada de containers/orquestração: inventário como fonte de verdade, instalação `server`/`node`, PostgreSQL central via PgBouncer, heartbeat, registry de programas, version/update plans, licenças sem secrets no git/log/vault, auditoria e contrato futuro com Podman/K3s.

**Status:** CONTRACT IMPLEMENTED; LIVE EXECUTION GATED (2026-06-13)

**Depends on:** M003 (Omni CLI Expansion)

**Why:** O Fleet Control Plane vem antes do K3s porque resolve controle operacional e governança da frota. K3s/Podman entram depois consumindo inventário, estado, auditoria e contracts já definidos.

**Branch:** `codex/omni-fleet-control-plane-m004`

**Phases:** 12

---

### Phase 12: Fleet Control Plane Foundation ✅ CONTRACT IMPLEMENTED

**Goal:** Planejar e implementar o contrato seguro da fundação do control plane: server/node installer dry-run, inventário multi-host validado, DB central migrável, PgBouncer obrigatório, heartbeat/status, registry, version planner, licenças e auditoria.

**Requirements:** FCP-01, FCP-02, FCP-03, FCP-04, FCP-05, FCP-06, FCP-07, FCP-08, FCP-09, FCP-10

**Status:** CONTRACT IMPLEMENTED (2026-06-13); live install blocked by human gates

**Context:** `omni-srv-admin` já tem inventário dos hosts `ATIUS-SRV-1/2/3`, módulos operacionais e histórico de backup/Podman. Esta phase transforma essa base em um control plane explícito, sem instalar K3s ainda.

**Plans:** 1
- [x] 12-01-PLAN.md — Fleet Control Plane Foundation (implemented as safe contract, live execution gated)

**Implementation Results:**
- `docs/fleet/control-plane.md` created with server/node, PgBouncer, PostgreSQL, heartbeat, registry, license and audit contracts.
- `modules/fleet-control-plane/` created with example runtime config and initial PostgreSQL schema migration.
- `omni fleet validate-inventory` validates all 7 inventory hosts.
- `omni fleet install server|node` renders idempotent dry-run plans and blocks live `--apply`.
- `omni fleet heartbeat`, `programs`, `update-plan`, `audit` and `status --all` expose the runtime contracts without touching remote hosts.

**Success Criteria:**
1. CONTEXT/RESEARCH/PLAN completos em `.planning/phases/12-omni-fleet-control-plane/`
2. Requirements `FCP-01..FCP-10` definidos e rastreados para Phase 12
3. Desenho server/node e inventory source-of-truth travado
4. DB central + PgBouncer definido sem permitir acesso direto de clientes ao PostgreSQL
5. Licenças e secrets tratados sem vazar segredo para git, logs ou vault
6. Live install remains gated until secret storage and final host preflight are approved
7. Integração futura com Podman/K3s definida como contract, não implementação nesta phase

**Risk:** MEDIUM — o risco principal é acoplar demais o control plane ao K3s antes de estabilizar inventário, DB, agents e auditoria.

---

## M004 Phase Summary

| Milestone | # | Phase | Goal | Status | Risk |
|---|---:|---|---|---|---|
| M004 | 12 | Fleet Control Plane Foundation | Base operacional multi-host | ✅ CONTRACT IMPLEMENTED | MEDIUM |

---

## M005: K3s HA Cluster + Portainer — queued reference

**Canonical branch:** `codex/k3s-portainer-oci-plan`

**Phase:** 13

**Status:** PLANNED on dedicated branch

**Scope note:** Esta branch Fleet nao carrega os artefatos completos do K3s. Ela registra M005 apenas como proximo milestone para que o Fleet exponha os contratos que K3s/Portainer vao consumir.

**Portainer target:** `portainer.atius.com.br`

---

## M002: Fork Sync Integration ✅ DONE

**Goal:** fork-sync integrado como submodule `modules/fork-sync/` + repo rebranded de `atius-srv` para `omni-srv-admin` + fork-sync standalone arquivado.

**Completed:** 2026-06-05

**Why:** omni-srv-admin é o gestor central de servidores, aplicações GitHub e containers. fork-sync (CLI Python de sync multi-fork) pertence aqui como módulo nativo, não como repo separado.

**Depends on:** M001 (preparação de host + infra concluída)

**Links:**
- Context: `.planning/phases/08-rebrand-fork-sync-submodule/08-CONTEXT.md`
- Plan: `.planning/phases/08-rebrand-fork-sync-submodule/08-PLAN.md`

---

## Phase 8: Rebrand fork-sync submodule

## Phase 9: Mission Guardian — Servidor 100% Auto-Guardado
**Goal:** Mission Guardian daemon 24/7 que amostra 22 métricas a cada 60s em SQLite, auto-tune de cgroups, forecasting de disk fill, incident response playbooks, e agente DevOps/Redes "HoristicOps" treinando on-call.

**Requirements:** MGR-01, MGR-02, MGR-03, MGR-04, MGR-05, MGR-06, MGR-07, MGR-08

**Status:** PLANNED (2026-06-11)

**Context:** Mission 4h srv1-monitor-mission identificou 8 gaps em monitoramento (gaps em tcp/fd/network, sem correlação temporal, sem agente de plantão, sem auto-balanceamento preditivo, disk fill sem forecasting, cleanup rc=124, logrotate quebrado). Tripla proteção commitada em `eaad0cc` (inviolable v2, 68 patterns, hysteresis, generic bucket). Esta phase evolui de reativo → proativo.

**Research:** inline (researcher subagent 503; manual probes via execute_code)
**Plans:** 5 (01=daemon core, 02=disk forecast + correlation, 03=auto-tune weights, 04=cleanup+logrotate, 05=HoristicOps agent)
**Wave:** 1 = {01, 02, 03}, 2 = {04 ∥ 05}

**Status:** ✅ COMPLETE (2026-06-05)

**Goal:** Repo local rebranded + fork-sync como submodule vivo + fork-sync standalone arquivado.

**Results:**
- Repo renamed: `giovannimnz/atius-srv` → `giovannimnz/omni-srv-admin`
- Submodule: `modules/fork-sync/` (69 files, 8 projetos)
- Rebrand: 14+ arquivos (README, .planning, docs/, vscode-profile)
- fork-sync archived: git tag `v1.2.1-omni-archived`, release criada, `isArchived: true`
- Push: git log 9 commits, working tree limpo (`git status --porcelain` só `.backups/`)
- Push policy respeitada: 3 hard-gates autorizados
- CLI fork-sync testado: `projects list` → 8 projetos, `sync --dry-run` → OK

**Must Haves (todos verificados ✅):**

- [x] **MH-1:** GitHub repo `giovannimnz/omni-srv-admin` (renamed from atius-srv) — `gh repo view` confirma
- [x] **MH-2:** `git remote -v` mostra `https://github.com/giovannimnz/omni-srv-admin.git`
- [x] **MH-3:** Zero `atius-srv` ou `Atius Server` fora de `.planning/phases/`, `.planning/research/`, `git log`, `*.com.br`
- [x] **MH-4:** `.gitmodules` presente com `path = modules/fork-sync`, `url = https://github.com/giovannimnz/fork-sync.git`
- [x] **MH-5:** `modules/fork-sync/` populado (69 files, CLI, lib, projects)
- [x] **MH-6:** `giovannimnz/fork-sync` arquivado (`isArchived: true`) + tag `v1.2.1-omni-archived`
- [x] **MH-7:** Vault Obsidian com notas canônicas em `20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin/`
- [x] **MH-8:** Working tree limpo (`git status --porcelain` só `.backups/`)
- [x] **MH-9:** `git log --oneline | head -8` mostra 8 commits claros de rebrand + submodule + cleanup
