---
phase: 51
slug: qwen3-embedding-e-rerank-podman-para-k3s
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 59 — Validation Strategy

GTE remains titular. Plan 59-01 seals `59-BASELINE-CONTRACT.json`,
`59-GTE-BASELINE-FREEZE.json`, and `59-WAVE0-GATE.json`; Plans 59-02..59-09
create plan-scoped readbacks that verify the original hashes and current
topology, pins, endpoints and aliases without rewriting sealed evidence.

Heavy builds/tests run through the `builds` profile at no more than 20% host
CPU. Runtime pods remain at 500m. The namespace ceiling is five pods/2500m:
four runtime pods plus exactly one 500m tool Job.

## Exact Per-Task Automated Commands

The commands below are copied literally from each final `<automated>` element.

## Automatic execution contract

This phase is executed with validation at three mandatory boundaries:

1. **Task boundary — 23/23 tasks:** `execute-plan` runs each task's
   `<automated>` command and then enforces every `<acceptance_criteria>` before
   the next task can start. A failed criterion blocks progression and must be
   repaired or escalated.
2. **Plan boundary — 9/9 plans:** the executor runs the plan-level
   `<verification>`, re-runs all task acceptance criteria during the SUMMARY
   self-check, and must write `## Self-Check: PASSED` before the plan is closed.
3. **Wave boundary — Waves 0 through 8:** `execute-phase` runs the configured
   `bash scripts/gsd-wave-regression.sh` post-merge test gate after the last
   plan in the wave, then dispatches the active `execute:wave:post` gates. The
   next wave is not released until this gate sequence finishes; `verify.key-links`
   then checks every prior-wave artifact before dispatch.

The runner is intentionally phase-neutral and regression-oriented: it runs all
discovered `scripts/embeddings-bench` unittest files and the Qwen reranker Node
suite once its lockfile exists. The unrelated legacy CLI suite is not part of
this wave gate because its current host-only baseline has two pre-existing
environment failures (`/home/ubuntu` runtime paths); those failures must not be
misclassified as Phase 59 regressions. The runner does not replace the
task-specific commands above, which remain responsible for live readbacks,
Kubernetes dry-runs, owner-host Go tests, Qdrant checks, and the 72-hour
asynchronous soak verification.

Wave 7 has one deliberate deferred state: `external_job_waiting`. In that wave,
the soak Job's manifest contains the core verification command and original-UID
reconciliation contract; the next wave remains unavailable until that external
result is terminal and verified. No re-dispatch is permitted.

`nyquist_compliant` and `wave_0_complete` remain `false` until real execution
evidence is written; this document is the pre-execution contract, not proof that
the checks have already passed.

### 59-01-01

`python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_inventory.py -v`

### 59-01-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --lease-decision .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-LEASE-STATE-DECISION.md --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --require-phase-50-summary .planning/phases/50-atius-wide-sso-closeout/50-01-SUMMARY.md --require-frozen-before-any-qwen-live-result &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-gate --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --require PASS`

### 59-02-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-02 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-02-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-02-GATE-READBACK.json --require PASS &amp;&amp; npm --prefix services/qwen-reranker-onnx test`

### 59-02-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-02 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-02-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-02-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; p='.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-RERANKER-WARMUP.json'; d=json.load(open(p)); assert d['architecture'] in ('arm64','aarch64'); assert d['model_revision']=='9995c50e2310679108a55f5ccd16ba8be9f17c20'; assert d['artifact_sha256']=='c9428382bb48bb31e01a6034647c86d6270761781735cafbf6d5cb4a396d0450'; assert d['cpu_limit_millicores']==500; assert d['oom_count']==0 and d['ranking_sanity_passed']"`

### 59-03-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-03 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_manifests.py -v &amp;&amp; kubectl kustomize k8s/qwen-canary &gt;/tmp/qwen-canary-rendered.yaml &amp;&amp; kubectl apply --dry-run=server -f /tmp/qwen-canary-rendered.yaml`

### 59-03-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-03 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json --require PASS &amp;&amp; { kubectl diff -k k8s/qwen-canary &gt; /tmp/qwen-canary.diff; rc=$?; test "$rc" -eq 0 -o "$rc" -eq 1; }`

### 59-03-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-03 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-03-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-K3S-ROLLOUT.json --gate-set k3s-rollout`

### 59-04-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-04 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-K3S-ROLLOUT.json --gate-set k3s-rollout &amp;&amp; ssh -n atius-srv-1 'cd /home/ubuntu/GitHub/containers/router-ai-atius &amp;&amp; omni srv1-ops resources run builds -- go test -race ./service/embeddinggovernor ./service/modelcatalog ./relay -run "Pipeline|Governor|Embedding|Catalog|Rerank" -count=3 &amp;&amp; test -z "$(git diff --cached --name-only)"'`

### 59-04-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-04 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-K3S-ROLLOUT.json --gate-set k3s-rollout &amp;&amp; python3 -c "import json; p='.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-ROUTER-LIFECYCLE.json'; d=json.load(open(p)); assert d['source_commit']['status']=='PASS'; assert d['live_activation']['status']=='PENDING'"`

### 59-04-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-04 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-ROUTER-LIFECYCLE.json --gate-set router-live`

### 59-05-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-05 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qdrant_qwen_canary.py -v &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py dry-run --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --all-corpora --include-dual-index`

### 59-05-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-05 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py preflight --read-only --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --tool-image-evidence .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-QDRANT-TOOL-IMAGE.json --export-aliases .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-QDRANT-ALIAS-EXPORT.json`

