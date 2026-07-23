---
phase: 41
status: passed
created: 2026-06-26
---

# Phase 41 Validation Strategy

## Validation Architecture

### Dimension 1: Public API contract

- `GET /v1/models` without auth returns `401 Unauthorized`.
- Authenticated `POST /v1/embeddings` accepts `model=embedding-pt-v1`.
- Smoke response for two pt-BR texts returns exactly two embeddings.
- First vector length is 768.

### Dimension 2: Internal routing

- New API channel base URL is `http://10.1.1.4:3000`.
- Channel base URL does not contain `router.atius.com.br`.
- Public alias maps to the TEI upstream model, not to another public gateway.

### Dimension 3: Backend runtime

- k3s namespace `ai-search` exists.
- TEI Deployment is Available.
- Service `tei-gte` is ClusterIP/internal only.
- TEI pod runs on `horistic-srv` with `hostNetwork: true` and binds to private IP `10.1.1.4`.
- No Ingress exposes TEI directly.

### Dimension 4: Model immutability

- Docs record model `Alibaba-NLP/gte-multilingual-base`.
- Docs record dimension `768`.
- Docs state model/digest/quantization/normalization/chunking changes require reembed/reindex.

### Dimension 5: Client migration safety

- GBrain migration includes backup before model/dimension changes.
- Existing non-768 vectors are not mixed with 768-dimensional vectors.
- Obsidian and Graphify use embeddings as auxiliary retrieval/indexing.

### Dimension 6: Secret hygiene

- No new artifact contains Bearer token, New API key, Authorization header, Vault secret value or Kubernetes Secret data.
- Smoke commands use `read -rsp`, environment variables loaded out-of-band, or secret references.

## Result

- Passed 2026-06-26 with public router smoke through `https://router.atius.com.br/v1`.
- Temporary smoke tokens were created and deleted without printing or saving token values.
- No TEI Ingress, Apache vhost or Cloudflare record was created.
