---
phase: 41
plan: 41-01
status: completed
created: 2026-06-26
updated: 2026-06-26
---

# Phase 41 Plan 41-01 Checkpoint

## Completed Live

- Created operational base folder `/home/ubuntu/GitHub/embeddings`.
- Applied TEI/GTE in k3s namespace `ai-search` on `horistic-srv`.
- Configured TEI model `Alibaba-NLP/gte-multilingual-base` with upstream served model `text-embeddings-inference`, `cls` pooling and 768 dimensions.
- Set TEI pod DNS to direct external resolvers for Hugging Face bootstrap after CoreDNS external-resolution failures.
- Bound TEI to private worker IP `10.1.1.4:3000` with `hostNetwork: true` so the Podman-based `router-ai-atius` on SRV-1 can reach it without public exposure.
- Created New API/router channel `Local TEI - GTE Embeddings` with public alias `embedding-pt-v1`.
- Verified public unauthenticated `GET https://router.atius.com.br/v1/models` returns `401`.
- Verified public authenticated `GET /v1/models` includes `embedding-pt-v1`.
- Verified public authenticated `POST /v1/embeddings` returns two 768-dimensional vectors with `error=null`.

## Verification Performed

```text
TEI rollout: deployment "tei-gte" successfully rolled out
TEI pod: ai-search/tei-gte Ready 1/1 on horistic-srv, IP 10.1.1.4
TEI health from SRV-1: HTTP 200
TEI health from router-ai-atius container: HTTP 200
Internal TEI smoke: quantidade=2, dimensoes=768, error=null
Router channel: id=9, base_url=http://10.1.1.4:3000, model_mapping={"embedding-pt-v1":"text-embeddings-inference"}
Router ability: default / embedding-pt-v1 / channel_id=9 / enabled=true
Public /v1/models unauthenticated: HTTP 401
Public /v1/models authenticated: HTTP 200, embedding-pt-v1 present
Public /v1/embeddings authenticated: HTTP 200, quantidade=2, dimensoes=768, error=null
Secret hygiene: temporary smoke tokens deleted; no token values saved
```

## Operational Notes

- `http://tei-gte.ai-search.svc.cluster.local` remains a k3s service name, but the router-facing upstream is `http://10.1.1.4:3000` because the router runs in Podman outside the k3s service DNS/ClusterIP path.
- No Ingress, Apache vhost or Cloudflare record was created for TEI.
- The public client entrypoint remains `https://router.atius.com.br/v1`.
- The alias contract is frozen as `embedding-pt-v1 -> Alibaba-NLP/gte-multilingual-base -> 768 dimensions`.
