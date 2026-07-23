---
phase: 51
slug: qwen3-embedding-e-rerank-podman-para-k3s
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 51 — Validation Strategy

GTE remains titular. Plan 51-01 seals `51-BASELINE-CONTRACT.json`,
`51-GTE-BASELINE-FREEZE.json`, and `51-WAVE0-GATE.json`; Plans 51-02..51-09
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
misclassified as Phase 51 regressions. The runner does not replace the
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

### 51-01-01

`python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_inventory.py -v`

### 51-01-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --lease-decision .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-LEASE-STATE-DECISION.md --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --require-phase-50-summary .planning/phases/50-atius-wide-sso-closeout/50-01-SUMMARY.md --require-frozen-before-any-qwen-live-result &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-gate --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --require PASS`

### 51-02-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-02 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-02-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-02-GATE-READBACK.json --require PASS &amp;&amp; npm --prefix services/qwen-reranker-onnx test`

### 51-02-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-02 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-02-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-02-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; p='.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-RERANKER-WARMUP.json'; d=json.load(open(p)); assert d['architecture'] in ('arm64','aarch64'); assert d['model_revision']=='9995c50e2310679108a55f5ccd16ba8be9f17c20'; assert d['artifact_sha256']=='c9428382bb48bb31e01a6034647c86d6270761781735cafbf6d5cb4a396d0450'; assert d['cpu_limit_millicores']==500; assert d['oom_count']==0 and d['ranking_sanity_passed']"`

### 51-03-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-03 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_manifests.py -v &amp;&amp; kubectl kustomize k8s/qwen-canary &gt;/tmp/qwen-canary-rendered.yaml &amp;&amp; kubectl apply --dry-run=server -f /tmp/qwen-canary-rendered.yaml`

### 51-03-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-03 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json --require PASS &amp;&amp; { kubectl diff -k k8s/qwen-canary &gt; /tmp/qwen-canary.diff; rc=$?; test "$rc" -eq 0 -o "$rc" -eq 1; }`

### 51-03-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-03 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-03-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-K3S-ROLLOUT.json --gate-set k3s-rollout`

### 51-04-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-04 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-K3S-ROLLOUT.json --gate-set k3s-rollout &amp;&amp; ssh -n atius-srv-1 'cd /home/ubuntu/GitHub/containers/router-ai-atius &amp;&amp; omni srv1-ops resources run builds -- go test -race ./service/embeddinggovernor ./service/modelcatalog ./relay -run "Pipeline|Governor|Embedding|Catalog|Rerank" -count=3 &amp;&amp; test -z "$(git diff --cached --name-only)"'`

### 51-04-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-04 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-K3S-ROLLOUT.json --gate-set k3s-rollout &amp;&amp; python3 -c "import json; p='.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-ROUTER-LIFECYCLE.json'; d=json.load(open(p)); assert d['source_commit']['status']=='PASS'; assert d['live_activation']['status']=='PENDING'"`

### 51-04-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-04 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-04-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py validate --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-ROUTER-LIFECYCLE.json --gate-set router-live`

### 51-05-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-05 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qdrant_qwen_canary.py -v &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py dry-run --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --all-corpora --include-dual-index`

### 51-05-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-05 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py preflight --read-only --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --tool-image-evidence .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-QDRANT-TOOL-IMAGE.json --export-aliases .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-QDRANT-ALIAS-EXPORT.json`

### 51-05-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-05 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-05-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify --evidence .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-QDRANT-REINDEX.json --require-idempotent-replay --require-dual-index-sources gbrain,obsidian,graphify --require-incumbent-unchanged`

### 51-06-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-06 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-06-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-06-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; d=json.load(open('.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-ROUTER-LIFECYCLE.json')); assert d['live_activation']['status']=='PASS'; assert d['active_router_sha']==d['source_commit']['after_sha']" &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_smoke.py -v`

### 51-06-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-06 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-06-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-06-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "import json; d=json.load(open('.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-ROUTER-LIFECYCLE.json')); assert d['live_activation']['status']=='PASS'; assert d['active_router_sha']==d['source_commit']['after_sha']" &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-smoke.py verify-report --report .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-FUNCTIONAL-SMOKE.json --require-all`

