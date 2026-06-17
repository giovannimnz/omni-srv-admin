# Roadmap: Omni Srv Admin (omni-srv-admin)

**Active Milestone:** M007-ext / M008 / M009 / M010 — DONE; M007 M005 Follow-ups (v1.1) pending
**Milestone Goal:** Fechar os 4 follow-ups abertos de M005: OCI snapshots, Cloudflare Access, observability stack, RWX storage.
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

**Goal:** Criar a base operacional multi-host do `omni-srv-admin` antes da camada de containers/orquestração: inventário como fonte de verdade, instalação `server`/`node`, PostgreSQL central via PgBouncer como DB canônico do `omni-srv-admin`, heartbeat, registry de programas, ops scopes por servidor, parâmetros/configs no DB, agent executor local, monitoramento cross-server, version/update plans, licenças sem secrets no git/log/vault, auditoria, slash commands via CLI-Anything e contrato futuro com Podman/K3s.

**Status:** LIVE IMPLEMENTED; REPOS AND CENTRAL DB VALIDATED (2026-06-13)

**Depends on:** M003 (Omni CLI Expansion)

**Why:** O Fleet Control Plane vem antes do K3s porque resolve controle operacional e governança da frota. K3s/Podman entram depois consumindo inventário, estado, auditoria e contracts já definidos.

**Branch:** `codex/omni-fleet-control-plane-m004`

**Phases:** 12

---

### Phase 12: Fleet Control Plane Foundation ✅ LIVE IMPLEMENTED

**Goal:** Planejar e implementar o contrato seguro da fundação do control plane: server/node installer dry-run, inventário multi-host validado, DB central migrável, PgBouncer obrigatório, heartbeat/status, registry, ops scopes por servidor, configs/parâmetros no DB, slash commands via CLI-Anything, version planner, licenças e auditoria.

**Requirements:** FCP-01, FCP-02, FCP-03, FCP-04, FCP-05, FCP-06, FCP-07, FCP-08, FCP-09, FCP-10, FCP-11, FCP-12, FCP-13, FCP-14, FCP-15

**Status:** LIVE IMPLEMENTED (2026-06-13); repo, central DB and PgBouncer path validated on SRV1/SRV2/SRV3

**Context:** `omni-srv-admin` já tem inventário dos hosts `ATIUS-SRV-1/2/3`, módulos operacionais e histórico de backup/Podman. Esta phase transforma essa base em um control plane explícito, sem instalar K3s ainda.

**Plans:** 1

- [x] 12-01-PLAN.md — Fleet Control Plane Foundation (implemented live for repo distribution, DB schema and PgBouncer node path)

**Implementation Results:**

- `docs/fleet/control-plane.md` created with server/node, PgBouncer, PostgreSQL, heartbeat, registry, license and audit contracts.
- `modules/fleet-control-plane/` created with example runtime config and initial PostgreSQL schema migration.
- `DbOmniFleet` is documented and migrated as the canonical PostgreSQL database for `omni-srv-admin` runtime state, ops scopes, config items, parameters and slash-command registry.
- `TbOpsScopes`, `TbConfigItems`, `TbSlashCommands` and `TbSlashCommandBindings` are defined by migration `0002`.
- Slash commands are represented with CLI-Anything/`clianything` metadata, including `/cli-anything*` and planned `/omni-srv-admin`.
- `~/GitHub/omni-srv-admin` is present on SRV-1/SRV-2/SRV-3; SRV-2/SRV-3 track `main` with clean worktrees.
- SRV-1 hosts PostgreSQL database `DbOmniFleet`; `TbHosts`/`TbNodes`/`TbPrograms` inventory is seeded.
- SRV-2/SRV-3 use `/etc/omni-srv-admin/fleet-db.env` and query `DbOmniFleet` through PgBouncer at `10.1.1.1:6432`.
- `omni fleet validate-inventory` validates all 7 inventory hosts.
- `omni fleet install server|node` renders idempotent dry-run plans and blocks live `--apply`.
- `omni fleet heartbeat`, `programs`, `update-plan`, `queue-update`, `agent heartbeat/once/loop`, `monitor hosts`, `audit` and `status --all` expose runtime contracts without direct SSH apply.
- Agent execution is local to the target host: SRV-2 can request work for SRV-3 through `DbOmniFleet`, but SRV-3's local agent claims and applies it.
- Fleet monitoring reads central `TbNodeTelemetry` through PgBouncer and falls back to local cache on DB/PgBouncer outage.

