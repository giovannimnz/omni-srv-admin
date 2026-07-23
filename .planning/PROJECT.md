# Omni Srv Admin (omni-srv-admin)

## What This Is

Central repository for ATIUS server operations, fleet governance, identity
infrastructure, internal AI services, and the operator runbooks that keep those
systems reproducible.

The repo is no longer just "server setup". It is the planning and control-plane
surface for:

- fleet inventory, CLI, and governance;
- FreeIPA / Keycloak / Samba domain work;
- internal AI routing and embeddings;
- Codex runtime hardening;
- internal service PKI and trust rollout.

## Core Value

Servidor Atius sempre provisionado, documentado e operante, com governanca e
identidade centralizadas, sem quebrar producao durante evolucoes de login,
runtime ou rede interna.

## Current Delivery Track

**Current milestone:** v1.8 - Runtime Trust and Codex Delivery Convergence
**Current phase:** 47.1 - Internal DNS Authority and FreeIPA Convergence
**Current objective:** planejar e executar a autoridade FreeIPA, o forwarding
CoreDNS/AdGuard e o split DNS deterministico antes do owner-host trust de
48-03; a lane independente de Phase 48 plans 48-01/48-02 pode continuar sem
Headroom e sem competir com a correcao `oci_admin_http`.

**Canonical delivery order:**

- Phase 46 - planning reconciliation (complete)
- Phase 47 - PKI listener/trust closeout (complete; continues 44-02/44-03)
- Phase 47.1 - FreeIPA authoritative internal DNS plus CoreDNS/AdGuard convergence (current prerequisite for 48-03)
- Phase 48 - Router Codex OAuth + Wayland local/remote ACP convergence (48-01/48-02 may continue; 48-03+ blocked on 47.1)
- Phase 49 - Headroom isolated canary and Wayland integration
- Phase 50 - SSO publication/logout/RBAC closeout (continues 42-03)

## Parallel Workstream: v1.9 RustDesk Fleet Remote Access

**Goal:** entregar acesso remoto self-hosted, reversível e exaustivamente
validado nos cinco computadores autorizados, com `atius-srv-2` como primary
`hbbs`/`hbbr` quando o capacity gate passar e `atius-srv-3` como standby apenas
depois de restore/failover real.

**Target features:**

- RustDesk Server OSS `1.1.15` e clients `1.4.9` pinados por digest/checksum;
- clients em `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv` e
  `GIOVANNI-W11-PC`, sem instalar no WSL nem no `GIOVANNI-S23`;
- direct-first em produção, forced-relay como gate controlado, secrets apenas no
  Vault e fallbacks RustGuac/XRDP/AnyDesk/NoMachine preservados;
- 20 pares dirigidos normais, cinco forced-relay por target, negativos,
  reboot/pre-login/UAC, soak, upgrade, rollback e DR antes do aceite final.

**Canonical planning:**
`.planning/workstreams/rustdesk-fleet/{REQUIREMENTS,ROADMAP,STATE}.md` e
`.planning/research/rustdesk-fleet/`.

**Recently shipped out of sequence:**

- v1.3 / Phase 41 - embeddings locais com `embedding-gte-v1`
- v1.5 / Phase 43 - Codex MCP bootstrap hardening no `GIOVANNI-W11-PC`

## Requirements

### v1.7 - Internal DNS / DRG Canonicalization

- [x] **DNS-01..DNS-08**: entregues na Phase 45; DRG/OCI e DNS interno sao canonicos e `wg100` permanece reserva/edge.

### v1.8 - Planning / Codex / Wayland

- [x] **PLN-01..PLN-05**: ordem historica/ativa e validacao por fase reconciliadas na Phase 46.
- [ ] **IDA-01..IDA-08**: FreeIPA, CoreDNS, AdGuard, A/PTR/SRV, split DNS, host keys, HA gate e rollback convergem na Phase 47.1.
- [ ] **WAC-01..WAC-08**: OAuth Codex, catalogo e local/remote ACP convergem sem Headroom na Phase 48.
- [ ] **HDR-01..HDR-08**: Headroom passa canario isolado, ACP, Wayland e rollback na Phase 49.

### v1.9 - RustDesk Fleet Remote Access

- [ ] **SCP-01..SCP-05**: escopo, OSS/Pro gate, direct-first, supply chain e isolamento GSD ficam explícitos.
- [ ] **SRV-01..SRV-07**: primary, edge, key, capacity, persistência, backup e portas mínimas são comprovados.
- [ ] **CLI-01..CLI-09**: os cinco clients são instalados, configurados, persistentes e compatíveis com os fallbacks atuais.
- [ ] **VAL-01..VAL-07**: a matriz 20+5, negativos, GUI, reboot e soak produzem evidência íntegra.
- [ ] **DR-01..DR-04**: standby, failover/failback, upgrade/downgrade e rollback real passam.
- [ ] **OPS-01..OPS-04**: monitoring, docs, inventory, Obsidian, GBrain, Graphify e UAT convergem com o runtime.

### v1.4 - Atius-wide SSO / Login

