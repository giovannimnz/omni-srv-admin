# Phase 59: Qwen3 Embedding e Rerank Podman para k3s - Pattern Map

**Mapped:** 2026-07-23
**Scope:** cutover autorizado Qwen titular, com GTE como rollback imutável até retirement
**Files/surfaces classified:** 36
**Analog coverage:** 26 com analog local; 10 `NEW` ou `UNKNOWN`

## Authority and interpretation

Este arquivo substitui integralmente a semântica anterior do Phase 59. As autoridades para o planner são, nesta ordem:

1. `59-CONTEXT.md` e `59-RESEARCH.md`;
2. `REQUIREMENTS.md` e o `ROADMAP.md` do workstream;
3. este pattern map;
4. código e manifests existentes apenas como analogs estruturais.

`59-VALIDATION.md` foi reconciliado com este mapa e é o contrato autoritativo
de Nyquist, task gates e wave gates. A tabela abaixo registra apenas semânticas
históricas aposentadas:

| Semântica antiga | Tratamento |
|---|---|
| GTE permanece titular | removida; Qwen é o titular depois da Wave 6 |
| `PROMOTION_EXECUTED=false` como estado final | removida; não é gate nem evidência válida |
| checkpoints/prompts manuais de promoção | removidos; cada wave fecha por JSON fail-closed |
| `k8s/qwen-canary` como target | removido; usar `k8s/qwen-production/` |
| pooling `mean` pré-decidido | removido; Wave 1 escolhe por oracle A/B |
| HPA Qwen 2-4 | removido; Qwen termina com exatamente 2 embedding + 2 reranker |

Não inferir estado live de arquivos versionados. Kubernetes API, Redis, Router DB e Qdrant exigem readback independente. A autoridade Qdrant — endpoint, versão, autenticação, storage, backups, aliases e collections — está `UNKNOWN` e bloqueia qualquer mutação até ser resolvida na Wave 0.

## Mandatory implementation rules

| Rule | Pattern to apply |
|---|---|
| Edição | Usar `apply_patch` para toda alteração de source/config/docs. Não gerar source com heredoc. |
| Builds | Executar somente pelo wrapper/profile `builds`, limitado a 20% da CPU total. No router, preferir `./scripts/podman-admin.sh build`; no repo operacional, `omni srv1-ops resources run builds -- ...`. |
| k3s CPU | Cada pod gerenciado, inclusive Job, tem `requests.cpu: 500m` e `limits.cpu: 500m`. Somar todos os containers do pod dentro dos 500m. |
| Runtime | Qwen final: exatamente 2 pods embedding + 2 pods reranker. Sem HPA Qwen. O rollout interno do reranker pode progredir 1 -> 2, mas o gate da Wave 3 exige 2 + 2. |
| Jobs | Oracle, build, reindex, eval e soak não rodam em Horistic. Usar runner externo ou node não-Horistic explicitamente comprovado; o selector/runner exato é `UNKNOWN` até Wave 0. |
| Kubernetes preflight | Renderizar e usar obrigatoriamente `kubectl apply --dry-run=server`; client-side dry-run não prova admission/defaulting/schema do cluster. |
| Transações | Snapshot/journal -> CAS -> mutation -> readback independente -> receipt. Em falha, compensar somente se o poststate ainda for o estado escrito pela transação; drift concorrente termina bloqueado, sem overwrite destrutivo. |
| Evidência | Não registrar corpus, query, documentos, prompts, vetores, tokens, auth ou payload bruto. Persistir apenas hashes, contagens, identidades, métricas agregadas e receipts allowlisted. |
| Wave gates | `status` aceita somente `PASS`, `BLOCK` ou `ROLLED_BACK`; invariants aceitam somente `PASS` ou `FAIL`. `UNKNOWN`, campo ausente, métrica indisponível, readback divergente ou receipt ausente implicam `status=BLOCK` e `next_wave_allowed=false`. |
| Soak | Reattach ao UID original do Job após `external_job_waiting`; persistir Job/Pod lineage e stream append-only; nunca redispatch automático para “obter PASS”. Um watchdog srv1 independente do Job executa rollback em heartbeat stale. |
| GTE | Wave 0 observa e congela o prestate HPA 2–4; Wave 2 altera deliberadamente source/live/recovery para 2–2 antes de gerar o anchor. Modelo, Service, aliases e collections GTE não mudam; é rollback anchor até retirement. |
| Graphify | `.planning/config.json`, config live e índice mudam para Qwen/1024 dentro da transação da Wave 6. Uma worktree de serving root-owned fica detached no `graphify_source_commit` e é a única cwd de produção até a Wave 8. Um publisher root-owned UDS de operações fixas é o único mutator e oferece publish/restore mais `heartbeat-current`; o timer no-argv é somente client sem write permission/`ReadWritePaths`. Executor/heartbeat/hooks/sweep/watchdog não escrevem bytes. Wave 8 solicita apenas `restore-gte`/`restore-qwen` sobre snapshots prebuilt, sem rebuild. |
| Redis durability | Todo lease/state/INFLIGHT/terminal/soak sample de segurança exige Redis ≥7.2, AOF no primary + réplica em failure domain independente e `WAITAOF 1 1` na mesma conexão após a escrita e antes de qualquer efeito externo. Ack curto bloqueia; `everysec`/`WAIT` não substituem fsync. |
| Qdrant data plane | Alias/control-plane pertence só ao alias arbiter. Um L7 data broker separado é o único holder da credential/egress nativa e não oferece passthrough. Um issuer sem Qdrant access TokenReviews e lê a cadeia live Pod→owner Job→runner/image/nonce antes de assinar; o broker revalida certificado+token+attestation. Clients privados mTLS distintos chamam apenas provision/upsert/snapshot/replay Qwen-only; broker/network negam aliases/delete/GTE/admin. Replay usa Job digest-pinned 500m anti-Horistic e finaliza com revoke, UID cleanup e TokenReview negativo. |

## Wave architecture and gates

