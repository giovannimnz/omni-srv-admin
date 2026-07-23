# Requirements: Qwen Local AI Canary

**Workstream:** `qwen-local-ai`
**Phase:** 59
**Status:** Planned

## Requirements

- [ ] **QAI-01**: GTE permanece titular, com aliases, namespace `ebeddings-local` e índices 768d intactos durante todo o canário.
- [ ] **QAI-02**: Qwen3 Embedding e o reranker dedicado executam em ARM64 com requests e limits de `500m` por pod, sem `hostNetwork` e com alcance privado.
- [ ] **QAI-03**: O router controla no máximo dois pipelines completos Embedding -> VectorDB -> Rerank, com lease idempotente em sucesso, erro, cancelamento e TTL.
- [ ] **QAI-04**: As collections Qdrant 1024d/Cosine são separadas das collections GTE 768d e possuem assinatura, corpus, chunk e logical IDs reproduzíveis.
- [ ] **QAI-05**: Smokes cobrem saúde, batch, dimensão, normalização, rerank, concorrência, falhas, alcance privado e isolamento do GTE.
- [ ] **QAI-06**: A avaliação pareada congela corpus/qrels e comprova qualidade e capacidade sem regressão acima dos limites definidos no contrato da Phase 59.
- [ ] **QAI-07**: O soak contínuo de pelo menos 72 horas conclui sem OOM, restart ou starvation e preserva os artefatos imutáveis da Wave 0.
- [ ] **QAI-08**: Rollback atômico e restore/replay são exercitados antes de qualquer decisão manual de promoção; a fase nunca promove Qwen automaticamente.

## Traceability

| Requirement | Phase | Primary evidence |
|---|---:|---|
| QAI-01..QAI-04 | 59 | `59-WAVE0-GATE.json`, manifests e lifecycle do router |
| QAI-05 | 59 | `59-FUNCTIONAL-SMOKE.json` |
| QAI-06 | 59 | `59-EVAL-FREEZE.json`, `59-QUALITY-CAPACITY-EVAL.json` |
| QAI-07 | 59 | `59-SOAK-RESULT.json` |
| QAI-08 | 59 | `59-ROLLBACK-DRILL.json`, decisão manual |

## Boundaries

- A migração de rede Horistic é propriedade do workstream `network-horistic-readdress`, Phase 54.
- Secrets, tokens, dados brutos de produção e material de Vault não entram em Git, `.planning`, Obsidian, GBrain ou logs.
- A Phase 59 resolve explicitamente a topologia antes da Wave 0: se a Phase 54 ainda não tiver sido executada, inventário versionado e probes live devem concordar no ramo `pre-phase54` (`10.21.1.21`); se já tiver sido executada, `54-04-SUMMARY.md`, `54-04-EVIDENCE.md`, inventário versionado e probes live devem concordar no ramo `post-phase54` (`10.31.1.31`). Estado misto, evidência ausente ou divergência bloqueiam a Wave 0. O gate de ordem herdado da Phase 50 (SSO) não é uma dependência técnica ou operacional do canário Qwen.
