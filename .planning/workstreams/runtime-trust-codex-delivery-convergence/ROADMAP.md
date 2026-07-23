# Roadmap: Omni Srv Admin (omni-srv-admin)

**Active Milestone:** v1.7 — Internal DNS and DRG Canonicalization
**Milestone Goal:** Tornar DNS interno, nomes de maquinas e endpoints de servicos DRG/OCI-first, mantendo `wg100` apenas como fallback e removendo `10.1.1.0/24` de qualquer caminho ativo.
**Milestone Branch Matrix:** `.planning/MILESTONES.md`
**Requirements:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md`
**Execution order:** planning/source-of-truth convergence -> `oci-admin` DRG dependency gate -> internal DNS/resolver cutover -> fallback boundaries and durable closeout

---

## Historical Phase Registry (01-27)

These phases remain in their original numbers because their directories,
commits, runbooks and incident evidence are historical identifiers. They are
listed here so GSD health and operators can distinguish retained history from
orphaned planning. Superseded means a later canonical phase owns any remaining
work; it does not erase the earlier implementation evidence.

## Phase 01: Preparacao do Host

**Status:** Complete - historical foundation. Retroactive validation is in
`.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/01-preparacao-do-host/01-VALIDATION.md`.

## Phase 02: Migracao Apache2 para Portas Alternativas

**Status:** Complete - historical foundation; retained as executed evidence.

## Phase 03: FreeIPA Server Container (Legacy Plan)

**Status:** Superseded by Phases 33-34. The incomplete legacy plans are kept as
research history and are not in the active execution queue.

## Phase 08: Rebrand and Fork-Sync Integration

**Status:** Complete - M002 historical delivery.

## Phase 09: Mission Guardian / Omni CLI Expansion

**Status:** Archived into M003. Later fleet-control and production-guard phases
own current behavior; unsummarized plans are validation debt, not active work.

## Phase 12: Omni Fleet Control Plane

**Status:** Complete - live implementation validated under M004.

## Phase 13: K3s HA and Portainer OCI

**Status:** Complete base rollout. Deferred cloud rollback/observability gates
are tracked separately and do not reopen the bootstrap phase.

## Phase 14: Resource Governor and PM2 Boot Hardening

**Status:** Complete base hardening. Remaining operational follow-ups are
tracked by their owning production phases.

## Phase 15: M005 OCI Snapshots

**Status:** Procedurally complete; real restore drills remain explicit live
gates in the runbook.

## Phase 16: M005 Cloudflare Access

**Status:** Procedurally complete; dashboard-side publication remains a gated
operation.

## Phase 17: M005 Observability and RWX

**Status:** Procedurally complete; production provisioning remains a gated
follow-up.

## Phase 18: Ubuntu Pro / ESM Apps Legacy Track

**Status:** Superseded by Phases 28-29, which contain the canonical four-host
upgrade and validation evidence.

## Phase 19: Fleet Standardization

**Status:** Complete.

## Phase 20: Podman Networking Standardization

**Status:** Complete.

## Phase 21: MT5 KVM Fleet Onboarding

**Status:** Complete for the delivered onboarding scope; later network blocks
remain inventory state, not unfinished Phase 21 execution.

## Phase 22: Horistic Rename and Rust/Zellij

**Status:** Complete.

## Phase 23: Omni Fleet Governance Legacy Plan

**Status:** Superseded by canonical governance Phases 30-32. Retained plans are
historical design input and are not executable queue entries.

## Phase 24: Production Recovery Guard Foundation (Legacy Number)

**Status:** Complete implementation source; canonized as Phase 37.

## Phase 25: Production Guard Repair Engine (Legacy Number)

**Status:** Complete implementation source; canonized as Phase 38.

## Phase 26: Production Guard Boot/Login Protocol (Legacy Number)

**Status:** Complete implementation source; canonized as Phase 39.

## Phase 27: Production Guard Horistic Remote and Rename Drift (Legacy Number)

**Status:** Complete implementation source; canonized as Phase 40.

## Milestone v1.2 Carry-over

The v1.2 phases below remain valid as canonized history. v1.3 and Phase 45
shipped, while unfinished work from Phase 42 and Phase 44 now continues only
through the ordered v1.8 phases 50 and 47 respectively.

## Phase 28: G18 Ubuntu Pro/ESM Fleet Gates ✅ COMPLETE

**Goal:** Consolidar estado Ubuntu Pro/ESM dos SRV-1/SRV-2/SRV-3/horistic-srv, preparar upgrade com backup/checkpoint e travar todos os gates antes de qualquer apt upgrade live.

**Requirements:** G18-01, G18-02
**Depends on:** v1.1 shipped, Phase 18 context
**Status:** Complete
**Risk:** HIGH — apt/ESM em hosts remotos com XRDP/PM2/K3s exige gate explicito.

**Plans:** 2/2 plans complete

- [x] 28-01-PLAN.md
- [x] 28-02-PLAN.md

- [x] 28-01 — Read-only Pro/ESM inventory, token/account/attach audit and backup manifest
- [x] 28-02 — Upgrade runbook, per-host gate checklist and rollback protocol

**Success Criteria:**

1. SRV-1/SRV-2/SRV-3/horistic-srv tem estado Ubuntu Pro/ESM documentado por host.
2. Token/account/attach status e apt sources DEB822 estao claros sem vazar secrets.
3. Snapshots/backups/checkpoints exigidos antes de upgrade estao listados e testados como preflight.
4. Nenhum `apt upgrade` live roda sem confirmacao explicita do operador.
5. Rollback e smoke tests pos-upgrade estao prontos para Phase 29.

---

## Phase 29: G18 Controlled Upgrade, RDP and Landscape SaaS Validation

**Goal:** Executar o upgrade ESM Apps/infra com gates, validar RDP nos 4 servidores e confirmar Landscape SaaS com hosts online.

**Requirements:** G18-02, G18-03, G18-04, G18-05
**Depends on:** Phase 28
**Status:** Complete
**Risk:** HIGH — pode afetar acesso remoto e servicos live.

**Plans:** 2/2 plans complete plus operational extensions

- [x] 29-01 — Gated apt upgrade execution and per-host smoke matrix
- [x] 29-02 — Microsoft RDP, Landscape SaaS and regression watchdog validation

**Success Criteria:**

1. [x] Apt upgrade executado apenas depois de checkpoint aprovado.
2. [x] Microsoft RDP/XRDP validado nos SRV-1/SRV-2/SRV-3/horistic-srv apos upgrade.
3. [x] Landscape SaaS mostra SRV-1/SRV-2/SRV-3/horistic-srv online ou registra blocker acionavel.
4. [x] PM2, K3s e Apache edges continuam operacionais; observability permanece yellow e foi diferido.
5. [x] Regressao pos-upgrade virou artefato repetivel em `29-02-G18-REGRESSION-WATCHDOG.md`.

**Closeout:** Microsoft RDP confirmed by operator; XRDP restarted host by host; apt drift remediated to `upgradable_count=0` on all four hosts; OCI ingress TCP 6554 for Landscape self-hosted resolved with scoped SRV1 NSG. Warnings deferred: SRV1/SRV2 root disks at 86% and observability yellow.

---

## Phase 29.1: Obsidian ARM64 AppImage pilot without Snap on atius-srv-1 (INSERTED)

**Goal:** Validar no `atius-srv-1` uma instalacao ARM64 do Obsidian sem Snap, preservando integralmente `~/GitHub/obsidian-vault/` e deixando instalacao, update, rollback, desktop launcher e futura replicacao sob gerenciamento versionado.
**Requirements:** GOV-03, GOV-04, GOV-05
**Depends on:** Phase 29
**Status:** Complete
**Risk:** HIGH — envolve app desktop Electron, perfil/local data e documentos do vault; nenhuma acao pode remover, mover ou sobrescrever notas.
**Plans:** 0 plans

**Canonical refs:**

- `/home/ubuntu/.codex/attachments/82b37bfc-2559-40ad-9b0a-ff8657f079d3/deep-research-obsidian-arm64-install.md` — pesquisa anexada sobre Obsidian ARM64 AppImage no Ubuntu ARM64.
- `docs/operations/managed-apps.md` — padrao atual de apps gerenciados sem Snap, fontes, wrappers, politicas e verificacao.

**Success Criteria:**

1. O vault `~/GitHub/obsidian-vault/` permanece intacto, com backup/manifest antes de qualquer teste visual.
2. Obsidian roda no `atius-srv-1` a partir de fonte ARM64 nao-Snap aprovada, com launcher CLI e desktop repetiveis.
3. Update/rollback do binario nao altera nem apaga conteudo do vault.
4. O estado instalado fica verificavel por comando local e preparado para futura replicacao, mas sem aplicar nos demais servidores nesta fase.

**Plans:**

- [ ] TBD (run /gsd-plan-phase 29.1 to break down)

## Phase 30: Landscape/Omni Governance Operating Model

**Goal:** Definir o modelo operacional entre Landscape, Omni Fleet, Cockpit, K3s/Portainer e observability, com responsabilidades, acesso e fallback.

**Requirements:** GOV-01, GOV-02, GOV-07
**Depends on:** Phase 29
**Status:** Complete
**Risk:** MEDIUM — decisoes erradas aqui duplicam control planes ou expõem consoles administrativos.

**Plans:** 1 plan

- [x] 30-01 — Governance responsibility matrix, access model and fallback runbook

**Success Criteria:**

1. [x] Matriz Landscape/Omni/Cockpit/K3s/Portainer/Observability publicada.
2. [x] Cockpit e Landscape nao substituem Omni Fleet como fonte central de inventario/auditoria.
3. [x] Modelo de acesso usa Access/SSO/VPN e nao expoe consoles admin diretamente.
4. [x] Fallback SaaS/self-hosted/LXD/VM/Juju/Omni-only esta documentado.

**Closeout:** Published `docs/fleet/landscape-omni-governance.md`; Landscape self-hosted is the durable Ubuntu machine-management endpoint, Landscape SaaS is fallback/reference, Omni Fleet remains governance/audit/source-of-truth, Cockpit is break-glass only, K3s/Portainer own workloads, and observability remains read-only signal plane.

---

## Phase 31: Omni Fleet Collectors and Desired-State Profiles

**Goal:** Implementar ou consolidar collectors reais de programas/pacotes/repositorios/policies/customizations e desired-state profiles com drift detectavel.

**Requirements:** GOV-03, GOV-04, GOV-05
**Depends on:** Phase 30
**Status:** Complete
**Risk:** MEDIUM — precisa respeitar mudancas paralelas em managed-apps/fork-sync/dark-theme.

**Plans:** 2 plans

- [x] 31-01 — Program/package/repository/policy/customization collectors
- [x] 31-02 — Desired-state profiles, update-plan approval and audit trail

**Success Criteria:**

1. [x] Omni Fleet reporta versoes reais por host usando fonte confiavel.
2. [x] Profiles cobrem packages/programs/repositories/policies/customizations.
3. [x] Drift e update-plan aparecem em CLI/DB sem aplicar mudanca automatica.
4. [x] Aprovacao e auditoria por host/scope ficam rastreaveis.

**Closeout:** Added read-only collectors, `omni fleet agent collect-programs`, governance schema `0004_governance_profiles.sql`, managed-apps desired-state profile rendering, and tests. Tests were added but not run during this pass.

---

## Phase 32: CVE/USN Reporting and Landscape Parity

**Goal:** Expor status CVE/USN/repository profile e fechar paridade operacional Landscape/Omni para priorizacao de patches.

**Requirements:** GOV-06, GOV-07
**Depends on:** Phase 31
**Status:** Complete
**Risk:** MEDIUM — dados incompletos podem induzir patching errado.

**Plans:** 1 plan

- [x] 32-01 — CVE/USN/repository reporting and Landscape parity dashboard/runbook

**Success Criteria:**

1. [x] CVE/USN/repository profile status fica visivel por host.
2. [x] Landscape e Omni tem limites/overlaps claros para patch governance.
3. [x] Prioridades de patch ficam acionaveis sem exigir deploy self-hosted prematuro.
4. [x] Runbook indica quando usar SaaS, self-hosted ou Omni-only.

**Closeout:** Added read-only Ubuntu Pro security report command, Landscape parity command, `TbSecurityFindings` schema and `docs/fleet/landscape-parity.md`. Tests were added but not run during this pass.

---

## Phase 33: FreeIPA Foundation and Host Prep

**Goal:** Retomar Domain Infrastructure preparando FreeIPA sem quebrar Apache, WireGuard, CoreDNS, K3s, PM2 ou Cloudflare edges.

**Requirements:** DOM-01, DOM-02
**Depends on:** Phase 32
**Status:** Complete
**Risk:** VERY HIGH — FreeIPA em ARM64/container e portas/DNS/CA sao sensiveis.

**Plans:** 2 plans

- [x] 33-01 — FreeIPA host prep, port/DNS/CA preflight and container build path
- [x] 33-02 — FreeIPA launch, realm bootstrap, backup and read-only smoke tests

**Success Criteria:**

1. [x] Portas, DNS, FQDN, NTP e CA validados antes do container.
2. [x] FreeIPA roda em container AlmaLinux 9 ou blocker tecnico fica documentado com fallback.
3. [x] Realm, LDAP/Kerberos, DNS interno e backup tem smoke test.
4. [x] Apache/Cloudflare/K3s/PM2 nao sofrem mutacao destrutiva sem gate.

**Checkpoint:** Direct host install rejected. Prefer isolated FreeIPA container/VM on `atius-srv-3` only after FQDN, realm, dedicated IP/network model, DNS authority/forwarding and backup/rollback are approved.

**Closeout:** Private FreeIPA foundation is live on `atius-srv-3` as Podman container `freeipa-atius`, FQDN `ipa.atius.internal`, realm `ATIUS.INTERNAL`, IP `10.89.53.10`, data `/srv/freeipa-atius/data`, root-only secrets and initial backup. No public ports were published. Phase 34 owns DNS coexistence and client enrollment.

---

## Phase 34: FreeIPA DNS and Client Enrollment

**Goal:** Integrar DNS FreeIPA/CoreDNS/WireGuard e ingressar maquinas Linux no dominio com rollback.

**Requirements:** DOM-03, DOM-04
**Depends on:** Phase 33
**Status:** Complete
**Risk:** HIGH — erro de DNS/VPN pode quebrar conectividade interna.

**Plans:** 2 plans

- [x] 34-01 — Disposable FreeIPA DNS/client enrollment gate
- [x] 34-02 — WireGuard/CoreDNS forwarding and first real Linux host enrollment

**Success Criteria:**

1. CoreDNS e FreeIPA DNS coexistem com encaminhamento previsivel.
2. Pelo menos uma maquina de teste ingressa no dominio.
3. Grupos/permissoes/sudo basicos funcionam via FreeIPA.
4. Rollback de DNS/client enrollment esta documentado.

**34-01 closeout:** Disposable AlmaLinux client `freeipa-client-test` enrolled successfully against `ipa.atius.internal` / `ATIUS.INTERNAL` inside the private FreeIPA Podman network. DNS returned `10.89.53.10`; `ipa-client-install`, `kinit admin`, and `ipa ping` passed. No real managed host was enrolled.

**34-02 closeout:** CoreDNS forwarding for `atius.internal` must now target the SRV-3 OCI/DRG private IP `10.13.1.13`; `atius-srv-3` privately gateways the required FreeIPA ports to the container at `10.89.53.10`; real-host enrollment succeeded on `atius-srv-3` as `atius-srv-3.atius.internal`; `getent`, `id`, `kinit admin`, `ipa ping`, and `sudo -l -U admin` passed. `horistic-srv` was explicitly deferred to the next controlled expansion step.

---

## Phase 35: Samba Kerberos Domain Member

**Goal:** Configurar Samba autenticando via FreeIPA/Kerberos e preservar shares/ownership durante migracao.

**Requirements:** DOM-05
**Depends on:** Phase 34
**Status:** Complete
**Risk:** MEDIUM — UID/GID, Kerberos e shares exigem rollback claro.

**Plans:** 1 plan

- [x] 35-01 — Samba domain member, Kerberos auth, shares migration and smoke tests

**Success Criteria:**

1. Samba autentica via FreeIPA/Kerberos.
2. Shares existentes continuam acessiveis com ownership correto.
3. `smbclient`/Kerberos smoke test passa em cliente de teste.
4. Rollback preserva acesso a arquivos.

**Closeout:** Samba moved from `atius-srv-2` to `atius-srv-1`; `srv1` joined `ATIUS.INTERNAL`, `ipa-client-samba` configured the host as member server, the `Shared` data was copied locally to `/srv/Shared`, the stable path `/home/ubuntu/Shared_smb` became a local bind mount, `srv2` Samba was disabled, and Kerberos access succeeded with `smbclient -k` using `ATIUS\\giovanni`.

---

## Phase 36: Keycloak SSO and Coexistence

**Goal:** Rodar Keycloak federado no FreeIPA LDAP e validar coexistencia com Apache SSO legado antes de qualquer migracao de apps.

**Requirements:** DOM-06, DOM-07
**Depends on:** Phase 35
**Status:** Complete
**Risk:** MEDIUM — OIDC/LDAP/TLS pode quebrar auth se acoplado cedo demais.

**Plans:** 1 plan

- [x] 36-01 — Keycloak LDAP federation, OIDC endpoint and Apache SSO coexistence smoke

**Success Criteria:**

1. Keycloak sobe com admin local e federacao LDAP FreeIPA.
2. OIDC em `auth.atius.com.br` tem smoke test.
3. Apache SSO legado continua funcional.
4. Nenhum app existente migra para Keycloak neste milestone sem fase futura.

**Closeout:** Keycloak 26.6.3 now runs natively on `atius-srv-1` with Java 21, private listener `127.0.0.1:8180`, Apache reverse proxy for `auth.atius.com.br`, LDAP federation to FreeIPA, imported user smoke for `giovanni`, and a working OIDC password-grant path through client `phase36-smoke`. Legacy Apache SSO/JWT endpoints stayed untouched.

---

## Phase 37: Production Guard Foundation Status/Doctor

**Goal:** Criar fundacao read-only do `production-guard` para ATS/Horistic cobrindo PM2, dump, namespaces, ecosystems, portas, endpoints, containers, timers e jobs systemd.

**Requirements:** PRG-01
**Depends on:** Phase 36, Phase 24-27 context
**Status:** Complete
**Risk:** MEDIUM — deve validar sem reiniciar servicos live.

**Plans:** 1 plan

- [x] 37-01 — PM2 boot, namespace, ecosystem, container/timer/job validator

**Success Criteria:**

1. `production-guard status/doctor` e read-only por default.
2. PM2 live vs dump, namespaces e ecosystems reportam JSON acionavel.
3. Portas/endpoints/container/timer/job checks nao disparam mutacao.
4. Contrato diferencia estado esperado de `waiting restart` dos launchers.

**Closeout:** The current `production-guard status/doctor` baseline is now canonical for Phase 37: read-only by default, structured JSON, PM2 live/dump parity and namespaces reported, with live blockers surfaced honestly as findings rather than repaired automatically.

---

## Phase 38: Production Guard Repair Engine

**Goal:** Adicionar repair seguro e gateado para PM2 apps/stacks, containers e systemd safe-starts, sempre dry-run por default.

**Requirements:** PRG-02, PRG-03
**Depends on:** Phase 37
**Status:** Complete
**Risk:** HIGH — repair live pode afetar trading/RDP se gates forem fracos.

**Plans:** 1 plan

- [x] 38-01 — Guarded repair planner, snapshot/checkpoint and apply confirmation

**Success Criteria:**

1. Repair default gera plano/diff sem aplicar.
2. Apply exige snapshot/checkpoint e confirmacao explicita.
3. `pm2 kill`, restart amplo e RDP/XRDP restart automatico sao bloqueados.
4. Logs redigem secrets e deixam auditoria acionavel.

**Closeout:** The guarded repair engine already in the repo is now canonical for Phase 38: `repair --dry-run --json` works, `apply_ready` remains blocked while critical health findings exist, and forbidden operations stay out of scope.

---

## Phase 39: Production Guard Boot/Login Protocol

**Goal:** Versionar protocolo de verificacao no reboot e login com units/timers read-only, docs operacionais e instalacao live gateada.

**Requirements:** PRG-04
**Depends on:** Phase 38
**Status:** Complete
**Risk:** MEDIUM — boot/login hooks nao podem prender user sessions ou quebrar XRDP.

**Plans:** 1 plan

- [x] 39-01 — Boot/login read-only verification units and runbook

**Success Criteria:**

1. Units/timers fazem verificacao read-only e nao reparo automatico.
2. Login/RDP/XRDP nao e reiniciado sem gate.
3. Runbook descreve instalacao, rollback e smoke tests.
4. Falhas viram alerta/status, nao mutacao automatica.

**Closeout:** The versioned boot/login protocol is now canonical for Phase 39: read-only systemd units/timer, runbook, rollback notes, and no automatic repair path.

---

## Phase 40: Production Guard Horistic Remote + Rename/Webhook Safe

**Goal:** Completar guard com validacao remota do Apache Horistic, drift de rename e contrato webhook-safe sem POST real para trading/Telegram.

**Requirements:** PRG-05, PRG-06, PRG-07
**Depends on:** Phase 39
**Status:** Complete
**Risk:** MEDIUM — validações remotas precisam evitar side effects.

**Plans:** 1 plan

- [x] 40-01 — Remote Horistic Apache checks, rename drift detector and webhook-safe validation

**Success Criteria:**

1. Apache remoto Horistic em `horistic-srv` e validado por unit/vhost/proxy target/porta.
2. Rename drift detecta host/pasta/repo/vhost legado sem mutar remoto.
3. Endpoint checks usam GET/HEAD e nunca POST real para trading/Telegram.
4. Webhook-safe validation documenta Circuit Breaker e split Telegram sem acionar producao.

**Closeout:** The Horistic remote Apache read-only checks, rename drift detector, and webhook-safe validation path are now canonical for Phase 40.

---

## Milestone v1.3: Local AI Embeddings and Semantic Retrieval

## Phase 41: Local AI Embeddings Gateway on horistic-srv

**Goal:** Implantar um backend local de embeddings em TEI no k3s usando `horistic-srv`, publicar o alias estável `embedding-gte-v1` no New API em `https://router.atius.com.br/v1`, validar compatibilidade OpenAI e documentar a migração segura para GBrain, Obsidian e Graphify.

