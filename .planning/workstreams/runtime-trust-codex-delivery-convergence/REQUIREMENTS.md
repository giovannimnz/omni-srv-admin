# Requirements: Omni Srv Admin — v1.2 to v1.7

**Defined:** 2026-06-24
**Milestone:** multi-milestone reconciliation through v1.7
**Core Value:** Servidor Atius sempre provisionado, documentado e operante, com governanca centralizada e identidade/SSO evoluindo sem quebrar producao.

## v1.2 Requirements

### G18 — Ubuntu Pro / ESM / Landscape SaaS

- [x] **G18-01**: Operador consegue ver o estado Ubuntu Pro/ESM dos SRV-1/SRV-2/SRV-3/horistic-srv, incluindo token/account, attach status, services, apt sources e pendencias por host.
- [x] **G18-02**: Operador consegue executar um plano de apt upgrade ESM Apps/infra com preflight, snapshot/backup/checkpoint e gate explicito antes de qualquer mutacao live.
- [x] **G18-03**: Operador consegue validar Microsoft RDP/XRDP nos 4 servidores apos upgrade, com smoke test documentado e rollback seguro para display/session config.
- [x] **G18-04**: Operador consegue confirmar Landscape SaaS com SRV-1/SRV-2/SRV-3/horistic-srv online e documentar o estado real de registro/telemetria.
- [x] **G18-05**: Operador consegue rodar watchdog/regressao pos-upgrade cobrindo apt, ESM, RDP, Landscape, PM2, K3s e edges sem reiniciar servicos sensiveis automaticamente.

### Landscape / Omni Governance

- [x] **GOV-01**: Operador tem matriz de responsabilidades clara entre Landscape, Omni Fleet, Cockpit, K3s/Portainer e observability.
- [x] **GOV-02**: Operador tem modelo de acesso para Cockpit/Landscape/Omni protegido por Access/SSO/VPN, sem expor consoles administrativos direto na internet.
- [x] **GOV-03**: Omni Fleet coleta versoes reais de programas, pacotes, repositorios, policies e customizations por host.
- [x] **GOV-04**: Omni Fleet representa desired-state profiles para packages/programs/repositories/policies/customizations com drift detectavel.
- [x] **GOV-05**: Operador consegue aprovar update plans com auditoria, dry-run e execucao controlada por host/scope.
- [x] **GOV-06**: Operador consegue enxergar CVE/USN/repository profile status e priorizar correcoes por host.
- [x] **GOV-07**: Operador tem runbook Landscape/Omni com fallback documentado para SaaS, self-hosted, LXD/VM/Juju ou modo Omni-only.

### Domain Infrastructure

- [x] **DOM-01**: Operador consegue preparar o host para FreeIPA sem conflitar com Apache, WireGuard, CoreDNS, K3s, PM2 ou Cloudflare edges.
- [x] **DOM-02**: FreeIPA roda em container AlmaLinux 9 com realm, CA, LDAP/Kerberos, DNS interno e backup verificavel.
- [x] **DOM-03**: Maquinas Linux conseguem ingressar no dominio FreeIPA por WireGuard com grupos/permissoes centralizados.
- [x] **DOM-04**: DNS FreeIPA, CoreDNS e WireGuard coexistem com resolucao interna previsivel e rollback documentado.
- [x] **DOM-05**: Samba autentica via FreeIPA/Kerberos e preserva shares/ownership durante migracao.
- [x] **DOM-06**: Keycloak roda federado no LDAP do FreeIPA e expõe OIDC em `auth.atius.com.br` sem quebrar o SSO Apache existente.
- [x] **DOM-07**: Apache SSO legado, Keycloak SSO e clients Linux coexistem com smoke tests e criterios claros de rollback.

### Production Guard

- [x] **PRG-01**: Operador consegue rodar `production-guard status/doctor` read-only para ATS/Horistic cobrindo PM2, dump, namespaces, ecosystems, portas, endpoints, containers, timers e jobs systemd.
- [x] **PRG-02**: Operador consegue gerar plano de repair seguro para PM2 apps/stacks, containers e systemd safe-starts, sempre dry-run por default.
- [x] **PRG-03**: Qualquer repair live exige snapshot/checkpoint, diff explicito e confirmacao, sem `pm2 kill` e sem restart de RDP/XRDP automatico.
- [x] **PRG-04**: Operador tem protocolo boot/login com units/timers read-only, docs operacionais e validacao sem mutacao live automatica.
- [x] **PRG-05**: Guard valida Apache remoto Horistic em `horistic-srv` com vhosts, proxy targets e endpoints publicos GET/HEAD.
- [x] **PRG-06**: Guard detecta drift seguro de renomeio de host/pasta/repo/vhost sem alterar remoto sem gate.
- [x] **PRG-07**: Guard valida webhooks ATS/Horistic sem POST real para trading/Telegram e sem acionar Circuit Breaker indevidamente.