| Wave | Outcome | Repo artifacts | Required live readback/gate |
|---|---|---|---|
| 0 — authority/freeze | Resolver owners e congelar baseline, corpus/qrels e rollback identity | inventory/freeze JSON, eval manifest, `59-WAVE-0-GATE.json` | Qdrant authority completa; GTE aliases/collections/HPA; Redis, Router DB, cluster/node/runner inventory; tudo conhecido e hash-bound |
| 1 — artifacts/oracle/reranker | Trancar revisions/digests, escolher pooling contra FP16 e harden reranker | artifact lock, pooling oracle, reranker contract, service/tests/image | model/revision/digest readback; oracle PASS; single/batch rerank PASS; logs redacted |
| 2 — GTE rollback anchor | Fazer a transição controlada do HPA GTE observado 2–4 para source/live/recovery 2–2 e provar GTE íntegro/restaurável | rollback-anchor evidence; identidade de modelo/Service/alias preservada | HPA source/live/recovery 2–2, GTE smoke, alias/collection/model hashes preservados; snapshot/restore target identificado |
| 3 — Qwen 2+2 | Implantar namespace privado e exatamente 2 embedding + 2 reranker | `k8s/qwen-production/**` | server-side dry-run PASS, rollout/readiness 2+2, 500m por pod, Jobs fora Horistic, sem Qwen HPA |
| 4 — Redis pipeline/router | State machine persistente, no máximo 2 pipelines completos e adapters públicos | source no owner repo do router; lifecycle evidence | hash-tag único, fencing, same-connection `WAITAOF 1 1`, primary/host-loss com réplica AOF, leases/states/TTL/cancel/recovery, Router DB readback |
| 5 — dual-index/eval | Criar collections Qwen 1024, reindexar e avaliar sem tocar GTE 768 | L7 data broker, clients temporários, reindex/eval, evidence | sole native data credential, no passthrough, provision/upsert/snapshot Qwen-only e revogados; aliases/deletes/GTE/admin/direct egress negados; qualidade/CPU PASS |
| 6 — cutover | Drenar, adquirir lock/fencing global e promover Qwen por transação compensável | `qwen-cutover.py`, journal/receipts, Graphify publisher/source commit/worktree, gate | zero leases, CAS Router DB, alias swap via arbiter, Graphify publish via sole root broker e readback; executor read-only; rollback condicional |
| 7 — soak | Manter Qwen titular por >=72h | `qwen-soak.py`, watchdog systemd, stream append-only, async manifest/status, soak evidence | original Job UID e Pod lineage, heartbeat watchdog, sem redispatch, hard-failure auto-rollback, SLO/quality/state integrity PASS |
| 8 — drill/replay/retirement | Executar Qwen -> GTE -> Qwen, reconciliar e aposentar legado | drill/reconciliation/retirement evidence, docs/inventory updates | restore/replay sem perda/duplicação, snapshots e artefatos GTE retidos, Graphify Qwen 1024 read-only PASS antes do retirement |

Nenhuma wave pode depender de aprovação textual ou “checkpoint concluído” sem o gate JSON correspondente.

## File classification

### Repo `omni-srv-admin`

