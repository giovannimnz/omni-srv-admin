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

The backend for this phase is TEI running inside k3s:

```text
http://10.1.1.4:3000
```

The loaded model is `Alibaba-NLP/gte-multilingual-base`. The upstream TEI served model name for the New API channel is `text-embeddings-inference`. The frozen vector dimension for this alias is `768`, with `cls` pooling.

TEI stays internal. Do not create an Ingress, Apache vhost, Cloudflare record, public NodePort, or any other direct public route to TEI. Our `router-ai-atius` / New API owns authentication, logging, quotas, token accounting, model aliases, and routing.

## Router Governor

The embedding governor lives inside the Go router process, not in a Python sidecar or extra container. The protected implementation paths in `router-ai-atius` are:

- `service/embeddinggovernor/`
- `relay/embedding_handler.go`

The only public governed embedding model is `embedding-gte-v1`. The old `embedding-pt-v1` and `*-batch` aliases are not active. The normal path starts at concurrency `1`, can scale up to `4` only when interactive queue pressure is healthy, and reduces to `1` on TEI errors, slow calls or cooldown. Batch calls use `X-Embedding-Workload: batch` or request-size classification on the same `embedding-gte-v1` model, and are capped separately at `1` so they do not consume all interactive capacity.

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
| Base URL | `http://10.1.1.4:3000` |
| Upstream model | `text-embeddings-inference` |
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
kubectl apply -f k8s/ai-search/tei-gte.yaml
```

Read-only checks after apply:

```bash
kubectl -n ai-search rollout status deployment/tei-gte
kubectl -n ai-search get deploy,svc,pvc tei-gte
kubectl -n ai-search get ingress
```

The expected service is `ClusterIP`. No TEI Ingress should exist.

The Phase 41 manifest uses the official ARM64 CPU TEI image:

```text
ghcr.io/huggingface/text-embeddings-inference:cpu-arm64-latest
```

The k3s Service remains ClusterIP-only for internal bookkeeping, but the router-facing upstream uses the private worker IP and TEI port:

```text
http://10.1.1.4:3000
```

The TEI pod runs on `horistic-srv` with `hostNetwork: true` and binds to the private node IP `10.1.1.4`. This is the router-facing internal URL because `router-ai-atius` runs in Podman on SRV-1 and does not reliably reach k3s PodIP/ClusterIP routes.

The TEI pod uses pod-level DNS (`dnsPolicy: None`, `1.1.1.1`, `8.8.8.8`, `ndots:1`) because CoreDNS external-resolution failures blocked Hugging Face model bootstrap. This is scoped to the TEI pod; no public Ingress is created.

Live resource contract:

| Setting | Value |
|---|---|
| CPU request | `1000m` = 1.0 node CPU/vCPU |
| CPU limit | `2000m` = 2.0 node CPU/vCPU |
| Memory request | `6Gi` |
| Memory limit | `12Gi` |
| Tokenization workers | `1` |
| Autoscaling | Disabled; `replicas: 1` |

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
  "model": "text-embeddings-inference",
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