**Requirements:** EMB-01, EMB-02, EMB-03, EMB-04, EMB-05, EMB-06, EMB-07, EMB-08
**Depends on:** Phase 29 runtime repair (`horistic-srv` joined as k3s worker), router-ai-atius/New API reachable, operator-provided New API token
**Status:** Complete - TEI/GTE live on `horistic-srv` in `ebeddings-local`, alias `embedding-gte-v1` validated, public smoke passed
**Risk:** HIGH — rota de embeddings mexe em gateway de IA, secrets, k3s e possíveis reindexações; mudar modelo/dimensão sem reindex quebra resultados.

**Canonical refs:**

- `/home/ubuntu/.codex/attachments/0811849f-3884-4179-a986-9c6516e5642e/deep-research-embbeding-k3s-local-model.md` — pesquisa anexada sobre modelos locais, TEI/Ollama, dimensões, k3s e integração GBrain/Obsidian/Graphify.
- `docs/operations/tailscale/GBRAIN-INGEST-PENDING.md` — histórico de GBrain via router; contém informação sensível legada e não deve ser copiado para novos artefatos.
- `modules/fork-sync/projects/atius-router/README.md` — contexto do fork New API/router-ai-atius e rotas OpenAI-compatible.
- `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` — guardas existentes de embeddings/provider routing no fork do router.
- `inventory/hosts/horistic-srv.yaml` — inventário do host alvo.

