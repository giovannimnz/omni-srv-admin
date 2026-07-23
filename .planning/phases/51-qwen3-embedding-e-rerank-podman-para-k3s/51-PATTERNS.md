# Phase 51: Qwen3 Embedding e Rerank Podman para k3s - Pattern Map

**Mapped:** 2026-07-23
**Files/responsibilities analyzed:** 25
**Analogs found:** 16 / 25
**Scope:** current `omni-srv-admin` checkout plus explicitly remote router paths

> Worktree caveat: the strongest local analogs are currently modified or
> untracked (`tei-gte*.yaml`, `k8s/embeddings-bench/`, `services/`,
> `scripts/embeddings-bench/`, the runbook, inventory and router guards).
> Preserve those user changes. Treat the excerpts below as the current working
> contract, not as proof that the same content exists at `HEAD`.

## File Classification

| New/Modified File or Responsibility | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `k8s/qwen-canary/namespace-resources.yaml` | config | request-response / scheduling | `k8s/embeddings-bench/base.yaml` | exact |
| `k8s/qwen-canary/tei-qwen3-embedding.yaml` | config | request-response / streaming metrics / file-I/O cache | `k8s/ebeddings-local/tei-gte.yaml`; `k8s/embeddings-bench/tei-qwen-onnx-int8.yaml` | composite exact-role |
| `k8s/qwen-canary/qwen3-reranker.yaml` | config | request-response / streaming metrics / file-I/O cache | `k8s/ebeddings-local/tei-gte-reranker.yaml` | exact-role |
| `k8s/qwen-canary/network-policy.yaml` | config | request-response / network policy | none | no analog |
| `k8s/qwen-canary/qdrant-seed-jobs.yaml` | config / migration | batch / CRUD | none | no analog |
| `k8s/qwen-canary/kustomization.yaml` | config | batch / transform | `k8s/embeddings-bench/kustomization.yaml` | exact |
| `services/qwen-reranker-onnx/server.mjs` | service | request-response / queued event-driven | same file | exact, harden |
| `services/qwen-reranker-onnx/package.json` | config | build/runtime resolution | same file | exact, extend |
| `services/qwen-reranker-onnx/package-lock.json` | config | build/runtime resolution | none in this service | no analog |
| `services/qwen-reranker-onnx/Containerfile` | config | file-I/O / build | `modules/fork-sync/projects/atius-router-docs/Dockerfile.template` | weak role-match |
| `services/qwen-reranker-onnx/server.test.mjs` (probable name) | test | request-response / event-driven | none for this service | no analog |
| `scripts/embeddings-bench/compare-embeddings.py` | utility | batch / transform / remote metrics | same file | exact, extend |
| `scripts/embeddings-bench/benchmark.py` | utility | batch / streaming metrics / transform | same file | exact, extend |
| `scripts/embeddings-bench/evaluate-rag-quality.py` | utility | batch / CRUD / transform | `compare-embeddings.py` | role-match |
| `scripts/embeddings-bench/qwen-canary-smoke.py` | utility / test | request-response / event-driven | `scripts/reranker-smoke.py`; `compare-embeddings.py` | role-match |
| `scripts/embeddings-bench/qwen-canary-soak.py` | utility / test | streaming / batch / event-driven | `benchmark.py`; `canary-control.sh` | role-match |
| Frozen PT-BR/code corpus and qrels under `scripts/embeddings-bench/` (final names TBD) | test fixture | file-I/O / batch | inline deterministic samples in `compare-embeddings.py` | weak role-match |
| `scripts/reranker-smoke.py` | utility / test | request-response | same file | exact, extend |
| `docs/operations/local-ai-embeddings.md` | documentation | request-response / operational runbook | same file | exact, extend |
| `inventory/hosts/horistic-srv.yaml` | config / inventory | CRUD | same file | exact, extend |
| `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` | config / guard documentation | event-driven sync | same file | exact, extend |
| Owner-host `service/embeddinggovernor/` | service | event-driven / request-response | remote current implementation; only guard paths are local | remote/no code analog |
| Owner-host `relay/embedding_handler.go` | controller | request-response | remote current implementation; only guard paths are local | remote/no code analog |
| Owner-host `relay/rerank_handler.go` | controller | request-response | remote current implementation; only guard paths are local | remote/no code analog |
| Owner-host `service/modelcatalog/` | service / model | CRUD / request-response | remote current implementation; only guard paths are local | remote/no code analog |

