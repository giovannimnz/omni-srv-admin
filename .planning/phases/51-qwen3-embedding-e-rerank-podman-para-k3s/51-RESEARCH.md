# Phase 51: Qwen3 Embedding e Rerank Podman para k3s - Research

**Researched:** 2026-07-23
**Domain:** inferência CPU ARM64, TEI/ONNX, reranking, k3s, governor de pipeline e Qdrant
**Confidence:** MEDIUM — contratos, protótipo e benchmark local estão verificados; a execução integrada em k3s e o sizing final ainda exigem prova no host.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** GTE continua titular em producao durante todo o canary. Qwen sera acessado por aliases versionados e isolados.
- **D-02:** Qwen Embedding usara `janni-t/qwen3-embedding-0.6b-int8-tei-onnx` no TEI com OrtBackend/ONNX Runtime. A quantizacao INT8 esta incorporada no `model.onnx`; nao sera criado runtime ONNX direto paralelo para embedding.
- **D-03:** Qwen Embedding tera pooling `mean`, dimensao 1024 e alias `embedding-qwen3-0.6b-int8-1024-v1`.
- **D-04:** Qwen Reranker usara `onnx-community/Qwen3-Reranker-0.6B-ONNX` em servico HTTP dedicado ONNX INT8, com endpoint privado `/rerank` e contrato publico convertido pelo router em `/v1/rerank`.
- **D-05:** O alias do reranker sera `reranker-qwen3-0.6b-int8-v1`; os aliases `embedding-gte-v1` e `reranker-gte-multilingual-v1` permanecem titulares.
- **D-06:** Revisoes dos modelos, digest das imagens e demais componentes de runtime deverao ser pinados antes do canary repetivel.
- **D-07:** O governor tera dois pipeline slots centralizados. Cada ciclo segue `Embedding -> Vector DB -> Reranker`, com apenas um estagio de inferencia ativo por ciclo; um terceiro ciclo aguarda a conclusao completa de um dos dois primeiros.
- **D-08:** O ciclo usara uma pipeline lease identificada por `pipeline_id`, com liberacao por sucesso, falha, cancelamento ou TTL. Rerank pendente tera prioridade sobre novo embedding. Chamadas somente de embedding continuam usando admission por chamada.
- **D-09:** Cada pod permanece em `500m`; o Qwen Embedding inicia com dois pods fixos, total `1000m`.
- **D-10:** O Qwen Reranker fara warmup inicial com um pod para medir RSS, startup e ranking; depois sera escalado para dois pods no teste integrado, com alvo futuro HPA de 2-4.
- **D-11:** O Qwen sera isolado no namespace `qwen-canary`, com quota propria. O GTE permanece em `ebeddings-local` e sua quota titular nao sera consumida pelo canary.
- **D-12:** Qwen Embedding nao usara `hostNetwork` com replicas; usara rede normal de pods e Service/NodePort privado para o router acessar o worker.
- **D-13:** O governor e a quota k3s sao controles complementares: a fila limita inferencia ativa; requests/limits e quotas continuam determinando scheduling e headroom.
- **D-14:** Qwen usara 1024 dimensoes para o corpus tecnico. Vetores GTE 768d nunca serao misturados ou preenchidos para simular 1024d.
- **D-15:** Qdrant sera usado no canary com colecoes 1024d separadas por corpus, incluindo `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1` e `graphify_qwen3_1024_v1`.
- **D-16:** Os indices GTE 768d permanecem intactos. Corpus, chunking e IDs logicos equivalentes permitirao comparacao pareada e rollback por alias.
- **D-17:** Documentos novos poderao receber dual-index controlado durante o canary; promocao exige reindexacao Qwen completa e aprovacao manual.
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

### Deferred Ideas (OUT OF SCOPE)

- Promover Qwen a titular antes do soak, da reindexacao completa e da aprovacao manual.
- Usar ONNX Runtime direto como runtime permanente do Qwen Embedding.
- Forcar Qwen Reranker dentro do TEI sem compatibilidade oficial e validacao real.
- Misturar colecoes GTE 768d e Qwen 1024d ou trocar o alias GTE durante o canary.
- Criar uma fila externa Redis/NATS antes de demonstrar a necessidade pela topologia de replicas do router.
</user_constraints>

## Summary

Implemente a fase como uma trilha canary inteiramente paralela: dois pods TEI de embedding, um pod inicial e depois dois pods do reranker dedicado, três coleções Qdrant 1024d e aliases Qwen separados. O router continua sendo a única borda pública, o governor passa a possuir a lease do ciclo inteiro e o GTE 768d não é alterado. [VERIFIED: `.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-CONTEXT.md`]

O embedding já foi comprovado no mesmo artifact LOCKED em ARM64/Podman, `500m`, `mean`, batch 1/4, saída normalizada 1024d e cosine single/batch `0.99999995`. No corpus pareado, Qwen 1024d consumiu 15.84, 17.01 e 16.81 CPU-s/1k palavras contra 18.90, 16.93 e 17.10 do GTE; portanto passa preliminarmente o teto GTE+5%, mas essa evidência não substitui medição k3s nem avaliação Recall@20/nDCG@10. [VERIFIED: `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md`]

O maior risco é de integração, não de formato: o artifact comunitário LOCKED declara mean pooling, enquanto o modelo oficial Qwen3 documenta last-token pooling. O benchmark valida o comportamento do artifact específico, mas a qualidade precisa ser tratada como hipótese até passar no corpus técnico PT-BR/código. [CITED: https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B]