**Plans:** 1/1 plans complete

- [x] 41-01 — TEI/GTE backend, New API alias, OpenAI smoke and client migration contract
  - Completed 2026-07-04 and reconciled 2026-07-10: TEI canonical private endpoint is `10.21.1.21:3115`, runtime namespace `ebeddings-local`, router alias `embedding-gte-v1`, public POST `/v1/embeddings` smoke passed.

**Success Criteria:**

1. `POST https://router.atius.com.br/v1/embeddings` com `model=embedding-gte-v1` retorna embeddings para lote pt-BR autenticado.
2. A resposta validada mostra `quantidade=2`, `dimensoes=768`, `error=null` e `model` coerente com o alias público.
3. O canal interno do New API aponta para `http://10.21.1.21:3115`, não para o próprio router público.
4. O contrato `modelo + versão/digest + dimensão + normalização + chunking` fica documentado, e qualquer troca exige reembed/reindex.
5. GBrain/Obsidian/Graphify têm runbook de consumo sem gravar secrets em Git, `.planning`, Obsidian, logs ou shell history.

---

## Milestone v1.4: Atius-wide SSO and Login

## Phase 42: Atius-wide SSO Login on sso.atius.com.br

**Goal:** Criar `sso.atius.com.br` como subdominio canonico de login da Atius, usando o Keycloak ja validado em Phase 36 como provedor OIDC e migrando o ATS como primeira aplicacao de referencia sem quebrar o SSO/JWT legado.

