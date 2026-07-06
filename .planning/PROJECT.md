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

**Current milestone:** v1.4 - Atius-wide SSO and Login
**Current phase:** 42
**Current objective:** fechar `42-03` para publicar `sso.atius.com.br` com
gate de edge, rollback e smoke real, preservando o `auth-token` e o RBAC ATS.

**Open carry-over after v1.4:**

- v1.6 / Phase 44 - Internal Service PKI and Fleet Trust (`44-02`, `44-03`)

**Recently shipped out of sequence:**

- v1.3 / Phase 41 - embeddings locais com `embedding-gte-v1`
- v1.5 / Phase 43 - Codex MCP bootstrap hardening no `GIOVANNI-W11-PC`

## Active Requirements

### v1.4 - Atius-wide SSO / Login

- [ ] **SSO-01**: `sso.atius.com.br` publicado como host canonico de login com contrato de DNS/Apache/Cloudflare/TLS e rollback.
- [ ] **SSO-02**: Keycloak em `auth.atius.com.br` usado como provedor OIDC controlado sem quebrar o SSO/JWT legado.
- [ ] **SSO-03**: ATS usa o novo fluxo SSO preservando `auth-token` e RBAC local.
- [ ] **SSO-04**: Redirect seguro de volta para `trade`, `painel`, `dashboard`, `backtest`, `strategy` e futuros apps ATIUS.
- [ ] **SSO-05**: Logout global limpa sessao Keycloak e cookies legados `.atius.com.br`.
- [ ] **SSO-06**: Nenhum token, secret ou credencial de smoke entra em Git, `.planning`, Obsidian, GBrain, logs ou shell history.

### v1.6 - Internal Service PKI / Fleet HTTPS

- [ ] **PKI-01**: Plano de PKI interna renderizado por inventario para os 4 hosts.
- [ ] **PKI-02**: `omni fleet trust-pki` existe com preflight, init, issue, install, verify e rollback-plan.
- [ ] **PKI-03**: CA interna root-only fora de Git, `.planning`, Obsidian, GBrain e logs.
- [ ] **PKI-04**: Cada host possui key/CSR/leaf/chain proprios com SANs corretos.
- [ ] **PKI-05**: Todos os hosts instalam a CA chain via trust store do sistema.
- [ ] **PKI-06**: Matriz 4x4 valida HTTPS entre todos os hosts com verify code `0`.
- [ ] **PKI-07**: A auditoria gera JSON/logs/docs redacted sem chaves ou passphrases.
- [ ] **PKI-08**: O plano deixa explicito que migracao real de TEI/servicos para HTTPS exige gate separado.

## Recently Validated

### v1.3 - Local AI Embeddings / Semantic Retrieval

- [x] **EMB-01** through **EMB-08**: entregues em Phase 41.
- TEI roda em `horistic-srv`, namespace `ebeddings-local`, endpoint privado
  `http://10.1.1.4:3115`.
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
- WireGuard legacy/rollback still exists on `10.1.1.0/24`.
- `wg100` is the active internal service path on `10.100.100.0/24`.

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

## Evolution

Update this file whenever:

1. the active milestone changes;
2. a phase closes and its requirements become validated;
3. a shipped milestone changes the next operator priority;
4. a cross-session reconciliation changes what the repo claims is complete.

---
*Last updated: 2026-07-06 during roadmap/requirements/state reconciliation*