## v1.3 Requirements

### Local AI Embeddings / Semantic Retrieval

- [x] **EMB-01**: Operador consegue chamar `https://router.atius.com.br/v1/embeddings` com autenticação Bearer e `model=embedding-gte-v1`.
- [x] **EMB-02**: New API possui canal interno para embeddings que aponta para o TEI em `http://10.21.1.21:3115`, nunca para `https://router.atius.com.br/v1`, evitando loop.
- [x] **EMB-03**: Backend TEI roda no k3s em `horistic-srv` sob namespace `ebeddings-local`, com Service ClusterIP, `hostNetwork` privado e sem ingress público direto.
- [x] **EMB-04**: Alias `embedding-gte-v1` fica ligado a `Alibaba-NLP/gte-multilingual-base`, 768 dimensões, com contrato de modelo + versão/digest + normalização + chunking documentado.
- [x] **EMB-05**: Smoke test externo em lote com dois textos pt-BR retorna `quantidade=2`, `dimensoes=768`, `error=null` e usage coerente.
- [x] **EMB-06**: GBrain tem runbook de migração para `openai:embedding-gte-v1` e 768 dimensões, com backup e reindex/retrieval-upgrade explícitos antes de alterar store existente.
- [x] **EMB-07**: Obsidian e Graphify têm contrato de consumo documentado: Obsidian via indexador externo sobre Markdown; Graphify apenas como retrieval auxiliar, sem substituir análise estrutural/grafo.
- [x] **EMB-08**: Chaves/tokens de New API ficam fora de Git, `.planning`, Obsidian, logs e shell history; testes usam token temporário limpo ou prompt/Vault/Secret.

## v1.4 Requirements

### Atius-wide SSO / Login

- [ ] **SSO-01**: Operador tem `sso.atius.com.br` definido como subdominio canonico de login da Atius, com contrato de DNS/Apache/Cloudflare/TLS e rollback antes de qualquer publicacao live.
- [ ] **SSO-02**: Keycloak existente em `auth.atius.com.br` vira provedor OIDC controlado para login Atius-wide sem quebrar o SSO/JWT legado durante a migracao.
- [ ] **SSO-03**: ATS usa o novo fluxo SSO como primeira aplicacao de referencia, preservando `auth-token`, RBAC (`is_admin`, `can_access_*`) e rotas protegidas ate a compatibilidade ser provada.
- [ ] **SSO-04**: `sso.atius.com.br` suporta redirect seguro de volta para `trade.atius.com.br`, `painel.atius.com.br`, `dashboard.atius.com.br`, `backtest.atius.com.br`, `strategy.atius.com.br` e futuros apps Atius sem open redirect.
- [ ] **SSO-05**: Logout global limpa sessao Keycloak e cookies legados `.atius.com.br`, com smoke test cross-subdomain e rollback documentado.
- [ ] **SSO-06**: Tokens, client secrets, session secrets e credenciais de smoke ficam fora de Git, `.planning`, Obsidian, logs e shell history.

## v1.5 Requirements

### Codex Runtime / MCP Bootstrap Reliability

- [x] **CDX-01**: Operador consegue iniciar o Codex em `GIOVANNI-W11-PC` sem timeouts ou warnings genericos para MCPs que sao opcionais no fluxo diario.
- [x] **CDX-02**: A base `C:\Users\muniz\.codex\config.toml` separa MCPs always-on de MCPs pesados ou task-specific por meio de perfis nomeados e rollback simples.
- [x] **CDX-03**: MCPs com pre-requisito externo - Cloudflare token, VPN/Obsidian REST, browsers locais ou stacks OCI - tem politica explicita de env/reachability/disable default em vez de falhar no boot padrao.
- [x] **CDX-04**: MCPs stdio pesados que permanecerem habilitados usam `startup_timeout_sec` explicito, command paths estaveis e preferencialmente sem `@latest` no bootstrap diario.
- [x] **CDX-05**: Operador tem smoke e doctor repetiveis para classificar falha como `missing-env`, `unreachable`, `slow-start`, `disabled` ou `ok`, sem imprimir secrets.
- [x] **CDX-06**: Documentacao do runtime Codex registra baseline lean, perfis opt-in, comandos `codex -p <profile>`, backups e rollback de `config.toml` antes de qualquer ajuste.