**Requirements:** SSO-01, SSO-02, SSO-03, SSO-04, SSO-05, SSO-06
**Depends on:** Phase 36 Keycloak/FreeIPA coexistence, ATS current SSO/JWT cookie flow, Apache/Cloudflare edge inventory
**Status:** Historical partial; continuation moved to Phase 50. Plans 42-01 and 42-02 remain completed evidence, while 42-03 is not executed in place.
**Risk:** HIGH — mexe em identidade, cookies `.atius.com.br`, redirect/login cross-subdomain e apps de trading live; qualquer cutover deve ser gateado e reversivel.

**Canonical refs:**

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-CONTEXT.md` — decisoes de coexistencia Keycloak/FreeIPA e preservacao do Apache SSO legado.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md` — prova atual do Keycloak em `auth.atius.com.br`, OIDC smoke e FreeIPA federation.
- `.planning/codebase/CONCERNS.md` — risco existente de SSO depender de `x-forwarded-host` no Apache.
- `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts` — roteamento e protecao atual por subdominio no ATS.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/auth/index.js` — contrato atual de `auth-token`, refresh e logout global `.atius.com.br`.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/routes/token/index.js` — emissao atual do JWT/cookie no login.
- `/home/ubuntu/GitHub/Atius-Capital/ats/backend/server/middleware/permissions.js` — RBAC atual baseado em `is_admin` e `can_access_*`.
- `/home/ubuntu/GitHub/Atius-Capital/ats/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js` — smoke runtime atual do SSO/JWT.

**Plans:** 2/3 plans executed

- [x] 42-01-PLAN.md
- [x] 42-02-PLAN.md
- [ ] 42-03-PLAN.md

**Wave 0 — Validation foundation**

- [x] 42-01 — Wave 0 validation, secret hygiene and edge/header smoke scaffolding

**Wave 1 *(blocked on Wave 0 completion)* — ATS reference implementation**

- [x] 42-02 — ATS SSO facade, OIDC bridge and RBAC-compatible session

**Wave 2 *(blocked on Wave 1 completion)* — Edge, Keycloak and gated publication**

- [ ] 42-03 — Apache/app-host headers, Keycloak client checkpoint, no-secrets runbook, Obsidian worklog and manual publication gate

**Cross-cutting constraints:**

- No live Cloudflare/DNS/Apache reload/Keycloak/PM2/secret mutation during planning or before the plan's explicit gates.
- ATS backend DB permissions remain authoritative; Keycloak authenticates but does not grant trading/app access directly.
- Redirect, logout, app-host header, and secret-hygiene behavior must be tested before publication.
- Evidence in Git, `.planning`, Obsidian, logs, screenshots, and shell history must exclude secret values, raw tokens, cookie values, passwords, and client secrets.

**Success Criteria:**

1. `sso.atius.com.br` fica especificado como host canonico de login e nao como alias ambiguo de app.
2. Keycloak/OIDC, Apache/Cloudflare e ATS tem contrato de redirect/callback/logout documentado antes de qualquer mudanca live.
3. ATS continua aceitando o fluxo legado ate a ponte OIDC -> sessao local ou validacao nativa de token estar provada.
4. Permissoes `is_admin`, `can_access_backtest`, `can_access_dashboard`, `can_access_automation`, `can_access_trade` e `can_access_lc` continuam enforcement do backend.
5. Smoke tests cobrem login, refresh, logout global, redirect seguro e acesso cross-subdomain sem vazar secrets.
6. Rollback restaura login legado por `trade.atius.com.br/login` e cookies `.atius.com.br` sem mexer em usuarios FreeIPA/Keycloak.

**Current open gate:** `42-03` still needs the edge/publication checkpoint for Apache headers, Keycloak client publication, `sso.atius.com.br` gate, and the final no-secrets rollout/runbook closeout.

---

## Milestone v1.5: Codex Runtime and MCP Bootstrap Reliability

## Phase 43: Codex MCP Bootstrap Hardening on GIOVANNI-W11-PC

**Goal:** Endurecer o bootstrap local do Codex em `GIOVANNI-W11-PC`, separando MCPs always-on de MCPs pesados ou opcionais, eliminando timeouts e warnings evitaveis no start e criando um fluxo opt-in claro para browser, OCI, Cloudflare e knowledge MCPs.

**Requirements:** CDX-01, CDX-02, CDX-03, CDX-04, CDX-05, CDX-06
**Depends on:** `docs/operations/codex-runtime-standard.md`, `C:\Users\muniz\.codex\config.toml`, `C:\Users\muniz\.codex\mcp-patch.toml`, endpoint `https://mcp.atius.com.br/obsidian` with private backend `10.11.1.11:27124`, repo local `oracle-oci-mcp`
**Status:** Complete
**Risk:** HIGH - uma configuracao ruim aqui degrada a abertura do Codex inteiro, remove ferramentas do operador e pode induzir copia indevida de secrets para o Windows local.

**Canonical refs:**

