# Requirements: Omni Srv Admin — v1.2 to v1.6

**Defined:** 2026-06-24
**Milestone:** multi-milestone reconciliation through v1.6
**Core Value:** Servidor Atius sempre provisionado, documentado e operante, com governanca centralizada e identidade/SSO evoluindo sem quebrar producao.

## v1.2 Requirements

### G18 — Ubuntu Pro / ESM / Landscape SaaS

- [ ] **G18-01**: Operador consegue ver o estado Ubuntu Pro/ESM dos SRV-1/SRV-2/SRV-3/horistic-srv, incluindo token/account, attach status, services, apt sources e pendencias por host.
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
- [x] **EMB-02**: New API possui canal interno para embeddings que aponta para o TEI em `http://10.1.1.4:3115`, nunca para `https://router.atius.com.br/v1`, evitando loop.
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

- [ ] **PKI-01**: Operador consegue renderizar, por inventario, o plano de PKI interna para `atius-srv-1`, `atius-srv-2`, `atius-srv-3` e `horistic-srv`, incluindo SANs, caminhos, dry-run e comandos sem material secreto.
- [ ] **PKI-02**: `omni-srv-admin` possui comando/versioned resource `omni fleet trust-pki` com preflight, init CA, issue-host, install-trust, verify, rollback-plan, onboard-host, reconcile-host e rotate-host, todos dry-run por default e mutacao apenas com gate explicito.
- [ ] **PKI-03**: A CA interna de servicos fica root-only fora de Git, `.planning`, Obsidian, GBrain, logs e shell history, com backup/serial/index/CRL state e regra de rotacao documentada.
- [ ] **PKI-04**: Cada servidor gerenciado, inclusive servidor novo cadastrado no inventario/DbOmniFleet, possui key/CSR/leaf/chain proprios, com private key local root-only e leaf contendo `serverAuth`, `clientAuth`, `CA:FALSE` e SANs de VPN IP, public IP e aliases declarados.
- [ ] **PKI-05**: Todos os servidores instalam e validam a CA chain via trust store do sistema (`update-ca-certificates`), sem instalar leafs de peers como root CAs.
- [ ] **PKI-06**: A validacao passa uma matriz 4x4: 4 verificacoes locais e 12 verificacoes HTTPS remotas entre os hosts, com hostname/IP SAN validation e TLS verify code `0`.
- [ ] **PKI-07**: A funcionalidade produz audit JSON/redacted logs, docs operacionais, Obsidian e GBrain com fingerprints, paths, backups e resultados, sem vazar chaves, tokens ou passphrases.
- [ ] **PKI-08**: O plano deixa explicito que HTTPS real de servicos, como TEI em `https://10.1.1.4:3115`, exige proxy/listener TLS e gate de servico separado antes de alterar channels ou portas em producao.

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
| SSO-01 | Phase 42 | In Progress |
| SSO-02 | Phase 42 | In Progress |
| SSO-03 | Phase 42 | In Progress |
| SSO-04 | Phase 42 | In Progress |
| SSO-05 | Phase 42 | In Progress |
| SSO-06 | Phase 42 | In Progress |
| CDX-01 | Phase 43 | Complete |
| CDX-02 | Phase 43 | Complete |
| CDX-03 | Phase 43 | Complete |
| CDX-04 | Phase 43 | Complete |
| CDX-05 | Phase 43 | Complete |
| CDX-06 | Phase 43 | Complete |
| PKI-01 | Phase 44 | In Progress |
| PKI-02 | Phase 44 | In Progress |
| PKI-03 | Phase 44 | In Progress |
| PKI-04 | Phase 44 | In Progress |
| PKI-05 | Phase 44 | In Progress |
| PKI-06 | Phase 44 | In Progress |
| PKI-07 | Phase 44 | In Progress |
| PKI-08 | Phase 44 | In Progress |

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

---
*Requirements defined: 2026-06-24*
*Last updated: 2026-07-06 after reconciling Phase 42/43/44 status and traceability*
