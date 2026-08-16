# Requirements: Qwen Local AI Cutover

**Workstream:** `qwen-local-ai`
**Phase:** 59
**Status:** Planned

## Requirements

- [ ] **QAI-01**: Qwen passa a titular com aliases de produção; GTE permanece disponível e rollback-ready até readiness, smoke, qualidade, capacidade, cutover, soak e rollback drill passarem, sendo então retirado de `ebeddings-local`.
- [ ] **QAI-02**: Qwen3 Embedding e o reranker dedicado executam em ARM64 com requests e limits de `500m` por pod, sem `hostNetwork` e com alcance privado. O envelope de modelos é desejado `2+2=4 pods/2000m`, piso degradado `1+1=2 pods/1000m` e máximo transitório de `5 pods/2500m` somente em rollout serial pós-GTE; quota/PDB negam sexto pod, HPA e dois surges simultâneos.
- [ ] **QAI-03**: O router controla no máximo dois pipelines completos Embedding -> VectorDB -> Rerank, com lease idempotente em sucesso, erro, cancelamento e TTL; cada epoch de segurança é duravelmente confirmado no AOF do Redis primary e de uma replica independente antes do efeito externo.
- [ ] **QAI-04**: As collections Qdrant 1024d/Cosine são separadas das collections GTE 768d e possuem assinatura, corpus, chunk e logical IDs reproduzíveis; aliases usam somente o alias arbiter, enquanto provisionamento, reindex, snapshot e replay atravessam um data broker L7 privado mTLS sem passthrough, único portador da credential/egress nativa. Um issuer separado usa bootstrap server-auth TLS pinado, nonce/CSR PoP e atesta TokenReview→Pod→owner Job→runner/image antes de assinar. Journal AOF-confirmed e finalizer sem Kubernetes credential solicitam cleanup a um Job authority temporário de 500m em failure domain independente; ele usa projected token/kubelet renewal com a API audience descoberta do k3s, DELETE UID/resourceVersion-preconditioned e terminal self-revoke, tornando revogação, exact UID deletion e negativos crash-durable.
- [ ] **QAI-05**: Smokes cobrem saúde, batch, dimensão 1024, normalização, rerank, concorrência, falhas, alcance privado, cutover e rollback para GTE.
- [ ] **QAI-06**: A avaliação pareada congela corpus/qrels e comprova qualidade e capacidade sem regressão acima dos limites definidos no contrato da Phase 59.
- [ ] **QAI-07**: O soak contínuo de pelo menos 72 horas monitora o Qwen já titular, preserva os artefatos imutáveis da Wave 0 e executa rollback automático em hard failure antes do retirement do GTE, inclusive após perda do processo/host do alias arbiter quando o journal durável estiver reconciliável; ambiguidade permanece drenada e bloqueada.
- [ ] **QAI-08**: Rollback atômico e restore/replay são exercitados antes da remoção definitiva dos recursos GTE; o índice Graphify servido só pode ser publicado/restaurado pelo publisher root-owned de operações fixas; a promoção Qwen foi autorizada manualmente pelo operador em 2026-07-23.

## Traceability

| Requirement | Phase | Primary evidence |
|---|---:|---|
| QAI-01..QAI-04 | 59 | `59-WAVE-0-GATE.json`, manifests e lifecycle do router |
| QAI-05 | 59 | `59-FUNCTIONAL-SMOKE.json` |
| QAI-06 | 59 | `59-EVAL-FREEZE.json`, `59-QUALITY-CAPACITY-EVAL.json` |
| QAI-07 | 59 | `59-SOAK-EVIDENCE.json`, `59-WAVE-7-GATE.json` |
| QAI-08 | 59 | `59-ROLLBACK-DRILL.json`, `59-RETIREMENT-EVIDENCE.json` |

## Boundaries

- A migração de rede Horistic é propriedade do workstream `network-horistic-readdress`, Phase 54.
- Secrets, tokens, dados brutos de produção e material de Vault não entram em Git, `.planning`, Obsidian, GBrain ou logs.
- A Phase 59 resolve explicitamente a topologia antes da Wave 0: se a Phase 54 ainda não tiver sido executada, inventário versionado e probes live devem concordar no ramo `pre-phase54` (`10.21.1.21`); se já tiver sido executada, `54-04-SUMMARY.md`, `54-04-EVIDENCE.md`, inventário versionado e probes live devem concordar no ramo `post-phase54` (`10.31.1.31`). Estado misto, evidência ausente ou divergência bloqueiam a Wave 0. O gate de ordem herdado da Phase 50 (SSO) não é uma dependência técnica ou operacional do cutover Qwen.