- `docs/operations/codex-runtime-standard.md` - baseline atual de runtime Codex e perfis.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` - prova operacional do endpoint Obsidian REST/MCP na porta 27124.
- `C:\Users\muniz\.codex\config.toml` - configuracao atual com 18 MCPs e bootstrap base ruidoso.
- `C:\Users\muniz\.codex\mcp-patch.toml` - historico local da adicao em lote de MCPs sem key.
- `C:\Users\muniz\.codex\config.toml.bak-20260702T042936-0300-context-profiles` - backup conhecido anterior a mudancas recentes de runtime.

**Plans:** 2/2 plans complete

- [x] 43-01 - Lean base MCP baseline plus opt-in profile split
- [x] 43-02 - Prerequisite-aware hardening, explicit timeouts and cold-start smoke

**Success Criteria:**

1. O start default do Codex deixa de tentar subir MCPs opcionais que exigem token, VPN ativa, browser local ou stacks OCI quando o operador nao pediu essas superficies.
2. `cloudflare-api` sem `CF_GLOBAL_API_KEY` e `obsidian_rest` fora de alcance deixam de aparecer como ruido inevitavel no baseline diario; passam a ser tratados por perfil opt-in ou preflight explicito.
3. MCPs pesados baseados em `npx` e `uv` saem do bootstrap padrao ou recebem `startup_timeout_sec` explicito e command paths estaveis quando permanecerem justificados.
4. O runtime local ganha perfis nomeados para browser, OCI, Cloudflare, knowledge e lab-tools com instrucoes exatas de uso via `codex -p <profile>`.
5. Existe smoke repetivel para classificar falha como `disabled`, `missing-env`, `unreachable`, `slow-start` ou `ok`, sem imprimir secrets.

**Closeout:** The Windows Codex baseline is now lean by default, heavy MCPs moved to opt-in profiles, bootstrap smoke exists, `cloudflare-api` is no longer forced into daily startup, and the Cloudflare/Vault wrapper path was hardened without persisting secrets into repo artifacts.

---

## Milestone v1.6: Internal Service PKI and Fleet HTTPS

## Phase 44: Internal Service PKI and Fleet Trust

**Goal:** Criar um recurso do `omni-srv-admin` para PKI interna de servicos na VPN ATIUS: cada servidor gerenciado recebe leaf TLS proprio, todos confiam na CA interna, a instalacao e auditavel via Omni Fleet, e a validacao 4x4 prova HTTPS entre todos os hosts antes de qualquer migracao de servico.

**Requirements:** PKI-01, PKI-02, PKI-03, PKI-04, PKI-05, PKI-06, PKI-07, PKI-08
**Depends on:** Phase 31 Omni Fleet desired-state/update-plan foundation, Phase 41 TEI service context, `docs/operations/rdp-trust-pki.md`, `docs/security/atius-secrets-vaults.md`
**Status:** Historical partial; continuation moved to Phase 47. Plan 44-01 remains completed evidence, while 44-02 and 44-03 are not executed in place.
**Risk:** HIGH - mexe em CA interna, trust store, chaves privadas, HTTPS interno e validacao cross-host; erro aqui pode criar falsa confianca ou quebrar clientes TLS.

**Canonical refs:**

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/44-internal-service-pki-and-fleet-trust/44-CONTEXT.md` - decisoes de CA, key locality, escopo e hosts.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/44-internal-service-pki-and-fleet-trust/44-RESEARCH.md` - pesquisa em repo, Obsidian, GBrain e preflight remoto read-only.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/44-internal-service-pki-and-fleet-trust/44-VALIDATION.md` - contrato de validacao antes/durante/depois do rollout.
- `.planning/spikes/001-fleet-service-pki-trust-matrix/README.md` - spike de viabilidade e correcao leaf-vs-CA.
- `docs/operations/rdp-trust-pki.md` - precedente de PKI separado para XRDP/RDP, nao reutilizado como CA de servicos.
- `docs/security/atius-secrets-vaults.md` - regra de segredo/chave privada fora de Git, `.planning`, Obsidian, GBrain e logs.
- `inventory/hosts/atius-srv-1.yaml`, `inventory/hosts/atius-srv-2.yaml`, `inventory/hosts/atius-srv-3.yaml`, `inventory/hosts/horistic-srv.yaml` - origem de host IDs, SSH, IPs e aliases.

**Plans:** 1/3 plans complete

- [x] 44-01 - Fleet PKI CLI/resource surface, dry-run safety, templates and tests
- [ ] 44-02 - Remote CA/CSR/leaf bootstrap, trust install, backups and rollback metadata
- [ ] 44-03 - 4x4 HTTPS validation matrix, service adapter plan and durable knowledge closeout

**Wave 1 - Resource surface**

- [x] 44-01 - Fleet PKI CLI/resource surface, dry-run safety, templates and tests

**Wave 2 *(blocked on Wave 1 completion)* - Controlled live bootstrap**

- [ ] 44-02 - Remote CA/CSR/leaf bootstrap, trust install, backups and rollback metadata

**Wave 3 *(blocked on Wave 2 completion)* - Matrix validation and closeout**

- [ ] 44-03 - 4x4 HTTPS validation matrix, service adapter plan and durable knowledge closeout

**Cross-cutting constraints:**

- Cada servidor tem leaf proprio, mas o trust store recebe a CA interna, nao leafs de peers como roots.
- Private keys nunca entram em Git, `.planning`, Obsidian, GBrain, stdout/stderr, logs ou shell history.
- Toda mutacao live exige backup timestampado, dry-run, `--execute` explicito ou update plan aprovado.
- SSH direto so vale para bootstrap/controlado; o recurso permanente deve passar por `omni fleet trust-pki` e comandos local-agent allowlisted.
- HTTPS de servicos reais, como TEI em `10.21.1.21:3115`, exige gate de servico separado; a fase prova PKI/trust, nao troca portas/proxies automaticamente.

**Success Criteria:**

1. `omni fleet trust-pki plan/preflight/render-host` gera plano deterministico para os 4 hosts a partir do inventario.
2. `atius-srv-1` possui CA interna root/issuing root-only, com serial/index/CRL state e backup validado.
3. Cada host possui key/CSR/leaf/chain proprios em `/etc/omni-srv-admin/tls/<host-id>/`, com SAN de VPN IP, public IP e aliases declarados.
4. A CA chain esta instalada e validada em todos os hosts via `update-ca-certificates` e `openssl verify -CApath /etc/ssl/certs`.
5. A matriz 4x4 passa: 4 checks locais + 12 checks HTTPS remotos, validando IP/DNS SAN e TLS verify code `0`.
6. Obsidian e GBrain recebem nota operacional com fingerprints, paths, backups, comandos e resultado, sem material secreto.
7. Runbook documenta rotacao, rollback e regra para nao reutilizar a PKI RDP/XRDP como CA de servicos.
8. TEI/Router permanece em HTTP ate uma fase/gate especifico de reverse proxy/TLS aprovar `https://10.21.1.21:3115`.

**Current open gate:** `44-02` and `44-03` remain blocked on explicit live CA/trust mutation approval and the full 4x4 verification rollout.

### Phase 51: Qwen3 Embedding e Rerank Podman para k3s

**Goal:** Operar Qwen3 Embedding e Rerank como canary ARM64 isolado no k3s, com GTE titular preservado, pipeline global de dois ciclos, índices Qdrant 1024d reversíveis e evidência funcional, de qualidade, capacidade e soak de 72 horas antes de qualquer promoção manual.
**Requirements**: Nenhum ID de requisito atribuído; rastreabilidade por D-01..D-24 e gates de `51-VALIDATION.md`.
**Depends on:** Phase 50; Phase 41 e fundações atuais do router/GTE/Qdrant permanecem contexto técnico obrigatório. Wave 0 resolve topologia, endpoints e consistência antes de implementação. Coordenar com a Phase 52 para que o endpoint privado inventariado seja a fonte autoritativa caso a migração de IP ocorra primeiro.
**Plans:** 9 plans

**Success Criteria:**

1. GTE permanece titular, com aliases, namespace `ebeddings-local` e índices 768d intactos durante toda a fase.
2. `qwen-canary` executa embedding TEI/OrtBackend exato em mean/1024d com 2×500m e reranker q8 dedicado após warmup de 1 pod em 2×500m, sem `hostNetwork` e com NodePorts privados.
3. O router admite no máximo dois ciclos completos Embedding→VectorDB→Rerank, usa `pipeline_id`, prioriza continuação de rerank e libera leases exatamente uma vez em sucesso, erro, cancelamento e TTL.
4. As três collections Qdrant exatas são 1024d/Cosine, possuem assinatura de embedding e corpus/chunk/logical IDs equivalentes, sem misturar ou preencher vetores GTE 768d.
5. Smokes passam para saúde, batch 1/4, dimensão, normalização, cosine ≥0.9999, rerank nativo/público, três ciclos concorrentes, falhas, alcance privado e isolamento GTE.
6. Recall@20 e nDCG@10 não ficam abaixo de GTE globalmente nem nos slices PT técnico/código; CPU-seconds/1.000 tokens é ≤1.05× GTE em pelo menos cinco rounds warm, sem OOM, restart ou starvation.
7. Uma janela GTE-only válida encerrada antes da Wave 0 congela métricas, proveniência e bandas numéricas em `51-GTE-BASELINE-FREEZE.json` antes de qualquer resultado live Qwen; contrato, freeze e gate ficam imutáveis, enquanto readbacks plan-scoped revalidam hashes/topologia/pins/aliases durante e após o soak contínuo ≥72h.
8. Rollback atômico é exercitado sem reindex emergencial e uma decisão manual explícita é registrada; a Phase 51 não promove Qwen automaticamente.

Plans:

**Wave 0**