- [ ] **SSO-01**: `sso.atius.com.br` publicado como host canonico de login com contrato de DNS/Apache/Cloudflare/TLS e rollback.
- [ ] **SSO-02**: Keycloak em `auth.atius.com.br` usado como provedor OIDC controlado sem quebrar o SSO/JWT legado.
- [ ] **SSO-03**: ATS usa o novo fluxo SSO preservando `auth-token` e RBAC local.
- [ ] **SSO-04**: Redirect seguro de volta para `trade`, `painel`, `dashboard`, `backtest`, `strategy` e futuros apps ATIUS.
- [ ] **SSO-05**: Logout global limpa sessao Keycloak e cookies legados `.atius.com.br`.
- [ ] **SSO-06**: Nenhum token, secret ou credencial de smoke entra em Git, `.planning`, Obsidian, GBrain, logs ou shell history.

### v1.6 - Internal Service PKI / Fleet HTTPS

- [x] **PKI-01**: Plano de PKI interna renderizado por inventario para os 4 hosts.
- [x] **PKI-02**: `omni fleet trust-pki` existe com preflight, init, issue, install, verify e rollback-plan.
- [x] **PKI-03**: CA interna root-only fora de Git, `.planning`, Obsidian, GBrain e logs.
- [x] **PKI-04**: Cada host possui key/CSR/leaf/chain proprios com SANs corretos.
- [x] **PKI-05**: Todos os hosts instalam a CA chain via trust store do sistema.
- [x] **PKI-06**: Matriz 4x4 valida HTTPS entre todos os hosts com verify code `0`.
- [x] **PKI-07**: A auditoria gera JSON/logs/docs redacted sem chaves ou passphrases.
- [x] **PKI-08**: O plano deixa explicito que migracao real de TEI/servicos para HTTPS exige gate separado.

## Recently Validated

### v1.3 - Local AI Embeddings / Semantic Retrieval

- [x] **EMB-01** through **EMB-08**: entregues em Phase 41.
- TEI roda em `horistic-srv`, namespace `ebeddings-local`, endpoint privado
  `http://10.21.1.21:3115`.
- Alias publico atual: `embedding-gte-v1`.

### v1.5 - Codex Runtime / MCP Bootstrap Reliability

- [x] **CDX-01** through **CDX-06**: entregues em Phase 43.
- Baseline daily do Codex ficou lean, com MCPs pesados migrados para perfis
  opt-in e smoke repetivel de bootstrap.

## Context

### Fleet and Internal Network

- `atius-srv-1`: control plane, router-facing operations, CA candidate for
  service PKI.
- `atius-srv-2`: governance / support services.
- `atius-srv-3`: Vault / FreeIPA / Keycloak-related private services.
- `horistic-srv`: k3s worker, TEI, internal AI workloads.
- DRG/OCI private IPs are the primary internal service plane:
  `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.
- `wg100` / `10.100.100.0/24` is reserve fallback only.
- `10.1.1.0/24` is retired and must not be reintroduced as active DNS,
  service routing, validation, or rollback path.
- `oci-admin` is the dependency owner for DRG route/security/private-IP proof;
  Phase 47.1 consumes a read-only snapshot and requires an approved OperationPlan
  before assigning the dedicated FreeIPA DNS secondary private IP.
- `home-proxy` / residential PPTP is home-edge fallback only; it must not
  redefine internal DNS or DRG routing.
- Wayland on `atius-srv-3` must expose GSD as skills/commands, not runtime
  agents; this is a parallel tooling track, not a DNS blocker.

### Identity and Auth

- FreeIPA, Keycloak, and Samba foundation phases are already canonized as
  complete.
- The ATS legacy auth contract remains authoritative until Phase 42 fully
  closes.
- Backend DB permissions remain authoritative even when Keycloak authenticates
  the user.

## Constraints

- Existing production auth and trading flows must remain reversible.
- No secret material in Git, `.planning`, Obsidian, GBrain, logs, screenshots,
  or shell history.
- Live edge publication, CA generation, or trust-store mutation requires an
  explicit gate.
- Planning artifacts must stay aligned with roadmap, requirements, summaries,
  and state.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Keycloak remains identity-only during SSO migration | Preserve ATS RBAC and current `auth-token` contract | Active |
| Internal service PKI uses CA trust, not peer leaf-as-root | Prevent trust-boundary and revocation problems | Active |
| TEI stays private behind router alias | Avoid self-loop and uncontrolled public exposure | Active |
| Codex runtime baseline stays lean | Reduce noisy MCP bootstrap and optional dependency failure | Shipped in Phase 43 |
| Internal DNS is DRG-first | DRG is faster and hardware-free; WireGuard is fallback only | Shipped in Phase 45 |
| FreeIPA owns `atius.internal` authority | Preserve A/PTR/SRV/Kerberos/SSSD in one source while CoreDNS and AdGuard remain resolver frontends | Planned in Phase 47.1 |
| Phase planning lives in `.planning` | Avoid stale execution order in docs/runbooks | Reconciled in Phase 46 |
| RustDesk v1.9 starts OSS and direct-first | Five-host single-operator scope does not require Pro control plane; relay remains testable fallback | Pending validation; Pro becomes mandatory if SSO/RBAC/human audit is required |
| RustDesk uses isolated GSD workstream | Preserve Phase 48 and prevent cross-lane planning mutations | Workstreams migrated with external snapshot on 2026-07-19 |

## Evolution

Update this file whenever:

1. the active milestone changes;
2. a phase closes and its requirements become validated;
3. a shipped milestone changes the next operator priority;
4. a cross-session reconciliation changes what the repo claims is complete.

---
*Last updated: 2026-07-19 during RustDesk v1.9 milestone initialization*