| New/modified file | Role | Data flow | Owner | Closest analog | Match |
|---|---|---|---|---|---|
| `k8s/qwen-production/namespace-resources.yaml` | config | request-response/batch | `omni-srv-admin` | `k8s/ebeddings-local/tei-gte.yaml:2-26` + `k8s/ebeddings-local/tei-gte-reranker.yaml:1-15` | role-match |
| `k8s/qwen-production/tei-qwen3-embedding.yaml` | config | request-response | `omni-srv-admin` | `k8s/embeddings-bench/tei-qwen-fp16.yaml:30-141` + `k8s/ebeddings-local/tei-gte-reranker.yaml:33-183` | role/data-flow |
| `k8s/qwen-production/qwen3-reranker.yaml` | config | request-response/batch | `omni-srv-admin` | `k8s/ebeddings-local/tei-gte-reranker.yaml:33-183` + `k8s/embeddings-bench/ort-qwen-q8.yaml` | role-match |
| `k8s/qwen-production/services.yaml` | config | request-response | `omni-srv-admin` | `k8s/ebeddings-local/tei-gte.yaml:182-203` | exact role |
| `k8s/qwen-production/network-policy.yaml` | config | request-response | `omni-srv-admin` | no production Qwen policy exists | `NEW` |
| `k8s/qwen-production/kustomization.yaml` | config | transform | `omni-srv-admin` | `k8s/embeddings-bench/kustomization.yaml:1-12` | exact role |
| `services/qwen-reranker-onnx/server.mjs` | service | request-response/batch | `omni-srv-admin` | same file, lines 1-136 | exact file, harden |
| `services/qwen-reranker-onnx/server.test.mjs` | test | request-response/batch | `omni-srv-admin` | no reranker unit test exists | `NEW` |
| `services/qwen-reranker-onnx/package.json` | config | build | `omni-srv-admin` | same file, lines 1-11 | exact file |
| `services/qwen-reranker-onnx/package-lock.json` | config | build | `omni-srv-admin` | same file | exact file |
| `services/qwen-reranker-onnx/Containerfile` | config | file-I/O/build | `omni-srv-admin` | Qwen bench manifests use pinned runtime/model identities; no production reranker image file | `NEW` |
| `scripts/embeddings-bench/qwen-cutover-inventory.py` | utility | batch/live-readback | `omni-srv-admin` | `scripts/embeddings-bench/canary-control.sh:10-70` | role-match; replace client-only dry-run |
| `scripts/embeddings-bench/qwen-pooling-oracle.py` | utility | request-response/transform | `omni-srv-admin` | `scripts/embeddings-bench/compare-embeddings.py:37-73` | role/data-flow |
| `scripts/embeddings-bench/qwen-functional-smoke.py` | utility | request-response | `omni-srv-admin` | `scripts/reranker-smoke.py:36-112` | role/data-flow |
| `scripts/embeddings-bench/qdrant-qwen-cutover.py` | utility | CRUD/batch | `omni-srv-admin` | `modules/rustdesk-fleet/tools/apply-phase53-edge.py:700-940` | transaction-match |
| `scripts/embeddings-bench/evaluate-rag-quality.py` | utility | batch/transform | `omni-srv-admin` | `scripts/embeddings-bench/benchmark.py:23-68,301-320,375-499` | role-match |
| `scripts/embeddings-bench/qwen-cutover.py` | service/utility | event-driven/CRUD | `omni-srv-admin` | `modules/rustdesk-fleet/tools/apply-phase53-edge.py:700-940,1174-1215` | transaction-match |
| `scripts/embeddings-bench/qdrant-alias-authority.py` | utility | security/provisioning/live-readback | `omni-srv-admin` | no enforceable sole-writer provisioner exists | `NEW` |
| `${isolated_worktree_path}/service/qdrantalias/arbiter.go` | service | durable serialized CRUD | router owner repo | Router DB/Redis transaction patterns; no Qdrant alias arbiter exists | `NEW` |
| `${isolated_worktree_path}/cmd/qdrant-alias-arbiter/main.go` + `modules/srv1-ops/systemd/qdrant-alias-arbiter.service` | standalone service | authenticated Unix-socket operations + sole Qdrant write egress | router owner repo + `omni-srv-admin` | existing systemd/Vault/Redis patterns; no isolated arbiter principal exists | `NEW` |
| `scripts/embeddings-bench/qdrant-qwen-data-broker.py` + `qdrant-qwen-data-authority.py` + separate broker/issuer systemd/RBAC/Vault/client policies | service/security | fixed-operation Qwen data management via independently attested temporary clients | `omni-srv-admin` | Qdrant native RBAC is too coarse for required deny matrix; no L7 broker/issuer authority exists | `NEW` |
| `scripts/embeddings-bench/graphify-generation-control.py` | utility | file-I/O/systemd/readers | `omni-srv-admin` | canonical GSD reader plus existing auto-update unit | `NEW` |
| `scripts/embeddings-bench/graphify-serving-publisher.py` + root systemd service | root-owned broker | fixed Qwen/GTE durable generation publication/restore | `omni-srv-admin` | no existing authority can write root-owned serving files without granting executor broad write access | `NEW` |
| `scripts/embeddings-bench/graphify-serving-heartbeat.py` + system oneshot/timer | unprivileged client | fixed no-argv request for publisher `heartbeat-current`; no serving filesystem write access | `omni-srv-admin` | actual GSD 24h mtime staleness reader + hardened systemd units | `NEW` |
| `scripts/embeddings-bench/qwen-npm-lock-audit.py` | utility | complete lock-graph and lifecycle audit | `omni-srv-admin` | package-lock plus npm `--ignore-scripts` policy | `NEW` |
| `scripts/embeddings-bench/qwen-soak.py` | utility | streaming/batch | `omni-srv-admin` | benchmark warmup/finally pattern at `scripts/embeddings-bench/benchmark.py:375-423`; async UID behavior has no local implementation | partial + `NEW` |
| `scripts/embeddings-bench/phase59-async-resumer.py` | utility | event-driven/argv-validation | `omni-srv-admin` | GSD async manifest contract; no autonomous signed resumer exists | `NEW` |
| `scripts/embeddings-bench/qwen-knowledge-replay.py` | utility | batch/live-readback | `omni-srv-admin` | migration parity tools lack independent multi-authority nonce/readback runner | `NEW` |
| `scripts/embeddings-bench/qwen-retirement.py` | utility | destructive/compensating CRUD | `omni-srv-admin` | Phase 53 transaction pattern plus actual direct-apply GTE manifests | `NEW` |
| `modules/srv1-ops/scripts/install-qwen-soak-watchdog.sh` | utility | security/systemd/Vault/RBAC | `omni-srv-admin` | existing srv1 installer scripts; no soak identity installer exists | `NEW` |
| `scripts/embeddings-bench/tests/` Phase 59 tests | test | request-response/batch/CRUD | `omni-srv-admin` | `modules/srv1-ops/tests/test_resource_governor.py:41-137,301-311` and `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` | role-match |
| frozen corpus/qrels under `scripts/embeddings-bench/` | test data | file-I/O/transform | `omni-srv-admin` | deterministic synthetic fixture generator at `benchmark.py:23-68` | partial; final paths `UNKNOWN` |
| `.planning/.../59-WAVE-N-GATE.json` family | config/evidence | transform/live-readback | phase evidence | Phase 53 strict transaction receipts and Phase 59 D-24 | role-match |
| `.planning/.../59-*-EVIDENCE.json` family | config/evidence | batch/live-readback | phase evidence | Phase 52/53 bounded evidence contracts | role-match |
| async soak manifest/status | config/evidence | event-driven | phase evidence | no reusable original-UID manifest implementation found | path/schema `NEW` |
| `.planning/config.json` | config | transform | `omni-srv-admin` | same file, current Graphify GTE/768 block | exact file; Wave 6 transaction only |
| `docs/operations/local-ai-embeddings.md` | docs | transform | `omni-srv-admin` | same file | exact file |
| `docs/operations/gbrain-embedding-migration.md` | docs | batch/transform | `omni-srv-admin` | same file | exact file |
| `inventory/hosts/horistic-srv.yaml` | config/inventory | live-readback | `omni-srv-admin` | same file | exact file; post-readback only |
| `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md` | config/docs | transform | `omni-srv-admin` | same file | exact file |
| `k8s/ebeddings-local/tei-gte.yaml` | rollback input | request-response | `omni-srv-admin` + cluster | same file | existing, freeze/read-only |
| `k8s/ebeddings-local/tei-gte-reranker.yaml` | rollback input | request-response | `omni-srv-admin` + cluster | same file | existing, freeze/read-only |

`ebeddings-local` é o caminho real existente, apesar do typo histórico. Não renomear durante esta fase.

### Router owner repo