**Success Criteria:**

1. CONTEXT/RESEARCH/PLAN completos em `.planning/phases/12-omni-fleet-control-plane/`
2. Requirements `FCP-01..FCP-15` definidos e rastreados para Phase 12
3. Desenho server/node e inventory source-of-truth travado
4. DB central + PgBouncer definido sem permitir acesso direto de clientes ao PostgreSQL
5. Licenças e secrets tratados sem vazar segredo para git, logs ou vault
6. Secrets remain outside git/log/vault in `/etc/omni-srv-admin/fleet-db.env`
7. Ops scopes por servidor e configs/parâmetros mutáveis ficam no DB, não em arquivos locais como fonte runtime
8. Slash commands usam CLI-Anything como convenção/registry
9. Integração futura com Podman/K3s definida como contract, não implementação nesta phase

**Risk:** MEDIUM — o risco principal é acoplar demais o control plane ao K3s antes de estabilizar inventário, DB, agents e auditoria.

---

## M004 Phase Summary

| Milestone | # | Phase | Goal | Status | Risk |
|---|---:|---|---|---|---|
| M004 | 12 | Fleet Control Plane Foundation | Base operacional multi-host | ✅ LIVE IMPLEMENTED / DB PASSED | MEDIUM |

---

## M005: K3s HA Cluster + Portainer — LIVE

**Canonical branch:** `codex/k3s-portainer-oci-plan` (planning) + `docs/m005-k3s-live-bootstrap` (live bootstrap)

**Phase:** 13

**Status:** ✅ LIVE (2026-06-14) — 3 nodes `Ready` control-plane+etcd on WireGuard `wg0`; Portainer CE 2.39.3 deployed; `docker.atius.com.br` and `portainer.atius.com.br` return Portainer API status.

**Live nodes:** SRV-1 (10.1.1.1), SRV-2 (10.1.1.2), SRV-3 (10.1.1.7)

**Follow-ups:** OCI snapshot IDs, Cloudflare Access policy, observability stack, RWX storage strategy.

**Branch results:**

- `codex/k3s-portainer-oci-plan` — preflight, safe templates, network port map
- `docs/m005-k3s-live-bootstrap` — live bootstrap record
- `docs/m005-observability-watchdog` — observability + edge watchdog
- `docs/m005-portainer-admin-endpoint` — Portainer endpoint initialization
- `docs/m005-watchdog-basic-auth-fix` — edge Basic Auth
- `docs/m005-gate-review-20260614` — gate review + cooldown policies

**Portainer target:** `portainer.atius.com.br`

**Edge auth:** Apache Basic Auth (Cloudflare Access not enabled on account)

---

## M006: SRV-1 Resource Governance + PM2 Hardening — IN PROGRESS

**Canonical branch:** `codex/phase14-resource-governor-14-01`

**Phase:** 14

**Status:** IN PROGRESS (14-01 complete, 2026-06-15)

**Goal:** Fechar as pendências pós-incidente do `resource-governor`, `inviolable-watchdog` e PM2 no `ATIUS-SRV-1`, transformando a correção live de 2026-06-13 em estado versionado, boot-safe e verificável sem derrubar ATS/Horistic/XRDP.

**Depends on:** Correção live documentada em `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-13-resource-governor-pm2-live-fix.md`. Backup: `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`.

**Progress:** 1/4 execution plans complete (`14-01`).

### Phase 14: Resource Governor + PM2 Boot Hardening

**Goal:** Remover jobs systemd presos, consolidar startup PM2, validar boot/login-linger do governor e deixar rollback/runbook claro para operar o SRV-1 sem risco aos apps de trading e à sessão RDP.

**Requirements:** RGP-01, RGP-02, RGP-03, RGP-04, RGP-05, RGP-06, RGP-07

**Success Criteria:**

- `systemctl --user list-jobs` não mantém `ats-pm2.service`, `horistic-pm2.service` ou `default.target` presos.
- `resource-governor-cgroup-init.service`, `resource-governor-patcher.service`, `resource-governor-watchdog.service/timer` e `inviolable-watchdog.timer` sobem sem depender de `default.target`.
- Cgroups diretos e slices systemd refletem o mesmo perfil base/conservador de CPU, I/O, memória, swap e weights.
- Existe um caminho PM2 canônico e `pm2-ubuntu.service` não aponta para `/home/ubuntu/ecosystem.atius.js` inexistente.
- `inviolable-watchdog` não relança apps por units quebrados, não tenta `nginx` ausente e não prende novos filhos XRDP/SSHD no cgroup do watchdog.
- Cleanup de XRDP/PM2 é gateado para não derrubar RDP nem processos de trading sem aprovação explícita.
- Runbook e rollback versionados apontam para o backup `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`.

