# Local AI Embeddings

## Contract

Clients call the public OpenAI-compatible gateway of our `router-ai-atius` / New API deployment:

```text
https://router.atius.com.br/v1
```

The stable public embedding alias is:

```text
embedding-gte-v1
```

The stable public reranker alias is:

```text
reranker-gte-multilingual-v1
```

The backend for this phase is TEI running inside k3s:

```text
http://10.21.1.21:3115
```

The loaded model is `Alibaba-NLP/gte-multilingual-base`. The upstream TEI served model name for the New API channel is `embedding-gte-v1`. The frozen vector dimension for this alias is `768`, with `cls` pooling.

TEI stays internal. Do not create an Ingress, Apache vhost, Cloudflare record, public NodePort, or any other direct public route to TEI. Our `router-ai-atius` / New API owns authentication, logging, quotas, token accounting, model aliases, and routing.

## GTE Multilingual Reranker

The reranker uses the official `Alibaba-NLP/gte-multilingual-reranker-base`
weights at revision `8215cf04918ba6f7b6a62bb44238ce2953d8831c`, served as FP16 by
TEI 1.9.3/Candle on ARM64 CPU. The private backend is
`http://10.21.1.21:31216/rerank`; clients use the governed public route
`POST https://router.atius.com.br/v1/rerank` with model
`reranker-gte-multilingual-v1`.

The Go router converts the public Jina/OpenAI-style contract
`query`/`documents`/`top_n` into TEI's native `query`/`texts` contract and maps
`score` back to `results[].relevance_score`. A request is capped at 20
documents. Embeddings and reranking share the same `embeddinggovernor`; the
reranker supplies workload, document-count and character-count admission data.

| Setting | Minimum | Maximum |
|---|---:|---:|
| Reranker pods | 2 | 4 |
| CPU per pod | 500m | 500m |
| Total CPU | 1000m | 2000m |
| Memory request | 4Gi | 8Gi |
| Memory limit | 6Gi | 12Gi |

The HPA target is 70% CPU. Scale-up is limited to one pod every 30 seconds and
scale-down to one pod every 120 seconds, with a 300-second stabilization window.
The namespace ResourceQuota covers one embedding pod plus four reranker pods:
5 pods, 2500m CPU, 14Gi memory requests and 24Gi memory limits.

Observed on 2026-07-22 after load: about 805Mi idle RSS per reranker pod. A
20-document long-text test peaked near 836Mi RSS and completed in about 64.3s
under the strict 500m limit. Short-text latency was about 0.38s for one
document, 3.63s for eight and 9.29s for twenty on one pod. These are operational
measurements, not model guarantees.

## Router Governor

The embedding governor lives inside the Go router process, not in a Python sidecar or extra container. The protected implementation paths in `router-ai-atius` are:

- `service/embeddinggovernor/`
- `relay/embedding_handler.go`

The governed local models are `embedding-gte-v1` and
`reranker-gte-multilingual-v1`. The old `embedding-pt-v1` and `*-batch` aliases
are not active. Embeddings use `X-Embedding-Workload`; reranking uses
`X-Rerank-Workload`. Both paths share the same governor so local inference
cannot bypass admission control.

Observed GBrain/Obsidian tuning data behind this default:

- Initial GBrain run had `3667 stale chunks` and `Embedded: 0`.
- Large page batches timed out before writing vectors.
- Provider sub-batch `4` was the first reliable size for pages that previously failed.
- Concurrency `2` produced useful progress but also load `~5.3` to `>6` on a 4-core host, with TEI around `115-148%` CPU and one heavier attempt reaching `~7.8GiB` RSS before upstream errors/readiness problems.
- Therefore catch-up/indexing should remain conservative, while interactive bursts may scale only under observed healthy latency and no recent failure.

## Graphify Bridge

Graphify remains graph-first. The local bridge only links Graphify-side auxiliary retrieval/indexing to the same governed embeddings endpoint:

```text
Config: ~/.graphify/embeddings.json
Helper: ~/.local/bin/graphify-embed
Endpoint: https://router.atius.com.br/v1
Model: embedding-gte-v1
Dimensions: 768
Batch cap: 4
Header: X-Embedding-Workload: batch
```

Smoke:

```bash
graphify-embed --text "Graphify retrieval smoke" --pretty
```

## New API Channel

Create or update a New API channel for embeddings with these fields:

| Field | Value |
|---|---|
| Type | OpenAI-compatible |
| Base URL | `http://10.21.1.21:3115` |
| Upstream model | `embedding-gte-v1` |
| Public alias | `embedding-gte-v1` |
| Backend model | `Alibaba-NLP/gte-multilingual-base` |
| Dimensions | `768` |
| Pooling | `cls` |

Hard rule: the channel Base URL must not contain `router.atius.com.br`. That domain is our public `router-ai-atius` entrypoint for clients, but an internal New API channel that points back to `https://router.atius.com.br/v1` creates a router self-loop.

The alias `embedding-gte-v1` may route to more than one replica only when every replica uses the same model, same revision or digest, same quantization, same dimension, same normalization, and same chunking contract.

Changing any part of the embedding contract requires reembedding and reindexing dependent stores:

```text
model + revision/digest + quantization + dimension + normalization + chunking
```

## TEI Manifest

Versioned manifest:

```bash
kubectl apply -f k8s/ebeddings-local/tei-gte.yaml
kubectl apply -f k8s/ebeddings-local/tei-gte-reranker.yaml
```

Read-only checks after apply:

```bash
kubectl -n ebeddings-local rollout status deployment/tei-gte
kubectl -n ebeddings-local get deploy,svc,pvc tei-gte
kubectl -n ebeddings-local get ingress
```

The expected service is `ClusterIP`. No TEI Ingress should exist.