O source do router não está neste checkout. O owner é `/home/ubuntu/GitHub/containers/router-ai-atius` em `atius-srv-1`, conforme `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md:120-135` e `deploy.yaml`.

| Surface to modify | Role | Data flow | Closest local analog | Status |
|---|---|---|---|---|
| `service/embeddinggovernor/` | service/governor | event-driven/Redis | protected path documented in `UPSTREAM-SYNC-GUARDS.md:40-79` | source/symbols `UNKNOWN` until read-only inventory |
| `relay/embedding_handler.go` | controller/adapter | request-response | protected path documented in `UPSTREAM-SYNC-GUARDS.md:25-26` | source/symbols `UNKNOWN` |
| `relay/rerank_handler.go` | controller/adapter | request-response/batch | protected path documented in `UPSTREAM-SYNC-GUARDS.md:25-26` | source/symbols `UNKNOWN` |
| `service/modelcatalog/` | model/service | CRUD/readback | protected path documented in `UPSTREAM-SYNC-GUARDS.md:40-79` | source/symbols `UNKNOWN` |
| `dto/embedding.go` | model | transform | protected path documented in `UPSTREAM-SYNC-GUARDS.md:40-79` | source/symbols `UNKNOWN` |
| `router/api-router.go` | route | request-response | protected path documented in `UPSTREAM-SYNC-GUARDS.md:40-79` | source/symbols `UNKNOWN` |

O planner deve primeiro inventariar os arquivos e símbolos reais no owner repo e só então nomear funções ou testes. Não criar nomes de structs, methods, Redis keys, DB tables ou CLI flags por inferência.

## Pattern assignments

### `k8s/qwen-production/**` — private production runtime

**Primary analogs**

- `k8s/ebeddings-local/tei-gte.yaml:2-26` — Namespace + LimitRange.
- `k8s/ebeddings-local/tei-gte-reranker.yaml:33-183` — Deployment, pinned image, probes, security context and 500m resource unit.
- `k8s/ebeddings-local/tei-gte.yaml:182-203` — Service shape.
- `k8s/embeddings-bench/kustomization.yaml:1-12` — explicit resource list.
- `k8s/embeddings-bench/tei-qwen-fp16.yaml:30-141` — official FP16 oracle identity and last-token candidate.
- `k8s/embeddings-bench/tei-qwen-onnx-int8.yaml:49-72` — `.partial` download, digest check and atomic rename pattern only.

**Resource pattern** (`tei-gte-reranker.yaml:148-154`):

```yaml
resources:
  requests:
    cpu: 500m
  limits:
    cpu: 500m
```

Add the existing memory request/limit style after measuring and freezing it; do not invent a memory value in planning. If init containers are used, account for Kubernetes init-container semantics and keep each regular pod at the canonical 500m CPU budget.

**Required differences**

- Pin Qwen embedding to `janni-t/qwen3-embedding-0.6b-int8-tei-onnx` and copy the complete revision from decision D-02 into the artifact lock; never abbreviate it in executable config.
- Pin reranker to `onnx-community/Qwen3-Reranker-0.6B-ONNX` and copy the complete revision from decision D-04 into the artifact lock; never abbreviate it in executable config.
- The embedding pooling argument comes from the Wave 1 oracle result. Do not hardcode `mean` or `last-token` before that gate.
- Use a dedicated namespace, no `hostNetwork`, private Services, Pod Security, ResourceQuota and default-deny NetworkPolicy with only explicit router/worker flows.
- Exactly two embedding and two reranker replicas at Wave 3 PASS. No Qwen HPA resource.
- Record the incumbent GTE HPA 2–4 without mutation in Wave 0; in Wave 2 patch/apply/read back source/live/recovery as 2–2 before generating the recovery anchor. Preserve model, Service, alias and collection identity.
- Exclude Horistic from all tooling Jobs. The exact node selector/affinity value is `UNKNOWN` pending Wave 0 inventory; do not guess a hostname label.
- Do not copy `:latest`, `hostNetwork`, host-bound probe addresses or public NodePort exposure from incumbent/bench manifests.
- `k8s/tei-qwen-fp16-hpa-2-4-proposal.yaml` is experimental history, not a production analog for autoscaling.

### `services/qwen-reranker-onnx/server.mjs`

**Analog:** existing prototype `services/qwen-reranker-onnx/server.mjs:1-136`.

Keep the existing HTTP/JSON service boundary and Qwen prompt/scoring flow, but refactor behind testable functions. Existing seams to preserve or harden:

- imports/runtime bootstrap: lines 1-14;
- prompt construction: lines 16-30;
- probability conversion: lines 33-38;
- batch scoring and rerank ordering: lines 40-66;
- model load: lines 69-80;
- JSON response: lines 82-89;
- request body and routes: lines 91-126;
- listener lifecycle: lines 129-136.

**Required hardening**

- disable remote model fetch at runtime and consume the artifact-locked local path;
- left padding, required suffix, deterministic truncation and context 512;
- public single and batch contracts; initial internal batch size 1 and at most 20 documents sequentially;
- bounded request body, queue, concurrency, timeout and TTL;
- cancellation propagation and graceful shutdown;
- stable allowlisted error JSON;
- no prompt/document/token/raw score vectors in logs;
- tests for duplicate/unknown fields, empty/oversized input, timeout, cancel, shutdown, single/batch equivalence, ordering and redaction.

`server.test.mjs` and `Containerfile` are `NEW`; copy repository module style only after confirming the current Node test runner from `package.json`. Do not invent framework imports.

### Inventory, oracle, smoke and evaluation scripts

**Analogs**

- `scripts/embeddings-bench/canary-control.sh:10-51` — allowlist and explicit target validation.
- `scripts/embeddings-bench/compare-embeddings.py:37-73` — HTTP embedding call, dimensionality, norm and cosine comparison.
- `scripts/reranker-smoke.py:36-67` — environment-sourced auth without printing it.
- `scripts/reranker-smoke.py:87-112` — redacted metric/result output.
- `scripts/embeddings-bench/benchmark.py:23-68` — deterministic generated fixtures.
- `scripts/embeddings-bench/benchmark.py:301-320` — output vector hash/norm instead of vector contents.
- `scripts/embeddings-bench/benchmark.py:375-423` — warmup and guaranteed cleanup.