## Pattern Assignments

### `k8s/qwen-canary/namespace-resources.yaml`

**Primary analog:** `k8s/embeddings-bench/base.yaml`

Copy the dedicated namespace, strict per-pod CPU unit and explicit quota shape
from lines 1-43. Rename the namespace and size the quota for four runtime pods
plus any admitted init container/Job:

```yaml
# k8s/embeddings-bench/base.yaml:1-43
apiVersion: v1
kind: Namespace
metadata:
  name: embeddings-bench
  labels:
    app.kubernetes.io/part-of: local-ai-embeddings
    atius.com/environment: benchmark
---
apiVersion: v1
kind: LimitRange
metadata:
  name: pod-500m-strict
spec:
  limits:
    - type: Container
      default:
        cpu: 500m
      defaultRequest:
        cpu: 500m
    - type: Pod
      max:
        cpu: 500m
---
apiVersion: v1
kind: ResourceQuota
spec:
  hard:
    pods: "1"
    requests.cpu: 500m
    limits.cpu: 500m
```

Do not copy the one-pod quota values. Phase 51 requires two embedding pods and,
after warmup, two reranker pods. If a pod gains an init container, Kubernetes
quota/admission math still has to be rendered and checked explicitly.

### `k8s/qwen-canary/tei-qwen3-embedding.yaml`

**Primary analogs:** `k8s/ebeddings-local/tei-gte.yaml` for labels, scheduling,
cache, probes and the 500m unit; `k8s/embeddings-bench/tei-qwen-onnx-int8.yaml`
for pinned model-fetch integrity.

Copy the node placement and resource/probe structure:

```yaml
# k8s/ebeddings-local/tei-gte.yaml:81-87,141-180
nodeSelector:
  kubernetes.io/hostname: horistic-srv
tolerations:
  - key: atius.com/manual-only
    operator: Equal
    value: "true"
    effect: NoSchedule
# ...
resources:
  requests:
    cpu: 500m
  limits:
    cpu: 500m
startupProbe:
  httpGet:
    path: /health
    port: http
  failureThreshold: 90
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health
    port: http
securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

Copy the download-to-`.partial`, SHA-256 check and atomic rename pattern, but
substitute the LOCKED `janni-t` revision/hash:

```yaml
# k8s/embeddings-bench/tei-qwen-onnx-int8.yaml:55-70
MODEL_DIR=/cache/qwen-onnx-int8
REVISION=c25a394dd583836952667c12f008335071b3f43d
MODEL_PATH="${MODEL_DIR}/onnx/model.onnx"
if ! ([ -f "${MODEL_PATH}" ] && echo "${MODEL_SHA256}  ${MODEL_PATH}" | sha256sum -c -); then
  curl --fail --location --retry 4 --output "${MODEL_PATH}.partial" \
    "${BASE_URL}/onnx/model_int8.onnx?download=true"
  echo "${MODEL_SHA256}  ${MODEL_PATH}.partial" | sha256sum -c -
  mv "${MODEL_PATH}.partial" "${MODEL_PATH}"