**Primary recommendation:** construir primeiro contratos e testes determinísticos, depois manifests/pinning, então governor/Qdrant, e só por último executar warmup, canary integrado e soak; nenhum alias titular muda nesta fase. [VERIFIED: `51-CONTEXT.md`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Auth, alias público e conversão `/v1/rerank` | API / Backend (router) | — | O router já é a única borda pública e converte o contrato público para o backend privado. [VERIFIED: `docs/operations/local-ai-embeddings.md`] |
| Pipeline lease, prioridade, TTL e cancelamento | API / Backend (`embeddinggovernor`) | Storage compartilhado somente se multi-réplica | A admissão precisa cobrir o ciclo completo e não pode ficar dentro dos workers. [VERIFIED: `51-CONTEXT.md`] |
| Embedding INT8 1024d | k3s worker / inference | Service privado | TEI/OrtBackend executa o artifact ONNX; o Service oferece balanceamento entre réplicas. [CITED: https://huggingface.co/docs/text-embeddings-inference/en/supported_models] |
| Busca top-K e coleções canary | Database / Storage (Qdrant) | API / Backend | A coleção fixa dimensão/métrica e o pipeline envia os candidatos ao reranker. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |
| Rerank INT8 | k3s worker / inference | API adapter | Serviço dedicado calcula probabilidade `yes/no`; o router normaliza a resposta pública. [CITED: https://huggingface.co/onnx-community/Qwen3-Reranker-0.6B-ONNX] |
| Quotas, scheduling, probes e isolamento | k3s control plane | worker `horistic-srv` | LimitRange/ResourceQuota controlam admissão e recursos; probes controlam disponibilidade. [CITED: https://kubernetes.io/docs/concepts/policy/limit-range/] |
| Promoção/rollback | Router aliases + Qdrant aliases | manifests k3s | Troca atômica de alias evita reindexação emergencial; GTE permanece intacto. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |

## Project Constraints (from AGENTS.md)

- Usar PT-BR e manter termos técnicos padronizados em English. [VERIFIED: `AGENTS.md`]
- Cada pod normal de runtime deve ter `requests.cpu=500m` e `limits.cpu=500m`; dois pods totalizam `1000m`. [VERIFIED: `AGENTS.md`]
- Builds, recompilações, container builds e suites pesadas devem passar pelo profile `builds` e ficar em até 20% da CPU do host. [VERIFIED: `AGENTS.md`]
- Não gravar valores de secrets em Git, `.planning`, logs, Obsidian, GBrain ou chat; Vault é a fonte autoritativa. [VERIFIED: `AGENTS.md`]
- Preservar worktree sujo e mudanças concorrentes; esta pesquisa não autoriza alteração live. [VERIFIED: `AGENTS.md`]
- Browser automation, se algum plano vier a precisar, deve ser headless e preservar evidência. [VERIFIED: `AGENTS.md`]
- Documentar trabalho operacional não trivial posteriormente no Obsidian autoritativo e GBrain, sem secrets. [VERIFIED: `AGENTS.md`]

## Standard Stack

### Core

| Component | Pin pesquisado | Purpose | Diretriz |
|---|---|---|---|
| TEI CPU ARM64 | imagem já usada no repo: digest `sha256:16c0a827cf79d5dc9b9ec1b0b5df7ffd165726f9bdf1daa9d4f7a355dd842f7e`; revalidar plataforma antes do apply | OrtBackend/ONNX do embedding | Usar a variante `cpu-arm64`, digest pinado, `--pooling mean`, um tokenizer worker e `emptyDir` per-pod populado por init container pinado/checksumado. [VERIFIED: `k8s/ebeddings-local/tei-gte-reranker.yaml`] [CITED: https://huggingface.co/docs/text-embeddings-inference/en/supported_models] |
| Embedding artifact | revision `8fe0c238c7c48016d28e750413ca492024be3ddf`; `model.onnx` 599,154,560 bytes; Xet SHA-256 `bd775071a80a1dde99a18d1a7083bf388a5ad4ce9db6d81806f25c4d6102ff08` | Qwen3 0.6B INT8, 1024d | Pin revision e verificar o arquivo antes de servir. [VERIFIED: Hugging Face model API/HEAD] |
| Reranker artifact | revision `9995c50e2310679108a55f5ccd16ba8be9f17c20`; `onnx/model_quantized.onnx` 1,219,344,796 bytes; Xet SHA-256 `c9428382bb48bb31e01a6034647c86d6270761781735cafbf6d5cb4a396d0450` | Qwen3 reranker INT8 dinâmico | Pin revision, arquivo e tokenizer; não usar `main`. [VERIFIED: Hugging Face model API/HEAD] |
| `@huggingface/transformers` | `4.2.0`, publicado/modificado em 2026-04-22 | tokenizer, CausalLM e ONNX Runtime no serviço Node | Manter pin exato e gerar lockfile; package legitimacy `OK`, 1,698,750 downloads/semana, sem postinstall. [VERIFIED: npm registry + package-legitimacy seam] |
| k3s | inventário registra `v1.35.5+k3s1`, ARM64 worker | scheduling, Service, quota, probes, HPA/PDB | Não assumir estado live sem preflight; usar manifests versionados. [VERIFIED: `inventory/hosts/horistic-srv.yaml`] |
| Qdrant | versão live não verificada | coleções 1024d, busca top-20 e aliases | Descobrir versão/API antes de aplicar strict mode ou snapshots. [ASSUMED] |

### Supporting

| Component | Purpose | Quando usar |
|---|---|---|
| Kubernetes `LimitRange` + `ResourceQuota` | impor unidade 500m e teto do namespace | Desde o primeiro apply; quota não substitui governor. [CITED: https://kubernetes.io/docs/concepts/policy/limit-range/] |
| NodePort privado | permitir acesso do router Podman em SRV-1 ao worker k3s | Para embedding e reranker; validar firewall e `nodePortAddresses`, pois NodePort normalmente escuta nos IPs dos nodes. [CITED: https://kubernetes.io/docs/concepts/services-networking/service/] |
| `NetworkPolicy` | default-deny e egress/ingress mínimo | Somente após provar que o CNI do k3s realmente a aplica. [CITED: https://kubernetes.io/docs/concepts/services-networking/network-policies/] |
| Qdrant collection aliases | promoção/rollback atômico | Alias canary por corpus; preservar aliases/coleções GTE. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |
| Prometheus metrics + redacted evidence JSON | fila, TTL, starvation, CPU/RSS e erro | Em todos os gates e durante soak. [VERIFIED: `docs/operations/local-ai-embeddings.md`] |

### Package Legitimacy Audit

| Package | Registry | Age/Downloads | Source Repo | Verdict | Disposition |
|---|---|---|---|---|---|
| `@huggingface/transformers@4.2.0` | npm | versão publicada em 2026-04-22; 1,698,750/semana na consulta | `github.com/huggingface/transformers.js` | OK; sem `postinstall` | Approved, pin exato + lockfile. [VERIFIED: npm registry + package-legitimacy seam] |

**Packages removed due to SLOP:** none.
**Packages flagged SUS:** none.

## Target Architecture

```text
Bearer client / indexer
        |
        v
router-ai-atius (public /v1; aliases; auth; conversion)
        |
        +--> embedding-only admission ------------------> Qwen TEI Service
        |
        +--> acquire pipeline_id (2 slots total)
                |
                v
          Qwen TEI Embedding (2 x 500m, 1024d)
                |
                v
          Qdrant alias -> *_qwen3_1024_v1 (top-20)
                |
                +--> cancel/error/TTL -> release exactly once
                |
                v  priority over new embedding
          Qwen Reranker Service (warmup 1 x 500m; integrated 2 x 500m)
                |
                v
          public results[].relevance_score -> release lease

GTE aliases + 768d collections remain separate and untouched throughout.
```

[VERIFIED: `51-CONTEXT.md`] [VERIFIED: `docs/operations/local-ai-embeddings.md`]

## Recommended Project Structure and Probable Files

```text
k8s/qwen-canary/
├── namespace-resources.yaml          # Namespace, PSA labels, LimitRange, ResourceQuota
├── tei-qwen3-embedding.yaml          # Deployment(2), per-pod emptyDir/init download, Service/NodePort, PDB
├── qwen3-reranker.yaml               # Artifact embedded in image, Service/NodePort, PDB; HPA staged
├── network-policy.yaml               # default-deny + explicit flows, only if CNI enforcement passes
├── qdrant-seed-jobs.yaml             # idempotent collection/alias creation; no secrets inline
└── kustomization.yaml

services/qwen-reranker-onnx/
├── server.mjs                        # hardened API, shutdown/cancel/error semantics, metrics
├── package.json
├── package-lock.json                 # exact transitive pin
└── Containerfile                     # multi-stage ARM64-capable, non-root, digest-pinned base

scripts/embeddings-bench/
├── compare-embeddings.py             # extend to retrieval quality and k3s metrics
├── evaluate-rag-quality.py           # Recall@20/nDCG@10 paired evaluator
├── qwen-canary-smoke.py              # functional + queue/TTL/cancel smoke
└── qwen-canary-soak.py               # 72h sampling and redacted evidence

modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md
docs/operations/local-ai-embeddings.md
inventory/hosts/horistic-srv.yaml

# Changes occur in the owner-host router checkout, not necessarily this repo:
/home/ubuntu/GitHub/containers/router-ai-atius/
├── service/embeddinggovernor/
├── relay/embedding_handler.go
├── relay/rerank_handler.go
└── service/modelcatalog/
```

The router source paths are canonical but were not available in this checkout during research; the planner must begin with a read-only inventory on the owner host and name exact files/tests before edits. [VERIFIED: `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`] [ASSUMED]

## Architecture Patterns

### Pattern 1: Pipeline lease as an explicit state machine

Represent each cycle as `queued -> embedding -> vector_db -> rerank_pending -> reranking -> terminal`, with one idempotent release path for `success`, `failure`, `cancelled` or `expired`. A lease carries `pipeline_id`, `created_at`, `expires_at`, workload, model aliases and current stage. [VERIFIED: `51-CONTEXT.md`]

Required invariants:

- no more than two non-terminal pipeline leases;
- each lease has at most one active inference stage;
- `rerank_pending` is dequeued before `embedding_pending`;
- cancellation propagates through request context and releases exactly once;
- TTL is checked while queued and at stage transitions;
- vector DB time counts inside the lease, although it is not an inference stage;
- standalone embedding retains call-scoped admission and cannot consume a pipeline slot. [VERIFIED: `51-CONTEXT.md`]

If the router has exactly one replica, in-process guarded state is acceptable for the canary. If it has multiple replicas or can restart during active cycles, local memory cannot provide global two-slot semantics; prove single-replica topology or add a shared consistency mechanism before enabling Qwen pipeline traffic. [ASSUMED]

### Pattern 2: Immutable model contract

Treat the embedding identity as:

```text
alias + model revision + model.onnx sha256 + tokenizer revision +
pooling(mean) + dimensions(1024) + normalization + query instruction +
chunking version
```

Persist this signature with every indexed point/batch and reject writes whose signature differs from the collection metadata. [VERIFIED: `docs/operations/local-ai-embeddings.md`] [CITED: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B]

### Pattern 3: Atomic collection alias switch

Create physical collections first, verify `vectors.size=1024` and `distance=Cosine`, seed with stable logical IDs, then bind canary aliases. Promotion/rollback changes aliases atomically; collection snapshots do not include aliases, so alias state requires separate exported evidence. [CITED: https://qdrant.tech/documentation/manage-data/collections/] [CITED: https://qdrant.tech/documentation/snapshots/]

Recommended physical names are the locked names:

```text
gbrain_qwen3_1024_v1
obsidian_qwen3_1024_v1
graphify_qwen3_1024_v1
```

Recommended canary aliases are `[ASSUMED]`:

```text
gbrain_qwen3_canary
obsidian_qwen3_canary
graphify_qwen3_canary
```

### Pattern 4: Slow-model probe separation

Use a generous startup probe for model load, readiness to remove busy/unhealthy pods from Service endpoints and liveness only for deadlock detection. Do not repeat the existing GTE failure mode in which a 5-second liveness timeout killed a healthy but CPU-throttled long request. [VERIFIED: `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md`] [CITED: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/]

## Concrete Manifest Guidance

Use namespace `qwen-canary`, Pod Security Admission labels at `restricted` if the images pass, `runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault`, read-only root filesystem where compatible, explicit writable cache mounts and no service-account token unless needed. [CITED: https://kubernetes.io/docs/concepts/security/pod-security-standards/]

Start quota sizing as a declared ceiling, not a measured recommendation:

| Resource | Initial canary ceiling | Basis |
|---|---:|---|
| Embedding pods | 2 | LOCKED D-09. [VERIFIED: `51-CONTEXT.md`] |
| Reranker pods | 2 during integrated test; HPA object disabled/omitted until warmup | LOCKED D-10. [VERIFIED: `51-CONTEXT.md`] |
| CPU requests/limits | 2000m total for four runtime pods | Four pods × 500m. [VERIFIED: `AGENTS.md`] |
| Extra Job/init CPU | Four runtime pods plus exactly one active 500m tool Job fit 2500m; each embedding pod remains effectively 500m | Kubernetes computes effective pod CPU as `max(max(init requests), sum(app requests))`; init=500m and TEI=500m therefore admit as 500m, not 1000m. [CITED: https://kubernetes.io/docs/concepts/workloads/pods/init-containers/] |
| Embedding memory | request 2Gi / limit 4Gi per pod as hypothesis | Podman observed 1.37–1.40Gi current under the benchmark; k3s warmup peak is unknown. [VERIFIED: benchmark] [ASSUMED] |
| Reranker memory | do not lock before one-pod warmup; temporary request 2Gi / limit 4Gi is hypothesis | ONNX file is ~1.22GB, but runtime RSS/peak is unmeasured. [VERIFIED: Hugging Face HEAD] [ASSUMED] |
| Embedding cache | Per-pod `emptyDir`; 500m init container downloads the exact `janni-t` revision/file to `.partial`, verifies SHA-256 and atomically renames | Removes shared-RWO ambiguity while keeping each replica independently reproducible. TEI reads local files with remote fallback disabled; controlled startup egress is validated separately. |
| Reranker artifact | Embedded and checksum-verified in the Plan 02 image | No reranker PVC or init download is required. |

Use normal pod networking and two private NodePorts. Exact ports remain unresolved; select unused values after checking cluster Services and the fleet port map. NodePort is reachable on node addresses by default, so private routing/firewall or `nodePortAddresses` must prevent unintended public exposure. [CITED: https://kubernetes.io/docs/concepts/services-networking/service/]

Do not copy `k8s/embeddings-bench/tei-qwen-onnx-int8.yaml`: it references `onnx-community/Qwen3-Embedding-0.6B-ONNX`, `last-token` and `hostNetwork`, which conflict with D-02, D-03 and D-12. [VERIFIED: `k8s/embeddings-bench/tei-qwen-onnx-int8.yaml`]

## Reranker Service Hardening

Reuse `services/qwen-reranker-onnx/server.mjs`, preserving prompt construction, token IDs `yes`/`no`, stable softmax, batch slicing, maximum 20 documents and `/health`. These match the official causal-LM reranking approach. [VERIFIED: `services/qwen-reranker-onnx/server.mjs`] [CITED: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B]

Before k3s:

- expose only `/health`, `/metrics` and private `/rerank`; remove or disable direct `/v1/rerank` so public conversion remains router-owned; [VERIFIED: `51-CONTEXT.md`]
- distinguish malformed input (`400`), too large (`413`), queue full (`429`), timeout (`504`), cancelled request and model unavailable (`503`); [ASSUMED]
- cap request body by bytes, documents, characters and tokenized length before inference; [VERIFIED: existing prototype body/doc caps]
- bind abort/connection-close to queued work so abandoned requests do not run; [ASSUMED]
- add graceful shutdown: readiness false, stop admission, bounded drain, then exit; [ASSUMED]
- emit stage latency, queue depth, batch size, document count, RSS/process CPU and outcome without document/query contents; [ASSUMED]
- replace the unbounded Promise-chain queue with an explicit bounded queue or rely exclusively on router admission plus backend concurrency=1; retain backend rejection as defense in depth; [VERIFIED: existing prototype]
- configure ORT to one intra-op thread and sequential execution if Transformers.js exposes the needed session options; otherwise prove actual thread count/cgroup CPU and document the limitation. Disabling spin may reduce wasted CPU but must be A/B measured. [CITED: https://onnxruntime.ai/docs/performance/tune-performance/threading.html] [ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Embedding inference | another direct ONNX runtime | TEI OrtBackend with locked artifact | D-02 excludes parallel embedding runtime; TEI already supplies batching, health and metrics. [VERIFIED: `51-CONTEXT.md`] |
| Vector index | custom ANN store | Qdrant collections + aliases | Enforces vector schema and supports atomic alias changes. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |
| CPU isolation | queue alone | requests/limits + quota + governor | Queue and scheduler solve different limits. [VERIFIED: `51-CONTEXT.md`] |
| Secret distribution | inline YAML/env committed to Git | Vault-fed Kubernetes Secret/runtime loader | Project security contract. [VERIFIED: `AGENTS.md`] |
| Rerank model scoring | heuristic similarity | official prompt and yes/no logits | The model is a CausalLM reranker, not a classifier endpoint. [CITED: https://huggingface.co/onnx-community/Qwen3-Reranker-0.6B-ONNX] |
| Rollback migration | deleting/rebuilding current index | versioned physical collections + aliases | Keeps GTE data intact and rollback bounded. [CITED: https://qdrant.tech/documentation/manage-data/collections/] |

## Common Pitfalls

### Pooling drift

**What goes wrong:** substituting official last-token pooling or an older benchmark manifest silently creates a different vector space.
**Avoid:** enforce `mean`, signature metadata and golden-vector fingerprint; fail startup/smoke if dimension/norm/fingerprint differs. [VERIFIED: `51-CONTEXT.md`]
**Warning signs:** Recall regression despite valid 1024-length vectors, or single/batch cosine below `0.9999`.

### Probe-induced restart under throttling

**What goes wrong:** liveness shares the congested worker and times out during a valid long inference.
**Avoid:** startup/readiness/liveness separation, health endpoint independent of inference queue where possible, and stress validation at 500m. [VERIFIED: benchmark]
**Warning signs:** increasing restart count during long-text smoke without OOM.

### False global governor

**What goes wrong:** two router replicas each allow two slots, producing four active cycles.
**Avoid:** prove one replica or implement shared state with atomic acquire/release/expiry. [ASSUMED]

### Shared cache versus replicas

**What goes wrong:** two pods cannot mount or roll safely when shared-volume topology differs.
**Avoid:** use independent per-pod `emptyDir` for embedding with the pinned init-download flow; keep the reranker artifact embedded in its digest-pinned image. Validate two replicas and Kubernetes effective 500m init accounting.

### NodePort exposure

**What goes wrong:** “private” NodePort listens on public-capable node interfaces.
**Avoid:** prove effective bind/firewall path from SRV-1 and reject public reachability. [CITED: https://kubernetes.io/docs/concepts/services-networking/service/]

### Alias-only rollback without recorded alias state

**What goes wrong:** snapshots restore points but not aliases.
**Avoid:** export alias mappings before every switch and make rollback command idempotent. [CITED: https://qdrant.tech/documentation/snapshots/]

### Quality comparison with non-equivalent corpus

**What goes wrong:** changed chunks/IDs make Recall/nDCG incomparable.
**Avoid:** same query set, qrels, chunking and logical IDs; only embedding/reranker path differs. [VERIFIED: `51-CONTEXT.md`]

## Known / Unknown / How to Prove

| Status | Item | Evidence now | How to prove before promotion |
|---|---|---|---|
| Known | Artifact embedding revision/hash, mean pooling contract, 1024d output | HF metadata plus Podman benchmark. [VERIFIED: HF API/HEAD + benchmark] | Per-pod 500m init-container `.partial` download/hash/atomic rename, k3s golden smoke and saved redacted signature. |
| Known | Qwen 1024 preliminary CPU is within GTE+5% on three profiles | Pareado em 500m, porém em Podman e por palavras. [VERIFIED: benchmark] | Repetir no k3s, mesma janela, tokens medidos, warm cache, ≥5 rounds/profile e intervalo/variância. |
| Known | Reranker algorithm is prompt + last-position yes/no logits + softmax | Official model cards and prototype. [CITED: official Qwen/HF pages] | Golden set with expected ordering, batch equivalence and score bounds `[0,1]`. |
| Unknown | TEI image digest still resolves to Linux/arm64 and loads the pinned `janni-t` revision in k3s | Existing digest is used by GTE, not yet proved for this deployment. [ASSUMED] | `skopeo inspect --raw`, image ID/platform capture, rollout and backend log showing OrtBackend. |
| Unknown | Reranker Transformers.js/ORT q8 works on target ARM64 image | Prototype exists; no integrated ARM64 result was read. [ASSUMED] | Build under CPU guardrail, one-pod warmup, `/health`, deterministic `/rerank`, inspect native dependencies/architecture. |
| Unknown | Reranker RSS, startup, CPU-s and safe memory limits | ONNX size alone is insufficient. [ASSUMED] | One-pod warmup + repeated batch 1/4/20, cgroup memory peak, OOM events and startup duration. |
| Unknown | Router replica count and suitable lease state | Source/topology not read live in this interrupted research. [ASSUMED] | `kubectl/podman/PM2` inventory; if >1, concurrency test proving exactly two global slots or shared store. |
| Unknown | Qdrant version, endpoint, auth, capacity, snapshots and strict-mode support | No Qdrant runtime config found in repo. [ASSUMED] | Version/API preflight, collection list, storage/RAM headroom, create/delete disposable 1024d collection, snapshot/restore drill. |
| Unknown | CNI enforces NetworkPolicy | API object existence does not prove enforcement. [CITED: Kubernetes NetworkPolicy docs] | Default-deny canary plus positive router flow and negative unrelated-pod/public probes. |
| Unknown | Free NodePorts and private-only reachability | Existing reranker uses 31216; Qwen ports not assigned. [ASSUMED] | Cluster-wide Service inventory, socket/firewall inventory, SRV-1 success and public/unauthorized failure probes. |
| Unknown | 1024d quality advantage justifies 33.3% more vector coordinates than 768d | Benchmark measured correctness/perf, not retrieval quality. [VERIFIED: benchmark] | Recall@20/nDCG@10 on frozen PT-BR/code qrels, plus Qdrant disk/RAM/latency comparison. |
| Unknown | No starvation with priority rerank | Architecture is LOCKED but not implemented. [ASSUMED] | Deterministic scheduler tests and sustained mixed-load test with bounded max wait per class. |
| Unknown | No measurable GTE impact for 72h | Canary has not run in k3s. [ASSUMED] | Plan 51-01 must freeze a qualifying historical GTE-only window ending before Wave 0, or BLOCK until a new baseline-only window completes; Plan 51-08 then runs the 72h soak against those immutable bands. |

## Validation Architecture

### Test Levels

| Level | Scope | Required evidence |
|---|---|---|
| L0 Static | manifests, pins, aliases, resource math, securityContext | rendered YAML, schema validation, image/model revisions and SHA-256 list |
| L1 Unit | governor state machine, priority, TTL, cancel/release; reranker parsing/scoring | focused Go/Node tests with race/error paths |
| L2 Component | each backend privately at 500m | health, batch 1/4, 1024d, norm, cosine, rerank ordering, RSS/startup/CPU |
| L3 Integration | router → embedding → Qdrant → rerank | two-slot behavior, public contract, top-20/top-10, timeout/cancel, alias isolation |
| L4 Quality/Capacity | paired GTE/Qwen corpus and mixed load | Recall@20, nDCG@10, CPU-s, p50/p95, queue wait, no starvation/OOM |
| L5 Soak/Rollback | 72h canary with GTE titular | time series, events/restarts, GTE impact report, successful alias rollback drill |

### Planned Commands and Smokes

Commands are templates; exact router paths, NodePorts and Qdrant endpoint must be resolved in the plan. No secret value may appear in output. [ASSUMED]

```bash
# L0 — render and server-side validate without mutation
kubectl kustomize k8s/qwen-canary > /tmp/qwen-canary.rendered.yaml
kubectl apply --dry-run=server -f /tmp/qwen-canary.rendered.yaml
kubectl -n qwen-canary get resourcequota,limitrange,networkpolicy

# L1 — owner-host router checkout, focused packages only
go test ./service/embeddinggovernor ./relay -count=1 -race
npm --prefix services/qwen-reranker-onnx test

# L2 — rollout and resource shape
kubectl -n qwen-canary rollout status deploy/tei-qwen3-embedding --timeout=20m
kubectl -n qwen-canary rollout status deploy/qwen3-reranker --timeout=20m
kubectl -n qwen-canary get pods -o custom-columns=NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,CPU_LIM:.spec.containers[*].resources.limits.cpu,RESTARTS:.status.containerStatuses[*].restartCount
kubectl -n qwen-canary top pod --containers

# L2 embedding redacted smoke
python3 scripts/embeddings-bench/qwen-canary-smoke.py \
  --embedding-url http://10.21.1.21:<embedding-nodeport> \
  --expect-dim 1024 --batch-sizes 1,4 --min-single-batch-cosine 0.9999

# L2 reranker redacted smoke
python3 scripts/reranker-smoke.py \
  --native --base-url http://10.21.1.21:<reranker-nodeport>

# L3 scheduler/integration
go test ./service/embeddinggovernor -run 'TestPipeline|TestPriority|TestTTL|TestCancel|TestNoStarvation' -count=20 -race
python3 scripts/embeddings-bench/qwen-canary-smoke.py \
  --router-url https://router.atius.com.br/v1 \
  --pipeline --concurrency 3 --expect-slots 2 --test-timeout --test-cancel --test-ttl

# L4 paired quality/capacity
python3 scripts/embeddings-bench/evaluate-rag-quality.py \
  --baseline embedding-gte-v1,reranker-gte-multilingual-v1 \
  --candidate embedding-qwen3-0.6b-int8-1024-v1,reranker-qwen3-0.6b-int8-v1 \
  --top-k 20 --ndcg-k 10 --require-non-inferior
python3 scripts/embeddings-bench/compare-embeddings.py

# L5 events and soak
kubectl -n qwen-canary get events --sort-by=.lastTimestamp
python3 scripts/embeddings-bench/qwen-canary-soak.py \
  --duration 72h --slots 2 --gte-baseline-freeze 51-GTE-BASELINE-FREEZE.json --fail-on-oom --fail-on-starvation
```

### Required Acceptance Criteria

| Gate | Pass criterion | Evidence |
|---|---|---|
| Functional embedding | health ready; batch 1 e 4; every vector exactly 1024; finite values; L2 norm within agreed tolerance around 1 | redacted JSON + pod/image/model identity |
| Consistency | cosine(single, same item in batch) `>= 0.9999` across frozen golden corpus | per-case minimum and aggregate report |
| Reranker | `/rerank` returns scores finite in `[0,1]`, stable descending order, correct relevant doc, batch/document cap and router conversion | native + public redacted responses |
| Governor | exactly 2 cycle leases globally; third waits; only one inference stage per cycle; rerank continuation precedes new embedding; release on success/failure/cancel/TTL | race-enabled unit tests + timestamped integration trace |
| Retrieval quality | candidate Recall@20 `>=` GTE Recall@20 and candidate nDCG@10 `>=` GTE nDCG@10, globally and in PT-BR technical/code slices | frozen qrels, query/corpus version and paired report |
| Resources | every runtime pod request/limit `500m`; no OOMKilled; zero unexpected restarts; candidate end-to-end CPU-seconds `<= 1.05 ×` matched GTE | cgroup/Kubernetes metrics with warmup excluded and same workload |
| Fairness | no starvation in either slot and bounded queue wait under sustained mixed traffic; the bound must be established from measured service time before soak | queue/stage metrics and max-wait report |
| Isolation | no Qwen resource in `ebeddings-local`; no GTE quota/alias/collection modification; no public direct backend reachability | namespace diff, alias dump and negative network probes |
| Soak | at least 72 continuous hours; no OOM/starvation; no measurable GTE regression beyond predeclared noise/error thresholds | baseline + soak time series and events |
| Rollback | atomic aliases restored to GTE mappings; GTE request succeeds immediately; Qwen remains isolated; no emergency reindex | before/after alias export, smoke and rollback timing |

### Evidence Contract

Store only: git SHA, manifest digest, image digest/platform, model revision/file SHA-256, alias map, collection schema/count, corpus/qrels version, aggregate quality metrics, latency/CPU/RSS, queue transitions, Kubernetes events and redacted errors. Never store tokens, Authorization headers, raw vectors, full query/document contents or Kubernetes Secret values. [VERIFIED: `AGENTS.md`] [VERIFIED: `docs/operations/local-ai-embeddings.md`]

### Frequency

- **Per task commit:** L0 plus focused L1 test under 30 seconds where possible.
- **Per wave merge:** full L1, component smoke for changed backend, server-side manifest dry-run.
- **Before integrated traffic:** L0–L2 all green and pins captured.
- **Per capacity run:** three warm runs minimum per profile; report variance, not only best result. [ASSUMED]
- **During 72h soak:** scrape/snapshot at 1-minute resolution for service metrics, 5-minute aggregate evidence, immediate event capture on restart/OOM/TTL; daily summary. [ASSUMED]
- **Phase gate:** L0–L5 green, full reindex complete, rollback drill green and explicit manual approval; otherwise GTE remains titular. [VERIFIED: `51-CONTEXT.md`]

### Wave 0 Gaps

- [ ] focused Go tests for pipeline lease, exact-once release, global slots, priority, TTL, cancellation and starvation;
- [ ] Node tests for prompt/token IDs, softmax stability, validation, body/doc limits, queue cancellation and graceful shutdown;
- [ ] `qwen-canary-smoke.py` for backend and router contracts;
- [ ] frozen PT-BR technical/code corpus, qrels and paired Recall@20/nDCG@10 evaluator;
- [ ] token-normalized CPU/resource collector for both k3s and GTE baseline;
- [ ] 72h soak collector/report and alias rollback smoke;
- [ ] manifest schema/security checks integrated with existing project tooling.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes, public router only | Bearer auth remains router-owned; workers have no public ingress. [VERIFIED: `docs/operations/local-ai-embeddings.md`] |
| V3 Session Management | no user session; yes pipeline lease lifecycle | opaque `pipeline_id`, bounded TTL, exact-once release, no authorization data in ID. [ASSUMED] |
| V4 Access Control | yes | alias allowlist, private backend network path, namespace RBAC and negative reachability tests. [VERIFIED: `51-CONTEXT.md`] |
| V5 Input Validation | yes | body bytes, UTF-8 strings, batch/doc/token limits, dimensions, finite scores and top_n bounds. [VERIFIED: prototype] |
| V6 Cryptography | yes for supply chain/integrity | SHA-256 model verification, image digest pinning, Vault for secrets; do not hand-roll crypto. [VERIFIED: `AGENTS.md`] |
| V8 Data Protection | yes | no raw technical corpus/query contents in metrics or evidence; Qdrant auth/backup policy must be discovered. [ASSUMED] |
| V10 Malicious Code | yes | exact package/image/model pins, lockfile, package legitimacy and no runtime package download. [VERIFIED: package audit] |
| V12 File/Resource | yes | payload/model cache limits, PVC quotas, no path traversal, read-only root FS where compatible. [ASSUMED] |
| V13 API/Web Service | yes | content type, size/rate/admission limits, explicit errors/timeouts and private `/rerank`. [ASSUMED] |

### Threats and Mitigations

| Pattern | STRIDE | Mitigation |
|---|---|---|
| Direct NodePort bypasses router/governor | Elevation/DoS | private firewall path, NetworkPolicy if enforced, negative public probe, backend concurrency cap |
| Crafted huge query/document batch | DoS | byte/character/token/document caps before tokenizer; bounded queue; TTL |
| Model/image drift | Tampering | revision + SHA-256 + digest pins; startup verification |
| Lease leak on disconnect | DoS | context cancellation, terminal-state CAS/exact-once release, expiry sweeper |
| Cross-corpus or 768/1024 write | Tampering | collection schema + embedding signature + logical corpus allowlist |
| Sensitive corpus in logs | Information disclosure | aggregate metrics, query hash/ID only, redacted evidence |
| Public alias changed prematurely | Tampering | explicit manual checkpoint, before/after alias export, GTE smoke and rollback command prepared |

## State of the Art and Local Baseline

| Existing/local approach | Phase 51 approach | Impact |
|---|---|---|
| GTE embedding, 768d, CLS, one 500m pod, `hostNetwork` | Qwen INT8, 1024d, mean, two 500m pods, normal pod network + private NodePort | separate vector space and doubled embedding allocation; no in-place replacement. [VERIFIED: manifests/context] |
| GTE reranker FP16 in TEI, HPA 2–4 | Qwen INT8 in dedicated Transformers.js/ORT service, warmup 1 then integrated 2 | backend contract must be hardened and measured; HPA is future target. [VERIFIED: manifests/context] |
| Per-request embedding/rerank leases | two cycle-wide pipeline leases | prevents embedding completion from releasing capacity before vector search/rerank. [VERIFIED: context] |
| Podman Qwen prototype | k3s `qwen-canary` with quota, probes and isolation | repeatability and scheduling improve, but compatibility must be re-proved. [VERIFIED: spike/context] |

## Open Questions (RESOLVED BY FAIL-CLOSED GATES)

Nenhum resultado live é assumido abaixo. O Plan 51-01 grava
`51-WAVE0-GATE.json` com `status=PASS|BLOCK|UNKNOWN`; somente `PASS` permite
qualquer tarefa downstream. `BLOCK` e `UNKNOWN` devem produzir exit não zero no
comando `qwen-canary-inventory.py assert-gate`.

1. **Qual é a topologia live do router?**
   Output obrigatório do Plan 51-01:
   `51-W0-INVENTORY.json` (`router_topology`) e
   `51-LEASE-STATE-DECISION.md`, ambos referenciados por
   `51-WAVE0-GATE.json`.
   PASS: exatamente uma réplica/restart domain permite `in_process`, ou um
   backend atômico compartilhado já existente é provado com operação,
   ownership, TTL e source integration. BLOCK: múltiplas réplicas sem esse
   backend, identidade ambígua ou decisão divergente do inventário.
   Downstream bloqueado: Plans 51-02 a 51-08, com enforcement direto em 51-04.

2. **Quais memory requests/limits são seguros para o reranker?**
   Output obrigatório do Plan 51-01:
   `51-W0-INVENTORY.json` (`reranker_warmup_prerequisites`) e
   `51-BASELINE-CONTRACT.json` (`reranker_sizing_gate`).
   PASS: capacidade para um warmup ARM64 de 500m, limites temporários,
   métricas RSS/startup/OOM e stop conditions estão declarados; o valor final
   continua sendo medido em 51-02, não inventado. BLOCK: falta de headroom,
   métricas, limite temporário ou rollback.
   Downstream bloqueado: 51-02 Task 2 e Plans 51-03 a 51-08.

3. **Quais NodePorts e controles de rede estão livres/efetivos?**
   Output obrigatório do Plan 51-01:
   `51-W0-INVENTORY.json` (`private_network_branch`, NodePorts, firewall,
   `nodePortAddresses`, CNI enforcement e probes planejados).
   PASS: dois NodePorts sem colisão e uma branch exata é selecionada:
   NetworkPolicy comprovadamente enforced, ou NetworkPolicy omitida com
   firewall/`nodePortAddresses` e probes positivo/negativo obrigatórios.
   BLOCK: colisão, alcance público, branch ambígua ou ausência de controle
   efetivo.
   Downstream bloqueado: Plans 51-03, 51-04, 51-06 e 51-08.

4. **Onde e em qual versão roda Qdrant?**
   Output obrigatório do Plan 51-01:
   `51-W0-INVENTORY.json` (`qdrant`) e o hash do export read-only inicial em
   `51-WAVE0-GATE.json`.
   PASS: identidade/version/auth-mode/capacidade/collections/aliases/snapshot
   e operação atômica de alias são legíveis e compatíveis. BLOCK: endpoint ou
   auth ambíguo, capacidade/snapshot insuficiente, alias export incompleto ou
   recurso necessário não suportado.
   Downstream bloqueado: Plans 51-05 a 51-08.

5. **Qual threshold define “sem impacto mensurável no GTE”?**
   Output obrigatório do Plan 51-01:
   `51-BASELINE-CONTRACT.json` com métricas, janela, suficiência, floors e
   equações, mais `51-GTE-BASELINE-FREEZE.json` com janela GTE-only,
   proveniência, bandas numéricas, hashes e
   `frozen_before_any_qwen_live_result=true`, ambos referenciados por
   `51-WAVE0-GATE.json`.
   PASS: uma janela histórica válida termina antes da Wave 0 e congela os
   números, ou uma nova janela baseline-only termina antes de qualquer Qwen.
   BLOCK: histórico insuficiente, qualquer número unset, proveniência/hash
   ausente ou possibilidade de ajuste após observar Qwen.
   Os três artefatos ficam imutáveis após 51-01. Plans 51-02..51-09 geram
   readbacks próprios que verificam hashes originais e topologia/pins/aliases
   atuais; idade isolada não reescreve nem invalida história, inclusive após
   o soak >72h. Downstream bloqueado: Plans 51-02 a 51-09.

## Assumptions Log

| # | Claim | Risk if Wrong |
|---|---|---|
| A1 | Estado in-process da pipeline é suficiente se houver exatamente uma réplica do router. | Slots podem vazar/duplicar em restart; exige prova de topologia. |
| A2 | Embedding request 2Gi/limit 4Gi por pod será suficiente no k3s. | OOM/warmup failure; medir antes de soak. |
| A3 | Reranker request 2Gi/limit 4Gi é um ponto inicial viável. | OOM ou quota superdimensionada; warmup é obrigatório. |
| A4 | O CNI suporta e aplica NetworkPolicy. | Backend pode permanecer acessível apesar do YAML. |
| A5 | Existem dois NodePorts privados livres. | Collision/apply failure ou exposição indevida. |
| A6 | Qdrant live suporta aliases, snapshots e opções de segurança necessárias. | Seed/rollback precisa de adaptação por versão. |
| A7 | O router checkout live contém os paths protegidos citados. | Plano de arquivos/testes precisará ser ajustado após inventory. |
| A8 | Os nomes de aliases Qdrant canary propostos são aceitáveis. | Apenas naming; não afeta os nomes físicos LOCKED. |
| A9 | Métricas a cada minuto e agregação a cada 5 minutos são sustentáveis. | Ajustar sampling sem perder eventos/peaks. |

## Sources

### Primary — HIGH confidence

- `.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-CONTEXT.md` — D-01..D-24, scope e refs.
- `scripts/embeddings-bench/results-2026-07-22-gte-qwen.md` e `compare-embeddings.py` — evidência ARM64/500m, cosine e CPU.
- `services/qwen-reranker-onnx/server.mjs` e `package.json` — protótipo e runtime.
- `k8s/ebeddings-local/tei-gte.yaml` e `tei-gte-reranker.yaml` — baseline k3s.
- `docs/operations/local-ai-embeddings.md` — contrato router/GTE/governor.
- https://huggingface.co/docs/text-embeddings-inference/en/supported_models — TEI ARM64.
- https://huggingface.co/docs/text-embeddings-inference/en/cli_arguments — pooling e runtime flags.
- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B — dimensão, normalização, instruction e pooling oficial.
- https://huggingface.co/Qwen/Qwen3-Reranker-0.6B — prompt e scoring oficial.
- https://onnxruntime.ai/docs/performance/tune-performance/threading.html — threads e spinning.
- https://qdrant.tech/documentation/manage-data/collections/ — schema, cosine e aliases.
- https://qdrant.tech/documentation/snapshots/ — snapshot e ausência de aliases.
- https://kubernetes.io/docs/concepts/policy/limit-range/ — resource policy.
- https://kubernetes.io/docs/concepts/services-networking/service/ — NodePort.
- https://kubernetes.io/docs/concepts/security/pod-security-standards/ — hardening.

### Secondary — MEDIUM confidence

- https://huggingface.co/janni-t/qwen3-embedding-0.6b-int8-tei-onnx — artifact comunitário LOCKED e mean pooling.
- https://huggingface.co/onnx-community/Qwen3-Reranker-0.6B-ONNX — export comunitário LOCKED e variantes ONNX.
- `inventory/hosts/horistic-srv.yaml` — inventário versionado; estado live não foi revalidado.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH para artefatos/pins e package; MEDIUM para compatibilidade k3s ainda não executada.
- Architecture: HIGH para boundaries LOCKED; MEDIUM para armazenamento da lease, dependente da topologia live.
- Sizing: MEDIUM para embedding; LOW para reranker até warmup.
- Quality: LOW até Recall@20/nDCG@10; cosine e normalização são HIGH no benchmark Podman.
- Security: MEDIUM; controles são conhecidos, mas CNI/firewall/Qdrant live precisam de prova.

**Research date:** 2026-07-23
**Valid until:** 2026-08-22 para contratos estáveis; pins/imagens e estado live devem ser revalidados imediatamente antes do apply.
