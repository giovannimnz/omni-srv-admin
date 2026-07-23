# Qwen reranker ONNX prototype

This directory contains an experimental Node/Transformers.js prototype for the
Phase 59 Qwen reranker canary. It is not a production service and must not be
built, deployed or registered in the router until the Phase 59 gates add:

- a pinned lockfile and reproducible ARM64 container build;
- unit tests for prompt construction, token IDs, scoring, validation and queue
  failure recovery;
- model and image digest evidence;
- CPU/memory containment at the `500m` pod unit;
- private-only network policy, health/readiness checks and rollback;
- equivalence evidence against the frozen GTE baseline.

The production GTE reranker under `k8s/ebeddings-local/` is independent from
this prototype.
