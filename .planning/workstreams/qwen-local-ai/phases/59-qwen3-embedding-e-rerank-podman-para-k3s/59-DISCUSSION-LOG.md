# Phase 59: Qwen3 Embedding e Rerank Podman para k3s - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-23
**Phase:** 59-Qwen3 Embedding e Rerank Podman para k3s
**Areas discussed:** contratos de modelos e runtimes, dimensao e indices, topologia k3s e governor, canary/promocao/rollback

---

## Contratos de modelos e runtimes

| Option | Description | Selected |
|--------|-------------|----------|
| TEI com OrtBackend ONNX INT8 | Qwen Embedding servido pelo TEI usando o grafo ONNX quantizado | ✓ |
| ONNX direto como embedding principal | Servidor proprio com ONNX Runtime, sem TEI | |
| ONNX direto apenas como challenger | Comparacao A/B temporaria contra TEI | |
| Servico ONNX dedicado para reranker | Qwen Reranker fora do TEI, com `/rerank` privado | ✓ |
| Forcar Qwen Reranker no TEI | Manter reranker causal dentro do TEI | |

**User's choice:** TEI+ONNX para embedding e ONNX dedicado apenas para reranking.
**Notes:** GTE permanece titular; aliases Qwen sao versionados e isolados.

## Dimensao e migracao dos indices

| Option | Description | Selected |
|--------|-------------|----------|
| 768d | Compatibilidade com GTE atual | |
| 1024d | Mais capacidade para documentacao tecnica | ✓ |
| Uma colecao Qwen global | Um indice Qwen compartilhado | |
| Colecoes por corpus | Qdrant separado para GBrain, Obsidian e Graphify | ✓ |
| Misturar vetores | Compartilhar 768d e 1024d | |

**User's choice:** Qwen em 1024d, Qdrant com colecoes separadas por corpus e indices GTE preservados.
**Notes:** Dual-index controlado durante o canary; promocao exige reindexacao completa.

## Topologia k3s, recursos e governor

| Option | Description | Selected |
|--------|-------------|----------|
| Lease por chamada | Comportamento atual do governor | |
| Lease transacional por pipeline | Dois ciclos completos, embedding ate rerank | ✓ |
| Um pod de embedding | 500m | |
| Dois pods de embedding | 1000m total, 500m por pod | ✓ |
| Namespace titular compartilhado | Consumir a quota do GTE | |
| `qwen-canary` isolado | Quota e rollback independentes | ✓ |
| Reranker 1 e depois 2 | Warmup, medicao e teste integrado | ✓ |

**User's choice:** Dois pods Qwen Embedding desde o inicio, dois pipeline slots, namespace separado e igualdade 2+2 no teste integrado.
**Notes:** O primeiro boot do reranker usa um pod para medir memoria e ranking; depois escala para dois.

## Envelope 2–5 pods sem HPA

**User's choice:** Replanejar com 2–5 pods Qwen, priorizando menor consumo de
processador e deixando o agente definir a combinação.

**Decision:** Quatro pods permanentes (2 embedding + 2 reranker, 2000m), piso
degradado 1+1 (1000m) e máximo cinco (2500m) somente como um surge serializado
de rollout após GTE retirement e headroom comprovado. Durante coexistência,
quota nega o quinto; após retirement, quota nega o sexto. HPA e terceiro
pipeline permanecem proibidos.

## Histórico: canary, promocao e rollback

> Superseded em 2026-07-23 pela autorização explícita registrada em
> `59-CONTEXT.md` D-01 e D-21: Qwen torna-se titular automaticamente na Wave 6
> quando todos os gates passam; GTE permanece rollback-ready até o retirement
> da Wave 8. A tabela abaixo preserva a conversa anterior, não a arquitetura
> executável atual.

| Option | Description | Selected |
|--------|-------------|----------|
| Promocao imediata | Trocar GTE pelo Qwen apos smoke | |
| GTE titular com Qwen canary | Promocao somente apos gates e aprovacao | ✓ (superseded) |
| Soak curto | Apenas validacao funcional | |
| Soak de 72 horas | Estabilidade antes de qualquer promocao | ✓ |
| Rollback por alias | Retornar para colecoes e aliases GTE | ✓ |
| Reindexacao emergencial | Reconstruir indice durante incidente | |

**User's choice:** Qwen fica somente em teste até completar qualidade, recursos, pipeline e estabilidade; GTE continua como fallback titular.
**Notes:** Gates incluem cosine single/batch >= 0.9999, qualidade não inferior ao GTE, CPU-seconds até 5% acima, ausência de OOM/starvation e soak mínimo de 72 horas.

**Decisão vigente:** cutover Qwen automático e transacional após gates; soak
ocorre com Qwen titular; rollback produtivo Qwen→GTE→Qwen precede a remoção dos
workloads GTE.

## the agent's Discretion

- Nomes finais de recursos k3s, portas privadas, jobs de seed e detalhes de PVC dentro dos limites decididos; HPA não faz parte da Phase 59.
- Mecanismo compartilhado da pipeline lease se o router tiver múltiplas réplicas.
- Ajuste de memória após o warmup real do Qwen Reranker.

## Deferred Ideas

- Promoção Qwen a titular.
- ONNX direto como runtime permanente de embedding.
- Qwen Reranker servido pelo TEI.
- Mistura ou substituição do índice GTE 768d.
- Redis/NATS externo sem necessidade comprovada.