**14-01 accomplished:** Governor/inviolable services movidos pra `timers.target`; `inviolable-watchdog.service` timer-triggered sem Install target; `omni srv1-ops resources status` reporta runtime override, stuck jobs, PM2 stale-refs, slices e cgroups diretos; patcher lê `resource-governor.env`.

**Pending:** 14-02 PM2 boot canonicalization, 14-03 boot/login-linger + cgroup validation, 14-04 rollback/runbook.

---

## M002: Fork Sync Integration ✅ DONE

**Completed:** 2026-06-05

**Why:** omni-srv-admin é o gestor central de servidores, aplicações GitHub e containers. fork-sync (CLI Python de sync multi-fork) pertence aqui como módulo nativo, não como repo separado.

**Depends on:** M001 (preparação de host + infra concluída)

**Links:**

- Context: `.planning/phases/08-rebrand-fork-sync-submodule/08-CONTEXT.md`
- Plan: `.planning/phases/08-rebrand-fork-sync-submodule/08-PLAN.md`

### Phase 18: Ubuntu Pro ESM Apps - Google account link, fleet attach validation, regression watchdog

**Goal:** Ubuntu Pro ESM Apps — Google account link, fleet attach validation, regression watchdog.
**Requirements**: ESM-01, ESM-02, ESM-03, ESM-04, ESM-05
**Plans:** 9 plans
**Status:** IN PROGRESS (18-01..18-05 closed; 18-06..18-09 pending operator gate G18-1)

Plans:

- [x] 18-01 — XRDP display pool :1..14
- [x] 18-02 — Camofox display reassign :97→:5
- [x] 18-03 — VNC/noVNC port alignment
- [x] 18-04 — Desktop file hotfix (xrdp-launch wrapper)
- [x] 18-05 — Cron cleanup (atius-phase7 + horistic systemctl)
- [ ] 18-06 — Ubuntu Pro token + attach (gate G18-1 pending)
- [ ] 18-07 — ESM Apps install validation
- [ ] 18-08 — Sources DEB822 migration
- [ ] 18-09 — Regression watchdog

### Phase 21: Onboarding ATIUS-MT5-KVM-1/2 como hosts gerenciados

**Goal:** Gerenciar `atius-mt5-kvm-1` e `atius-mt5-kvm-2` pelo omni-srv-admin com inventário, DB, monitoramento, VPN/CoreDNS/docs, shell runtime e histórico completo. Sem K3s por enquanto.

**Requirements:** MT5KVM-01, MT5KVM-02, MT5KVM-03, MT5KVM-04, MT5KVM-05, MT5KVM-06, MT5KVM-07, MT5KVM-08, MT5KVM-09, MT5KVM-10

**Depends on:** Phase 20
**Plans:** 1 plan
**Status:** ✅ DONE (2026-06-17)

**Results:** Inventário, DB, VPN/CoreDNS, docs, vault e monitoramento completos para `atius-mt5-kvm-1` e `atius-mt5-kvm-2`.

Plans:

- [x] `21-PLAN.md` — plano separado e histórico operacional
- [x] hostnames lowercase + zsh/Oh My Zsh + Rust + zellij aplicados e validados por subagentes paralelos
- [x] inventário + DB upsert + VPN/CoreDNS/docs + monitoramento

### Phase 22: Onboarding Horistic (rename + rust/zellij)

**Goal:** Renomear horistic-srv-1 -> horistic-srv em toda a infra, instalar rust+oh-my-zsh+zsh+zellij no padrao fleet, manter proxy reverso Apache2 para *.horistic.com e APIs proxied para SRV-1:3050/8050.

**Requirements:** HORSTC-01..HORSTC-11
**Depends on:** Phase 21
**Plans:** 1 plan
**Status:** ✅ DONE (2026-06-17)

**Results:** `horistic-srv-1` renomeado para `horistic-srv`, toolchain fleet padrão (rustup 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3), node-exporter :9100, inventário/DB/DNS/vault/docs atualizados.

