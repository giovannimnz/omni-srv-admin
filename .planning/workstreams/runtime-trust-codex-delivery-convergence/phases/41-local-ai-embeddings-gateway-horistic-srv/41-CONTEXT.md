# Phase 41: Local AI Embeddings Gateway on horistic-srv - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning
**Source:** User-provided deep research and summary

<domain>
## Phase Boundary

Phase 41 owns the first production-grade local embeddings path for Atius:

`GBrain / Obsidian / Graphify -> https://router.atius.com.br/v1 (our router-ai-atius/New API) -> TEI in k3s -> Alibaba-NLP/gte-multilingual-base`

This phase creates the embedding service contract, the internal backend, the New API alias, smoke tests, and migration/runbook material. It does not replace Graphify's structural graph pipeline, does not mass-reindex existing stores without an explicit operator gate, and does not expose TEI directly to the public internet.

</domain>

<decisions>
## Implementation Decisions

### Public API contract
- **D-01:** Client entrypoint is `https://router.atius.com.br/v1`, the public domain of our `router-ai-atius` / New API deployment, not the internal TEI service.
- **D-02:** Public model alias is `embedding-pt-v1`.
- **D-03:** External clients use OpenAI-compatible `POST /v1/embeddings` with Bearer auth, `model`, `input`, and `encoding_format="float"`.
- **D-04:** `GET /v1/models` without a token returning `401 Unauthorized` is healthy gateway protection. `GET /v1/embeddings` returning `404` is expected because embeddings are created with POST.

### Backend and routing
- **D-05:** Our `router-ai-atius` / New API deployment is the gateway for auth, token accounting, logs, quotas, aliases and routing. It does not execute the embedding model and does not replace the vector store.
- **D-06:** The New API internal channel must not point to `https://router.atius.com.br/v1`; even though that is our own router public URL, using it as an upstream channel would create a routing loop.
- **D-07:** The New API channel base URL must point to the private TEI route, implemented as `http://10.1.1.4:3000` because `router-ai-atius` runs in Podman on SRV-1 and cannot rely on k3s service DNS/ClusterIP.
- **D-08:** Backend runtime for this phase is TEI, not Ollama. Ollama remains a fallback path but is not the selected production target.
- **D-09:** TEI runs in namespace `ai-search` on `horistic-srv` with a ClusterIP service plus `hostNetwork` binding on private IP `10.1.1.4`. No Ingress or public Apache/Cloudflare exposure is part of this phase.

### Model contract
- **D-10:** Initial model is `Alibaba-NLP/gte-multilingual-base`.
- **D-11:** Public alias `embedding-pt-v1` maps to upstream model `text-embeddings-inference` through the New API channel.
- **D-12:** Dimension is frozen at 768 for this contract.
- **D-13:** The durable contract is `model + version/digest + dimension + normalization + chunking`.
- **D-14:** The alias must not randomly balance across GTE, Qwen, BGE or other embedding models. Multiple replicas are allowed only if they use the same model, same version/digest, same quantization, same dimension and same normalization.
- **D-15:** Changing the model behind `embedding-pt-v1` requires regenerating vectors and rebuilding every dependent index.

### Clients and stores
- **D-16:** GBrain migration must back up file-plane config and DB-plane vector/config state before changing embedding model or dimension.
- **D-17:** Existing GBrain embeddings may have different dimensions. Do not mix 1536-dimensional or other legacy vectors with the new 768-dimensional store.
- **D-18:** Obsidian consumption should be through an external indexer over Markdown files, not through a plugin that owns an incompatible embedding model silently.
- **D-19:** Graphify remains graph/structure-first. Embeddings are an auxiliary retrieval layer for docs and search, not a replacement for Graphify's code graph.
- **D-20:** Vector database selection beyond pilot storage is deferred. The phase may document FAISS/pgvector/Qdrant/Milvus choices, but the must-have is the stable embedding API contract.

### Secrets and safety
- **D-21:** New API keys must be read from a prompt, Vault, or Kubernetes Secret. They must not be pasted into shell history, Git, `.planning`, Obsidian or logs.
- **D-22:** Historical docs that already mention router/GBrain tokens are read-only references. New artifacts must not copy those token values.
- **D-23:** Smoke-test output stored in repo must include status, model, vector count, dimension and usage only; never request headers or tokens.
- **D-24:** This phase must not restart XRDP, broad PM2 stacks, trading bots, Apache public edges or unrelated k3s workloads.

### the agent's Discretion
The executor may choose exact manifest filenames under a clear infra path such as `k8s/ai-search/` or `modules/ai-search/`, as long as the generated docs and verification commands point to the final paths. The executor may also decide whether the TEI deployment is applied directly with `kubectl` or first staged as versioned manifests, but production apply remains gated by the plan.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### User research and embedding contract
- `/home/ubuntu/.codex/attachments/0811849f-3884-4179-a986-9c6516e5642e/deep-research-embbeding-k3s-local-model.md` — selected model/runtime tradeoffs, TEI/Ollama options, vector-store implications, k3s deployment notes, and model-change reindex warnings.

### Router/New API history
- `modules/fork-sync/projects/atius-router/README.md` — local fork context for router-ai-atius/New API, model catalog and embeddings/provider routing.
- `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` — provider routing guards and embedding-related sync constraints.
- `modules/fork-sync/manuals/atius-router.md` — operational fork manual and channel/model notes.
- `docs/operations/tailscale/GBRAIN-INGEST-PENDING.md` — historical GBrain/router embedding configuration. Treat as sensitive historical evidence; do not copy token material from it.

### Fleet/k3s target
- `inventory/hosts/horistic-srv.yaml` — host inventory for the target k3s worker.
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` — fleet network/port reservations and public edge context.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-04-RUNTIME-REPAIR.md` — runtime repair that joined `horistic-srv` to k3s as worker.

### Existing planning constraints
- `.planning/PROJECT.md` — milestone scope and global project constraints.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` — EMB-01 through EMB-08.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` — Phase 41 goal, success criteria and refs.

</canonical_refs>

<specifics>
## Specific Ideas

- Namespace: `ai-search`.
- Service name: `tei-gte`.
- Internal TEI base URL for New API: `http://10.1.1.4:3000`.
- Public OpenAI-compatible base URL: `https://router.atius.com.br/v1` (`router-ai-atius` / New API).
- Public alias: `embedding-pt-v1`.
- Upstream TEI model name used by the OpenAI-compatible server: `text-embeddings-inference`.
- Real model: `Alibaba-NLP/gte-multilingual-base`.
- Frozen dimension: 768.
- Smoke texts:
  - `O Obsidian armazena notas em arquivos Markdown.`
  - `Busca semântica permite localizar textos com significados semelhantes.`
- Healthy smoke summary shape:
  - `model` is present
  - `quantidade` is `2`
  - `dimensoes` is `768`
  - `error` is `null`

</specifics>

<deferred>
## Deferred Ideas

- Running multiple embedding models behind one alias is deferred and only allowed for identical replicas.
- Switching to Qwen3, BGE-M3 or Ollama is deferred to a future benchmark/reindex phase.
- A production vector database migration to FAISS/pgvector/Qdrant/Milvus is deferred until the API contract is validated.
- Mass reindex of all GBrain/Obsidian/Graphify corpora is deferred until backup and acceptance gates are complete.
- Public direct exposure of TEI is out of scope.

</deferred>

---

*Phase: 41-local-ai-embeddings-gateway-horistic-srv*
*Context gathered: 2026-06-26*
