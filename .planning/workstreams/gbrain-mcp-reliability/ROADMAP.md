# GBrain MCP Reliability Roadmap

**Milestone:** v2.0 — GBrain MCP Reliability Recovery
**Workstream:** `gbrain-mcp-reliability`
**Status:** Planned
**Execution order:** strict 60 → 61 → 62 → 63 → 64 → 65

## Objective

Transformar o GBrain HTTP MCP de “endpoint responde” em um sistema restaurável, atualizado, íntegro, observável e documentado, com métricas honestas e evidência ponta a ponta.

## Phase Gates

### Phase 60: Recovery Foundation

**Goal:** Backups restauráveis, fila serial, secret hygiene e conectividade PgBouncer antes de qualquer mutação de corpus.
**Requirements:** BKP-01, BKP-02, BKP-03, BKP-04, BKP-05, SEC-01, SEC-02, SEC-03, SYNC-01
**Plans:** 4
**Depends on:** none
**Status:** Not started

- [ ] `60-01-PLAN.md` — Immutable baseline and restore harness
- [ ] `60-02-PLAN.md` — Serial backup queue and stuck-job recovery
- [ ] `60-03-PLAN.md` — MCP secret and log hygiene
- [ ] `60-04-PLAN.md` — PgBouncer-compatible GBrain runtime

**Exit gate:** `60-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

### Phase 61: Source Truth and Sync

**Goal:** Restaurar o fluxo vault→GBrain e tornar freshness/automação honestos.
**Requirements:** SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06
**Plans:** 2
**Depends on:** 60
**Status:** Not started

- [ ] `61-01-PLAN.md` — Sync contract, freshness truth and host migrations
- [ ] `61-02-PLAN.md` — Controlled source synchronization and automation proof

**Exit gate:** `61-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

### Phase 62: Graph and Context Recovery

**Goal:** Reindexar conteúdo com preservação, extrair links/timeline e recuperar contextual retrieval.
**Requirements:** GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05
**Plans:** 3
**Depends on:** 61
**Status:** Not started

- [ ] `62-01-PLAN.md` — Corpus-preserving reindex and extraction harness
- [ ] `62-02-PLAN.md` — Markdown reindex and link/timeline extraction
- [ ] `62-03-PLAN.md` — Orphan classification and contextual retrieval recovery

**Exit gate:** `62-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

### Phase 63: Embedding Integrity and Catch-up

**Goal:** Reconciliar provenance/signatures e completar embeddings 768d com quality gates.
**Requirements:** EMB-01, EMB-02, EMB-03, EMB-04, EMB-05
**Plans:** 3
**Depends on:** 62
**Status:** Not started

- [ ] `63-01-PLAN.md` — Embedding space and provenance contract
- [ ] `63-02-PLAN.md` — Embedding metadata reconciliation
- [ ] `63-03-PLAN.md` — Rate-governed embedding catch-up and semantic acceptance

**Exit gate:** `63-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

### Phase 64: Control Plane, Schema and PostgreSQL

**Goal:** Corrigir skills, schema, config planes, métricas e menor privilégio PostgreSQL.
**Requirements:** CTL-01, CTL-02, CTL-03, CTL-04, CTL-05, CTL-06, OBS-01
**Plans:** 4
**Depends on:** 63
**Status:** Not started

- [ ] `64-01-PLAN.md` — MCP skill catalog and schema-pack identity
- [ ] `64-02-PLAN.md` — Schema graph, aliases and taxonomy convergence
- [ ] `64-03-PLAN.md` — Truthful health metrics and config-plane convergence
- [ ] `64-04-PLAN.md` — PostgreSQL collation and least privilege

**Exit gate:** `64-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

### Phase 65: Observability, Docs and Closeout

**Goal:** Fechar causas de falha, regressão MCP, documentação e aceite integral.
**Requirements:** OBS-02, OBS-03
**Plans:** 3
**Depends on:** 64
**Status:** Not started

- [ ] `65-01-PLAN.md` — Disconnect and reranker failure root cause
- [ ] `65-02-PLAN.md` — End-to-end MCP and operational acceptance
- [ ] `65-03-PLAN.md` — Canonical documentation, GBrain indexing and milestone closeout

**Exit gate:** `65-VERIFICATION.md` must be PASS; all owned requirements have evidence and rollback state.

## Global Success Criteria

- PostgreSQL backup has current checksum and successful disposable restore.
- Source bookmark equals the approved vault HEAD and freshness reflects real time/commit state.
- Link, contextual retrieval and embedding coverage use active-only denominators and documented targets.
- MCP skills/schema/config/health operations are internally consistent and pass public-edge regression.
- GBrain DB role is least-privilege, collation is current and PgBouncer exposure is justified/hardened.
- Obsidian, repo docs and GBrain index agree; no secret appears in evidence.

## Out of Scope

- Replacing Obsidian as source of truth.
- Migrating to an unrelated npm package named `gbrain` (registry latest 1.3.1 is not this runtime).
- Running rclone outside the fleet queue.
- Altering unrelated RustDesk, Qwen, network or runtime-trust workstreams.