fi
```

Required divergences from both analogs:

- `replicas: 2`, normal pod networking, Service + private NodePort;
- no `hostNetwork`, no fixed pod-IP `--hostname`, and no probe `host`;
- model `janni-t/qwen3-embedding-0.6b-int8-tei-onnx`;
- pinned revision `8fe0c238c7c48016d28e750413ca492024be3ddf`;
- `--pooling mean`, 1024 dimensions and alias
  `embedding-qwen3-0.6b-int8-1024-v1`;
- digest-pin the TEI image only after ARM64 inspection.

The experimental manifest is specifically not a literal template: lines 12-18
select a different artifact, line 41 enables `hostNetwork`, lines 96-97 use
`last-token`, and lines 107/131/139 bind probes/server to the node address.

### `k8s/qwen-canary/qwen3-reranker.yaml`

**Analog:** `k8s/ebeddings-local/tei-gte-reranker.yaml`

Copy the private NodePort, HPA behavior and PDB structure:

```yaml
# k8s/ebeddings-local/tei-gte-reranker.yaml:189-209
apiVersion: v1
kind: Service
spec:
  type: NodePort
  externalTrafficPolicy: Local
  selector:
    app.kubernetes.io/name: tei-gte-reranker
  ports:
    - name: http
      port: 80
      targetPort: http
      nodePort: 31216
```

```yaml
# k8s/ebeddings-local/tei-gte-reranker.yaml:211-263
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 4
  behavior:
    scaleUp:
      policies:
        - type: Pods
          value: 1
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
---
apiVersion: policy/v1
kind: PodDisruptionBudget
spec:
  minAvailable: 1
```

Keep HPA omitted/disabled during the one-pod memory warmup and fixed two-pod
integrated test. Only stage the 2-4 HPA after measured RSS/startup results.
Copy the 500m resource unit and probes from lines 148-183, but run the dedicated
Node service and its `/health`, not TEI arguments. Resolve a free NodePort and
prove private success plus public/unrelated-pod failure.

### `k8s/qwen-canary/network-policy.yaml`

**Analog:** none in this checkout.

Use `51-RESEARCH.md` as the design source. The file is conditional: create/apply
default-deny plus minimum DNS/router/Qdrant/model-fetch flows only after a live
test proves the installed CNI enforces `NetworkPolicy`. An accepted YAML object
without positive and negative traffic tests is not evidence.

### `k8s/qwen-canary/qdrant-seed-jobs.yaml`

**Analog:** none; no Qdrant code or manifest exists in the searched checkout.

Implement an idempotent batch Job only after live version/auth/capacity
inventory. Required sequence:

1. inspect existing collection and alias state without mutation;
2. create physical 1024d/Cosine collections only when absent;
3. reject an existing collection whose dimension/signature differs;
4. export alias state, then atomically bind canary aliases;
5. keep GTE 768d collections and aliases untouched;
6. log schema/count/digests only, never credentials, raw vectors or corpus.

Locked physical names are `gbrain_qwen3_1024_v1`,
`obsidian_qwen3_1024_v1` and `graphify_qwen3_1024_v1`.

### `k8s/qwen-canary/kustomization.yaml`

**Analog:** `k8s/embeddings-bench/kustomization.yaml:1-12`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - base.yaml
  - tei-qwen-onnx-int8.yaml
```

List every phase manifest explicitly. `network-policy.yaml` must only be in the
rendered set when the CNI gate is satisfied; do not make a non-enforced policy
look like isolation.

### `services/qwen-reranker-onnx/server.mjs`

**Analog:** the existing prototype in the same file.

Preserve its model API and numerically stable yes/no softmax:

```javascript
// services/qwen-reranker-onnx/server.mjs:1-14,33-38
import { createServer } from "node:http";
import { AutoModelForCausalLM, AutoTokenizer, env } from "@huggingface/transformers";

const MODEL_ID = process.env.MODEL_ID || "onnx-community/Qwen3-Reranker-0.6B-ONNX";
const MODEL_DTYPE = process.env.MODEL_DTYPE || "q8";
const MAX_DOCUMENTS = Number(process.env.MAX_DOCUMENTS || 20);

function probability(yes, no) {
  const max = Math.max(yes, no);
  const yesExp = Math.exp(yes - max);
  const noExp = Math.exp(no - max);
  return yesExp / (yesExp + noExp);
}
```

Preserve batching and descending native results:

