---
phase: 51
slug: qwen3-embedding-e-rerank-podman-para-k3s
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. GTE
> remains the production baseline; every Qwen result is canary evidence until
> the quality, capacity, soak, and manual-promotion gates pass.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Go `testing`/race detector for the governor and router; Node test runner for the ONNX reranker; Python benchmark/evaluation scripts; `kubectl`/Kustomize for k3s |
| **Config file** | Existing router and service configs plus Wave 0 scripts under `scripts/embeddings-bench/`; exact owner-host router paths must be inventoried before edits |
| **Quick run command** | `go test ./service/embeddinggovernor -count=1 && npm --prefix services/qwen-reranker-onnx test` |
| **Full suite command** | Focused Go race tests, Node tests, rendered-manifest validation, private component smokes, and paired quality/capacity scripts described below |
| **Estimated runtime** | Quick: under 60 seconds; pre-canary suite: up to 20 minutes after models are warm; soak: 72 hours |

Heavy suites, image builds, and compilation must run through the project
`builds` profile and stay under the 20% host CPU guardrail. Runtime pods remain
governed by their explicit `500m` requests/limits, not by the build guardrail.

---

## Sampling Rate

- **After every task commit:** Run the narrowest relevant unit/static command,
  with a target feedback latency below 60 seconds.
- **After every plan wave:** Run all focused tests for the components changed in
  that wave and validate rendered manifests server-side when cluster access is
  available.
- **Before integrated canary traffic:** L0 static checks and L1/L2 unit and
  component gates must be green.
- **Before `$gsd-verify-work`:** Full L0-L5 evidence must be green, including the
  72-hour soak and rollback drill.
- **Max feedback latency:** 60 seconds for task-local checks; long-running
  component, capacity, and soak gates are explicit plan checkpoints.

---

## Per-Task Verification Map

The planner must replace provisional task IDs with final plan/task IDs while
preserving every row and its ordering constraints.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-W0-01 | W0 | 0 | Validation harness | T-51-01 | Evidence excludes secrets, raw vectors, and corpus contents | static/unit | Focused Python/Node fixture tests | ❌ W0 | ⬜ pending |
| 51-W0-02 | W0 | 0 | Governor pipeline lease | T-51-02 | Exactly two global leases; exact-once release on success/error/cancel/TTL | unit/race | `go test ./service/embeddinggovernor -run 'TestPipeline\|TestPriority\|TestTTL\|TestCancel\|TestNoStarvation' -count=20 -race` | ❌ W0 | ⬜ pending |
| 51-W0-03 | W0 | 0 | Reranker contract | T-51-03 | Bounded input/queue, cancellation, stable finite scores, graceful drain | unit | `npm --prefix services/qwen-reranker-onnx test` | ❌ W0 | ⬜ pending |
| 51-STATIC | TBD | 1 | Pins, manifests, quota, aliases | T-51-01 / T-51-04 | Immutable artifacts, four runtime pods at `500m`, private-only workers | static | `kubectl kustomize k8s/qwen-canary` plus server-side dry-run | ❌ W0 | ⬜ pending |
| 51-EMBED | TBD | 2 | Qwen embedding INT8 1024d | T-51-01 | Pinned TEI/ONNX artifact, no direct public access | component | `python3 scripts/embeddings-bench/qwen-canary-smoke.py --expect-dim 1024 --batch-sizes 1,4 --min-single-batch-cosine 0.9999` | ❌ W0 | ⬜ pending |
| 51-RERANK | TBD | 2 | Qwen reranker INT8 | T-51-03 | Private `/rerank`, payload limits, scores in `[0,1]` | component | `python3 scripts/reranker-smoke.py --native --base-url http://10.21.1.21:<nodeport>` | ✅ existing script, extend as needed | ⬜ pending |
| 51-PIPELINE | TBD | 3 | Embedding → Qdrant → Rerank | T-51-02 / T-51-05 | Alias isolation, dimensions enforced, no leaked lease | integration | `qwen-canary-smoke.py --pipeline --concurrency 3 --expect-slots 2 --test-timeout --test-cancel --test-ttl` | ❌ W0 | ⬜ pending |
| 51-QUALITY | TBD | 4 | GTE 768d vs Qwen 1024d | — | Frozen equivalent corpus/chunking/IDs prevents biased comparison | quality | `evaluate-rag-quality.py --top-k 20 --ndcg-k 10 --require-non-inferior` | ❌ W0 | ⬜ pending |
| 51-CAPACITY | TBD | 4 | CPU, memory, fairness | T-51-02 / T-51-03 | No OOM/starvation and Qwen CPU-seconds `<= 1.05 × GTE` | capacity | Paired collector, at least five warm rounds per profile | ❌ W0 | ⬜ pending |
| 51-SOAK | TBD | 5 | 72-hour canary | T-51-02 / T-51-04 | GTE remains titular and unaffected; Qwen remains isolated | soak | `qwen-canary-soak.py --duration 72h --slots 2 --capture-gte-baseline --fail-on-oom --fail-on-starvation` | ❌ W0 | ⬜ pending |
| 51-ROLLBACK | TBD | 5 | Promotion/rollback | T-51-05 | Atomic alias restore, no emergency reindex, Qwen retained for diagnosis | integration/manual gate | Alias export/switch/restore plus immediate GTE smoke | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Focused Go tests for pipeline lease state transitions, global two-slot
  admission, rerank priority, TTL, cancellation, exact-once release, and
  starvation.
