# Phase 59: Qwen3 Embedding e Rerank Podman para k3s - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrar a trilha Qwen3 de canary do Podman para o k3s, mantendo o GTE como
titular: Qwen3 Embedding INT8 via TEI/ONNX Runtime em 1024 dimensoes, Qwen3
Reranker INT8 via servico ONNX dedicado, governor com fila de ciclo completo,
colecoes Qdrant isoladas, testes funcionais/de qualidade/capacidade e
procedimentos de promocao e rollback.

Esta fase nao promove Qwen a titular, nao altera os aliases GTE existentes,
nao mistura vetores 768d e 1024d e nao executa reindexacao produtiva sem os
gates aprovados.

</domain>

<decisions>
## Implementation Decisions

### Modelo e runtime

- **D-01:** GTE continua titular em producao durante todo o canary. Qwen sera acessado por aliases versionados e isolados.
- **D-02:** Qwen Embedding usara `janni-t/qwen3-embedding-0.6b-int8-tei-onnx` no TEI com OrtBackend/ONNX Runtime. A quantizacao INT8 esta incorporada no `model.onnx`; nao sera criado runtime ONNX direto paralelo para embedding.
- **D-03:** Qwen Embedding tera pooling `mean`, dimensao 1024 e alias `embedding-qwen3-0.6b-int8-1024-v1`.
- **D-04:** Qwen Reranker usara `onnx-community/Qwen3-Reranker-0.6B-ONNX` em servico HTTP dedicado ONNX INT8, com endpoint privado `/rerank` e contrato publico convertido pelo router em `/v1/rerank`.
- **D-05:** O alias do reranker sera `reranker-qwen3-0.6b-int8-v1`; os aliases `embedding-gte-v1` e `reranker-gte-multilingual-v1` permanecem titulares.
- **D-06:** Revisoes dos modelos, digest das imagens e demais componentes de runtime deverao ser pinados antes do canary repetivel.

### Pipeline, governor e recursos

- **D-07:** O governor tera dois pipeline slots centralizados. Cada ciclo segue `Embedding -> Vector DB -> Reranker`, com apenas um estagio de inferencia ativo por ciclo; um terceiro ciclo aguarda a conclusao completa de um dos dois primeiros.
- **D-08:** O ciclo usara uma pipeline lease identificada por `pipeline_id`, com liberacao por sucesso, falha, cancelamento ou TTL. Rerank pendente tera prioridade sobre novo embedding. Chamadas somente de embedding continuam usando admission por chamada.
- **D-09:** Cada pod permanece em `500m`; o Qwen Embedding inicia com dois pods fixos, total `1000m`.
- **D-10:** O Qwen Reranker fara warmup inicial com um pod para medir RSS, startup e ranking; depois sera escalado para dois pods no teste integrado, com alvo futuro HPA de 2-4.
- **D-11:** O Qwen sera isolado no namespace `qwen-canary`, com quota propria. O GTE permanece em `ebeddings-local` e sua quota titular nao sera consumida pelo canary.
- **D-12:** Qwen Embedding nao usara `hostNetwork` com replicas; usara rede normal de pods e Service/NodePort privado para o router acessar o worker.
- **D-13:** O governor e a quota k3s sao controles complementares: a fila limita inferencia ativa; requests/limits e quotas continuam determinando scheduling e headroom.

### Dimensao, indices e dados

- **D-14:** Qwen usara 1024 dimensoes para o corpus tecnico. Vetores GTE 768d nunca serao misturados ou preenchidos para simular 1024d.
- **D-15:** Qdrant sera usado no canary com colecoes 1024d separadas por corpus, incluindo `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1` e `graphify_qwen3_1024_v1`.
- **D-16:** Os indices GTE 768d permanecem intactos. Corpus, chunking e IDs logicos equivalentes permitirao comparacao pareada e rollback por alias.
- **D-17:** Documentos novos poderao receber dual-index controlado durante o canary; promocao exige reindexacao Qwen completa e aprovacao manual.

### Gates, promocao e rollback

- **D-18:** Gates funcionais incluem health, batch 1/4, dimensao 1024, normalizacao, `/rerank`, fila, timeout e TTL.
- **D-19:** Gates de qualidade incluem Recall@20 e nDCG@10 nao inferiores ao GTE, com avaliacao especifica para portugues tecnico e codigo.
- **D-20:** Consistencia single/batch devera ter cosine de pelo menos `0.9999`.
- **D-21:** Gates de recursos exigem pods em `500m`, sem OOM, CPU-seconds no maximo 5% acima do GTE e ausencia de starvation nos dois pipeline slots.
- **D-22:** O canary devera passar soak de no minimo 72 horas sem impacto mensuravel no GTE titular.
- **D-23:** Promocao somente ocorrera apos reindexacao completa e aprovacao manual explicita.
- **D-24:** Rollback sera feito pela troca dos aliases e colecoes de volta para GTE, sem reindexacao emergencial; Qwen permanecera isolado para investigacao.

### the agent's Discretion

