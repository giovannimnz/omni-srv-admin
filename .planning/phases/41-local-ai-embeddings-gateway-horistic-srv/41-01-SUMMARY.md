---
phase: 41
plan: 41-01
status: complete
completed: 2026-06-26
---

# Plan 41-01 Summary

## Result

Phase 41 delivered the local embeddings path requested for `horistic-srv`.

```text
Public OpenAI-compatible URL: https://router.atius.com.br/v1
Public alias: embedding-gte-v1
Router channel: Local TEI - GTE Embeddings
Router upstream Base URL: http://10.1.1.4:3115
k3s namespace: ebeddings-local
k3s deployment/service: tei-gte
Backend: TEI
Model: embedding-gte-v1 -> Alibaba-NLP/gte-multilingual-base
Served model: text-embeddings-inference
Pooling: cls
Dimensions: 768
```

## Evidence

- `kubectl -n ebeddings-local rollout status deployment/tei-gte` passed.
- `kubectl -n ebeddings-local get deploy,pod,svc,endpointslice -o wide` showed `deployment/tei-gte` available and pod IP `10.1.1.4` on `horistic-srv`.
- `/home/ubuntu/GitHub/embeddings/scripts/smoke-internal.sh` returned `quantidade=2`, `dimensoes=768`, `error=null`.
- Temporary-token local router smoke returned `/v1/models` HTTP 200 with `embedding-gte-v1` present and `/v1/embeddings` HTTP 200 with `quantidade=2`, `dimensoes=768`, `error=null`.
- Temporary-token public smoke through `https://router.atius.com.br/v1` returned the same embedding result.
- Unauthenticated public `/v1/models` stayed protected with HTTP 401.

## Files

- `/home/ubuntu/GitHub/embeddings/`
- `k8s/ebeddings-local/tei-gte.yaml`
- `docs/operations/local-ai-embeddings.md`
- `docs/operations/gbrain-embedding-migration.md`
- `.planning/phases/41-local-ai-embeddings-gateway-horistic-srv/41-VERIFICATION.md`

## Residual Risk

- Hugging Face model revision is still `main`; pin to the concrete snapshot SHA after the next maintenance window if immutability beyond cached artifact retention is required.
- The source repo has unrelated dirty work in `router-ai-atius`; only the live DB/channel config and small `clianything` overview update were required for this phase.