```javascript
// services/qwen-reranker-onnx/server.mjs:57-67
async function rerank(query, documents) {
  const results = [];
  for (let offset = 0; offset < documents.length; offset += BATCH_SIZE) {
    const batchDocuments = documents.slice(offset, offset + BATCH_SIZE);
    const scores = await scoreBatch(query, batchDocuments);
    scores.forEach((score, index) => {
      results.push({ index: offset + index, score });
    });
  }
  return results.sort((left, right) => right.score - left.score);
}
```

Replace the prototype's unsafe/unfinished seams:

- lines 13-14 permit runtime remote model downloads; production must consume
  the pinned cached revision/hash;
- line 25 is an unbounded promise queue;
- lines 91-100 do not stop reading after rejecting an oversized body;
- line 107 exposes `/v1/rerank`; the worker contract must expose private
  `/rerank` only, with public conversion owned by the router;
- lines 113-120 lack query/document byte, character and token bounds;
- lines 124-126 collapse model/internal failures into HTTP 400;
- lines 129-136 lack graceful shutdown/drain and startup failure exit policy.

Tests must cover prompt/token IDs, finite `[0,1]` scores, ordering, malformed and
oversized bodies, bounded queue, timeout/cancel, exact error classes and
SIGTERM drain.

### `package.json`, `package-lock.json`, `Containerfile`, `server.test.mjs`

Keep the exact dependency pin from
`services/qwen-reranker-onnx/package.json:1-10`:

```json
{
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "dependencies": {
    "@huggingface/transformers": "4.2.0"
  }
}
```

Add a Node test-runner script and generate a lockfile from the exact pin. There
is no same-service lockfile or test analog. The only Node container analog,
`modules/fork-sync/projects/atius-router-docs/Dockerfile.template`, is a
documentation build and is not suitable beyond its multi-stage/non-root idea.
The new Containerfile must use digest-pinned ARM64-capable bases, install from
the lockfile, run non-root, avoid runtime package/model downloads and expose
only the service port.

### Benchmark, smoke, quality and soak scripts

**Primary analogs:** `scripts/embeddings-bench/compare-embeddings.py`,
`scripts/embeddings-bench/benchmark.py`, `scripts/reranker-smoke.py` and
`scripts/embeddings-bench/canary-control.sh`.

Copy redacted vector validation:

```python
# scripts/embeddings-bench/benchmark.py:301-320
def vector_summary(vectors, expected_dimensions):
    norms = []
    hashes = []
    for vector in vectors:
        if len(vector) != expected_dimensions:
            raise RuntimeError(
                f"expected {expected_dimensions} dimensions, received {len(vector)}"
            )
        if not all(math.isfinite(value) for value in vector):
            raise RuntimeError("embedding contains NaN or infinity")
        norms.append(math.sqrt(sum(value * value for value in vector)))
        # Save only a digest, not the vector.
    return {
        "norm_min": min(norms),
        "norm_max": max(norms),
        "first_vector_sha256": hashes[0],
    }
```

Copy warmup exclusion, `try/finally` metric cleanup and CPU/RSS reporting from
`benchmark.py:375-423` and `424-499`. Extend it to token-normalized paired
GTE/Qwen collection; do not compare only words or best runs.

Copy the single/batch shape and cosine check from
`compare-embeddings.py:58-73`, but enforce dimension `1024` and cosine
`>= 0.9999`:

```python
single = post_embed(url, [text], dimensions)[0]
batch = post_embed(url, [text, "..."], dimensions)[0]
norms = [math.sqrt(sum(value * value for value in vector))
         for vector in [single, batch]]
return {
    "dimension": len(single),
    "norm_min": min(norms),
    "norm_max": max(norms),
    "single_batch_cosine": cosine(single, batch),
}
```

Copy secret handling and native/public contract separation from
`scripts/reranker-smoke.py:36-67` and redacted output from lines 87-112.
Extend the script for the Qwen alias and native ONNX response, preserving the
rule that tokens are read from environment and never printed.