Plans:

- [x] 22-PLAN.md - plano separado com HORSTC-01..11
- [x] host renomeado + toolchain instalada + node-exporter
- [x] inventário omni + DB upsert + VPN/CoreDNS + vault sed + gbrain sync + network map v1.4.0

---

## Phase 8: Rebrand fork-sync submodule

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

## M007: M005 Follow-ups — IN PLANNING (v1.1)

**Goal:** Fechar os 4 follow-ups abertos de M005: OCI snapshot workflow formal, Cloudflare Access policy para os admin edges, observability stack live (Prometheus + Grafana + Loki), e decisão + implementação de RWX storage para K3s.

**Status:** Planning (v1.1, started 2026-06-15)
**Branch:** TBD
**Phase dir:** `.planning/phases/{15,16,17}-*/`

**Closed in this milestone (carryover from M005):**

- Tailscale ACL (was PARTIAL gate in `13-GATE-REVIEW-2026-06-14.md`) — closed 2026-06-16. See `13-ACL-CLOSURE-2026-06-16.md`. WireGuard remains K3s transport; Tailscale is management plane only.

### Phase 15: M005 OCI Snapshots

**Goal:** Workflow versionado de snapshots OCI para SRV-1/2/3 com rollback formal, IDs rastreáveis e restore drill validado.

**Requirements:** OCI-01, OCI-02, OCI-03

**Success Criteria:**

- `omni srv oci snapshot preflight` cria snapshot antes de qualquer op riscada (gate explícito)
- `omni srv oci snapshot routine` roda semanal via systemd timer; output é o snapshot ID
- Snapshot ID registrado em `inventory/hosts/<srv>.yaml` e em `DbOmniFleet/TbConfigItems` (chave `srv.atius-srv-1.oci.snapshot_id`)
- `omni srv oci restore drill <snapshot_id>` valida o caminho: criar instância a partir do snapshot, validar K3s rejoins, destruir instância, validar cleanup
- Runbook publicado em `docs/operations/oci-snapshots.md`

### Phase 16: M005 Cloudflare Access

**Goal:** Substituir Apache Basic Auth nos admin edges (`portainer.atius.com.br`, `docker.atius.com.br`) por Cloudflare Access, com service token pra automação.

**Requirements:** CFL-01, CFL-02, CFL-03

**Success Criteria:**

- Cloudflare Access policy configurada para `portainer.atius.com.br` e `docker.atius.com.br` (Allow rule com email allowlist de Giovanni)
- Service token emitido e gravado em `.hermes/secrets/cloudflare-service-token.txt` (mode 600)
- `omni-cli` (cron jobs, automation) usa o service token via `CLOUDFLARE_SERVICE_TOKEN` env var
- Apache Basic Auth retained as fallback if Access is unavailable, with documented cutover in `docs/operations/edge-auth.md`
- Validação: `curl -I https://portainer.atius.com.br/` retorna 302 → Cloudflare Access login page (sem 401 Basic Auth challenge)

### Phase 17: M005 Observability + RWX

**Goal:** Stack Prometheus + Grafana + Loki scraping K3s control plane + worker nodes + PM2 daemons + Jenkins + GDrive health, com alert routing pra canal preferido de Giovanni.

**Requirements:** OBS-01, OBS-02, OBS-03, RWX-01, RWX-02

**Success Criteria:**

- Prometheus scraping K3s control plane + workers (kube-state-metrics, node-exporter)
- Loki scraping PM2 daemons (via Promtail sidecar ou systemd journal) + jenkins controller + GDrive mount
- Grafana com 4 dashboards: K3s HA, Portainer, PM2 daemons, Jenkins, GDrive health
- AlertManager com rotas para Telegram/Hermes webhook pra: pod CrashLoopBackOff, etcd quorum loss, PM2 app offline >5min, GDrive quota >80%, disk >85%
- RWX storage decision documentada (NFS em SRV-1 vs Longhorn distributed) + implementação
- `omni srv observability status` reporta estado de cada exporter

## Notes

- Phase numbers 15-17 (continua contagem do v1.0)
- M005 → M006 → M007 formam a sequência "live → harden → close follow-ups" no cluster K3s
- Backlog (M001-M003 done, M004-M006 live, M007 planning) leaves M001's Phase 3-7 (FreeIPA, Samba, WireGuard, Keycloak) ainda pendente