### 51-07-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-07 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_evaluate_rag_quality.py -v &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py validate-fixtures --corpus scripts/embeddings-bench/fixtures/qwen3-corpus.jsonl --qrels scripts/embeddings-bench/fixtures/qwen3-qrels.json --freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-EVAL-FREEZE.json`

### 51-07-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-07 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py review --qrels scripts/embeddings-bench/fixtures/qwen3-qrels.json --freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-EVAL-FREEZE.json --assert-no-results`

### 51-07-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-07 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-07-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/evaluate-rag-quality.py verify-report --report .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-QUALITY-CAPACITY-EVAL.json --freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-EVAL-FREEZE.json --min-rounds 5 --max-cpu-ratio 1.05 --require-no-regression`

### 51-08-01

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-08 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-08-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-08-GATE-READBACK.json --require PASS &amp;&amp; python3 -m unittest scripts/embeddings-bench/tests/test_qwen_canary_soak.py -v &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-image --evidence .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-SOAK-TOOL-IMAGE.json --job k8s/qwen-canary/qwen-soak-job.yaml --require-arm64 --require-digest-pin --require-cpu-millicores 500`

### 51-08-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-08 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-08-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-08-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-dispatch --manifest .planning/async-jobs/phase-51-qwen-soak.json --job k8s/qwen-canary/qwen-soak-job.yaml --require-original-job-uid --require-single-job --require-dual-index-suspended --require-zero-active-before-dispatch --require-runtime-pods 4 --require-tool-pods 1 --require-total-cpu-millicores 2500 --require-status running`

### 51-09-01

`test -f .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-08-SUMMARY.md &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-soak.py verify-report --report .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-SOAK-EVIDENCE.json --contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --min-hours 72 --require-original-job --require-continuous --require-dual-index-suspended &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-09 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py preflight-rollback --alias-export .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-QDRANT-ALIAS-EXPORT.json --soak .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-SOAK-EVIDENCE.json --require-current-hashes --require-gte-smoke-command`

### 51-09-02

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-09 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json --require PASS &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-rollback --evidence .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-ROLLBACK-DRILL.json --require-no-reindex --require-gte-smoke &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-dual-index-reconciliation --evidence .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-DUAL-INDEX-RECONCILIATION.json --require-sources gbrain,obsidian,graphify --require-no-lost-writes --require-no-duplicate-writes --require-idempotent-replay --require-cronjob-restored &amp;&amp; python3 -c "import json; d=json.load(open('.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-KNOWLEDGE-CLOSEOUT.json')); assert d['obsidian_http']['readback']=='PASS'; assert d['gbrain_http']['readback']=='PASS'; assert d['redaction']=='PASS'"`

### 51-09-03

`python3 scripts/embeddings-bench/qwen-canary-inventory.py refresh-lineage --plan-id 51-09 --inventory .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-W0-INVENTORY.json --baseline-contract .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-BASELINE-CONTRACT.json --gte-baseline-freeze .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-GTE-BASELINE-FREEZE.json --gate .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-WAVE0-GATE.json --output .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json &amp;&amp; python3 scripts/embeddings-bench/qwen-canary-inventory.py assert-lineage --readback .planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-09-GATE-READBACK.json --require PASS &amp;&amp; python3 -c "from pathlib import Path; s=Path('.planning/phases/51-qwen3-embedding-e-rerank-podman-para-k3s/51-PROMOTION-DECISION.md').read_text(); assert 'PROMOTION_EXECUTED: false' in s; assert any(x in s for x in ('approved-for-separate-promotion-change','rejected','defer'))" &amp;&amp; python3 scripts/embeddings-bench/qdrant-qwen-canary.py verify-current-aliases --require-gte-titular --require-no-promotion`

## Manual Gates

- 51-03-02: first live `qwen-canary` apply.
- 51-04-02: exact router activation.
- 51-05-02: Qdrant creation/reindex.
- 51-07-02: frozen qrels.
- 51-09-01: post-soak alias drill.
- 51-09-03: explicit decision with `PROMOTION_EXECUTED: false`.

## Async Closure

51-08-02 is the final Plan 08 task and returns literal `external_job_waiting`.
The execute-phase core may close `51-08-SUMMARY.md` only after the manifest's
literal `verification_command` reconciles the original Job UID without
redispatch, writes and verifies `51-SOAK-EVIDENCE.json` for at least 72
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