- [ ] 51-01-PLAN.md — Harness, inventário live, baseline GTE-only numérico congelado, artefatos imutáveis e decisão de estado dos leases

**Wave 1** *(blocked on Wave 0 completion)*

- [ ] 51-02-PLAN.md — Reranker dedicado q8: contratos TDD, limites, lifecycle, imagem ARM64 e warmup

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 51-03-PLAN.md — Manifests com init-download per-pod e rollout controlado do namespace `qwen-canary`

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 51-04-PLAN.md — Catálogo/router/governor com aliases canary, `/v1/rerank` e dois slots de pipeline

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 51-05-PLAN.md — Collections Qdrant 1024d, reindex idempotente e aliases/rollback atômicos

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 51-06-PLAN.md — Smokes funcionais, concorrência, cancel/TTL, alcance privado e isolamento GTE

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 51-07-PLAN.md — Avaliação pareada de qualidade e capacidade com corpus/qrels congelados

**Wave 7** *(blocked on Wave 6 completion)*

- [ ] 51-08-PLAN.md — Imagem ARM64 de soak, suspensão serializada do dual-index e dispatch terminal `external_job_waiting`

**Wave 8** *(blocked on Wave 7 completion)*

- [ ] 51-09-PLAN.md — Rollback drill, restore/replay do dual-index, runbook/guards/knowledge e decisão manual sem promoção

**Execution Waves:**

- Wave 0: 51-01
- Wave 1: 51-02
- Wave 2: 51-03
- Wave 3: 51-04
- Wave 4: 51-05
- Wave 5: 51-06
- Wave 6: 51-07
- Wave 7: 51-08
- Wave 8: 51-09

---

## Milestone v1.7: Internal DNS and DRG Canonicalization

## Phase 45: Internal DNS and DRG Canonicalization

**Goal:** Fazer `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv` e clientes internos resolverem nomes curtos e `*.atius.internal` para os IPs privados OCI/DRG, usando `10.11.1.11:53` como DNS interno canonico e mantendo WireGuard `wg100` apenas como fallback documentado.

**Requirements:** DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06, DNS-07, DNS-08
**Depends on:** Phase 41 TEI context, Phase 43 MCP bootstrap, Phase 44 PKI surface, `C:\Users\muniz\Documents\GitHub\oci-admin` DRG/OCI evidence, `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md`
**Status:** Complete
**Risk:** HIGH - DNS/resolver drift pode quebrar acesso a DB, Vault, Obsidian, TEI, SSO e automacoes Codex; live resolver mutation precisa de rollback por host.

**Canonical refs:**

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-PLAN.md` - plano executavel canonico.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md` - matriz de validacao de fechamento.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-SESSION-INTAKE.md` - intake das sessoes Codex revisadas.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CROSS-PROJECT-DEPENDENCIES.md` - contrato `omni-srv-admin` / `oci-admin`.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-REVIEWS.md` - convergencia manual de review.
- `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md` - runbook publico Cloudflare vs DNS interno.
- `docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md` - referencia/runbook legado; nao e a fonte de execucao da fase.
- `docs/operations/ATIUS-DRG-DNS-SESSION-LEARNINGS.md` - decisoes e aprendizados da migracao.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` - mapa operacional de portas e endpoints.
- `inventory/hosts/*.yaml` - fonte versionada de `oci_private_ip` e excecoes.

**Plans:** 4/4 tasks complete

- [x] 45-01 - Planning/source-of-truth convergence, session intake and AGENTS parity
- [x] 45-02 - `oci-admin` DRG dependency gate and edge-client proof
- [x] 45-03 - Internal DNS/resolver cutover with hostname ping validation
- [x] 45-04 - Fallback boundaries, drift automation, remote merge queue and Obsidian/GBrain closeout

**Wave 1 - Planning source of truth**

- [x] 45-01 - Record cross-session intake, enable plan convergence, make `.planning` canonical and fix local AGENTS drift.

**Wave 2 - OCI dependency gate**

- [x] 45-02 - Prove DRG routes/security/private IPs in `oci-admin`, classify W11/S23 edge state and block DNS cutover if OCI evidence is incomplete.

**Wave 3 - Internal DNS/resolver cutover**

- [x] 45-03 - Ensure `10.11.1.11:53` serves short names and `*.atius.internal`, then validate `ping atius-srv-1` and service reachability.

**Wave 4 - Automation and closeout**

- [x] 45-04 - Add drift checks, keep home-proxy/Wayland in the correct lanes, reconcile the remote dirty worktree queue, update Obsidian/GBrain, and leave parity evidence.

**Cross-cutting constraints:**

- `10.1.1.0/24` is retired. Do not reintroduce it as live compatibility, rollback, resolver, validation, or service path.
- `10.100.100.0/24` is reserve fallback only. `GIOVANNI-W11-PC` may stay on reserve until direct DRG reachability is proven.
- Public `atius.com.br` DNS stays Cloudflare-managed; internal hostnames and private IP identity stay in internal DNS/inventory.
- Phase planning stays in `.planning`; docs are runbooks/evidence, not the source of execution order.
- `oci-admin` must prove OCI/DRG route/security/private-IP state before live resolver cutover is considered complete.
- Home-proxy/PPTP residential LAN reservations are home-edge fallback only and must not become internal DNS/DRG authority.
- Wayland GSD skill/runtime work is tracked as a parallel operator-runtime dependency, not a DNS blocker.
- No secret values may enter Git, `.planning`, Obsidian, GBrain, logs or shell history.
- Live resolver changes require per-host before/after evidence and a rollback path.

**Success Criteria:**

1. `rg -n "10\.1\.1\."` returns only historical/retired references or tracked cleanup notes, not active config or validation.
2. `dig +short @10.11.1.11 atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv` maps to `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.
3. Linux `getent hosts` on SRV-1/SRV-2/SRV-3/Horistic resolves short names to OCI/DRG IPs.
4. `ping atius-srv-1` and equivalent short-hostname tests resolve through internal DNS from Linux and Windows validation points; ICMP failures are classified separately from DNS failures.
5. PgBouncer, Obsidian, Vault and TEI validations prefer `10.11.1.11:6432`, `10.11.1.11:27124`, `10.13.1.13:8202`, `10.21.1.21:3115`.
6. Cloudflare docs list public `atius.com.br` records only; internal host identity is not delegated to Cloudflare.
7. Watchdog scripts and resolver configs cannot reapply `10.1.1.2` or make `10.100.100.1` primary.
8. W11 and S23 have explicit edge-client status: W11 bridge path validated; S23 handset-side outbound proof captured or retained as blocker.
9. Repo, `oci-admin`, Obsidian and GBrain all contain the final canonical DNS model, responsibility split and validation evidence.

## Milestone v1.8: Runtime Trust and Codex Delivery Convergence

**Milestone Goal:** Close the remaining trust/runtime gates in their actual
operational order without rewriting historical phase identifiers: reconcile
planning, close service PKI, converge native Codex OAuth plus remote ACP, add
Headroom through an isolated canary, then close the SSO publication carry-over.

**Execution lanes:** Phases 46-47 are complete. Inserted Phase 47.1 is the
urgent internal-DNS authority prerequisite for Phase 48 plan 48-03 and later
owner-local transport work; Phase 48 plans 48-01/48-02 may continue in their
independent OAuth/ACP lane. Phase 49 remains the isolated Headroom lane. Phase
50 closes the independent SSO carry-over after PKI. A phase cannot bypass its
own stop conditions merely because another lane is ready.

- [x] Phase 46: Planning Surface Reconciliation and Validation Architecture
- [x] Phase 47: Internal Service PKI Listener and Trust Closeout
- [ ] Phase 47.1: Internal DNS Authority and FreeIPA Convergence (INSERTED)
- [ ] Phase 48: Codex OAuth and Wayland Remote ACP Convergence
- [ ] Phase 49: Wayland Codex Headroom Canary and Integration
- [ ] Phase 50: Atius-wide SSO Publication Closeout

## Phase 46: Planning Surface Reconciliation and Validation Architecture

**Goal:** Restore a healthy, complete and dependency-correct GSD planning surface without renaming historical evidence.
**Requirements:** PLN-01, PLN-02, PLN-03, PLN-04, PLN-05
**Depends on:** Phase 45 closeout evidence
**Status:** Complete
**Risk:** MEDIUM - incorrect renumbering can orphan executed evidence or make
GSD report false completion.
**Plans:** 1/1 complete

- [x] 46-01 - Reconcile historical registry, active ordering, requirements,
  state/config and per-phase validation contracts.

**Validation:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/46-planning-surface-reconciliation/46-VALIDATION.md`