The Phase 41 manifest uses the official ARM64 CPU TEI image:

```text
ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-latest
```

The embedding Service remains ClusterIP-only for internal bookkeeping, but the router-facing upstream uses the private worker IP and TEI port:

```text
http://10.21.1.21:3115
```

The embedding TEI pod runs on `horistic-srv` in namespace `ebeddings-local`
with `hostNetwork: true`. The reranker uses a private NodePort because
`router-ai-atius` runs on SRV-1 and must reach the worker through the OCI/DRG
private address rather than the worker PodIP. `10.100.100.4` remains reserve
fallback only.

`horistic-srv` is tainted as manual-only. This TEI workload has the only explicit `atius.com/manual-only=true:NoSchedule` toleration in its manifest; generic agents must not schedule there.

The TEI pod uses pod-level DNS (`dnsPolicy: None`, `1.1.1.1`, `8.8.8.8`, `ndots:1`) because CoreDNS external-resolution failures blocked Hugging Face model bootstrap. This is scoped to the TEI pod; no public Ingress is created.

Live resource contract:

| Setting | Value |
|---|---|
| CPU request | `500m` = 0.5 node CPU/vCPU |
| CPU limit | `500m` = 0.5 node CPU/vCPU |
| Memory request | `6Gi` |
| Memory limit | `12Gi` |
| Tokenization workers | `1` |
| Autoscaling | Disabled; `replicas: 1` |

Namespace default:

| Setting | Value |
|---|---|
| Default CPU request | `500m` |
| Default CPU limit | `500m` |
| Pod CPU max | `500m` |

ATIUS k3s resource-management unit: `1 pod = 500m = 0.5 host CPU/vCPU`.
Two replicas/pods at this standard equal `1000m`, i.e. one full CPU core.
Kubernetes accounts CPU per container, so multi-container pods must explicitly
split the total pod budget and stay at or below `500m`.

`--tokenization-workers 1` is intentionally pinned. During resource tuning, TEI auto-selected 3 tokenization workers when the CPU ceiling was higher and exceeded the earlier 8Gi memory limit while warming up. Keeping one tokenization worker preserves predictable memory behavior with the current 12Gi memory limit.

After the first live validation, pin the Hugging Face model revision to a concrete commit SHA instead of `main`, then re-run the smoke tests and update the manifest annotation.

## Internal Smoke

Run from SRV-1 through the private worker IP:

```bash
/home/ubuntu/GitHub/embeddings/scripts/smoke-internal.sh
```

Healthy result:

```json
{
  "model": "embedding-gte-v1",
  "quantidade": 2,
  "dimensoes": 768,
  "error": null
}
```

## External Smoke

Do not paste tokens into shell history. Load the token interactively or from an approved secret loader:

```bash
read -rsp "New API key: " NEW_API_KEY
export NEW_API_KEY
echo
```

Unauthenticated model listing should stay protected:

```bash
curl -sS -o /tmp/router-models-unauth.json -w "%{http_code}\n" \
  "https://router.atius.com.br/v1/models"
```

Expected HTTP status: `401`.

Authenticated model IDs:

```bash
curl -sS \
  "https://router.atius.com.br/v1/models" \
  -H "Authorization: Bearer ${NEW_API_KEY}" \
  | jq -r '.data[]?.id'
```

Embedding smoke:

```bash
curl -sS \
  -X POST \
  "https://router.atius.com.br/v1/embeddings" \
  -H "Authorization: Bearer ${NEW_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON | jq '{
    model: .model,
    quantidade: (.data | length),
    dimensoes: (.data[0].embedding | length),
    usage: .usage,
    error: .error
  }'
{
  "model": "embedding-gte-v1",
  "input": [
    "O Obsidian armazena notas em arquivos Markdown.",
    "Busca semântica permite localizar textos com significados semelhantes."
  ],
  "encoding_format": "float"
}
JSON
```

Only save the redacted summary fields: `model`, `quantidade`, `dimensoes`, `usage`, and `error`. Do not save Authorization headers, request tokens, Kubernetes Secret values, full embedding arrays, or raw shell transcripts.

## Python Client

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://router.atius.com.br/v1",
    api_key=os.environ["NEW_API_KEY"],
)

response = client.embeddings.create(
    model="embedding-gte-v1",
    input=[
        "Como integrar embeddings locais no k3s?",
        "O New API funciona como gateway centralizado.",
    ],
    encoding_format="float",
)

vectors = [item.embedding for item in response.data]
print("Quantidade:", len(vectors))
print("Dimensões:", len(vectors[0]))
```

## Secret Hygiene

Do not write New API keys, Bearer tokens, Hugging Face tokens, Kubernetes Secret values, or Authorization headers to Git, `.planning`, Obsidian, logs, shell history, saved curl output, or screenshots.

Historical notes may contain old router/GBrain token material. Treat those notes as sensitive evidence only. Do not copy token values into new docs or planning artifacts.

## References

- [Hugging Face TEI CLI arguments](https://huggingface.co/docs/text-embeddings-inference/en/cli_arguments): `--model-id`, `--revision`, `--served-model-name`, `--port`, `--huggingface-hub-cache`.
- [Hugging Face TEI supported hardware](https://huggingface.co/docs/text-embeddings-inference/en/supported_models): ARM64 CPU is supported; the live registry validation used `ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-latest`.
- [`Alibaba-NLP/gte-multilingual-base` model card](https://huggingface.co/Alibaba-NLP/gte-multilingual-base): TEI usage, CLS pooling, normalization, and 768-dimensional embeddings.
- [`Alibaba-NLP/gte-multilingual-reranker-base` model card](https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base): official multilingual reranker, 8192-token model context and TEI usage.