**Copy pattern**

```python
# Evidence shape, not a raw payload:
{
    "model_identity": "...",
    "input_manifest_sha256": "...",
    "item_count": 0,
    "metrics": {},
    "raw_corpus_present": False,
}
```

The object above is a schema pattern, not an existing symbol. Final schemas must reject duplicate keys, unknown keys and non-finite numbers, and must bind all inputs/artifacts by SHA-256.

**Per-file assignment**

- `qwen-cutover-inventory.py`: enumerate repo config plus independent live authorities; emit `UNKNOWN` rather than defaults. Its Kubernetes validation must render and invoke server-side dry-run.
- `qwen-pooling-oracle.py`: compare `mean` and `last-token` INT8 candidates against official FP16, with query instruction only on query inputs, no instruction on documents, 1024 dimensions, L2 normalization, batch 1 and single/batch cosine >= 0.9999.
- `qwen-functional-smoke.py`: exercise public router boundary and private worker contracts without bypassing auth; report hashes/counts/latency/status only.
- `evaluate-rag-quality.py`: frozen PT-BR/code corpus and qrels, Recall@20 and nDCG@10, at least five warm rounds, no predeclared quality regression and CPU seconds <= 1.05x GTE.

`results-2026-06-29.md` is historical, mean-pooling and non-gating. Do not use it as Wave 1 or Wave 5 acceptance.

### `qdrant-qwen-cutover.py` and `qwen-cutover.py`

**Transaction analog:** `modules/rustdesk-fleet/tools/apply-phase53-edge.py:700-940,1174-1215`.

Copy the injected-backend state machine structure:

```python
class EdgeTransaction:
    """Pure state machine over an injected backend; performs no I/O itself."""
```

Snapshot and CAS pattern (`apply-phase53-edge.py:746-763`):

```python
snapshot = self.backend.snapshot()
self._prestate = copy.deepcopy(snapshot)
current_revision = self.backend.current_revision()
if str(current_revision) != str(expected_revision):
    raise EdgeBlocked("edge-cas-stale")
```

Readback and compensation pattern (`apply-phase53-edge.py:814-829,889-901`):

```python
self.backend.apply_nft(candidate, semantics)
self._poststate = self.backend.observe()
if observed != semantics:
    raise EdgeBlocked("nft-semantic-readback-drift")
```

Rollback drift guard (`apply-phase53-edge.py:903-940`):

```python
if (
    self._poststate is None
    or current.get("revision") != self._poststate.get("revision")
    or current["state"] != self._poststate["state"]
):
    self.state = "CONTAINED_REQUIRES_MANUAL_RECOVERY"
```

Also copy the filesystem compensation principle from `modules/fleet-backup/scripts/phase52-install-state.py:444-463,482-525`: verify current reality against source/backup hashes, reject ambiguous compensation, stage atomically, and compensate on any `BaseException`.

**Required Phase 59 transaction**

1. Capture durable journal with Router DB generation and Qdrant exact alias-map prestate/hash, shared lock/fencing identity, collection IDs, leases and writer state.
2. Drain admission, wait for zero active leases, pause all writers, and re-read both authorities.
3. CAS Router DB routing/model aliases.
4. Read back Router DB independently.
5. Send all alias changes through the sole standalone arbiter provisioned in Wave 4. Its dedicated `qdrant-arbiter` UID owns the only credential/network path; Router/watchdog/reindex have only authenticated operation access over the private Unix socket. It persists PREPARED/INFLIGHT in Redis AOF before send and never admits a successor after unknown outcome. Cold handoff requires zero ambiguity and exact order: revoke old credential, block old egress/socket/token, negative-probe old host including partition-heal/rejoin, issue new generation, start standby. Inference/read paths continue if the arbiter is down while mutations fail closed.
6. Read back Qdrant independently.
7. Resume writers/admission only after all invariants pass.
8. On any failure, compensate in reverse order only while the transaction still owns the lock/fencing token and current semantics equal its exact poststate.
9. If concurrent drift makes ownership ambiguous, remain drained/contained and fail closed; never overwrite the drift.

The physical Qwen collection contract is:

- `gbrain_qwen3_1024_v1`
- `obsidian_qwen3_1024_v1`
- `graphify_qwen3_1024_v1`
- vector size 1024, distance Cosine

GTE 768 vectors and Qwen 1024 vectors must never share a physical collection.

### Router Redis pipeline and adapters

**Source authority:** `/home/ubuntu/GitHub/containers/router-ai-atius` on `atius-srv-1`. Local guards are at `modules/fork-sync/projects/atius-router/UPSTREAM-SYNC-GUARDS.md`.

The required state machine is:

```text
QUEUED -> EMBEDDING -> VECTOR_SEARCH -> RERANK -> COMPLETED
                    \-> FAILED | CANCELLED | EXPIRED
```

This is a contract from `59-RESEARCH.md`, not an existing local symbol. Before implementation, inspect the real owner-repo types, keys, transactions and tests.

Required behavior:

- persistent Redis state, idempotent lease for the full pipeline, TTL and restart recovery;
- one Redis Cluster hash-tag for every key touched atomically, plus monotonic fencing epoch and owner token; no CROSSSLOT fallback;
- same-connection `WAITAOF 1 1` after each atomic safety write and before backend calls/admission/slot reuse; process, primary and independent-host-loss fixtures must recover only acknowledged epochs;
- at most two complete pipelines active;
- continuations have priority over new admissions;
- standalone embedding uses a separate limiter and cannot consume the complete-pipeline lease budget;
- cancel/expiry release exactly the owned lease;
- public `/v1/embeddings` and `/v1/rerank` remain authenticated router APIs;
- private worker endpoints are implementation details and must not become a new public boundary;
- Router DB remains routing/model-alias authority and participates in Wave 6 CAS/readback.

