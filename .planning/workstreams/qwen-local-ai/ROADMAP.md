# Roadmap: Qwen Local AI Canary

**Workstream:** `qwen-local-ai`
**Current phase:** 59
**Requirements:** `.planning/workstreams/qwen-local-ai/REQUIREMENTS.md`
**State:** `.planning/workstreams/qwen-local-ai/STATE.md`

## Phase 59: Qwen3 Embedding e Rerank Podman para k3s

**Goal:** Operar Qwen3 Embedding e Rerank como canary ARM64 isolado no k3s, com GTE titular preservado, pipeline global de dois ciclos, índices Qdrant 1024d reversíveis e evidência funcional, de qualidade, capacidade e soak de 72 horas antes de qualquer promoção manual.
**Requirements:** QAI-01..QAI-08
**Depends on:** Phase 50; Phase 41 como contexto técnico; e o inventário autoritativo do workstream `network-horistic-readdress`/Phase 54 se a migração de IP ocorrer primeiro.
**Status:** Planned
**Risk:** HIGH
**Plans:** 0/9 complete

### Execution waves

- [ ] Wave 0 — `59-01-PLAN.md`: harness, inventário live, baseline GTE-only e decisão de leases.
- [ ] Wave 1 — `59-02-PLAN.md`: reranker dedicado q8, contratos TDD, limits e warmup.
- [ ] Wave 2 — `59-03-PLAN.md`: manifests e rollout controlado de `qwen-canary`.
- [ ] Wave 3 — `59-04-PLAN.md`: catálogo/router/governor, `/v1/rerank` e dois slots.
- [ ] Wave 4 — `59-05-PLAN.md`: collections Qdrant 1024d e rollback atômico.
- [ ] Wave 5 — `59-06-PLAN.md`: smokes funcionais, concorrência, cancel/TTL e isolamento GTE.
- [ ] Wave 6 — `59-07-PLAN.md`: avaliação pareada de qualidade e capacidade.
- [ ] Wave 7 — `59-08-PLAN.md`: soak serializado de pelo menos 72 horas.
- [ ] Wave 8 — `59-09-PLAN.md`: rollback drill, restore/replay, knowledge e decisão manual.

### Success criteria

1. O canário não altera o GTE titular nem mistura vetores 768d e 1024d.
2. Cada pod respeita a unidade de `500m` e o orçamento agregado declarado.
3. Os gates funcionais, de qualidade, capacidade e soak passam com evidência redatada.
4. Rollback é reproduzível e não exige reindex emergencial.
5. Promoção depende de decisão manual explícita após todos os gates.

**Validation:** `.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-VALIDATION.md`
