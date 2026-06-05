# Roadmap: Omni Srv Admin (omni-srv-admin)

**Active Milestone:** M002 — Fork Sync Integration
**Milestone Goal:** fork-sync integrado como submodule + repo rebranded de omni-srv-admin para omni-srv-admin

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

**Total:** 7 phases | 39 requirements mapped | 36 requirements covered ✓

---

## M002: Fork Sync Integration (ACTIVE)

**Goal:** fork-sync integrado como submodule `modules/fork-sync/` + repo rebranded de `omni-srv-admin` para `omni-srv-admin` + fork-sync standalone arquivado.

**Why:** omni-srv-admin é o gestor central de servidores, aplicações GitHub e containers. fork-sync (CLI Python de sync multi-fork) pertence aqui como módulo nativo, não como repo separado.

**Depends on:** M001 (preparação de host + infra concluída)

**Links:**
- Context: `.planning/phases/08-rebrand-fork-sync-submodule/08-CONTEXT.md`
- Plan: `.planning/phases/08-rebrand-fork-sync-submodule/08-PLAN.md`

---

### Phase 8: Rebrand + fork-sync submodule

**Status:** 🟢 READY TO EXECUTE

**Goal:** Repo local rebranded + fork-sync como submodule vivo + fork-sync standalone arquivado.

**Requirements:** (nenhuma nova — integra requisitos existentes)

**Plans:** 2 plans
- [ ] 08-CONTEXT.md — 7 decisões locked (D-01 a D-07) + 5 gray areas
- [ ] 08-PLAN.md — 15 tasks sequenciais com 9 Must Haves (MH-1 a MH-9)

**Push Policy (D-06):**

| Operação | Auth | Comandos |
|---|---|---|
| Commit local | Auto | `git commit` |
| `gh repo rename` | Soft (clarified) | `gh repo rename giovannimnz/omni-srv-admin omni-srv-admin --yes` |
| `git remote set-url` | Auto | `git remote set-url origin ...` |
| `git push origin main` | Auto após rebrand commit | `git push origin main` |
| Push tag fork-sync | **Hard-gate** — pedir confirmação | `git push fork-sync v1.2.1-omni-archived` |
| Create release fork-sync | **Hard-gate** — pedir confirmação | `gh release create v1.2.1-omni-archived` |
| Archive fork-sync repo | **Hard-gate** — pedir confirmação | `gh repo archive giovannimnz/fork-sync --yes` |

**Success Criteria (9 Must Haves):**
- [ ] **MH-1:** GitHub repo `giovannimnz/omni-srv-admin` renomeado pra `giovannimnz/omni-srv-admin`
- [ ] **MH-2:** `git remote -v` mostra `https://github.com/giovannimnz/omni-srv-admin.git`
- [ ] **MH-3:** Zero `omni-srv-admin` ou `Omni Srv Admin` fora de `.planning/phases/`, `.planning/research/`, `git log`, `*.com.br`
- [ ] **MH-4:** `.gitmodules` presente com `path = modules/fork-sync`, `url = https://github.com/giovannimnz/fork-sync.git`
- [ ] **MH-5:** `modules/fork-sync/` populado (104 files, CLI, lib, projects)
- [ ] **MH-6:** `giovannimnz/fork-sync` arquivado (`isArchived: true`) + tag `v1.2.1-omni-archived`
- [ ] **MH-7:** Vault Obsidian com notas canônicas em `20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin/`
- [ ] **MH-8:** Working tree limpo (`git status --porcelain` vazio)
- [ ] **MH-9:** `git log --oneline | head -3` mostra commits claros rebrand+submodule

**Execution order:** Strict sequential (Tasks 01-10 → HARD-GATE CHECKPOINT → Tasks 11-15)