## v1.6 Requirements

### Internal Service PKI / Fleet HTTPS

- [x] **PKI-01**: Operador consegue renderizar, por inventario, o plano de PKI interna para `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e `horistic-srv`, incluindo SANs, caminhos, dry-run e comandos sem material secreto.
- [x] **PKI-02**: `omni-srv-admin` possui comando/versioned resource `omni fleet trust-pki` com preflight, init CA, issue-host, install-trust, verify, rollback-plan, onboard-host, reconcile-host e rotate-host, todos dry-run por default e mutacao apenas com gate explicito.
- [x] **PKI-03**: A CA interna de servicos fica root-only fora de Git, `.planning`, Obsidian, GBrain, logs e shell history, com backup/serial/index/CRL state e regra de rotacao documentada.
- [x] **PKI-04**: Cada servidor gerenciado, inclusive servidor novo cadastrado no inventario/DbOmniFleet, possui key/CSR/leaf/chain proprios, com private key local root-only e leaf contendo `serverAuth`, `clientAuth`, `CA:FALSE` e SANs de VPN IP, public IP e aliases declarados.
- [x] **PKI-05**: Todos os servidores instalam e validam a CA chain via trust store do sistema (`update-ca-certificates`), sem instalar leafs de peers como root CAs.
- [x] **PKI-06**: A validacao passa uma matriz 4x4: 4 verificacoes locais e 12 verificacoes HTTPS remotas entre os hosts, com hostname/IP SAN validation e TLS verify code `0`.
- [x] **PKI-07**: A funcionalidade produz audit JSON/redacted logs, docs operacionais, Obsidian e GBrain com fingerprints, paths, backups e resultados, sem vazar chaves, tokens ou passphrases.
- [x] **PKI-08**: O plano deixa explicito que HTTPS real de servicos, como TEI em `https://10.21.1.21:3115`, exige proxy/listener TLS e gate de servico separado antes de alterar channels ou portas em producao.

## v1.7 Requirements

### Internal DNS / DRG Canonicalization