- Definir nomes finais dos Deployments, Services, PVCs, Jobs de seed e portas privadas, preservando os contratos acima.
- Escolher o mecanismo de estado da pipeline lease de acordo com a topologia real do router; se houver mais de uma replica, demonstrar consistencia ou usar armazenamento compartilhado.
- Ajustar memory requests/limits do Qwen Reranker depois do warmup real, sem ultrapassar a unidade de `500m` por pod.
- Fixar revisoes e digests concretos somente depois de validar que os artefatos e imagens correspondem ao ARM64 do alvo.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing GTE contract and k3s

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/41-local-ai-embeddings-gateway-horistic-srv/41-CONTEXT.md` — alias GTE, 768d, TEI privado, router sem self-loop e regra de reindexacao.
- `k8s/ebeddings-local/tei-gte.yaml` — Deployment, Service, quota unit e limites atuais do GTE Embedding.
- `k8s/ebeddings-local/tei-gte-reranker.yaml` — TEI GTE Reranker FP16, HPA 2-4, NodePort privado e PDB.
- `inventory/hosts/horistic-srv.yaml` — host ARM64, node k3s, IP privado e contratos operacionais atuais.
- `docs/operations/local-ai-embeddings.md` — contrato publico, conversao `/v1/rerank`, governor compartilhado, quotas e runbooks.

### Qwen evidence and prototype

- `.planning/spikes/006-qwen-podman-rag/README.md` — resultado do spike, artefato Qwen INT8, pooling mean, canary e arquitetura de fallback.
- `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md` — benchmark pareado GTE/Qwen em ARM64 com 768d e 1024d.
- `services/qwen-reranker-onnx/server.mjs` — prototipo do servidor Qwen Reranker, prompt yes/no, limite de 20 documentos e fila local.
- `services/qwen-reranker-onnx/package.json` — runtime Transformers.js usado pelo prototipo ONNX.
- `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` — caminhos protegidos do governor Go, contratos GTE e conversao publica/TEI.
- `modules/srv1-ops/configs/resource-governor.env` — limites globais do governor e separacao entre runtime e build.

### Official runtime/model references

- `https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx/tree/main` — artefato ONNX INT8 do embedding.
- `https://huggingface.co/Qwen/Qwen3-Reranker-0.6B` — arquitetura e contrato oficial do reranker Qwen.
- `https://huggingface.co/docs/text-embeddings-inference/main/en/index` — TEI, batching, health, metrics e runtimes.
- `https://onnxruntime.ai/docs/performance/tune-performance/threading.html` — controle de threads e spinning do ONNX Runtime.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `services/qwen-reranker-onnx/server.mjs` ja implementa tokenizer, score yes/no, limite de 20 documentos, fila local e `/health`; deve ser endurecido e adaptado para o contrato k3s.
- `scripts/embeddings-bench/compare-embeddings.py` e o resultado de 2026-07-22 fornecem o corpus e a metodologia de comparacao inicial.
- `k8s/ebeddings-local/tei-gte-reranker.yaml` fornece o padrao de probes, NodePort privado, HPA e PDB.

### Established Patterns

- O router Go possui `service/embeddinggovernor/` compartilhado por embedding e reranking, com filas separadas por workload e leases por chamada.
- `relay/embedding_handler.go` e `relay/rerank_handler.go` fazem `Acquire` separado e liberam a lease ao final de cada request; a pipeline lease e uma extensao arquitetural desta fase.
- O namespace titular usa `1 pod = 500m`, nodeSelector para `horistic-srv` e protecao de acesso privado.
- O router acessa o worker pelo IP OCI privado; ClusterIP nao e suficiente para o router Podman em SRV-1.

### Integration Points

- New API/router model catalog e allowlist dos aliases Qwen.
- `embeddinggovernor` para pipeline slots, prioridade de continuacao e metricas de espera/TTL.
- Qdrant ingestion/retrieval para colecoes Qwen 1024d e comparacao GTE/Qwen.
- Governor headers, `/v1/embeddings`, `/v1/rerank` e adaptador nativo TEI/ONNX.
- K3s manifests, PVC/cache, probes, NodePort privado, quota e HPA.

</code_context>

<specifics>
## Specific Ideas

- A prioridade operacional e menor consumo de processador, mas a fila nao deve esconder limites de scheduling, memoria ou quota do Kubernetes.
- O teste inicial deve ter dois Qwen Embedding pods de `500m` e dois pipeline slots.
- O ciclo validado e sequencial: Qwen Embedding, busca vetorial top-K, Qwen Reranker top-N.
- GTE continua ativo e titular para fallback e comparacao durante todo o período de teste.
- Documentacao tecnica crescente e o motivo para fixar 1024d no Qwen, sem alterar o contrato GTE 768d.

</specifics>

<deferred>
## Deferred Ideas

- Promover Qwen a titular antes do soak, da reindexacao completa e da aprovacao manual.
- Usar ONNX Runtime direto como runtime permanente do Qwen Embedding.
- Forcar Qwen Reranker dentro do TEI sem compatibilidade oficial e validacao real.
- Misturar colecoes GTE 768d e Qwen 1024d ou trocar o alias GTE durante o canary.
- Criar uma fila externa Redis/NATS antes de demonstrar a necessidade pela topologia de replicas do router.

</deferred>

---

*Phase: 59-qwen3-embedding-e-rerank-podman-para-k3s*
*Context gathered: 2026-07-23*