Copy safe deployment allowlisting and dry-run pattern from
`canary-control.sh:33-86`; never interpolate an arbitrary deployment name.

Per target:

- `compare-embeddings.py`: keep paired resource profiles; freeze Qwen to 1024d.
- `benchmark.py`: become/reuse the token-normalized CPU/RSS/latency collector.
- `evaluate-rag-quality.py`: load frozen corpus/qrels, compute paired Recall@20
  and nDCG@10 globally and for PT-BR technical/code slices, and fail on
  inferiority. Do not mutate qrels after seeing results.
- `qwen-canary-smoke.py`: cover health, batch 1/4, norm, dimensions, native and
  public rerank, three-cycle/two-slot queueing, timeout, cancel and TTL.
- `qwen-canary-soak.py`: sample events/restarts/OOM/queue/starvation and a GTE
  baseline for 72 hours; write aggregate/redacted evidence.
- frozen fixtures: stable logical IDs and equivalent chunking; no production
  corpus contents in logs.
- `scripts/reranker-smoke.py`: preserve the existing GTE path and add Qwen as an
  explicit model/backend selection rather than replacing the titular default.

### `docs/operations/local-ai-embeddings.md`

**Analog:** same runbook.

Preserve the boundary and conversion contract from lines 31 and 42-46:

```text
TEI stays internal. Do not create an Ingress, Apache vhost, Cloudflare record,
public NodePort, or any other direct public route to TEI.

The Go router converts query/documents/top_n into the native query/texts
contract and maps score back to results[].relevance_score.
```

Preserve immutable embedding identity and reindexing rules from lines 122-130,
the 500m pod unit from lines 184-195, redacted evidence from lines 274 and
secret hygiene from lines 301-305. Add a separate Qwen canary section; do not
rewrite GTE 768d/CLS as Qwen 1024d/mean. Document warmup, two-slot lifecycle,
collection aliases, quality/capacity gates, 72h soak, promotion checkpoint and
atomic rollback.

### `inventory/hosts/horistic-srv.yaml`

**Analog:** existing `tei-gte` and `tei-gte-reranker` app entries.

Copy the inventory shape:

```yaml
# inventory/hosts/horistic-srv.yaml:67-89
- id: tei-gte-reranker
  runtime: k3s
  namespace: ebeddings-local
  service: tei-gte-reranker
  model: Alibaba-NLP/gte-multilingual-reranker-base
  revision: 8215cf04918ba6f7b6a62bb44238ce2953d8831c
  listen: 10.21.1.21:31216
  public_alias: reranker-gte-multilingual-v1
  router_upstream: http://10.21.1.21:31216
  replicas_min: 2
  replicas_max: 4
  cpu_per_pod: 500m
  managed_by: "omni-srv-admin"
  update_policy: "plan-first"
```

Add separate Qwen embedding/reranker entries only after NodePorts, pins, memory
and replica states are proven. Keep `platform.arch: arm64`, worker node/IP and
GTE entries unchanged.

### `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`

**Analog:** existing protected local-AI guard.

Extend, do not replace, lines 25-26:

```text
Local TEI embeddings must remain governed inside the Go router through
service/embeddinggovernor/ and relay/embedding_handler.go.

Preserve the /v1/rerank to /rerank conversion and acquisition of the same
Go-native governor from relay/rerank_handler.go.
```

Add Qwen aliases, pipeline lease state-machine invariants, 1024d isolation,
exact-once terminal release and tests to the protected paths/checks. Preserve
the owner-host check location and command pattern at lines 123-135.

### Owner-host router responsibilities

**Local evidence only:** `UPSTREAM-SYNC-GUARDS.md:40-57,123-135` names protected
paths and focused Go tests. No Go source from
`/home/ubuntu/GitHub/containers/router-ai-atius` exists in this checkout.

The first router task must inventory the owner host read-only and record exact
files, symbols, tests, process/replica topology and current `Acquire`/release
paths before planning edits. Expected responsibilities:

- `service/embeddinggovernor/`: pipeline state machine, exactly two global
  leases, rerank-continuation priority, TTL/cancel and exact-once release;
- `relay/embedding_handler.go`: retain call-scoped admission for standalone
  embeddings and attach/start pipeline leases only for the pipeline contract;
- `relay/rerank_handler.go`: continue the same `pipeline_id`, prioritize
  pending rerank and terminate the lease on every outcome;
- `service/modelcatalog/`: Qwen aliases are canary-only allowlisted additions;
  GTE aliases remain titular.

If more than one router replica or restart domain is active, in-process state
is an anti-pattern because it cannot enforce two global slots. Prove
single-replica topology or select a shared atomic store before traffic.

## Shared Patterns

### Private edge and authentication

**Source:** `docs/operations/local-ai-embeddings.md:29-46`

Apply to both manifests, router handlers, smoke scripts and docs. Only the
router owns Bearer auth/public `/v1`; workers expose private native endpoints.
NodePort means private reachability, not public exposure, and requires positive
and negative network evidence.

### Resource and scheduling contract

**Sources:** `AGENTS.md` CPU/K3s rules;
`k8s/ebeddings-local/tei-gte-reranker.yaml:148-178`;
`modules/srv1-ops/configs/resource-governor.env:49-62`

Every normal runtime pod requests and limits `500m`. The k3s quota controls
scheduling; the Go inference queue controls active work; the host `builds`
profile controls builds. These are complementary controls and must not be
substituted for one another.

### Model and vector identity

**Source:** `docs/operations/local-ai-embeddings.md:122-130`

Apply to manifests, Qdrant seed, scripts, inventory, router catalog and docs:

```text
model + revision/digest + quantization + dimension + normalization + chunking
```

For Qwen also record pooling `mean`, tokenizer revision, model file SHA-256 and
query instruction. Reject cross-signature writes. Never pad 768d to 1024d.

### Error handling and evidence hygiene

**Sources:** `benchmark.py:246-268,403-423`;
`reranker-smoke.py:75-112`; `local-ai-embeddings.md:274,301-305`

Bound requests, classify HTTP/timeout/invalid-response/internal failures, and
always stop metric samplers in `finally`. Evidence contains aggregate
dimensions/norms/hashes, timing, CPU/RSS, queue transitions and redacted
errors—not tokens, headers, full vectors or corpus text.

### Validation pattern

**Sources:** `51-VALIDATION.md`; router guard checks at
`UPSTREAM-SYNC-GUARDS.md:123-135`

Use focused Go race tests for lease transitions and Node tests for the
reranker. Render with `kubectl kustomize`, then server-side dry-run when cluster
access exists. Heavy build/test work must run through the `builds` profile.

## Anti-Patterns and Conflicts

| Conflict | Evidence | Required treatment |
|---|---|---|
| `hostNetwork` with replicated Qwen | GTE embedding `tei-gte.yaml:88`; experimental Qwen `tei-qwen-onnx-int8.yaml:41` | Do not copy; use normal pod network and private NodePort |
| Wrong Qwen artifact | experimental manifest `:12-18` uses `onnx-community/Qwen3-Embedding-0.6B-ONNX` | Use LOCKED `janni-t/...int8-tei-onnx` revision/hash |
| Wrong pooling | experimental manifest `:96-97` uses `last-token` | Phase contract is `mean`; assert it in manifest and smoke |
| Wrong/flexible dimension | `compare-embeddings.py:204-213` tests 1024 and 768 | Canary production contract is fixed 1024d |
| Unpinned runtime | GTE embedding `tei-gte.yaml:58-59,104,109-110` uses `main`/latest | Pin image digest and model revision after ARM64 proof |
| Local queue without bounds/cancel | `server.mjs:25,121-123` | Bounded admission, timeout/cancel, graceful drain |
| Worker exposes public contract | `server.mjs:107` accepts `/v1/rerank` | Worker exposes `/rerank`; router owns `/v1/rerank` conversion |
| Shared RWO cache with replicas | GTE PVC is `ReadWriteOnce` (`tei-gte.yaml:37-42`) | Prove storage semantics; do not assume one RWO PVC safely supports independently scheduled replicas |
| Local lease state with multiple router replicas | router source/topology unavailable | Prove one replica or use shared atomic state |
| Quota treated as governor | namespace manifests vs router governor contract | Keep scheduling quota and inference admission distinct |
| HPA before warmup | GTE HPA `tei-gte-reranker.yaml:211-248` | Qwen warmup at one fixed pod, then two fixed; HPA only after sizing |
| Alias/dimension mixing | current GTE contract `local-ai-embeddings.md:124-130` | Separate Qwen aliases/collections; no GTE mutation |
| Secrets/raw vectors in evidence | runbook `:274,301-305` | Save only redacted aggregate evidence |
| Treating remote filenames as confirmed | guards name directories, not current symbols | Owner-host read-only inventory is a Wave 0 prerequisite |

