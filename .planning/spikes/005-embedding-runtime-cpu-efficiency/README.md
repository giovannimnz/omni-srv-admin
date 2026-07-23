---
spike: 005
name: embedding-runtime-cpu-efficiency
type: comparison
validates: "Qwen3-Embedding-0.6B at 1024 dimensions can run quantized to 8-bit in k3s under a strict 500m CPU pod ceiling with lower CPU cost than the current GTE service"
verdict: INVALIDATED
related: [41]
tags: [embeddings, qwen3, int8, gguf, onnx, tei, llama-cpp, ollama, k3s, arm64, cpu]
---

# Spike 005: Embedding Runtime CPU Efficiency

## What This Validates

Given the ARM64 `horistic-srv` k3s worker and the live
`Alibaba-NLP/gte-multilingual-base` TEI service, when Qwen3-Embedding-0.6B
variants are measured at 1024 output dimensions under the same `500m` CPU
ceiling, then ATIUS can choose the runtime/quantization combination that uses
the least total processor while keeping peak CPU, latency, memory and vector
correctness within explicit gates.

The existing `ebeddings-local/tei-gte` Deployment is a read-only baseline. It
must remain running and must not be edited, restarted, scaled or routed during
this spike.

## Research Outcome

### Live constraints

- `horistic-srv` is ARM64 with 4 Neoverse N1 cores, 23 GiB RAM and no swap.
- The node exposes ARM `asimd` and `asimddp`, but not native ARM BF16.
- The current GTE pod requests and limits `500m` CPU and presently serves 768
  dimensions through TEI.
- Historical concurrency above the governor produced high host load and memory
  pressure. Every canary therefore remains at one inference thread and one pod.
- Qwen3-Embedding-0.6B has native 1024-dimensional output. No post-hoc padding,
  projection or mixed 768/1024 index is allowed.

### Pinned model artifacts

| Artifact | Revision | Quantization | Size |
|---|---|---:|---:|
| `Qwen/Qwen3-Embedding-0.6B` | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | BF16 upstream; FP32 CPU control | 1,191,586,416 bytes |
| `Qwen/Qwen3-Embedding-0.6B-GGUF` | `370f27d7550e0def9b39c1f16d3fbaa13aa67728` | `Q8_0` | 639,150,592 bytes |
| `onnx-community/Qwen3-Embedding-0.6B-ONNX` | `c25a394dd583836952667c12f008335071b3f43d` | signed INT8 or Q8/UINT8 | 613,527,539 / 613,527,631 bytes |
| `qwen3-embedding:0.6b-q8_0` | model digest prefix `ac6da0dfba84` | `Q8_0` | 639 MB |

The GGUF and ONNX payloads are downloaded from pinned revisions. Their large
model files are checked against pinned SHA-256 values before startup.

### Runtime triage

| Runtime | Live treatment | Reason |
|---|---|---|
| TEI + current GTE FP32 | Baseline | Existing production path and 768-dimension control |
| TEI + official Qwen Safetensors FP32 | Rejected live | OOMKilled during Candle warm-up with an 8 GiB limit |
| llama.cpp + official GGUF Q8_0 | Valid | Lean native ARM64 server; strongest balanced Qwen candidate |
| llama.cpp + GGUF Q8_0 + Q8_0 KV | Valid but CPU-losing | Saves memory while increasing CPU in every measured profile |
| Ollama + Q8_0 model + Q8_0 KV setting | Valid by workload | Best valid Qwen for short input, but degrades sharply on long context |
| TEI + ONNX dynamic INT8 | Rejected live | OOMKilled during warm-up at both 6 GiB and 8 GiB |
| ONNX Runtime + signed INT8/Q8 | Invalidated | Raw CPU was excellent, but batch and semantic consistency failed |
| Transformers.js + Q8 | Invalidated | Intended artifact runtime reproduced the ONNX Q8 correctness failure |
| Infinity + ONNX | Eliminated from initial live run | Official `latest-cpu` image advertises amd64 only; custom build is not justified before TEI/ONNX is tested |
| vLLM CPU ARM64 | Conditional only | ARM64 exists, but the runtime is much heavier and this N1 lacks native BF16 |
| Transformers + bitsandbytes/torchao | Eliminated from initial live run | Python/PyTorch overhead and ARM CPU INT8 uncertainty conflict with the minimum-CPU goal |

TEI officially supports Qwen3 and an ARM64 CPU image, but its CLI exposes only
`float16`/`float32` dtype forcing; GGUF Q8_0 is therefore not a TEI artifact.
llama.cpp publishes a multi-architecture ARM64 server image and directly loads
GGUF. Ollama's official Qwen tag is a 596M-parameter, 639 MB Q8_0 model.