## Phase 47: Internal Service PKI Listener and Trust Closeout

**Goal:** Finish host-specific service certificate binding and fleet trust proof on canonical DRG endpoints.
**Requirements:** PKI-01, PKI-02, PKI-03, PKI-04, PKI-05, PKI-06, PKI-07, PKI-08
**Depends on:** Phases 44-01 and 45
**Status:** Complete 2026-07-12
**Risk:** HIGH - listener certificate changes can break Vault, Obsidian and
fleet automation.
**Plans:** 1/1 complete

- [x] 47-01 - Bind issued service leaf/chains, install trust, prove the 4x4
  matrix and Windows HTTPS without insecure verification.

**Validation:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/47-internal-service-pki-closeout/47-VALIDATION.md`
**Verification:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/47-internal-service-pki-closeout/47-VERIFICATION.md`

### Phase 47.1: Internal DNS Authority and FreeIPA Convergence (INSERTED)

**Goal:** Make FreeIPA the single authoritative source for `atius.internal`,
the four OCI/DRG reverse zones and IdM service discovery, while CoreDNS remains
the canonical DRG resolver at `10.11.1.11` and AdGuard remains the filtering
resolver through explicit conditional forwarding and reversible client cutover.
**Requirements:** IDA-01, IDA-02, IDA-03, IDA-04, IDA-05, IDA-06, IDA-07, IDA-08
**Depends on:** Phase 45 closeout evidence, Phase 47, canonical
`inventory/hosts/*.yaml`, and read-only OCI/DRG private-IP, route and security
proof from `oci_admin_http` before any live network mutation.
**Blocks:** Phase 48 plan 48-03 and therefore 48-04..48-06. Phase 48 plans
48-01/48-02 and the separate `oci_admin_http` MCP correction may continue.
**Status:** Planned - ready to execute before Phase 48 plan 48-03
**Risk:** HIGH - authoritative DNS, FreeIPA, resolver and reverse-zone mistakes
can break Kerberos/SSSD, Vault, internal services and every owner-host alias.
**Plans:** 0/8 complete

- [ ] 47.1-01 - Build the declarative authority model, reconciler CLI, sanitized fixtures and focused validator tests.
- [ ] 47.1-02 - Discover exact targets/owners, capture backups and OCI proof, approve the OperationPlan and publish the private endpoint.
- [ ] 47.1-03 - Converge direct FreeIPA forward/reverse authority, srv-3 FQDN and four SSSD host-key records.
- [ ] 47.1-04 - Establish a distinct replica/equivalent failure domain and prove primary-loss recovery before any cutover.
- [ ] 47.1-05 - Cut CoreDNS over to the resilient FreeIPA authority with canary, fail-closed NXDOMAIN and rollback.
- [ ] 47.1-06 - Cut AdGuard over through conditional forwarding without overwriting its dirty checkout or creating duplicate authority.
- [ ] 47.1-07 - Roll out manifest-bound Linux route-only DNS, Windows NRPT and edge-client policy with per-target rollback.
- [ ] 47.1-08 - Run the final matrix, rollback/latency proof and durable closeout, then emit the Phase 48 release gate.

**Wave 1 - Declarative foundation**

- [ ] 47.1-01 - Desired-state schema, reconciler and tests.

**Wave 2 *(blocked on Wave 1 completion)* - Discovery, backup and OCI gate**

- [ ] 47.1-02 - Exact target manifest, backups, OperationPlan and private endpoint.

**Wave 3 *(blocked on Wave 2 completion)* - Direct authority and host identity**

- [ ] 47.1-03 - FreeIPA A/PTR/SOA/NS/SRV/TXT, FQDN and SSSD key convergence.

**Wave 4 *(blocked on Wave 3 completion)* - Resilience before cutover**

- [ ] 47.1-04 - Replica/equivalent failure domain and primary-loss recovery PASS.

**Wave 5 *(blocked on Wave 4 completion)* - CoreDNS frontend**

- [ ] 47.1-05 - CoreDNS conditional forwarding, canary and rollback.

**Wave 6 *(blocked on Wave 5 completion)* - AdGuard frontend**

- [ ] 47.1-06 - AdGuard conditional forward/local PTR cutover under dirty-owner gate.

**Wave 7 *(blocked on Wave 6 completion)* - Client split DNS**

- [ ] 47.1-07 - Linux, Windows and edge rollout from the approved target manifest.

**Wave 8 *(blocked on Wave 7 completion)* - Matrix, rollback and release**

- [ ] 47.1-08 - Full evidence, durable closeout and non-bypassable `47.1-RELEASE-GATE.json`.

**Canonical refs:**

- `.planning/phases/47.1-internal-dns-authority-and-freeipa-convergence/47.1-CONTEXT.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-CONTEXT.md`
- `.planning/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md`
- `.planning/phases/48-codex-oauth-wayland-acp-convergence/48-03-PLAN.md`
- `inventory/hosts/*.yaml`
- `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md`
- `docs/domain/freeipa-dns-client-enrollment.md`

**Success Criteria:**

1. FreeIPA is authoritative for `atius.internal` and the exact reverse zones
   `1.11.10.in-addr.arpa`, `1.12.10.in-addr.arpa`,
   `1.13.10.in-addr.arpa`, and `1.21.10.in-addr.arpa`; SOA, NS and existing
   LDAP/Kerberos SRV/TXT records remain valid.

2. A/PTR identity is exact and symmetric:
   `atius-srv-1.atius.internal -> 10.11.1.11`,
   `atius-srv-2.atius.internal -> 10.12.1.12`,
   `atius-srv-3.atius.internal -> 10.13.1.13`, and
   `horistic-srv.atius.internal -> 10.21.1.21`; no `.0.*` host address or
   active `10.1.1.*` path is introduced.

3. FreeIPA DNS is exposed privately through a dedicated secondary IP in
   `10.13.1.0/24` selected and approved by an OCI OperationPlan; the plan does
   not guess an address, repurpose `10.13.1.13`, expose DNS publicly or depend
   on the Podman-only `10.89.53.10` outside srv-3.

4. CoreDNS at `10.11.1.11` and AdGuard forward only `atius.internal` plus the
   four private reverse zones to FreeIPA; public recursion/filtering remains
   AdGuard-owned, and AdGuard rewrites/hosts-file inheritance never become the
   internal source of truth.

5. Linux route-only DNS, Windows NRPT and edge-client FQDN resolution are
   deterministic; public DNS is not a co-equal resolver for the internal
   namespace and internal NXDOMAIN never leaks to a public fallback.

6. A canary name absent from `/etc/hosts`, AdGuard rewrites and CoreDNS static
   hosts proves the authoritative path before duplicate FQDN compatibility
   records are removed; every live change has backup, bounded TTL/cache flush,
   one-host rollback and fail-closed evidence.

7. `atius-srv-3` returns the exact FQDN from `hostname -f`; FreeIPA/SSSD
   publishes the four host keys, and `ubuntu@atius-srv-3.atius.internal` remains
   explicit local identity metadata rather than a self-SSH target.

8. Failure-domain/replica readiness is proved before DNS or authentication
   becomes hard-dependent on one FreeIPA container, and final `dig`, `getent`,
   `resolvectl`, `Resolve-DnsName`/`nslookup`, TCP/UDP 53, host-key and rollback
   evidence is recorded without secrets.

## Phase 48: Codex OAuth and Wayland Remote ACP Convergence