- [ ] Node tests for prompt/token IDs, stable softmax, malformed/oversized input,
  document limits, bounded queue, cancellation, timeout, and graceful shutdown.
- [ ] `scripts/embeddings-bench/qwen-canary-smoke.py` for private backend and
  router contracts.
- [ ] `scripts/embeddings-bench/evaluate-rag-quality.py` plus a frozen PT-BR
  technical/code corpus and qrels for paired Recall@20/nDCG@10.
- [ ] Token-normalized CPU/RSS/latency collector with warmup exclusion and
  equivalent GTE/Qwen workloads.
- [ ] `scripts/embeddings-bench/qwen-canary-soak.py` with restart/OOM/TTL,
  starvation, and GTE-baseline evidence.
- [ ] Idempotent Qdrant schema/alias inspection and rollback smoke without
  secrets or corpus contents in logs.
- [ ] Rendered-manifest validation for resources, pinning, security context,
  namespace isolation, NodePorts, probes, PDB, and staged HPA.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Router topology and lease-state decision | Two pipeline slots are global | The correct state mechanism depends on the live router replica/restart topology | Inventory the owner-host runtime. Permit in-process state only with one proved replica; otherwise require a shared atomic store and a three-request concurrency proof |
| ARM64 artifact and image compatibility | Reproducible TEI/ONNX and reranker startup | Registry/model metadata does not prove the exact target execution path | Capture image platform/digest, model revision/hash, OrtBackend/native runtime logs, startup time, and deterministic private smoke |
| Private NodePort reachability | Workers cannot bypass router/governor publicly | Effective exposure depends on node interfaces, firewall, and CNI behavior | Prove SRV-1 private success and public/unrelated-pod failure for both backends |
| Reranker memory sizing | Safe requests/limits | RSS and startup peak are unknown until one-pod warmup | Run batch 1/4/20 warmup at `500m`, capture cgroup peak/RSS/restarts, then freeze memory values before scaling to two |
| Qdrant preflight and rollback | 1024d collections remain isolated and recoverable | Live version, auth, storage, aliases, and snapshots must be inspected | Test disposable 1024d collection, alias export/switch/restore, snapshot behavior, and capacity before seed |
| Quality approval | Recall@20 and nDCG@10 are non-inferior | Qrels for Portuguese technical/code queries require owner review | Freeze corpus/qrels before results, run paired report, inspect failed slices, and sign off without changing labels post hoc |
| Soak and promotion | 72 hours without measurable GTE impact | Long-duration operational evidence and promotion authority are manual gates | Freeze baseline/tolerances first, run 72h, review daily evidence, execute rollback drill, then request explicit promotion approval |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no three consecutive tasks without automated verify.
- [ ] Wave 0 covers all MISSING references.
- [ ] No watch-mode flags.
- [ ] Feedback latency below 60 seconds for task-local checks.
- [ ] GTE aliases, quota, and 768d collections stayed unchanged.
- [ ] Qwen embedding ran as two `500m` pods; reranker warmup ran as one and
  integrated test as two `500m` pods.
- [ ] Recall@20 and nDCG@10 are not below GTE globally or for PT-BR
  technical/code slices.
- [ ] Single/batch cosine is at least `0.9999`.
- [ ] Qwen end-to-end CPU-seconds are at most 5% above the matched GTE baseline.
- [ ] No OOM, unexpected restart, lease leak, or starvation occurred.
- [ ] The 72-hour soak and alias rollback drill passed.
- [ ] Manual promotion approval was recorded; otherwise GTE remains titular.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after
  the corresponding evidence exists.

**Approval:** pending
