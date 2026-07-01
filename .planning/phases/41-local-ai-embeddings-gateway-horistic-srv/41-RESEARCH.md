# Phase 41: Local AI Embeddings Gateway on horistic-srv - Research

## RESEARCH COMPLETE

**Question:** How should Atius deploy a local embedding model on k3s and expose it through the existing New API router for GBrain, Obsidian and Graphify?

**Primary source:** User-provided deep research at `/home/ubuntu/.codex/attachments/0811849f-3884-4179-a986-9c6516e5642e/deep-research-embbeding-k3s-local-model.md`, plus local repo/vault context for router-ai-atius and GBrain.

## Findings

### Selected architecture

The right production boundary is not "clients call TEI directly." The stable boundary is:

`clients -> https://router.atius.com.br/v1 -> New API -> internal TEI service -> embedding model`

New API owns authentication, logs, quotas, model aliasing and channel routing. TEI owns model execution. A vector database or local index owns vector persistence and search.

### Selected backend

TEI is the selected backend for this milestone because it exposes an OpenAI-compatible `/v1/embeddings` API and fits the user's chosen model path. Ollama remains a lower-friction fallback, but the user locked this phase to:

- Backend: TEI
- Model: `Alibaba-NLP/gte-multilingual-base`
- Public alias: `embedding-pt-v1`
- Dimension: 768

### Model rationale

`Alibaba-NLP/gte-multilingual-base` is a strong default for this fleet because it is multilingual, suitable for pt-BR and English technical notes, uses 768 dimensions, and has a smaller operational footprint than larger 0.6B+ alternatives. The 768-dimensional output also avoids the pgvector/HNSW problems that can appear with very high dimensions.

### Alias safety

Embedding aliases are not like chat-model aliases. Two different embedding models create incompatible vector spaces. Random routing between GTE, Qwen and BGE would make stored vectors semantically inconsistent.

Allowed behind `embedding-pt-v1`:

- same model
- same version or digest
- same quantization
- same dimension
- same normalization
- same chunking contract

Anything else requires reembedding and reindexing.

### GBrain implications

GBrain already has history using `https://router.atius.com.br/v1/embeddings` through the router. The migration must not mix vector dimensions. If current data was embedded with a 1536-dimensional provider, moving to 768 dimensions requires a new store, explicit reindex, or a documented retrieval-upgrade path.

### Obsidian implications

Obsidian is a Markdown vault. The robust integration pattern is an external indexer that watches or scans the vault, chunks Markdown, calls `embedding-pt-v1`, and stores vectors outside the vault. This avoids plugin lock-in and prevents silent model drift.

### Graphify implications

Graphify is graph/structure-first. Embeddings can help document retrieval, search and semantic sidecar workflows, but should not replace Graphify's graph extraction or code relationship model.

## Validation Architecture

### Gate 1: Static safety checks

- New API channel base URL is not `https://router.atius.com.br/v1`.
- Public alias is exactly `embedding-pt-v1`.
- Model contract documents 768 dimensions and `Alibaba-NLP/gte-multilingual-base`.
- No API key appears in repo diffs, `.planning`, Obsidian notes or captured logs.

### Gate 2: k3s/TEI checks

- Namespace `ai-search` exists.
- Deployment for TEI is Available.
- Service `tei-gte` resolves inside the cluster.
- Internal TEI smoke with OpenAI-compatible POST returns one or more embeddings.
- TEI has no public Ingress.

### Gate 3: New API checks

- `GET https://router.atius.com.br/v1/models` without auth returns `401`.
- Authenticated `/v1/models` lists `embedding-pt-v1` or the configured public alias.
- Authenticated `POST /v1/embeddings` with two pt-BR texts returns:
  - vector count 2
  - dimension 768
  - `error=null`
  - usage present when New API reports it

### Gate 4: Client contract checks

- Python OpenAI SDK works with `base_url="https://router.atius.com.br/v1"` and `model="embedding-pt-v1"`.
- GBrain migration plan names the backup, target model string, dimension, and reindex command or blocker.
- Obsidian and Graphify docs state that embeddings are auxiliary retrieval/indexing, not a replacement for source Markdown or graph structure.

## Risks

- A New API channel loop would route router -> router and fail or recurse.
- Changing dimensions without reindex breaks existing vector stores.
- Copying historical API keys from old docs would leak secrets into new artifacts.
- Publicly exposing TEI would bypass router auth/quota/logging.
- Load on `horistic-srv` could affect Apache/Horistic duties if resources are not bounded.

## Recommendation

Proceed with one executable plan: deploy TEI/GTE internally, configure `embedding-pt-v1` in New API, validate OpenAI-compatible embedding calls, and publish migration/runbook material for GBrain, Obsidian and Graphify. Keep vector DB selection and mass reindex for a follow-up once the endpoint is proven.
