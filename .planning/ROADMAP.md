# Roadmap: Omni Srv Admin (omni-srv-admin)

**Active Milestone:** v1.4 — Atius-wide SSO and Login
**Milestone Goal:** Publicar `sso.atius.com.br` como host canonico de login ATIUS, usando Keycloak como provedor OIDC controlado e preservando o `auth-token` e o RBAC legado do ATS ate a publicacao completa.
**Milestone Branch Matrix:** `.planning/MILESTONES.md`
**Requirements:** `.planning/REQUIREMENTS.md`
**Execution order:** Wave 0 validation -> ATS SSO facade -> edge/header publication gate -> rollback/runbook closeout

---

## Milestone v1.2 Carry-over

The v1.2 phases below remain valid as canonized history. v1.3 shipped, Phase 43
also shipped out of sequence for runtime reasons, and the active operator focus
is now finishing Phase 42 before resuming Phase 44.

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

### Phase 29.1: Obsidian ARM64 AppImage pilot without Snap on atius-srv-1 (INSERTED)

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

**34-02 closeout:** CoreDNS on `atius-srv-2` now forwards only `atius.internal` to `10.1.1.3`; `atius-srv-3` privately gateways the required FreeIPA ports to the container at `10.89.53.10`; real-host enrollment succeeded on `atius-srv-3` as `atius-srv-3.atius.internal`; `getent`, `id`, `kinit admin`, `ipa ping`, and `sudo -l -U admin` passed. `horistic-srv` was explicitly deferred to the next controlled expansion step.

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
  - Completed 2026-07-04 and reconciled 2026-07-06: TEI live on `10.1.1.4:3115`, runtime namespace `ebeddings-local`, router alias `embedding-gte-v1`, public POST `/v1/embeddings` smoke passed.

**Success Criteria:**

1. `POST https://router.atius.com.br/v1/embeddings` com `model=embedding-gte-v1` retorna embeddings para lote pt-BR autenticado.
2. A resposta validada mostra `quantidade=2`, `dimensoes=768`, `error=null` e `model` coerente com o alias público.
3. O canal interno do New API aponta para `http://10.1.1.4:3115`, não para o próprio router público.
4. O contrato `modelo + versão/digest + dimensão + normalização + chunking` fica documentado, e qualquer troca exige reembed/reindex.
5. GBrain/Obsidian/Graphify têm runbook de consumo sem gravar secrets em Git, `.planning`, Obsidian, logs ou shell history.

---

## Milestone v1.4: Atius-wide SSO and Login

## Phase 42: Atius-wide SSO Login on sso.atius.com.br

**Goal:** Criar `sso.atius.com.br` como subdominio canonico de login da Atius, usando o Keycloak ja validado em Phase 36 como provedor OIDC e migrando o ATS como primeira aplicacao de referencia sem quebrar o SSO/JWT legado.

**Requirements:** SSO-01, SSO-02, SSO-03, SSO-04, SSO-05, SSO-06
**Depends on:** Phase 36 Keycloak/FreeIPA coexistence, ATS current SSO/JWT cookie flow, Apache/Cloudflare edge inventory
**Status:** In Progress
**Risk:** HIGH — mexe em identidade, cookies `.atius.com.br`, redirect/login cross-subdomain e apps de trading live; qualquer cutover deve ser gateado e reversivel.

**Canonical refs:**

- `.planning/phases/36-keycloak-sso-and-coexistence/36-CONTEXT.md` — decisoes de coexistencia Keycloak/FreeIPA e preservacao do Apache SSO legado.
- `.planning/phases/36-keycloak-sso-and-coexistence/36-VERIFICATION.md` — prova atual do Keycloak em `auth.atius.com.br`, OIDC smoke e FreeIPA federation.
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
**Depends on:** `docs/operations/codex-runtime-standard.md`, `C:\Users\muniz\.codex\config.toml`, `C:\Users\muniz\.codex\mcp-patch.toml`, endpoint `https://10.1.1.1:27124/mcp/`, repo local `oracle-oci-mcp`
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
**Status:** In Progress
**Risk:** HIGH - mexe em CA interna, trust store, chaves privadas, HTTPS interno e validacao cross-host; erro aqui pode criar falsa confianca ou quebrar clientes TLS.

**Canonical refs:**

- `.planning/phases/44-internal-service-pki-and-fleet-trust/44-CONTEXT.md` - decisoes de CA, key locality, escopo e hosts.
- `.planning/phases/44-internal-service-pki-and-fleet-trust/44-RESEARCH.md` - pesquisa em repo, Obsidian, GBrain e preflight remoto read-only.
- `.planning/phases/44-internal-service-pki-and-fleet-trust/44-VALIDATION.md` - contrato de validacao antes/durante/depois do rollout.
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
- HTTPS de servicos reais, como TEI em `10.1.1.4:3115`, exige gate de servico separado; a fase prova PKI/trust, nao troca portas/proxies automaticamente.

**Success Criteria:**

1. `omni fleet trust-pki plan/preflight/render-host` gera plano deterministico para os 4 hosts a partir do inventario.
2. `atius-srv-1` possui CA interna root/issuing root-only, com serial/index/CRL state e backup validado.
3. Cada host possui key/CSR/leaf/chain proprios em `/etc/omni-srv-admin/tls/<host-id>/`, com SAN de VPN IP, public IP e aliases declarados.
4. A CA chain esta instalada e validada em todos os hosts via `update-ca-certificates` e `openssl verify -CApath /etc/ssl/certs`.
5. A matriz 4x4 passa: 4 checks locais + 12 checks HTTPS remotos, validando IP/DNS SAN e TLS verify code `0`.
6. Obsidian e GBrain recebem nota operacional com fingerprints, paths, backups, comandos e resultado, sem material secreto.
7. Runbook documenta rotacao, rollback e regra para nao reutilizar a PKI RDP/XRDP como CA de servicos.
8. TEI/Router permanece em HTTP ate uma fase/gate especifico de reverse proxy/TLS aprovar `https://10.1.1.4:3115`.

**Current open gate:** `44-02` and `44-03` remain blocked on explicit live CA/trust mutation approval and the full 4x4 verification rollout.

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
| 42 | Atius-wide SSO Login | `sso.atius.com.br` + Keycloak/OIDC + ATS reference migration | SSO-01..SSO-06 | In Progress | HIGH |
| 43 | Codex MCP Bootstrap Hardening | Lean default startup + opt-in MCP profiles + cold-start smoke | CDX-01..CDX-06 | Complete | HIGH |
| 44 | Internal Service PKI and Fleet Trust | Per-host service leaf certs + internal CA trust + 4x4 HTTPS validation | PKI-01..PKI-08 | In Progress | HIGH |

**Total:** 18 phases | 54 requirements mapped | 16 complete / 2 open

### Scope addendum - 2026-06-24

- G18 fleet scope expanded from 3 SRVs to 4 managed hosts by adding `horistic-srv`.
- `horistic-srv` enters Phase 29 inventory, go/no-go, RDP validation, and Landscape SaaS/web validation before any live upgrade decision.
- Landscape SaaS/web is temporary onboarding. Landscape self-hosted is promoted into the active governance target for Phase 32 via `GOV-08`.
