# Roadmap: Qwen Local AI Cutover

**Workstream:** `qwen-local-ai`
**Current phase:** 59
**Requirements:** `.planning/workstreams/qwen-local-ai/REQUIREMENTS.md`
**State:** `.planning/workstreams/qwen-local-ai/STATE.md`

## Phase 59: Qwen3 Embedding e Rerank Podman para k3s

**Goal:** Substituir GTE Embedding/Rerank por Qwen3 Embedding INT8/ONNX 1024d e Qwen3 Reranker ONNX no k3s ARM64. O cutover foi explicitamente autorizado: Qwen deve ficar pronto, validado e com rollback capturado antes de remover os workloads GTE.
**Requirements:** QAI-01..QAI-08
**Depends on:** Phase 41 como contexto técnico; e o inventário autoritativo do workstream `network-horistic-readdress`/Phase 54 se a migração de IP ocorrer primeiro.
**Status:** Ready for execution bootstrap
**Risk:** HIGH
**Plans:** 0/9 complete

### Execution waves

- [ ] Wave 0 — `59-01-PLAN.md`: autoridade/freeze, Qdrant control/data plane, Redis AOF+WAITAOF, qrels, baseline e rollback imutável.
- [ ] Wave 1 — `59-02-PLAN.md`: artefatos reproduzíveis, oracle FP16, auditoria npm transitiva/ignored-script, reranker hardening e manifests.
- [ ] Wave 2 — `59-03-PLAN.md`: âncora GTE 768d, backup/restore e congelamento do HPA.
- [ ] Wave 3 — `59-04-PLAN.md`: rollout Qwen 2x Embedding + 2x Reranker a 500m, quota de coexistência 4/2000m, PDB 1+1 e rollout sem surge.
- [ ] Wave 4 — `59-05-PLAN.md`: state machine Redis durável, router/governor, alias arbiter exclusivo e API `/v1/rerank`.
- [ ] Wave 5 — `59-06-PLAN.md`: data broker L7 + issuer Qdrant, clients com owner attestation, dual reindex 768/1024, tool/image/Job de replay congelados, oracle, qualidade, capacidade e smokes.
- [ ] Wave 6 — `59-07-PLAN.md`: cutover transacional Qwen titular, incluindo Graphify Qwen/1024 com publisher root-owned de operações fixas, heartbeat metadata-only e rollback compensatório.
- [ ] Wave 7 — `59-08-PLAN.md`: soak pós-cutover de 72h, UID/Pod lineage, Redis AOF-confirmed, watchdog independente e auto-rollback sob arbiter outage reconciliável.
- [ ] Wave 8 — `59-09-PLAN.md`: finalizer sem Kubernetes credential + cleanup-authority Job temporário de 500m em failure domain independente, drill Qwen→GTE→Qwen, replay por client temporário do data broker com UID/resourceVersion cleanup e authority self-revoke comprovados, restore publisher-only/readback Graphify 1024, retirement GTE e ativação validada do teto transitório 5/2500m com rollout serial.

### Success criteria

1. Qwen é titular em 1024d; os vetores 768d GTE permanecem isolados e recuperáveis somente pelo backup/rollback.
2. Cada pod respeita a unidade de `500m` e o orçamento agregado declarado.
3. Os gates funcionais, de qualidade, capacidade, cutover e soak passam com evidência redatada.
4. Rollback é reproduzível e não exige reindex emergencial.
5. A promoção/cutover foi autorizada pelo operador em 2026-07-23; a remoção do GTE só ocorre depois dos gates de readiness, qualidade, cutover, soak e rollback drill.

**Validation:** `.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-VALIDATION.md`
