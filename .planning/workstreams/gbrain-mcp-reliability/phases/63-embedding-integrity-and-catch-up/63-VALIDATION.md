---
phase: 63-embedding-integrity-and-catch-up
status: planned
nyquist: required
---

# Phase 63 Validation Strategy

## Test layers

1. Unit/fixture tests for every new parser, guard, patcher and state transition.
2. Dry-run against redacted snapshots/live read-only state.
3. Canary mutation only after preflight and explicit gate where required.
4. Readback against an independent surface (SQL, MCP, systemd, remote checksum or semantic query).
5. Rollback rehearsal before broad apply.
6. Phase verification maps every owned requirement to evidence.

## Gates mensuráveis incorporados da revisão assíncrona

- `gbrain embed --all --dry-run` precisa resolver sem mutation antes do canary.
- Source proof: `parseModelId()` separa `openai:embedding-gte-v1`; `resolveEmbeddingProvider()` entrega apenas `embedding-gte-v1` ao SDK.
- Provider smoke: HTTP 200, vetor 768d, sem key/vector persistido em evidência.
- Metadata: model `openai:embedding-gte-v1`, dimensions `768`, signature `openai:embedding-gte-v1:768`; amostra 5/5.
- Coverage: `missing_embeddings=0` para chunks ativos elegíveis. O valor `557` sugerido pela revisão como PASS foi rejeitado por estar semanticamente invertido.
- Qualidade: corpus fixo versionado com pelo menos 5 queries e comparação pré/pós. Score universal `>0.7` rejeitado porque a escala depende do modelo/reranker.
- Contagens live devem ser recalculadas; 3.941 e 3.942 apareceram em leituras distintas.

## Stop conditions

- Backup/restore gate not PASS.
- Source HEAD/generation drift.
- Secret detected in output/artifact.
- Unknown/malformed evidence.
- Active/deleted denominator ambiguity.
- Error budget, cost cap or timeout exceeded.
- Rollback unavailable or untested.

## Required phase artifact

Create `63-VERIFICATION.md` with PASS/BLOCK/UNKNOWN per requirement, commands, evidence paths and residual risk. The phase cannot close on summary-only evidence.