Do not copy names from this map into Go until the real owner repo confirms them.

### `qwen-soak.py` and async manifest

The async behavior is `NEW`; only the benchmark measurement/cleanup pattern has a local analog.

The manifest must persist:

- original Kubernetes Job UID and immutable job identity;
- dispatch timestamp, observed resource version and current phase;
- last readback timestamp and bounded aggregate metrics;
- `external_job_waiting` while detached;
- `redispatch_count: 0`;
- Qwen titular aliases at each readback;
- rollback receipt if a hard failure occurs.
- append-only sample/heartbeat stream where only same-connection `WAITAOF 1 1` acknowledged events advance continuity, Job UID plus every Pod UID lineage, collector fencing, Redis primary/host-loss tests and independent srv1 watchdog receipt.
- expected artifact identities, exact argv-only verification/resume chains and their hashes;
- frozen executor mode, combined bootstrap/autopilot receipt hash and append-only state transitions.

Reconciliation must attach to the original Job UID and verify complete Pod UID
lineage. Missing/duplicate/recreated Job, UID mismatch or redispatch attempt is
`status=BLOCK`; replacement Pods are accepted only when appended to that
lineage and cannot reset elapsed time. A signed finalizer changes `running` to
`completed-unverified`; only the autopilot-signed exact-chain resumer may
continue automatically. The execute-phase fallback retains the GSD core human
confirmation boundary. The gate requires >=72 hours from the first accepted
sample, durable stream continuity, signed rollback-access/cold-start proof and
watchdog PASS.

### Wave gate and evidence JSON

Every wave emits one canonical `59-WAVE-N-GATE.json`. Freeze the exact zero-padding/naming convention in Wave 0 and use it consistently; do not preserve both `WAVE0` and `WAVE-0` variants.

Minimum gate shape:

```json
{
  "schema_version": 1,
  "phase": 59,
  "wave": 0,
  "input_hashes": {},
  "prestate": {},
  "poststate": {},
  "invariants": [],
  "receipts": [],
  "aliases": {},
  "leases": {},
  "rollback_target": {},
  "unknowns": [],
  "status": "BLOCK",
  "next_wave_allowed": false
}
```

This is a `NEW` schema contract, not an existing checked-in schema. Required derivation:

```text
next_wave_allowed =
  status == PASS
  AND unknowns is empty
  AND every required invariant == PASS
  AND all required hashes/readbacks/receipts exist
  AND rollback_target is independently readable
```

Parsing is strict and fail-closed: reject duplicate/unknown keys, invalid enum values, non-finite metrics, unhashed inputs, stale readbacks and phase/wave mismatch. Evidence records no secrets or raw corpus.

### Graphify, GBrain, Obsidian and documentation

**Analogs**

- `.planning/config.json` — current Graphify model/dimension settings.
- `docs/operations/local-ai-embeddings.md:5-46` — router public boundary and rerank adapter.
- `docs/operations/local-ai-embeddings.md:67-100` — governor/config paths and Graphify bridge.
- `docs/operations/local-ai-embeddings.md:124-130` — immutable embedding identity and reindex rule.
- `docs/operations/local-ai-embeddings.md:184-195` — 500m pod unit.
- `docs/operations/local-ai-embeddings.md:274,301-305` — redacted output and secret hygiene.
- `docs/operations/gbrain-embedding-migration.md:25-57` — no vector mixing and backup-first.
- `docs/operations/gbrain-embedding-migration.md:99-118` — reindex flow.
- `docs/operations/gbrain-embedding-migration.md:126-156` — current Graphify GTE/768 baseline replaced transactionally in Wave 6.

Apply the Graphify Qwen/1024 change only inside Wave 6. The canonical GSD reader opens `.planning/graphs/graph.json` relative to cwd, so do not introduce a side pointer. Commit the Qwen config/source and create a root-owned detached serving worktree at `/home/ubuntu/GitHub/worktrees/omni-srv-admin-phase59-graphify-${source12}`; this exact cwd is the production Graphify authority through Wave 8 even as the execution worktree advances. Build immutable generation archives outside the serving worktree. A root-owned peer-authenticated UDS publisher is the sole serving mutator and accepts only `publish-qwen`, `restore-gte`, `restore-qwen` and `heartbeat-current`; it derives fixed source/destination paths from immutable config and rejects caller paths/argv. Under a shared publication lock, set `graphify.auto_update=false`, register the serving realpath/HEAD in the versioned sweep exclusion, deny existing hook writers, quiesce readers and let only the publisher perform same-filesystem temp write + file fsync + `rename(2)` + parent-directory fsync + independent reopen/hash readback. Verify through actual `gsd-tools graphify status/query` from the serving cwd. Install a separate no-argv system timer as an unprivileged UDS client with `ProtectSystem=strict` and no `ReadWritePaths`/write permission over the serving tree. It requests only `heartbeat-current`; the publisher verifies expected hashes, performs `utimensat`, reruns the reader and records pre/post byte hashes at ≤12h. Executor, heartbeat client, Ubuntu, hooks, sweeps and watchdog cannot write graph bytes or alter publisher arguments/config. Resume readers only; keep publisher and automatic-writer exclusion through and after Wave 8. Wave 8 requests fixed restore operations over prebuilt archives; it performs no build and never writes canonical files directly.

GBrain file and DB planes, Obsidian index writer and Graphify live config each need independent readback and full reindex evidence. Updating repo docs/config is not live proof.

## Shared patterns

### CPU and build admission

**Sources**

- `AGENTS.md:18-32`
- `modules/srv1-ops/configs/resource-governor.env:49-62`
- `modules/srv1-ops/README.md:48,57-77`
- `cli/omni/srv1_ops.py:172-181,470-532`
- `modules/srv1-ops/tests/test_resource_governor.py:104-137`

The canonical profile sets:

```dotenv
RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20
RG_PROFILE_BUILDS_CPU_QUOTA=20%
```

The governor computes the total-host quota, serializes heavy work and blocks when admission/doctor fails. A 4-vCPU host therefore gets 0.8 CPU, not one full core.

### Kubernetes admission and placement

Apply both:

```bash
kubectl kustomize k8s/qwen-production > /tmp/qwen-production-rendered.yaml
kubectl apply --dry-run=server -f /tmp/qwen-production-rendered.yaml
```

Do not replace the second command with `--dry-run=client`. The resulting live apply is a later authorized execution action, not implied by validation.

### Auth and API boundary

**Source:** `docs/operations/local-ai-embeddings.md:5-46` and `scripts/reranker-smoke.py:36-67`.

- Bearer auth terminates at router public APIs.
- Load credentials from runtime environment/Vault hydration; never argv, source, evidence or logs.
- Private worker Services remain cluster-private.
- Preserve stable public response/error formats while model aliases change behind the router.

### Error handling and redaction

**Sources:** `scripts/reranker-smoke.py:87-112`, `benchmark.py:301-320`, and `apply-phase53-edge.py:889-901`.

- known validation/contract failures produce bounded stable error codes;
- unexpected backend exceptions become fail-closed errors and trigger compensation if this transaction owns a mutation;
- evidence uses hashes, dimensions, norms, counts, latency and status;
- no raw corpus, query, documents, prompts, vectors, token IDs, model output text, auth or backend stdout/stderr.

### GTE rollback immutability

Freeze and read back:

- exact manifest hashes;
- model IDs/revisions and runtime image digests;
- current Deployments, Services, HPA/PDB and replica state;
- GTE physical collections and aliases;
- backups/snapshots and restore target;
- functional smoke baseline.

Wave 2 must transition the observed/repo GTE HPA from 2–4 to 2–2, apply and independently read back live 2–2, and only then generate recovery manifests frozen at 2–2. It cannot remap GTE aliases to Qwen, change GTE model/Service identity or mix dimensions. This explicit capacity freeze is not a generic HPA modernization.

## API, data and live-state seams

| Seam | Repo/config plane | Live authority | Wave that must resolve/prove |
|---|---|---|---|
| Public embedding/rerank API | router owner repo | running router + auth/config | 0 inventory, 4 implementation, 6 cutover |
| Pipeline lifecycle | router owner repo | Redis ≥7.2 AOF primary + independent replica | 0 version/AOF/WAITAOF/failure-domain gate; 4 state machine and primary/host-loss |
| Routing/model aliases | router owner repo/schema | Router DB | 0 authority; 6 CAS/readback |
| Vector collections/aliases | standalone alias arbiter for aliases; separate private-mTLS L7 data broker plus least-privilege issuer and temporary Qwen-only provision/upsert/snapshot/replay clients | Qdrant | 0 native permission/bypass/runner transport inventory; 4 alias arbiter; 5 broker/issuer owner-attestation + frozen tool/replay Job + dual-index; 6/8 alias swap; 8 one real task-bound replay Job, revoke, UID cleanup and TokenReview negative |
| Qwen workers | `k8s/qwen-production/**` | Kubernetes API | 3 |
| GTE rollback | direct-apply `k8s/ebeddings-local/tei-gte*.yaml`, then excluded `rollback-only/**` | Kubernetes API + Qdrant | 0 freeze, 2 anchor, 8 actual source/live retirement |
| GBrain embeddings | docs/config plus migration scripts | GBrain file + DB planes | 5 dual-index, 6 cutover, 8 replay |
| Obsidian embeddings | docs/config plus migration scripts | Obsidian writer/index | 5, 6, 8 |
| Graphify embeddings | `.planning/config.json`, root-owned detached serving worktree, immutable archives, fixed-operation root publisher, writer exclusion and no-argv unprivileged heartbeat client | actual GSD graph reader plus sole publisher mutator | 6 build/publish/restore/heartbeat authority; 7 heartbeat/status/query; 8 publisher-only prebuilt drill/read-only verification |
| Soak continuity | async manifest/finalizer/signed resumer | Kubernetes Job API + srv1 systemd | 7; original UID and executor-mode boundary required |
| Placement/capacity | manifests/inventory | scheduler/nodes/cgroups | 0 inventory, 3/5/7 readback |

## Validation command contracts — NOT RUN

These are planner-facing command patterns. This mapping task did not execute them.

### Static/unit regression

```bash
omni srv1-ops resources run builds -- \
  python3 -m unittest discover -s scripts/embeddings-bench/tests -p 'test_*.py' -v

omni srv1-ops resources run builds -- \
  npm --prefix services/qwen-reranker-onnx ci --ignore-scripts

omni srv1-ops resources run builds -- \
  npm --prefix services/qwen-reranker-onnx test

omni srv1-ops resources run builds -- \
  bash scripts/gsd-wave-regression.sh
```

### Manifest admission

```bash
kubectl kustomize k8s/qwen-production > /tmp/qwen-production-rendered.yaml
kubectl apply --dry-run=server -f /tmp/qwen-production-rendered.yaml
kubectl diff -k k8s/qwen-production
```

`kubectl diff` may contact live state but does not mutate it. It belongs to execution preflight, not this pattern-mapping run.

### Builds

Router owner repo:

```bash
cd /home/ubuntu/GitHub/containers/router-ai-atius
./scripts/podman-admin.sh build
```

If the reranker owner repo has no dedicated wrapper:

```bash
omni srv1-ops resources run builds -- \
  podman build -f services/qwen-reranker-onnx/Containerfile \
  services/qwen-reranker-onnx
```

Never run raw `podman build`, `docker build`, `npm run build`, `bun run build` or broad Go tests outside the `builds` profile.

### NEW Phase 59 CLI contracts

The following commands describe required interfaces for files that do not yet exist. The planner must create tests before treating the flags as implemented:

```bash
python3 scripts/embeddings-bench/qwen-cutover-inventory.py \
  assert-wave-gate --wave 0 --phase-dir \
  .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s \
  --output .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-WAVE-0-GATE.json

python3 scripts/embeddings-bench/qdrant-qwen-cutover.py \
  prepare-journal --require-titular-unchanged

python3 scripts/embeddings-bench/qwen-cutover.py \
  fault-test --require-all-boundaries

python3 scripts/embeddings-bench/qwen-cutover.py \
  preflight --journal \
  .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-CUTOVER-JOURNAL.json

python3 scripts/embeddings-bench/qwen-soak.py \
  verify-report --report \
  .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s/59-SOAK-EVIDENCE.json \
  --min-hours 72 --require-original-job-uid --forbid-redispatch
```

Every command returns nonzero for `UNKNOWN`, absent evidence, stale readback, wrong UID or `next_wave_allowed != true`.

### Router owner-repo validation

After read-only inventory confirms real package paths:

```bash
cd /home/ubuntu/GitHub/containers/router-ai-atius
omni srv1-ops resources run builds -- \
  go test -race ./service/embeddinggovernor ./service/modelcatalog ./relay -count=1
```

If those package paths differ in the owner repo, use the discovered paths. Do not force the command from this map.

### Wave 8 Graphify replay verification

Only after drill/reconciliation PASS:

```bash
node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" graphify status
node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" graphify query \
  "phase 59 qwen3 embedding 1024 retirement"
```

The final gate must parse `.planning/config.json` and independently read the
existing Wave 6 serving-worktree Graphify config/index, proving exact serving
realpath/HEAD, active writer exclusion, Qwen identity, dimension 1024, unchanged
graph byte hash, fresh/commit-current actual status/query and `no_rebuild=true`.
Wave 8 may run the allowlisted verify-before-utime heartbeat, request only fixed
publisher restore operations over prebuilt generations, replay and verify
but cannot run `graphify update` or conceal byte/source drift with a rebuild.
`graphify status` alone is insufficient.

## No analog or unresolved authority

| File/surface | Reason | Blocking wave |
|---|---|---|
| `k8s/qwen-production/network-policy.yaml` | no production Qwen NetworkPolicy exists | 3 |
| `server.test.mjs` | no reranker unit-test module exists | 1 |
| reranker `Containerfile` | no production reranker image recipe exists | 1 |
| frozen corpus/qrels final paths | content contract exists, path names are not frozen | 0 |
| async soak manifest/schema | original-UID/no-redispatch implementation is new | 7 |
| Qdrant endpoint/version/auth/storage/backups/aliases/collections | live authority unknown | 0; blocks all later mutation |
| Redis and Router DB location/schema/generation mechanism | owner-repo/live inventory not yet read | 0/4 |
| router source symbols and exact test packages | separate owner repo not accessible in this checkout | 4 |
| non-Horistic Job runner/node selector | placement target not yet inventoried | 0/3 |
| Graphify canonical Qwen config value | final identity must match artifact lock and supported live schema | 6 |

## Planner handoff

Plans must follow the wave order exactly and include:

1. files changed with repo/host owner;
2. read-only prestate and authority resolution;
3. existing analog and required differences;
4. narrow tests using injected/fake backends before live operations;
5. wrapper-governed commands and 500m pod accounting;
6. server-side dry-run for Kubernetes;
7. mutation journal, CAS, independent readback and compensation;
8. fail-closed wave gate JSON;
9. explicit rollback target;
10. no progression while any required field is `UNKNOWN`.

Schedule the Graphify 1024 config/index transition only inside Wave 6 and bind it
to an immutable `graphify_source_commit` plus root-owned serving worktree. Keep
that cwd writer-excluded and fresh through the fixed-operation root publisher
and separate hash-preserving metadata heartbeat. Wave 8 may request only
publisher-mediated restore of the prebuilt GTE/Qwen generations during its
fenced drill, then replay and independently verify the final Qwen state; the
executor cannot write serving files, build or reindex.
Do not schedule GTE retirement
before the Wave 8 drill, promotion checkpoints or `PROMOTION_EXECUTED=false`.

## Qwen 2–5 pod envelope pattern

Use three distinct states and never call them autoscaling:

| State | Embedding | Reranker | Total CPU | Allowed meaning |
|---|---:|---:|---:|---|
| Degraded | 1 | 1 | 1000m | Failure/maintenance recovery only; cannot close a wave |
| Permanent | 2 | 2 | 2000m | Normal serving and all steady-state gates |
| Embedding surge | 3 | 2 | 2500m | Embedding rollout only, post-GTE, then return to 2+2 |
| Reranker surge | 2 | 3 | 2500m | Reranker rollout only after embedding returned to 2+2 |

During coexistence, use quota `pods=4`, CPU `2000m`,
`maxSurge=0/maxUnavailable=1` and PDB `minAvailable=1` per service. After GTE
retirement and headroom proof, change to quota `pods=5`, CPU `2500m` and
`maxSurge=1/maxUnavailable=0`. Serialize embedding then reranker with a durable
drain/rollout token. Try both updates concurrently in a fault test: one fifth
pod may appear, the sixth must be denied. Jobs use another namespace/runner.
The governor remains two pipelines in all three states.

## Metadata

**Analog search scope:** `k8s/`, `services/qwen-reranker-onnx/`, `scripts/embeddings-bench/`, `modules/srv1-ops/`, `modules/fork-sync/projects/atius-router/`, `modules/rustdesk-fleet/`, `modules/fleet-backup/`, `docs/operations/`, `.planning/workstreams/qwen-local-ai/`
**Graphify refresh:** rebuilt locally with Graphify 0.8.41 after planning edits; status was fresh at base commit `f12c3ec`, while task-specific queries returned no Phase 59 nodes, so focused file reads remained authoritative
**Planning work performed:** read-only repo/live inspection, official-source research, multi-review convergence, planning/helper edits, lightweight helper tests and generated Graphify refresh; no k3s apply, model build, live cutover or deployment
**Pattern extraction date:** 2026-07-23