### 59-05-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-05 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-05-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify --evidence .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-QDRANT-REINDEX.json --require-idempotent-replay --require-dual-index-sources gbrain,obsidian,graphify --require-incumbent-unchanged`

### 59-06-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-06 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-06-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-06-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; d=json.load(open('.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-ROUTER-LIFECYCLE.json')); assert d['live_activation']['status']=='PASS'; assert d['active_router_sha']==d['source_commit']['after_sha']" &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_smoke.py -v`

### 59-06-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-06 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-06-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-06-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; d=json.load(open('.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-ROUTER-LIFECYCLE.json')); assert d['live_activation']['status']=='PASS'; assert d['active_router_sha']==d['source_commit']['after_sha']" &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-smoke.py verify-report --report .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-FUNCTIONAL-SMOKE.json --require-all`

### 59-07-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-07 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_evaluate_rag_quality.py -v &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py validate-fixtures --corpus scripts/embeddings-bench/fixtures/qwen3-corpus.jsonl --qrels scripts/embeddings-bench/fixtures/qwen3-qrels.json --freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-EVAL-FREEZE.json`

### 59-07-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-07 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py review --qrels scripts/embeddings-bench/fixtures/qwen3-qrels.json --freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-EVAL-FREEZE.json --assert-no-results`

### 59-07-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-07 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-07-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py verify-report --report .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-QUALITY-CAPACITY-EVAL.json --freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-EVAL-FREEZE.json --min-rounds 5 --max-cpu-ratio 1.05 --require-no-regression`

### 59-08-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-08 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-08-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-08-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_soak.py -v &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-image --evidence .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-SOAK-TOOL-IMAGE.json --job k8s/qwen-canary/qwen-soak-job.yaml --require-arm64 --require-digest-pin --require-cpu-millicores 500`

### 59-08-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-08 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-08-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-08-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-dispatch --manifest .planning/async-jobs/phase-59-qwen-soak.json --job k8s/qwen-canary/qwen-soak-job.yaml --require-original-job-uid --require-single-job --require-dual-index-suspended --require-zero-active-before-dispatch --require-runtime-pods 4 --require-tool-pods 1 --require-total-cpu-millicores 2500 --require-status running`

### 59-09-01

`test -f .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-08-SUMMARY.md &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-report --report .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-SOAK-EVIDENCE.json --contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --min-hours 72 --require-original-job --require-continuous --require-dual-index-suspended &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-09 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py preflight-rollback --alias-export .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-QDRANT-ALIAS-EXPORT.json --soak .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-SOAK-EVIDENCE.json --require-current-hashes --require-gte-smoke-command`

### 59-09-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-09 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-rollback --evidence .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-ROLLBACK-DRILL.json --require-no-reindex --require-gte-smoke &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-dual-index-reconciliation --evidence .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-DUAL-INDEX-RECONCILIATION.json --require-sources gbrain,obsidian,graphify --require-no-lost-writes --require-no-duplicate-writes --require-idempotent-replay --require-cronjob-restored &amp;&amp; python3 -c "import json; d=json.load(open('.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-KNOWLEDGE-CLOSEOUT.json')); assert d['obsidian_http']['readback']=='PASS'; assert d['gbrain_http']['readback']=='PASS'; assert d['redaction']=='PASS'"`

### 59-09-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 59-09 --inventory .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-W0-INVENTORY.json --baseline-contract .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-GTE-BASELINE-FREEZE.json --gate .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE0-GATE.json --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-09-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "from pathlib import Path; s=Path('.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-PROMOTION-DECISION.md').read_text(); assert 'PROMOTION_EXECUTED: false' in s; assert any(x in s for x in ('approved-for-separate-promotion-change','rejected','defer'))" &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-current-aliases --require-gte-titular --require-no-promotion`

## Manual Gates

- 59-03-02: first live `qwen-canary` apply.
- 59-04-02: exact router activation.
- 59-05-02: Qdrant creation/reindex.
- 59-07-02: frozen qrels.
- 59-09-01: post-soak alias drill.
- 59-09-03: explicit decision with `PROMOTION_EXECUTED: false`.

## Async Closure

59-08-02 is the final Plan 08 task and returns literal `external_job_waiting`.
The execute-phase core may close `59-08-SUMMARY.md` only after the manifest's
literal `verification_command` reconciles the original Job UID without
redispatch, writes and verifies `59-SOAK-EVIDENCE.json` for at least 72
continuous hours, and refreshes Plan 08 lineage. Plan 09 depends on that closed
summary.

## Sign-Off

- [ ] Phase 50 completion is proven.
- [ ] Wave 0 GTE-only numeric freeze is PASS before any Qwen live result.
- [ ] Sealed baseline/freeze/gate hashes never change after Plan 01.
- [ ] Plan 03 two-replica init-download/effective-500m tests pass.
- [ ] Plan 04 live router activation is PASS before Plan 06 traffic.
- [ ] Dual-index is suspended with zero active Job before soak and restored/replayed only in Plan 09.
- [ ] Original soak Job supplies at least 72 continuous hours.
- [ ] Rollback, GTE smokes, no-loss/no-duplicate replay and knowledge readbacks pass.
- [ ] `PROMOTION_EXECUTED: false`; GTE remains titular.
- [ ] Set `nyquist_compliant: true` and `wave_0_complete: true` only after execution evidence exists.

**Approval:** pending