## No Analog Found

| File/Responsibility | Reason and planner fallback |
|---|---|
| `k8s/qwen-canary/network-policy.yaml` | No `NetworkPolicy` manifest exists; use research guidance plus live CNI enforcement proof |
| `k8s/qwen-canary/qdrant-seed-jobs.yaml` | No Qdrant implementation exists; inventory live API/version/auth first |
| `services/qwen-reranker-onnx/package-lock.json` | Generate from exact package pin; do not borrow an unrelated lock |
| `services/qwen-reranker-onnx/server.test.mjs` | No Node test suite for this service; derive cases from `51-VALIDATION.md` |
| Frozen corpus/qrels files | Existing scripts only contain inline samples; define immutable fixture format/version |
| Owner-host governor source | Not present in checkout; only protected path names are available |
| Owner-host embedding handler | Not present in checkout |
| Owner-host rerank handler | Not present in checkout |
| Owner-host model catalog | Not present in checkout |

## Metadata

**Graphify queries:** `qwen`, `embeddinggovernor`, `NodePort`

**Graphify result:** Qwen located `compare-embeddings.py`, spike 006 and the
paired benchmark; no graph nodes for governor or NodePort. All candidates were
confirmed with `rg` and numbered file reads.

**Analog search scope:** `k8s/`, `services/`, `scripts/`,
`docs/operations/`, `inventory/hosts/`, `modules/fork-sync/projects/atius-router/`,
`modules/srv1-ops/configs/`

**Strong analog families:** 5 (GTE embedding, GTE reranker, Qwen benchmark
manifests, Node/ONNX prototype, Python benchmark/smoke harness)

**Pattern extraction date:** 2026-07-23

## PATTERN MAPPING COMPLETE

**Phase:** 51 - Qwen3 Embedding e Rerank Podman para k3s
**Files/responsibilities classified:** 25
**Analogs found:** 16 / 25

### Coverage

- Exact/composite analog: 10
- Role-match/weak analog: 6
- No local code analog: 9

### Key Patterns Identified

- `tei-gte-reranker.yaml` is the closest Service/NodePort/probe/HPA/PDB
  template, but Qwen must stage warmup and fixed replicas before HPA.
- `base.yaml` supplies namespace/LimitRange/ResourceQuota structure with the
  canonical 500m pod unit.
- `server.mjs` already contains Qwen prompt/scoring/batching, but needs bounded
  queueing, cancellation, error classes, private-only routing and shutdown.
- `benchmark.py`, `compare-embeddings.py` and `reranker-smoke.py` supply
  redacted shape/norm/cosine/resource and native/public contract patterns.
- Router implementation remains an explicit owner-host gap; guard paths are
  known, current symbols/topology are not.

### Ready for Planning

The planner can reference the concrete excerpts above. It must keep GTE
titular, preserve 768d/1024d isolation, inventory remote router/Qdrant/network
state in Wave 0 and treat promotion as a manual gate after the 72-hour soak.