- [x] **DNS-01**: Inventario, docs, scripts e validadores usam `oci_private_ip` como campo de roteamento canonico para `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e `horistic-srv`.
- [x] **DNS-02**: `wg100` / `10.100.100.0/24` aparece apenas como fallback/reserva documentada, com excecao explicita para `GIOVANNI-W11-PC` ate prova de reachability DRG.
- [x] **DNS-03**: `10.1.1.0/24` nao aparece como caminho ativo em configuracao, scripts, validadores ou runbooks; referencias remanescentes ficam marcadas como historicas ou entram em lista de cleanup.
- [x] **DNS-04**: O resolvedor interno canonico e `10.11.1.11:53`, servindo short names e `*.atius.internal` para IPs privados OCI/DRG.
- [x] **DNS-05**: Linux hosts, clientes Windows e edge clients usam resolvers/rotas que preferem DRG/OCI quando disponivel e nao reintroduzem `10.1.1.2` ou `10.100.100.1` como primario por watchdog/script.
- [x] **DNS-06**: Cloudflare gerencia apenas DNS publico de `atius.com.br`; nomes de maquinas e IPs privados vivem no DNS interno e em inventario versionado.
- [x] **DNS-07**: Servicos internos criticos usam endpoints OCI/DRG por padrao: PgBouncer `10.11.1.11:6432`, Obsidian `10.11.1.11:27124`, Vault `10.13.1.13:8202`, TEI `10.21.1.21:3115`.
- [x] **DNS-08**: Validacao final cobre `dig/getent/nslookup`, `ping <hostname>`, reachability de servicos, diff repo-wide contra `10.1.1.x`, dependencia `oci-admin`, e registro em Obsidian/GBrain sem segredos.

## v1.8 Requirements

### Planning Surface Reconciliation

- [x] **PLN-01**: Todos os diretorios de fase existentes aparecem no `ROADMAP.md` como ativos, completos, legados ou superseded; nenhum historico executado e renumerado.
- [x] **PLN-02**: `MILESTONES.md`, `PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md` e `config.json` concordam sobre milestone, fase corrente e ordem operacional.
- [x] **PLN-03**: Cada fase ativa 46-50 possui plano, validacao, stop conditions, rollback e evidencia esperada.
- [x] **PLN-04**: `gsd-tools` health, stats e roadmap analyzer reconhecem v1.8 e nao reportam fases orfas ou config keys invalidas.
- [x] **PLN-05**: A ordem final e registrada no repo, Obsidian e GBrain sem segredos.

### Codex OAuth and Wayland ACP Convergence

- [ ] **WAC-01**: Router Phase 32 e auditada em shell funcional sem sobrescrever mudancas concorrentes e possui testes deterministas para metadata, refresh, regenerate, probe e upstream auth.
- [ ] **WAC-02**: `token_invalidated`, `refresh_token_invalidated`, `invalid_api_key`, 401 e 403 upstream sao distintos da autenticacao interna do Router.
- [ ] **WAC-03**: Credencial Codex nativa funciona antes de qualquer Headroom, com refresh/regeneration e health persistido sem tokens em logs/respostas.
- [ ] **WAC-04**: Catalogo final de modelos e reasoning effort passa no Codex CLI e no Wayland sem expectativas antigas de GPT-5.6.
- [ ] **WAC-05**: `codex-acp` local passa initialize, session/new, prompt, tool, approval, cancel, resume e shutdown.
- [ ] **WAC-06**: ACP remoto/ACPX/OpenClaw passa Upgrade auth, gateway auth, approvals e reconnect sem reduzir o contrato local.
- [ ] **WAC-07**: Wayland preserva `Wayland -> codex-acp -> codex`, sem converter GSD skills em runtime agents.
- [ ] **WAC-08**: Ownership, backup, rollback e validacao live estao registrados antes de liberar Phase 49.

### Wayland Codex Headroom

- [ ] **HDR-01**: Headroom fica pinado em release/commit/hash aprovado e instalado de forma user-level reproduzivel no `atius-srv-3`.
- [ ] **HDR-02**: O primeiro canario usa `CODEX_HOME` isolado sem copiar/symlinkar SQLite de sessoes e sem mutar `/home/ubuntu/.codex` ativo.
- [ ] **HDR-03**: Proxy Headroom fica somente em loopback e inicia sem MCP, memory, context-tool, learning ou output shaping.
- [ ] **HDR-04**: Codex direto passa OAuth, `/v1/responses`, WebSocket, tools, apply_patch, cancel/reconnect e model/effort parity atraves do proxy.
- [ ] **HDR-05**: Uma carga elegivel comprova transformacao e savings maiores que zero; simples passthrough nao conta como sucesso.
- [ ] **HDR-06**: `codex-acp` passa o lifecycle completo usando o canario Headroom sem mudar o protocolo ACP.
- [ ] **HDR-07**: Wayland passa smoke em Chromium headless via Chrome DevTools para conversa, streaming, approval, cancel/resume e model/effort.
- [ ] **HDR-08**: Rollback ensaiado restaura o caminho nativo sem perda de config, auth, sessions ou provider tags; Obsidian/GBrain recebem evidencia redatada.

## Future Requirements

- **LSC-SELF-01**: Deploy Landscape self-hosted em Podman/K3s se SaaS nao cobrir governanca necessaria ou se custo/controle justificar.
- **DOM-WIN-01**: Integração Windows/Mac ao dominio, explicitamente fora do escopo Linux-first deste milestone.
- **SSO-MIG-01**: Promovido para v1.4 como `SSO-01`..`SSO-06` e Phase 42.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Apt upgrade live sem gate | Risco direto para RDP, PM2, K3s e acesso remoto. |
| Restart automatico de XRDP/RDP em execucao autonoma | Pode derrubar a sessao remota do operador. |
| `pm2 kill` ou reset amplo de processos trading | Risco operacional alto para ATS/Horistic. |
| POST real para webhooks de trading/Telegram em validacao | Pode gerar side effects financeiros/operacionais. |
| Migracao de apps para Keycloak neste milestone | Primeiro precisa fechar FreeIPA/Keycloak coexistente e smoke tests. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| G18-01 | Phase 28 | Complete |
| G18-02 | Phase 28, Phase 29 | Complete |
| G18-03 | Phase 29 | Complete |
| G18-04 | Phase 29 | Complete |
| G18-05 | Phase 29 | Complete |
| GOV-01 | Phase 30 | Complete |
| GOV-02 | Phase 30 | Complete |
| GOV-03 | Phase 31 | Complete |
| GOV-04 | Phase 31 | Complete |
| GOV-05 | Phase 31 | Complete |
| GOV-06 | Phase 32 | Complete |
| GOV-07 | Phase 30 | Complete |
| DOM-01 | Phase 33 | Complete |
| DOM-02 | Phase 33 | Complete |
| DOM-03 | Phase 34 | Complete |
| DOM-04 | Phase 34 | Complete |
| DOM-05 | Phase 35 | Complete |
| DOM-06 | Phase 36 | Complete |
| DOM-07 | Phase 36 | Complete |
| PRG-01 | Phase 37 | Complete |
| PRG-02 | Phase 38 | Complete |
| PRG-03 | Phase 38 | Complete |
| PRG-04 | Phase 39 | Complete |
| PRG-05 | Phase 40 | Complete |
| PRG-06 | Phase 40 | Complete |
| PRG-07 | Phase 40 | Complete |
| EMB-01 | Phase 41 | Complete |
| EMB-02 | Phase 41 | Complete |
| EMB-03 | Phase 41 | Complete |
| EMB-04 | Phase 41 | Complete |
| EMB-05 | Phase 41 | Complete |
| EMB-06 | Phase 41 | Complete |
| EMB-07 | Phase 41 | Complete |
| EMB-08 | Phase 41 | Complete |
| SSO-01 | Phase 42, Phase 50 | In Progress |
| SSO-02 | Phase 42, Phase 50 | In Progress |
| SSO-03 | Phase 42, Phase 50 | In Progress |
| SSO-04 | Phase 42, Phase 50 | In Progress |
| SSO-05 | Phase 42, Phase 50 | In Progress |
| SSO-06 | Phase 42, Phase 50 | In Progress |
| CDX-01 | Phase 43 | Complete |
| CDX-02 | Phase 43 | Complete |
| CDX-03 | Phase 43 | Complete |
| CDX-04 | Phase 43 | Complete |
| CDX-05 | Phase 43 | Complete |
| CDX-06 | Phase 43 | Complete |
| PKI-01 | Phase 44, Phase 47 | Complete |
| PKI-02 | Phase 44, Phase 47 | Complete |
| PKI-03 | Phase 47 | Complete |
| PKI-04 | Phase 47 | Complete |
| PKI-05 | Phase 47 | Complete |
| PKI-06 | Phase 47 | Complete |
| PKI-07 | Phase 47 | Complete |
| PKI-08 | Phase 47 | Complete |
| DNS-01 | Phase 45 | Complete |
| DNS-02 | Phase 45 | Complete |
| DNS-03 | Phase 45 | Complete |
| DNS-04 | Phase 45 | Complete |
| DNS-05 | Phase 45 | Complete |
| DNS-06 | Phase 45 | Complete |
| DNS-07 | Phase 45 | Complete |
| DNS-08 | Phase 45 | Complete |
| PLN-01 | Phase 46 | Complete |
| PLN-02 | Phase 46 | Complete |
| PLN-03 | Phase 46 | Complete |
| PLN-04 | Phase 46 | Complete |
| PLN-05 | Phase 46 | Complete |
| WAC-01 | Phase 48 | Planned |
| WAC-02 | Phase 48 | Planned |
| WAC-03 | Phase 48 | Planned |
| WAC-04 | Phase 48 | Planned |
| WAC-05 | Phase 48 | Planned |
| WAC-06 | Phase 48 | Planned |
| WAC-07 | Phase 48 | Planned |
| WAC-08 | Phase 48 | Planned |
| HDR-01 | Phase 49 | Planned |
| HDR-02 | Phase 49 | Planned |
| HDR-03 | Phase 49 | Planned |
| HDR-04 | Phase 49 | Planned |
| HDR-05 | Phase 49 | Planned |
| HDR-06 | Phase 49 | Planned |
| HDR-07 | Phase 49 | Planned |
| HDR-08 | Phase 49 | Planned |

**Coverage:**

- v1.2 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0
- v1.3 requirements: 8 total
- v1.3 mapped to phases: 8
- v1.3 unmapped: 0
- v1.4 requirements: 6 total
- v1.4 mapped to phases: 6
- v1.4 unmapped: 0
- v1.5 requirements: 6 total
- v1.5 mapped to phases: 6
- v1.5 unmapped: 0
- v1.6 requirements: 8 total
- v1.6 mapped to phases: 8
- v1.6 unmapped: 0
- v1.7 requirements: 8 total
- v1.7 mapped to phases: 8
- v1.7 unmapped: 0
- v1.8 requirements: 21 total
- v1.8 mapped to phases: 21
- v1.8 unmapped: 0

**Total:** 83 requirements | 55 complete | 28 open | 0 unmapped

---
*Requirements defined: 2026-06-24*
*Last updated: 2026-07-12 after Phase 46 planning reconciliation and v1.8 ordering*