References:

- [Qwen3-Embedding-0.6B model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Official Qwen GGUF repository](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF)
- [TEI supported models and ARM64 image](https://huggingface.co/docs/text-embeddings-inference/en/supported_models)
- [TEI CLI arguments](https://huggingface.co/docs/text-embeddings-inference/en/cli_arguments)
- [llama.cpp Docker images](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)
- [Ollama Qwen3 embedding Q8_0](https://ollama.com/library/qwen3-embedding:0.6b-q8_0)
- [Ollama OpenAI compatibility](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx)
- [Qwen3 Embedding ONNX model card](https://huggingface.co/onnx-community/Qwen3-Embedding-0.6B-ONNX)
- [ONNX Runtime quantization guidance](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)

## Comparison Questions

| Variant | Given / When / Then | Main risk |
|---|---|---|
| 005a baseline | Given live GTE/TEI, when the fixed corpus runs, then establish CPU-seconds, peak CPU and latency reference without mutation | Background traffic can add noise |
| 005b ONNX INT8 | Given pinned INT8 ONNX weights, when TEI loads them on ARM64, then prove 1024 dimensions and measure dot-product CPU efficiency | Export/backend incompatibility |
| 005c llama.cpp Q8_0 | Given official GGUF, when direct llama-server runs one thread, then validate last-token pooling and minimum CPU | Pooling or endpoint semantics drift |
| 005d Q8 KV and Ollama | Given the same Q8 model, when KV type and wrapper change, then isolate cache and orchestration overhead | KV has little benefit for embeddings |
| 005e TEI Qwen FP32 | Given the official model, when TEI runs FP32, then quantify the non-quantized control cost | Expected to lose the CPU objective |

## Kubernetes Isolation Contract

- Namespace: `embeddings-bench`.
- Every Deployment is committed with `replicas: 0`.
- A `ResourceQuota` permits exactly one canary pod and at most `500m` CPU.
- Each canary requests and limits `500m`; tokenizer/inference thread count is 1.
- Models bind only to `10.21.1.21` on private benchmark ports `3215-3221`.
- No Ingress, NodePort, Cloudflare record or router alias is created.
- The shared 8 GiB PVC stores pinned model payloads; candidates run sequentially.
- Starting a candidate first scales every other benchmark Deployment to zero.

Versioned manifests live in `k8s/embeddings-bench/`. The control and benchmark
harness live in `scripts/embeddings-bench/`.

## Measurement Contract

Three profiles run after two warm-up calls:

| Profile | Shape | Default rounds | Purpose |
|---|---:|---:|---|
| interactive | batch 1, about 64 words | 8 | Peak CPU and user-facing latency |
| batch | batch 4, about 128 words each | 5 | CPU amortization and governed indexing |
| long | batch 1, about 2048 words | 3 | Long-text CPU and cache behavior |

The harness records:

- total cgroup CPU-seconds and CPU-seconds per 1,000 reported input tokens;
- sampled peak/mean millicores;
- CFS throttled seconds and throttled-period ratio;
- p50/p95/max latency and tokens per CPU-second;
- peak working set and lifetime maximum memory;
- exact dimension, finite values, L2 norm range and a non-reversible vector
  fingerprint without persisting embedding arrays.

CPU deltas and throttling now come directly from the container cgroup v2
`cpu.stat`; kubelet samples remain only for in-run memory/CPU shape. This avoids
attributing a delayed kubelet counter refresh to the request being measured.

The first cross-runtime screening uses `3/1/1` measured rounds and limits the
long profile to about 512 words. Only the two CPU finalists repeat the full
default matrix; this avoids spending several CPU-minutes on an already losing
runtime. A 2048-word Q8_0 direct sample is retained as worst-case evidence.

## Decision Rule

All three requested winners are reported:

1. **Minimum total processor:** lowest CPU-seconds per 1,000 tokens.
2. **Minimum peak processor:** lowest sampled peak millicores with no hidden
   throttling regression.
3. **Balanced CPU:** best total CPU first, breaking near-ties by peak CPU,
   p95 latency and memory.

A candidate is invalid regardless of speed if it does not return exactly 1024
finite dimensions, uses the wrong pooling contract, fails batch/single
consistency, or cannot start under the `500m`/8 GiB ceiling.

## Commands

```bash
scripts/embeddings-bench/canary-control.sh validate
scripts/embeddings-bench/canary-control.sh apply
scripts/embeddings-bench/canary-control.sh start llama-qwen-q8
scripts/embeddings-bench/canary-control.sh status
scripts/embeddings-bench/canary-control.sh stop
```

Example benchmark:

```bash
scripts/embeddings-bench/benchmark.py \
  --base-url http://10.21.1.21:3216 \
  --api openai \
  --model qwen3-embedding-0.6b-gguf-q8 \
  --expected-dimensions 1024 \
  --profile interactive \
  --namespace embeddings-bench \
  --selector app.kubernetes.io/name=llama-qwen-q8 \
  --container llama-server
```

## Results

### Valid performance results

All candidates ran sequentially under the same hard `500m` CPU limit. Values
are CPU-seconds per 1,000 input tokens; lower is better. Memory is peak working
set for the measured regime.

| Runtime / weights / KV | 64 words | batch 4 x 128 words | 512 words | Memory | Correctness |
|---|---:|---:|---:|---:|---|
| Current TEI / GTE FP32 / n/a (768d) | **12.48** | **10.31** | **11.76** | 1.40-1.45 GiB | Production baseline |
| llama.cpp / GGUF Q8_0 / F16 default (1024d) | 22.30 | 22.91 | **28.92** | 1.55 GiB | Pass |
| llama.cpp / GGUF Q8_0 / Q8_0 (1024d) | 22.95 | 25.50 | 40.66 | **1.13 GiB** | Pass |
| Ollama / GGUF Q8_0 / Q8_0, ctx 1024 (1024d) | **20.92** | **21.46** | 35.76 | 0.92-1.90 GiB | Pass |

For the valid Qwen candidates, Ollama wins the short and batch screens by
about 6-7% CPU. At 512 words, direct llama.cpp with default F16 KV wins by
19.1% CPU and 20.2% wall time. The KV-Q8 direct variant saves about 421 MiB
against F16 KV, but costs 40.6% more CPU at 512 words; it is therefore contrary
to the primary optimization objective.

Reducing Ollama `num_ctx` from 8192 to 1024 did not reduce CPU materially, but
saved about 420 MiB working set: 0.92 GiB for short input, 1.06 GiB for the
batch profile and 1.90 GiB at 973 tokens. The optimized Ollama profile therefore
uses `num_ctx=1024` and must reject or rechunk larger inputs.

The canary creates `qwen3-embedding-atius:0.6b-q8_0` from the pinned official
model with `num_ctx=1024` and `num_thread=1` in its Modelfile. Its
OpenAI-compatible `/v1/embeddings` endpoint reproduced the native API vector
fingerprint, the official-example error of 0.0078 and 20.92 CPU-seconds/1k
tokens. The router therefore does not need Ollama-native request options.

The 2048-word sample contained 3,865 Qwen tokens. Direct llama.cpp with default
KV completed in 346.9 seconds; Ollama with Q8 KV took 828.3 seconds and reached
3.57 GiB working set. Both were continuously constrained by the same `500m`
quota, so the 2.39x wall-time ratio is also the reliable processor-budget ratio
for this saturated regime. Long chunks should not be used on this host.

The original hypothesis is invalidated: even the best valid Qwen Q8 path used
about 68% more CPU than current GTE for 64-word input, and direct llama.cpp used
about 2.46x GTE CPU per token at 512 words. Qwen remains a quality/capability
upgrade candidate, not a CPU-saving replacement.

### Correctness and rejected paths

- Ollama Q8_0 returned 1024 normalized dimensions, had batch/single cosine
  approximately 1.0, and stayed within 0.0078 absolute cosine of the official
  FP32 example. Direct llama.cpp and Ollama agreed at cosine 0.9989-0.9996.
- Custom ONNX Runtime was superficially fastest: 8.10, 9.15 and 14.23
  CPU-seconds/1k tokens for the three screens, with 0.85-1.29 GiB memory.
  It is invalid: batch/single cosine fell to 0.91-0.95 and cross-runtime cosine
  fell as low as 0.64.
- Switching the ONNX payload from signed `model_int8.onnx` to the Q8/UINT8
  `model_quantized.onnx`, correcting position IDs, and running the artifact
  through Transformers.js did not repair it. The official example still
  deviated by up to 0.10-0.14 and batch/single consistency remained about
  0.92-0.94.
- TEI FP32 Qwen exceeded the 8 GiB canary memory gate. TEI ONNX INT8 also
  exceeded it with `--max-batch-tokens=8192`, but starts under the same 8 GiB
  gate when the operational input ceiling is reduced to 1024 tokens.
  Infinity's published CPU image was amd64-only. vLLM and PyTorch/bitsandbytes
  were not promoted because their runtime footprint cannot beat the surviving
  native candidates on this ARM N1 host.

### Current TEI 1.9.3 non-GGUF follow-up

The production image resolved to
`sha256:16c0a827cf79d5dc9b9ec1b0b5df7ffd165726f9bdf1daa9d4f7a355dd842f7e`
and reports TEI `1.9.3` (`f9a0643`). Its CLI exposes only `float16` and
`float32`; INT8 requires a pre-quantized ONNX artifact rather than a TEI
quantization flag.

Both Qwen canaries used that exact image, one inference pod, one thread, a hard
`500m` CPU limit, `--max-batch-tokens=1024`, and `max-client-batch-size=4`.
`max-concurrent-requests` must be at least 4 for a four-input OpenAI request;
setting it to 1 returns HTTP 429 for that batch.

| Runtime / output | CPU-s / 1k tokens, 64 words | CPU-s / 1k tokens, batch 4 x 128 | Working set | Correctness |
|---|---:|---:|---:|---|
| Current TEI / GTE FP32 / 768d | 10.80 | 10.21 | 1.42-1.44 GiB | Production baseline |
| TEI 1.9.3 / Qwen Safetensors FP16 / 1024d | 19.99 | 20.76 | 1.2-2.5 GiB cold/warm-up envelope | Pass |
| TEI 1.9.3 / Qwen Safetensors FP16 / 768d | 20.00 | Not repeated | Same model envelope | Pass |
| TEI 1.9.3 / Qwen ONNX dynamic INT8 / 1024d | 8.20 | Not promoted | 1.20 GiB | Fail |
| TEI 1.9.3 / Qwen ONNX dynamic INT8 / 768d | 8.20 | Not promoted | 1.20 GiB | Fail |

The FP16 path returned exact 1024-dimensional normalized vectors,
batch/single cosine `1.0` for all four official-example inputs and maximum
absolute score error `0.00295` against the model card. The tested community
INT8 ONNX export starts and is fast, but remains invalid: batch/single cosine
fell to `0.9307-0.9391` and maximum official-example error reached `0.1019`.

Requesting 768 instead of 1024 dimensions changed Qwen FP16 CPU by only 0.05%
in the short screen and INT8 CPU by only 0.08%. MRL truncation happens after
the transformer forward pass, so 768 saves 25% of vector transfer and index
storage but does not materially save model CPU or model memory. GTE cannot
produce 1024 dimensions; the live endpoint returns HTTP 422 when requested.

The requested HPA proposal is versioned at
`k8s/tei-qwen-fp16-hpa-2-4-proposal.yaml`: 2-4 pods at the canonical `500m`
per pod, giving `1000m` total at the minimum and `2000m` total at the maximum.
It deliberately removes `hostNetwork`, because multiple replicas cannot bind
the same host port, and proposes NodePort `31222`. The build/compile 20% CPU
guardrail does not constrain this explicitly sized container workload. It is
not applied pending a separate GTE-versus-Qwen rollout decision and retrieval
quality acceptance, not because of CPU scheduling capacity.

### Decision

1. Minimum processor overall: retain current GTE/TEI at 768 dimensions.
2. Mandatory Qwen Q8 and 1024 dimensions, variable or 512+ word chunks: use
   direct llama.cpp with GGUF Q8_0, one thread and default F16 KV.
3. Mandatory Qwen Q8, mandatory Q8 KV, and inputs below 1024 tokens: use Ollama
   with `num_thread=1`, `num_ctx=1024`, one loaded model and one parallel slot;
   reject or rechunk larger inputs.
4. Minimum memory regardless of CPU: direct llama.cpp with Q8_0 KV at about
   1.13 GiB; this is not the selected CPU-first architecture.
5. Peak CPU is a controlled tie: every candidate is capped at `500m`. Lowering
   the Kubernetes limit reduces peak but increases latency; it does not make
   Qwen consume less total work.
6. If TEI and non-GGUF Qwen are mandatory, Safetensors FP16 is the only tested
   correct path on this ARM64 node. Keep the 1024-token operational ceiling,
   use 768 or 1024 through the OpenAI `dimensions` field, and expect roughly
   twice the current GTE CPU per token. Do not promote the tested INT8 ONNX
   artifact.

Any 1024-dimensional rollout requires a new public alias, a separate vector
store/index, full reembedding and retrieval-quality acceptance before cutover.
The live `embedding-gte-v1` alias and its 768-dimensional vectors remain
unchanged.