**Goal:** Make native Codex OAuth, models, local/remote ACP and owner-host development transport reliable before any proxy layer is introduced.
**Requirements:** WAC-01, WAC-02, WAC-03, WAC-04, WAC-05, WAC-06, WAC-07, WAC-08, WAC-09, WAC-10
**Depends on:** Router Phase 32 completion, ownership release from sessions
`019f3e9a-9964-7912-a982-65596e9954d3` and
`019f2ba1-1982-7c03-a17d-3ce28c589ac1`, native Codex model parity
**Plan dependency:** Phase 47.1 must be complete before 48-03 starts; 48-01 and
48-02 remain independent of that DNS-authority gate.
**Status:** Current - target ownership, native gpt-5.6-sol and Wayland port 25725 parity pass; Router Phase 32 evidence, CPU-capped Go executor repair, full local/remote ACP lifecycle and owner-local transport convergence remain
**Risk:** HIGH - auth or ACP regressions can break every Wayland Codex session.
**Plans:** 0/6 complete

- [ ] 48-01 - Reconcile Router evidence, renew native ubuntu OAuth, and prove native plus local ACP without Headroom.
- [ ] 48-02 - Prove authenticated remote WSS, Wayland Chromium lifecycle, and sanitized closeout before Phase 49 can open.
- [ ] 48-03 - Consume the completed Phase 47.1 DNS/FreeIPA authority, then deploy strict encrypted owner aliases with additive inventory metadata and rollback.
- [ ] 48-04 - Protect the Wayland fork paths, install pinned owner-native ACP launchers, and add ACP stdio-over-SSH with separate `agentCwd`.
- [ ] 48-05 - Add default-off per-conversation owner-local routing and containment-safe UI path mapping while active work stays owner-native.
- [ ] 48-06 - Run fork-sync, CPU-capped/headless fleet validation, latency/resource/failure benchmarks, rollback, and durable closeout.

**Validation:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/48-VALIDATION.md`

## Phase 49: Wayland Codex Headroom Canary and Integration

**Goal:** Route the Codex CLI used by Wayland through a pinned, isolated and reversible Headroom canary.
**Requirements:** HDR-01, HDR-02, HDR-03, HDR-04, HDR-05, HDR-06, HDR-07, HDR-08
**Depends on:** Phase 48
**Status:** Planned
**Risk:** HIGH - Headroom mutates Codex provider/config state and proxies HTTP
plus WebSocket traffic.
**Plans:** 0/1 complete

- [ ] 49-01 - Install pinned Headroom canary, prove direct Codex transport,
  then ACP and Wayland integration with rollback rehearsal.

**Validation:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/49-wayland-codex-headroom/49-VALIDATION.md`

## Phase 50: Atius-wide SSO Publication Closeout

**Goal:** Close the remaining SSO publication, redirect, logout and RBAC gates after PKI trust is valid.
**Requirements:** SSO-01, SSO-02, SSO-03, SSO-04, SSO-05, SSO-06
**Depends on:** Phase 47 and completed Phase 42 plans 42-01/42-02
**Execution order:** After Phase 49; the PKI dependency is already satisfied,
but the operator queue remains 48 -> 49 -> 50.
**Status:** Queued after Phase 49 - continuation of 42-03
**Risk:** HIGH - redirect, cookie or RBAC regressions can lock operators out of
multiple production applications.
**Plans:** 0/1 complete

- [ ] 50-01 - Execute the remaining edge/Keycloak/app-host publication gate,
  cross-domain logout and RBAC-compatible validation.

**Validation:** `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/50-atius-wide-sso-closeout/50-VALIDATION.md`

## Phase Summary

| # | Phase | Goal | Requirements | Status | Risk |
|---|-------|------|--------------|--------|------|
| 28 | G18 Ubuntu Pro/ESM Fleet Gates | Pro/ESM state + upgrade gates | G18-01, G18-02 | Complete | HIGH |
| 29 | G18 Controlled Upgrade/RDP/Landscape | Upgrade + RDP + SaaS validation | G18-02..G18-05 | Complete | HIGH |
| 29.1 | Obsidian ARM64 AppImage pilot | Managed non-Snap Obsidian pilot on `atius-srv-1` | GOV-03..GOV-05 | Complete | HIGH |
| 30 | Landscape/Omni Governance Operating Model | Matrix/access/fallback | GOV-01, GOV-02, GOV-07 | Complete | MEDIUM |
| 31 | Omni Fleet Collectors/Profile | Collectors + desired-state | GOV-03..GOV-05 | Complete | MEDIUM |
| 32 | CVE/USN + Landscape Parity | Patch reporting + parity | GOV-06, GOV-07 | Complete | MEDIUM |
| 33 | FreeIPA Foundation | Host prep + FreeIPA | DOM-01, DOM-02 | Complete | VERY HIGH |
| 34 | FreeIPA DNS + Clients | DNS coexistence + enrollment | DOM-03, DOM-04 | Complete | HIGH |
| 35 | Samba Kerberos | Samba domain member | DOM-05 | Complete | MEDIUM |
| 36 | Keycloak SSO | LDAP federation + coexistence | DOM-06, DOM-07 | Complete | MEDIUM |
| 37 | Production Guard Status/Doctor | Read-only validator | PRG-01 | Complete | MEDIUM |
| 38 | Production Guard Repair | Dry-run repair + gated apply | PRG-02, PRG-03 | Complete | HIGH |
| 39 | Production Guard Boot/Login | Read-only boot/login protocol | PRG-04 | Complete | MEDIUM |
| 40 | Production Guard Horistic Remote | Remote checks + webhook-safe | PRG-05..PRG-07 | Complete | MEDIUM |
| 41 | Local AI Embeddings Gateway | TEI backend + New API alias + client migration | EMB-01..EMB-08 | Complete | HIGH |
| 42 | Atius-wide SSO Login | `sso.atius.com.br` + Keycloak/OIDC + ATS reference migration | SSO-01..SSO-06 | Historical partial; continues in 50 | HIGH |
| 43 | Codex MCP Bootstrap Hardening | Lean default startup + opt-in MCP profiles + cold-start smoke | CDX-01..CDX-06 | Complete | HIGH |
| 44 | Internal Service PKI and Fleet Trust | Per-host service leaf certs + internal CA trust + 4x4 HTTPS validation | PKI-01..PKI-08 | Historical partial; continues in 47 | HIGH |
| 45 | Internal DNS and DRG Canonicalization | DRG/OCI DNS, resolver and service endpoint canonicalization | DNS-01..DNS-08 | Complete | HIGH |
| 46 | Planning Surface Reconciliation | Historical registry, active order and validation architecture | PLN-01..PLN-05 | Complete | MEDIUM |
| 47 | Internal Service PKI Closeout | Listener leaf/chain binding and trust proof | PKI-01..PKI-08 | Complete 2026-07-12 | HIGH |
| 47.1 | Internal DNS Authority and FreeIPA Convergence | Authoritative FreeIPA A/PTR/SRV, CoreDNS/AdGuard forwarding and deterministic split DNS | IDA-01..IDA-08 | Planning; blocks 48-03 | HIGH |
| 48 | Codex OAuth and Wayland ACP Convergence | Router OAuth, native Codex, remote ACP and owner-local parity | WAC-01..WAC-10 | Executing | HIGH |
| 49 | Wayland Codex Headroom | Isolated canary, ACP integration and rollback | HDR-01..HDR-08 | Blocked by Phase 48 | HIGH |
| 50 | Atius-wide SSO Closeout | Remaining publication, redirect, logout and RBAC gate | SSO-01..SSO-06 | Queued after Phase 49 | HIGH |

**Active v1.8:** 6 phases | 2 complete / 1 planning / 1 executing / 2 queued or gated

### Scope addendum - 2026-06-24

- G18 fleet scope expanded from 3 SRVs to 4 managed hosts by adding `horistic-srv`.
- `horistic-srv` enters Phase 29 inventory, go/no-go, RDP validation, and Landscape SaaS/web validation before any live upgrade decision.
- Landscape SaaS/web is temporary onboarding. Landscape self-hosted is promoted into the active governance target for Phase 32 via `GOV-08`.
