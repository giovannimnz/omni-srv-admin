---
phase: 59
slug: qwen3-embedding-e-rerank-podman-para-k3s
status: planned
nyquist_compliant: true
nyquist_basis: planned_coverage_only
execution_evidence: canonical_wave_gate_json
created: 2026-07-23
updated: 2026-07-23
plan_bundle_required: /home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json
---

# Phase 59 — Validation Strategy

`nyquist_compliant: true` means only that all 30 planned tasks have an
executable behavioral check and are connected to plan, wave and final gates.
It is not execution evidence. This signed strategy stays byte-immutable during
execution; Wave 0 completion is recorded only by the real
`59-WAVE-0-GATE.json` plus the mutable `STATE.md` projection.

The execution contract is the nine-plan sequence whose paths and SHA-256 values
are recorded only after convergence and the final planning commit in external
bootstrap artifact `/home/ubuntu/.local/state/gsd/phase59/59-PLAN-BUNDLE.json`.
Its absence from the repository before that commit is mandatory, not missing
evidence, because the bundle signs `final_execution_commit`. The bundle records a
runtime `final_execution_commit`; no current or historical commit is accepted
as a fixed execution identity. Qwen is rolled out privately at permanent 2+2
under a coexistence cap of four model pods, becomes titular through the journaled Wave 6
transaction, soaks on its original external Job UID in Wave 7, and reaches the
final state only after the Wave 8 round trip, replay verification of the Wave 6
knowledge reindex, Graphify/1024 readback, actual GTE workload removal and
validation of the post-GTE single-surge envelope (steady 4, degraded floor 2,
transient maximum 5; never HPA). GTE remains an
independently proven rollback target until that final removal; its snapshots,
alias exports and restore instructions remain retained.

In `autopilot` mode there is no human checkpoint; authorization is already
recorded and the only pause is the external async wait. In
`execute-phase-fallback`, the installed GSD core's human confirmation at
`completed-unverified` is intentionally preserved. All other decisions use
frozen inputs and automated readbacks.

## Test Infrastructure

| Surface | Level | Runner / contract | Required placement |
|---|---|---|---|
| Python contracts and fault fixtures | Unit/component | `python3 -m unittest ... -v` | Local for light suites; srv1 `builds` profile for heavy suites |
| Reranker lifecycle/supply chain | Unit/component | Full transitive lock audit, clean `npm ci --ignore-scripts`, zero lifecycle-child observation, CPU/offline startup, then exact Node test runner | srv1 after builds doctor, inside 20% profile |
| Router/governor | Unit/integration/race | `router-owner-run.py` plus focused/full `go test -race` through isolated `./scripts/podman-admin.sh profile-run builds --` | Frozen dedicated owner worktree on srv1; owner checkout is read-only |
| Kubernetes resources | Static/integration | Python manifest tests, deterministic render, server-side dry-run, live rollout/readback | k3s control plane; runtime remains 500m per pod |
| Qdrant/router/consumer lifecycle | Integration/end-to-end | Phase CLIs with injected fault fixtures, CAS, independent live readbacks and redacted evidence | srv1 coordinator plus external runner where specified |
| Quality/capacity | Behavioral/capacity | frozen corpus/qrels, at least five paired warm rounds and metrics fallback | Digest-pinned 500m Job outside Horistic |
| Soak | Asynchronous end-to-end | one original-UID 500m Job, reattach-only verification, at least 72 continuous hours | Frozen external runner, never Horistic |
| Wave regression | Secondary regression | self-contained `bash scripts/gsd-wave-regression.sh` | Before active hooks and final gate assertion; script itself enforces srv1 `/home/ubuntu/.local/bin/omni`, doctor, recursion guard and 20% profile |

## Pre-Execution Blocking Checks

These checks are machine gates, not requests for approval:

1. Before autopilot only, follow `59-AUTOPILOT-BOOTSTRAP.md`. It validates the
   post-planning `59-PLAN-BUNDLE.json`, its `final_execution_commit`, all nine
   PLAN hashes and a clean dedicated srv1 worktree without touching the dirty
   owner checkout.
2. Bootstrap Graphify freshness/query and autopilot doctor must be explicit
   PASS before autopilot invocation. The known doctor query bug remains
   fail-closed and is not repaired by Wave 0. Bootstrap failure does not create
   Wave evidence and does not start Wave 0.
3. The fallback executor, from a Codex task rooted in the same srv1 worktree,
   remains `$gsd-execute-phase 59 --ws qwen-local-ai`. If an autopilot lock
   already exists, `transition-fallback` first requires an exact external
   skill-doctor FAIL/BLOCK receipt, clean base worktree, no Gate 0/Summary,
   no combined receipt and the same owner/bundle/base/hashes; it atomically
   replaces the lock and emits a new fallback bootstrap receipt. This state is
   bootstrap-only and never appears as Wave 0 evidence.
4. Wave 0 itself must resolve one Phase 54 network branch, every authority, the
   non-Horistic runner, a usable metrics source/fallback, rollback targets and
   dirty-worktree ownership before any acceptance observation or mutation. Its
   Redis gate requires version `>=7.2`, AOF primary+independent replica and
   same-connection `WAITAOF 1 1`; its Qdrant gate separately inventories
   alias/control-plane writers and temporary create/upsert/snapshot data-plane
   permissions for the three exact Qwen collections.

The previously questioned historical planning commit did contain all nine
PLAN files as proven by `git ls-tree`; that fact corrects the checker record
but does not make the historical hash the final bundle identity.

## Task → Plan → Wave Contract

For every task, `gsd-execute-phase`, `gsd-autonomous` and
`gsd-execute-autopilot` must:

1. execute the task's exact `<verify><automated>` command;
2. enforce every `<acceptance_criteria>` statement against behavioral evidence;
3. stop the plan on non-zero exit, missing evidence, stale readback, skipped
   required probe, unavailable metrics without fallback, secret finding,
   overlap, `UNKNOWN`, or acceptance mismatch;
4. execute the plan-level `<verification>`;
5. before Summary, run the self-contained `bash scripts/gsd-wave-regression.sh`,
   then render/dispatch every active `execute:wave:post` hook through
   `run-gsd-wave-post-hooks.py`, then verify registry/live-parser conformance
   for every completed producer, then run the canonical `assert-wave-gate`;
6. require that exact regression→hooks→completed-parser-conformance→gate chain
   to pass before Summary. The
   installed core's native post-Summary hooks run again as a second defense;
   any blocking result prevents dependent-plan/next-wave dispatch. Advisory
   hooks may report but cannot convert a failed regression or gate into success.

No SUMMARY, dependent plan or next wave may be closed/dispatched before this
chain succeeds. Plan 59-08 is the sole exception to immediate continuation:
its terminal async task returns `external_job_waiting`, and execution resumes
only through the original manifest's verification command.

### Per-Task Verification Map — 30/30

The “Automated” column is an exact pointer to the named task's
`<verify><automated>` element whose hash is in `59-PLAN-BUNDLE.json`. The
executor must run that literal element without shortening or substituting it.

| Task | Requirement / decision coverage | Test level | Automated | Primary evidence | Blocking behavior |
|---|---|---|---|---|---|
| 59-01-01 | QAI-03, QAI-08; D-13, D-21, D-24 | Unit/schema/harness | `59-01-PLAN.md → Task 1 → <verify><automated>` | gate CLI fixtures, post-hook dispatcher fixtures, contained regression static fixtures | Schema/hook contract gap or any broad runner reachable outside srv1 builds containment blocks all later tasks |
| 59-01-02 | QAI-01, QAI-03, QAI-04, QAI-08; D-01, D-05, D-12..D-17, D-21, D-23..D-26 | Integration/read-only | `59-01-PLAN.md → Task 2 → <verify><automated>` | `59-AUTHORITY-INVENTORY.json`, `59-GTE-PRESTATE.json`, live k3s accepted API audience set/selected cleanup audience, Redis version/AOF/failure-domain/WAITAOF proof and Qdrant control/data-plane authority map | Missing/assumed audience, Redis `<7.2`, short/unsupported local+replica fsync, unfenceable Qdrant path, runner, metric source or independent readback blocks Wave 0; autopilot doctor is explicitly out of Wave 0 |
| 59-01-03 | QAI-02, QAI-06, QAI-07; D-19, D-20, D-22, D-24, D-30 | Contract/integration | `59-01-PLAN.md → Task 3 → <verify><automated>` | frozen corpus/qrels, `59-BASELINE-CONTRACT.json`, explicit 2/4/5 pod and 1000m/2000m/2500m envelope, post-GTE headroom, serialized rollout, sixth denial, governor=2, PDB voluntary-only semantics, `59-EVAL-FREEZE.json`, Wave 0 gate | Any post-observation threshold, D-30 mismatch, missing hash/ID or non-PASS gate blocks Wave 1 |
| 59-02-01 | QAI-02, QAI-06; D-02, D-03, D-06, D-19 | Unit/component/oracle | `59-02-PLAN.md → Task 1 → <verify><automated>` | `59-ARTIFACT-LOCK.json`, `59-POOLING-ORACLE.json` | Mutable/non-ARM64 artifact or oracle failure blocks image/manifests |
| 59-02-02 | QAI-05; D-04, D-18, D-21, D-28 | Unit/component/supply-chain | `59-02-PLAN.md → Task 2 → <verify><automated>` | full lock-graph audit, clean `npm ci --ignore-scripts`, zero lifecycle-child observation, CPU/offline startup, reranker Node suite and redacted lifecycle behavior | Mutable/missing-integrity transitive node, any lifecycle child, offline startup failure, bounds/suffix/scoring/cancellation or 20% containment failure blocks build and requires replan rather than implicit scripts |
| 59-02-03 | QAI-02; D-06, D-21, D-24, D-28 | Build/component | `59-02-PLAN.md → Task 3 → <verify><automated>` | `59-RERANKER-HARDENING.json`, complete lock audit, ignored-script ARM64 image build/digest, Wave 1 gate | Doctor/profile/lifecycle/metrics/image/readback failure blocks rollback anchoring |
| 59-03-01 | QAI-08; D-23, D-24 | Unit/contract | `59-03-PLAN.md → Task 1 → <verify><automated>` | `test_qwen_rollback_anchor.py` | Incomplete alias/DB/snapshot/restore contract blocks live export |
| 59-03-02 | QAI-01; D-01, D-05, D-12, D-15, D-21, D-24 | Integration/backup/fault | `59-03-PLAN.md → Task 2 → <verify><automated>` | fault-injected source patch→server dry-run→live apply→independent readback→recovery-generation boundaries; source/live/recovery HPA 2–2; GTE export, Router DB backup and Qdrant snapshots/aliases | Any boundary failure conditionally restores source/live 2–4 prestate, emits ROLLED_BACK and blocks; drift, unreadable hash or incomplete backup also blocks |
| 59-03-03 | QAI-05, QAI-08; D-12, D-21, D-24 | Integration/restore/smoke | `59-03-PLAN.md → Task 3 → <verify><automated>` | `59-GTE-ROLLBACK-ANCHOR.json`, isolated restore readback, Wave 2 gate | Non-isolated/mismatched restore or failed GTE smoke blocks rollout |
| 59-04-01 | QAI-02, QAI-05; D-09..D-13, D-18 | Static/server admission | `59-04-PLAN.md → Task 1 → <verify><automated>` | temporary one-service-at-a-time sizing manifests and server-side dry-runs | Concurrent sizing, non-500m CPU, missing headroom receipt, public path or premature production/quota blocks sizing |
| 59-04-02 | QAI-02; D-02, D-04, D-09, D-10 | Live sizing/metrics | `59-04-PLAN.md → Task 2 → <verify><automated>` | `59-QWEN-SIZING.json`, startup/steady/peak metrics and removal receipts | Missing metrics/fallback, exceeded temporary ceiling, overlap or leftover sizing object blocks final manifests |
| 59-04-03 | QAI-02, QAI-05; D-09..D-12, D-21, D-24, D-30 | Static/live integration/network/availability | `59-04-PLAN.md → Task 3 → <verify><automated>` | sizing-bound manifests; live coexistence apply; quota 4/2000m; rollout 0/1; policy/v1 Eviction test proving one voluntary disruption and second denial until recovery; fifth-pod/concurrent-update no-surge denial; `59-QWEN-ROLLOUT.json`; independent 2+2/network/GTE readback; Wave 3 gate | Invented memory, quota/PDB mismatch, admitted fifth pod, HPA, unsafe rollout, involuntary-failure overclaim or compensation/readback failure removes only Qwen resources and blocks Wave 4 |
| 59-05-01 | QAI-03; D-07, D-08, D-13, D-24 | Unit/read-only integration | `59-05-PLAN.md → Task 1 → <verify><automated>` | NEW `router-owner-run.py`/fixtures and `59-ROUTER-OWNER-INVENTORY.json` with exact `isolated_worktree_path` | Non-absolute/out-of-allowlist/symlink/drift path, unknown symbol or dirty overlap blocks mutation; owner checkout remains untouched |
| 59-05-02 | QAI-03, QAI-05; D-07, D-08, D-18, D-21, D-25 | Unit/integration/race/failover | `59-05-PLAN.md → Task 2 → <verify><automated>` | helper-confined race suite, Redis Cluster hash-tag/fencing, same-connection `WAITAOF 1 1`, process/primary/independent-host loss and NEW `relay/pipeline_governor_test.go` | CROSSSLOT, stale token, short/wrong-connection fsync acknowledgement, action from unacknowledged epoch, third-slot, duplicate terminal/release or unsafe failover blocks route activation |
| 59-05-03 | QAI-01, QAI-05; D-05, D-18, D-24..D-26, D-29 | Integration/build/security/smoke | `59-05-PLAN.md → Task 3 → <verify><automated>` | standalone single-active Qdrant arbiter UID/private socket, same-connection AOF journal acknowledgement, active restart/primary/host-loss replay, disabled standby, credential revocation, negative bypass and sent-request ambiguity tests, helper-confined router build/activation, DB CAS, Wave 4 gate | Any direct writer, short journal acknowledgement, ambiguous INFLIGHT successor, automatic standby, lost restart journal, policy/readback failure or runtime drift restores DB/runtime/arbiter state, proves GTE and blocks Wave 5 |
| 59-06-01 | QAI-04; D-24, D-26 | Unit/integration/security | `59-06-PLAN.md → Task 1 → <verify><automated>` | isolated L7 broker/issuer install, server-TLS CA/SPKI-pinned nonce+CSR-PoP bootstrap, TokenReview live owner attestation, mTLS, RBAC and negative plaintext/replay/egress/operation probes | Any credential/egress leakage, bootstrap downgrade/replay/token logging, self-asserted owner chain, passthrough or forbidden send blocks all collection work |
| 59-06-02 | QAI-04; D-06, D-14..D-17, D-24, D-26 | Build/data integration/security | `59-06-PLAN.md → Task 2 → <verify><automated>` | digest-pinned data tool delivered by registry/import and independently resolved on runner, 500m anti-Horistic Jobs, three source-equivalent 1024d collections, and a disposable cleanup fixture with disjoint SA/Role/RoleBinding/Job, exact resourceNames, self-revoke/post-revoke denial and live-authority/replay/Qdrant negatives | Local-only/digest-unavailable image, authority hash drift, fixture identity/target overlap, excess permission, failed self-revoke/preservation, template/resource/parity/revocation failure blocks evaluation |
| 59-06-03 | QAI-05, QAI-06; D-03, D-19..D-21 | Unit/behavioral/capacity | `59-06-PLAN.md → Task 3 → <verify><automated>` | functional and quality evaluator suites | Missing probe/formula/slice/round/metric or 20% containment failure blocks acceptance run |
| 59-06-04 | QAI-04, QAI-05, QAI-06; D-17, D-19..D-21, D-24 | End-to-end/capacity | `59-06-PLAN.md → Task 4 → <verify><automated>` | functional report, quality/capacity report, PREPARED journal, Wave 5 gate | Any failed/skipped probe, regression, metric gap or titular drift blocks cutover |
| 59-07-01 | QAI-08; D-24, D-27 | Unit/install/security | `59-07-PLAN.md → Task 1 → <verify><automated>` | root fixed-operation publisher and separate unprivileged heartbeat authority with fsync and denied direct writes | Any arbitrary path/operation, non-publisher mutation or heartbeat filesystem write blocks cutover tooling |
| 59-07-02 | QAI-03, QAI-08; D-07, D-08, D-15..D-17, D-21, D-24, D-27 | Unit/fault integration | `59-07-PLAN.md → Task 2 → <verify><automated>` | cutover/consumer tooling, detached build/serving worktrees and publisher-mediated transaction fixtures | Unsafe compensation, reader overlap, serving drift or ambiguous authority state blocks preflight |
| 59-07-03 | QAI-08; D-21, D-24 | Fault/integration/read-only | `59-07-PLAN.md → Task 3 → <verify><automated>` | all-boundary compensation receipts and fresh PREPARED journal | Missing compensation or generation/source mismatch blocks execution |
| 59-07-04 | QAI-01, QAI-04, QAI-05, QAI-08; D-01, D-05, D-15..D-17, D-21, D-24 | Transactional end-to-end | `59-07-PLAN.md → Task 4 → <verify><automated>` | `59-CUTOVER-EVIDENCE.json`, Wave 6 knowledge reindex, Graphify Qwen/1024 current-query proof and independent authority readbacks | Any failure restores Graphify config/graphs then compensates to GTE; BLOCK/ROLLED_BACK cannot release Wave 7 |
| 59-08-01 | QAI-07; D-06, D-12, D-13, D-22, D-24 | Unit/build/async | `59-08-PLAN.md → Task 1 → <verify><automated>` | immutable soak Job/image delivered and independently resolved by exact ARM64 digest, original-UID and mode-bound argv-only resume fixtures | Local-only image, redispatch, wrong mode/owner/hash, shell injection, invalid state or placement blocks watchdog installation |
| 59-08-02 | QAI-05, QAI-07; D-21, D-22, D-24, D-25, D-27, D-29 | Integration/watchdog/security | `59-08-PLAN.md → Task 2 → <verify><automated>` | WAITAOF stream, Redis/arbiter host-loss, ordered cold handoff, independent rollback access and Graphify heartbeat continuity | Unacknowledged sample, reordered handoff, old-host rejoin write, stale heartbeat without clean rollback or ambiguous successor blocks dispatch |
| 59-08-03 | QAI-01, QAI-07; D-01, D-22, D-24, D-25 | Asynchronous end-to-end | `59-08-PLAN.md → Task 3 → <verify><automated>` | PREPARED-before-create nonce journal with same-connection WAITAOF failure-domain tests, API-send/CAS reconciliation, exactly one original UID, mode-conditional receipt, wave-closeout, signed handoff, Summary and 59-09 dispatch | Missing PREPARED/nonce or any duplicate/ambiguous dispatch blocks; `running` is only the post-create external-job deferral, while final autopilot/fallback closeout remains mode-bound |
| 59-09-01 | QAI-04, QAI-08; D-23..D-26 | Unit/install/crash recovery/least privilege | `59-09-PLAN.md → Task 1 → <verify><automated>` | Finalizer has no Kubernetes credential/egress; exactly one temporary digest-pinned 500m cleanup-authority Job runs outside Horistic and srv1, uses kubelet-renewed projected token with Wave0 audience, survives authority-Pod restart and srv1 outage beyond TTL, enforces UID/resourceVersion deletes; a disposable fixture proves terminal self-RoleBinding revoke while the original live authority UID/authorization is preserved for Task2; admission, WAITAOF and crash tests pass | Missing/assumed audience, authority colocated with srv1, non-renewing projected token, direct finalizer API, replacement deletion, missing fixture self-revoke/post-revoke denial, live-authority loss, excess permission, short acknowledgement or crash non-convergence blocks replay |
| 59-09-02 | QAI-04, QAI-08; D-21, D-23..D-27 | Live rollback/replay/security | `59-09-PLAN.md → Task 2 → <verify><automated>` | signed Task1 authority UID/image/node/audience/restart receipt plus terminal fixture-self-revoke and live-authority-preserved fields revalidated before one separate digest-pinned 500m anti-Horistic data replay Job; issuer owner attestation; `replay-exact`; journal-driven finalizer/authority reconciliation and actual live self-revoke; publisher-only Graphify restore | Missing/stale Task1 receipt, missing fixture/preservation proof, direct Job Qdrant path, wrong identity, leaked client/object, authority self-revoke/TTL-cleanup failure, loss/duplicate/non-idempotency or non-Qwen final state blocks retirement |
| 59-09-03 | QAI-04, QAI-05; D-14, D-16, D-17, D-21, D-23 | Read-only replay/integration | `59-09-PLAN.md → Task 3 → <verify><automated>` | dedicated replay runner, fresh authority nonces and independent live Graphify/GBrain/Obsidian readbacks | Self-produced-only evidence, stale nonce, missing live receipt, rebuild/config mutation or parity failure blocks GTE removal |
| 59-09-04 | QAI-01, QAI-02, QAI-05, QAI-08; D-01, D-05, D-21, D-23, D-24, D-30 | Destructive integration/final readback/rollout envelope | `59-09-PLAN.md → Task 4 → <verify><automated>` | retirement fault tests, desired/live GTE deletion, headroom-bound quota 4→5/CPU 2000m→2500m, rollout 0/1→1/0, serialized service updates, fifth admission/sixth denial, zero-final-surge, API/connector receipts and Wave 8 gate | Partial deletion, missing headroom/snapshot, active GTE, simultaneous surges, admitted sixth, third governor slot, leftover fifth pod, non-2+2 steady Qwen or connector failure blocks completion and restores coexistence envelope |

## Plan Verification and Wave Release

`PHASE_DIR` below is always the literal directory
`.planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s`.
Each plan's `<verification>` supplies the literal gate command. The release
order is fixed and is never inferred from table-column order:

| Plan | Wave | Pre-Summary closeout | Post-Summary defense |
|---|---:|---|---|
| 59-01 | 0 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 0` | Native blocking hooks; then Wave 1 |
| 59-02 | 1 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 1` | Native blocking hooks; then Wave 2 |
| 59-03 | 2 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 2` | Native blocking hooks; then Wave 3 |
| 59-04 | 3 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 3` | Native blocking hooks; then Wave 4 |
| 59-05 | 4 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 4` | Native blocking hooks; then Wave 5 |
| 59-06 | 5 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 5` | Native blocking hooks; then Wave 6 |
| 59-07 | 6 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 6` | Native blocking hooks; then Wave 7 |
| 59-08 | 7 | Original-UID resumer: regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 7` | Native blocking hooks; then Wave 8 |
| 59-09 | 8 | regression → active hooks → completed-parser conformance → `assert-wave-gate --wave 8` | Native blocking hooks; then final sign-off |

## Canonical Wave-Gate JSON Contract

Only these filenames are valid:

`59-WAVE-0-GATE.json`, `59-WAVE-1-GATE.json`,
`59-WAVE-2-GATE.json`, `59-WAVE-3-GATE.json`,
`59-WAVE-4-GATE.json`, `59-WAVE-5-GATE.json`,
`59-WAVE-6-GATE.json`, `59-WAVE-7-GATE.json`,
`59-WAVE-8-GATE.json`.

The soak report is exactly `59-SOAK-EVIDENCE.json`.

Every `59-WAVE-N-GATE.json` is atomically written and reread by
`assert-wave-gate`. Its strict root schema requires:

| Field | Required contract |
|---|---|
| `schema_version` | Supported exact version; no implicit/default version |
| `phase` / `wave` | Exact Phase 59 identity and integer wave matching filename/CLI |
| `phase_goal_hash` | SHA-256 of the exact frozen Phase 59 goal |
| `requirement_ids` | Complete relevant QAI/D IDs, hash-bound to the frozen source |
| `hashes` | Non-empty hashes for all consumed/produced gate artifacts |
| `identities` | Concrete host, workload, image, model, Job/UID and authority identities as applicable |
| `prestate` / `poststate` | Complete redacted state, independently comparable; equal for declared no-mutation gates |
| `invariants` | Known keys only; every value exactly `PASS` or `FAIL` |
| `receipts` | Ordered, hash-bound operation/readback receipts |
| `aliases` | Exact Router DB generation, Qdrant alias-map hash plus lock/fencing token, and consumer alias generations |
| `leases` | Active/waiting/terminal counts and lifecycle receipts |
| `rollback_target` | Concrete target, generation, hashes and executable inverse/restore identity |
| `metrics` | Finite values with provenance; Prometheus or cgroup/container fallback required |
| `independent_readback` | Separate connection/process/plane identity, timestamp and PASS |
| `redaction_scan` | PASS and zero secret/raw-corpus findings |
| `dirty_overlap_check` | PASS and zero unowned overlapping hunks |
| `status` | `PASS`, `BLOCK` or `ROLLED_BACK`; never inferred |
| `next_wave_allowed` | Derived boolean; `true` iff the complete gate is `PASS` |

Duplicate keys, unknown keys, unknown enum values, non-finite metrics, stale or
missing readback, missing hashes/identities/receipts, wrong filename/wave,
unavailable metrics without fallback, secret/raw-corpus findings, dirty
overlap, or any `UNKNOWN` marker at any depth are schema failures and exit
non-zero.

Status semantics:

- `PASS`: every invariant and receipt passes, independent readbacks agree,
  rollback/no-mutation receipt is valid, and `next_wave_allowed=true`.
- `BLOCK`: prerequisite, acceptance, readback, metric or invariant did not
  pass. Persist redacted diagnostic evidence when safe, set
  `next_wave_allowed=false`, exit non-zero and do not dispatch the successor.
- `ROLLED_BACK`: a mutation failed and compensation restored the last proven
  state. The rollback receipt is evidence of safety, not success; set
  `next_wave_allowed=false`, exit non-zero and require a fresh execution from
  the relevant preflight.
- `UNKNOWN`: prohibited. Missing knowledge is a hard failure, never a deferred
  pass or implicit default.

Mutation waves require an actual rollback/compensation receipt. Non-mutation
waves require a hash-bound no-mutation receipt proving equal prestate/poststate.

## Wave Ledger

| Wave | Required entry state | Authorized mutations | Independent readbacks | Rollback / containment | Release condition |
|---:|---|---|---|---|---|
| 0 | Separate bootstrap/fallback selection complete; one network branch and all live authorities/metrics/runner resolved | Planning evidence and frozen non-secret fixtures only; no live production mutation | Qdrant control/data-plane authority; Redis `>=7.2`, AOF primary+independent replica, same-connection `WAITAOF 1 1`; Router DB/k3s/GTE topology, metrics and runner from separate planes | Hash-bound no-mutation receipt; any unresolved live field, Redis durability shortfall or unfenceable Qdrant path BLOCK | `59-WAVE-0-GATE.json` PASS, contained secondary PASS, active hooks PASS; no autopilot doctor/parity field in Wave evidence |
| 1 | Wave 0 PASS; frozen corpus/qrels/thresholds | Pin/oracle artifacts, harden reranker, audit complete npm lock graph, clean ignored-script install, guarded ARM64 embedding/reranker image builds and content-addressed distribution | Registry/preload manifests, every-node digest availability, model/image/package/full-lock hashes, zero lifecycle children, CPU/offline startup, CPU-only ORT providers, offline oracle/rootless processes | No production route mutation; any required lifecycle script or offline startup failure BLOCKs for replan; otherwise discard/rebuild candidate artifacts | `59-WAVE-1-GATE.json` PASS plus secondary/hooks |
| 2 | Wave 1 PASS; immutable artifacts; Wave0 observed GTE HPA 2–4 | Patch/apply/read back GTE HPA source/live/recovery 2–2 before anchor; create distinct Router DB/Qdrant backups, pinned GTE recovery manifest/artifact retention and cold isolated restores | Versioned/live/recovery HPA 2–2, preserved GTE model/Service/aliases, backup hashes, empty-cache pinned workload and isolated DB/Qdrant restore | Cold-restore-tested GTE anchor at 2–2; no Qwen route cutover | `59-WAVE-2-GATE.json` PASS plus secondary/hooks |
| 3 | Wave 2 PASS and rollback anchor PASS | Apply private `qwen-production`; embedding 2 and reranker 1→2 under coexistence quota pods=4/CPU=2000m, rollout 0/1 and PDB minAvailable=1 | API-server objects, offline digest/provider/model identity, pod resources/readiness, representative aggregate 2+2 metrics/headroom, fifth-pod/simultaneous-surge denial, voluntary-disruption floor 1+1, positive/negative network probes, unchanged GTE | Remove only Qwen resources and prove incumbent path; failed rollout is not PASS | `59-WAVE-3-GATE.json` PASS with exact 2+2 at 500m each and no fifth model pod |
| 4 | Wave 3 PASS; exact dedicated `isolated_worktree_path` frozen and helper-verified | Persistent Redis lifecycle with cluster hash-tag/fencing and same-connection AOF acknowledgement; standalone alias arbiter; distinct Router DB Wave4 prestate, catalog CAS and tested router activation | Helper path/HEAD/drift proof, Redis process/primary/independent-host loss from acknowledged offsets, arbiter journal/restart/ambiguity proof, DB generation/rows, active SHA/image/routes/aliases, GTE/Qwen smokes | Owner checkout and immutable Wave2 DB anchor untouched; short acknowledgement or ambiguous INFLIGHT remains fail-closed; compensating Wave4 DB/runtime restore and GTE smoke | `59-WAVE-4-GATE.json` PASS plus contained secondary/hooks |
| 5 | Wave 4 PASS; GTE anchor and Qwen runtime healthy | Install sole-native-credential L7 data broker plus separate issuer; create/fill Qwen collections via private mTLS+TokenReview clients; build/freeze data-tool image; server-dry-run then apply/read back dedicated replay namespace/admission/SA/RBAC/issuer binding without dispatching the Job; PREPARED journal | No passthrough; live token→Pod→owner Job attestation; broker/issuer least privilege; fixed operation/name/schema allowlist; runner/SA/Job/Pod/image identity; live allowed/forbidden admission matrix; aliases/deletes/GTE/admin/direct-egress denied; TTL/revocation; 500m/anti-Horistic replay template | Revoke current certificate/token/authorization before containment; broker/issuer remain isolated; remove/repair only transaction-owned Qwen targets and replay prerequisites; titular route unchanged | `59-WAVE-5-GATE.json` PASS, all temporary clients revoked, replay namespace/admission/identity live and hash-frozen, image/template frozen but not dispatched, and all acceptance gates PASS |
| 6 | Wave 5 PASS; PREPARED journal; generations current; zero leases/writers after drain | CAS Router DB; alias swap via arbiter; move consumers; install root fixed-operation Graphify publisher as sole mutator plus unprivileged heartbeat client; publish Qwen through publisher only | Separate authority readbacks, serving path/HEAD, publisher peer/fixed-operation/sole-mutator evidence, executor+heartbeat-client negative writes, publish/restore/file+directory-fsync and heartbeat-current receipts, actual status/query | Reverse compensation uses publisher restore only; executor/client cannot mutate serving files; arbiter/Graphify ambiguity remains drained BLOCK | `59-WAVE-6-GATE.json` PASS with Qwen titular, Graphify Qwen/1024 serving authority and rollback-ready GTE |
| 7 | Wave 6 PASS; Qwen titular; exact 2+2; GTE anchor intact | Dispatch one external 500m soak Job plus independent srv1 watchdog/finalizer, or reattach original identities; append only same-connection `WAITAOF 1 1`-confirmed events; run only root-broker hash-bound Graphify metadata heartbeats ≤12h | UID lineage, Redis primary/host-loss, fenced/durable samples, stale-heartbeat active-arbiter crash/host-loss branches, signed rollback access/cold-start receipt, expected artifacts, exact argv hashes, metrics, serving HEAD, unchanged graph bytes, active writer exclusion and actual fresh status/query | Clean journal performs bounded same-active restart or reconciled cold handoff then automatic GTE compensation; ambiguous INFLIGHT remains drained/BLOCK; finalizer writes terminal state | Initial `external_job_waiting`; original UID becomes completed-unverified; only autopilot-signed or fallback-confirmed exact chain releases Wave 7 after ≥72h |
| 8 | Wave 7 PASS from original UID/hooks; Qwen titular; archives retained | Install crash-durable finalizer/authority; productive round trip/replay; retire GTE; if headroom passes, transition quota 4→5 and strategies 0/1→1/0; fault-test serialized embedding then reranker rollouts | Authority lifecycle; replay cleanup; zero GTE; CPU+largest-pod-memory+system-reserve headroom; PDB; one fifth admitted, sixth denied, simultaneous-surge race, governor remains max two and final live count returns to 2+2 | Compensate to last proven state; retain GTE artifacts; remove temporary Jobs; failed envelope transition restores quota 4/2000m and rollout 0/1; 1+1 remains degraded only | `59-WAVE-8-GATE.json` PASS proving zero replay/authority objects/credentials, GTE removal, Graphify Qwen 1024, post-GTE max 5/2500m and steady Qwen 2+2/2000m |

## Wave 7 Original-UID Async Contract

Plan 59-08 Task 3 is terminal. It must atomically create or reuse
`.planning/async-jobs/phase-59-qwen-soak.json` with:

- `plan_id=59-08`, initial durable `status=PREPARED` with unique nonce,
  template/image/runner hashes persisted by file fsync→rename→parent fsync
  plus same-connection Redis `WAITAOF 1 1` before Kubernetes create;
- only after create or nonce-based reconciliation of an API-send/CAS crash,
  CAS to `status=running`, `result=external_job_waiting` with the one original
  Job UID/resourceVersion;
- cluster, namespace, Job name, original Job UID/resourceVersion and append-only Pod UID lineage;
- `redispatch_count=0`;
- immutable image/script/config hashes and Qwen/GTE identities;
- `expected_artifacts` with path, schema/hash and producer identity;
- exact argv-only `verification_argv_chain` plus `verification_chain_sha256`;
- exact argv-only `resume_argv` plus `resume_argv_sha256`;
- fixed GSD-compatible commands: `verification_command` invokes the versioned
  wrapper's `resume-fallback` for completed-unverified; `resume_command` invokes
  only `reconcile-failed-fallback` for failed/cancelled/timeout and cannot
  redispatch. Both bind manifest/hash; metacharacters/other executables fail;
- frozen `executor_mode` and append-only transition lineage;
- for autopilot, combined bootstrap/skill-doctor receipt plus signed autonomous
  resumer/handoff identities; for fallback, bootstrap-only receipt and explicit
  no-autopilot-ownership proof, with combined receipt forbidden.

If the manifest exists, execution reattaches only its original Job UID.
Missing, duplicate, deleted/recreated or identity-mismatched Jobs fail.
Replacement Pods are accepted only in the append-only lineage and cannot reset
elapsed time; there is no second-Job redispatch path. A separately fenced srv1
watchdog must remain active against the durable heartbeat stream.

The initial task returns the literal `external_job_waiting` and performs no
post-wait work. A signed least-privilege finalizer observes only the original
UID and atomically transitions `running` to `completed-unverified` (or a
terminal failure) when the Job ends. It cannot create Jobs, alter expected
artifacts or execute arbitrary commands. The frozen exact argv chain is:

1. reattach the original Job UID with `--require-original-uid`,
   `--require-job-pod-lineage` and `--forbid-redispatch`;
2. collect durable stream-backed `59-SOAK-EVIDENCE.json`;
3. verify the independent watchdog receipt, collector fencing and no stale heartbeat;
4. verify at least 72 continuous hours, immutable Graphify serving realpath/HEAD,
   active writer exclusion, ≤12h heartbeat lineage, unchanged graph byte hash,
   fresh/commit-current actual status/query, metrics fallback, exact 2+2 and
   zero leaked leases;
5. run exactly `python3 scripts/embeddings-bench/phase59-wave-closeout.py
   --wave 7 --phase-dir
   .planning/workstreams/qwen-local-ai/phases/59-qwen3-embedding-e-rerank-podman-para-k3s`,
   which executes contained regression → active hooks → completed-parser conformance → final Gate 7 assertion
   and rejects any missing, reordered or nonzero receipt.

Only that resumed primary → wave-closeout → final-closeout
chain can release Wave 7. With `executor_mode=autopilot`, a separately signed
resumer validates the combined receipt, runs the exact argv chain, atomically
marks `verified`, then makes one idempotent same-root Codex handoff whose sole
prompt is `$gsd-execute-autopilot --resume --ws qwen-local-ai`. Closeout
requires its task/run ID, `59-08-SUMMARY.md`, Phase59 reclassification and
Plan59-09 dispatch receipt. With `executor_mode=execute-phase-fallback`, the
combined receipt is forbidden, autonomous resumer is disabled and the GSD
core's human confirmation remains mandatory. Changing mode after Wave 0 is
forbidden.

Fallback reconciliation enters `$gsd-resume-work --ws qwen-local-ai`. After
human confirmation, the installed core runs `verification_command`;
`resume-fallback` revalidates executor lock/mode/manifest/hash and executes
only the stored argv. It marks `verified` and returns to the core, which must
create `59-08-SUMMARY.md` and release Plan59-09. Re-running is idempotent and
cannot redispatch compute.

## Resource, Build and Metrics Assertions

- Every normal Qwen runtime container has
  `resources.requests.cpu=500m` and `resources.limits.cpu=500m`.
- Permanent runtime is exactly two embedding pods plus two reranker pods:
  `2 × 500m + 2 × 500m = 2000m`.
- Degraded floor is one embedding plus one reranker (`1000m`) only while
  recovering; it cannot satisfy a wave gate.
- During GTE coexistence, quota is four model pods/`2000m` and rollout is
  `maxSurge=0,maxUnavailable=1`. After GTE retirement and measured headroom,
  quota is five/`2500m` and rollout is `maxSurge=1,maxUnavailable=0`; only one
  service rolls at a time, the sixth pod is denied, and the fifth must be gone
  before PASS. No Qwen HPA is accepted.
- Evaluation, soak and Wave 8 replay Jobs request/limit exactly `500m`, permit only one active
  Job, use the frozen external-runner selector and explicit anti-Horistic
  placement. The replay Job also requires the Wave 5 digest-pinned data-tool
  image, projected broker-audience token, full Job/Pod lineage and
  independent journal-driven finalizer cleanup. A Job observed on Horistic
  fails its task and wave.
- Builds, image builds, broad rebuilds and heavy suites run only after the
  builds doctor passes and only through the canonical srv1 20%-of-total-host
  CPU containment (`/home/ubuntu/.local/bin/omni srv1-ops resources run builds --` or the router's
  `./scripts/podman-admin.sh profile-run builds --` / build wrapper).
- Runtime 500m limits do not prove build containment, and the build profile
  does not replace k3s requests/limits.
- Metrics are mandatory. Prefer Prometheus; if unavailable, use recorded
  cgroup/container fallback with finite CPU/RSS/restart/OOM/latency/queue
  values and provenance. If neither source works, status is BLOCK.

## Source-Grounded Requirement and Decision Coverage

| ID | Source-grounded behavior | Planned proof / terminal gate |
|---|---|---|
| QAI-01 | Preserve GTE identities/rollback safety through cutover/soak, then prove final removal only after all gates | Waves 0, 2, 4, 6, 7; final zero-object readback in Wave 8 |
| QAI-02 | ARM64 private Qwen at 500m per pod; steady 4/2000m, degraded floor 2/1000m, one post-GTE rollout surge to 5/2500m, no HPA/hostNetwork | Wave 3 coexistence quota/PDB/2+2 readback and Wave 8 fifth-admission/sixth-denial/zero-final-surge proof |
| QAI-03 | At most two complete persistent pipelines with exact terminal release | Redis race/fault tests, Wave 4 lifecycle and Wave 6 drain/readback |
| QAI-04 | Separate reproducible 1024d/Cosine collections and deterministic IDs | Waves 5–6 plus Wave 8 broker-controlled replay and independent readback parity |
| QAI-05 | Health, batch, dimension, norm, rerank, queue, failures, reachability, cutover and rollback smokes | Task suites and evidence across Waves 1–8 |
| QAI-06 | Frozen paired corpus/qrels and non-regressing quality/capacity | Wave 0 freeze, oracle, Wave 5 reports with ≥5 rounds |
| QAI-07 | Continuous ≥72h Qwen-titular soak without OOM/starvation or unobserved monitor loss | Original Job UID plus Pod lineage, durable stream, independent watchdog, `59-SOAK-EVIDENCE.json` and Wave 7 gate |
| QAI-08 | Transactional compensation, productive round trip and restore/replay before retirement | Waves 2, 6 and final Wave 8 drill/reconciliation |
| D-01 | Qwen is titular at phase end; GTE remains immutable and available as rollback until the final retirement gate | Wave 6 Qwen titular readback, Wave 7 rollback-ready evidence, Wave 8 actual GTE removal |
| D-02 | Embedding uses exact `janni-t/qwen3-embedding-0.6b-int8-tei-onnx` revision in TEI OrtBackend/ONNX with embedded INT8 model | Wave 1 artifact/model hashes and Wave 3 live workload identity |
| D-03 | Pooling is frozen by last-token-vs-mean A/B against official FP16, with normative last-token preference and 1024d normalized production output | Wave 1 blinded oracle plus Wave 5 instruction/ranking acceptance |
| D-04 | Reranker uses exact `onnx-community/Qwen3-Reranker-0.6B-ONNX` revision in a dedicated HTTP ONNX service, not TEI | Wave 1 service/image lock, Wave 3 private workload and Wave 4 `/v1/rerank` readback |
| D-05 | Exact Qwen aliases are distinct; GTE aliases are never silently remapped | Catalog tests and per-wave Router/Qdrant/consumer alias maps |
| D-06 | Images, models, lockfiles and build bases are revision/digest pinned and ARM64-validated; registry/import delivery plus target-runner pull/inspect is required; `latest`/`main` block | Wave 1 lock/SBOM/platform evidence and Waves 1/5/7 target-runner digest readbacks |
| D-07 | Redis persists `QUEUED→EMBEDDING→VECTOR_SEARCH→RERANK→COMPLETED` plus FAILED/CANCELLED/EXPIRED | Wave 4 state-machine/race/restart evidence |
| D-08 | At most two complete pipelines hold leases through the full cycle; continuations have priority; terminal release is idempotent; standalone embedding is separate | Wave 4 helper-confined race/fault tests and Wave 6/7 lease readbacks |
| D-09 | Permanent Qwen runtime is exactly 2 embedding + 2 reranker pods, each request=limit=500m | Wave 3 manifest/live readback and Waves 6–8 continuity |
| D-10 | Reranker rolls out 1→2 after warmup/sizing; final 2+2 is fixed and Qwen HPA 2–4 is out of scope | Wave 3 one-pod metrics then exact two-pod readback; HPA absence checks |
| D-11 | Qwen uses a dedicated private namespace with quota, Pod Security, proven NetworkPolicy, no hostNetwork and router-only Services/NodePorts | Server dry-run, policy/CNI positive-negative probes and live object readback |
| D-12 | Wave 0 observes incumbent GTE HPA 2–4; Wave 2 deliberately transitions source/live/recovery to 2–2 before anchor, preserving model/Service/alias identity; build/reindex/oracle/soak Jobs that would consume the fifth slot run outside Horistic at exactly 500m | Wave 0 prestate plus Wave 2 versioned/apply/readback/recovery 2–2 receipts and Waves 1/5/7 Job runner/node/resource receipts |
| D-13 | Redis governor and Kubernetes controls are complementary; absent Metrics API requires Prometheus or cgroup/container evidence and never bypass | Waves 3–8 queue/quota/resource metrics with unavailable-source BLOCK |
| D-14 | Qwen is 1024d and GTE 768d; padding, truncation or mixed vector spaces are forbidden | Wave 5 schema/signature tests, Wave 6 Graphify reindex and Wave 8 replay readbacks |
| D-15 | Wave 0 resolves Qdrant endpoint/version/auth/storage/backups/aliases/collections before any mutation; `UNKNOWN` blocks | `59-AUTHORITY-INVENTORY.json`, `59-GTE-PRESTATE.json` and Gate 0 |
| D-16 | Exact Qwen physical collections are `gbrain_qwen3_1024_v1`, `obsidian_qwen3_1024_v1`, `graphify_qwen3_1024_v1`, Cosine; GTE collections remain immutable/recoverable | Wave 5 allowlist/schema readback and Wave 8 retained snapshot proof |
| D-17 | GTE and Qwen indexing uses the same frozen source, chunking, logical IDs, high-water marks and checksums | Wave 5 dual-index parity, Wave 6 Graphify reindex and Wave 8 replay reconciliation |
| D-18 | Reranker fixes left padding, suffix preservation, truncation budget, bounded queue, TTL, cancellation, redaction, shutdown and single/batch scoring at batch1/context512/max20 | Wave 1 exact Node test script and hardening evidence; Wave 4/5 route/function probes |
| D-19 | Embedding gate applies instruction only to queries, verifies documents without instruction, 1024d/norm, batch1/4 cosine ≥0.9999, FP16 oracle/ranking, with thresholds frozen in Wave 0 | Wave 0 freeze, Wave 1 oracle and Wave 5 functional evidence |
| D-20 | Frozen PT-BR technical/code qrels require non-regressing Recall@20/nDCG@10 and ≥5 warm rounds with CPU-seconds ≤1.05× GTE | `59-EVAL-FREEZE.json` and Wave 5 paired quality/capacity report |
| D-21 | Cutover drains admission/leases/writers, CASes Router DB, fences atomic Qdrant alias actions, independently reads back and conditionally compensates | Wave 6 all-boundary/lock-loss fault evidence and committed cutover receipts |
| D-22 | Soak is ≥72 continuous hours with Qwen titular and GTE rollback-ready; independent watchdog auto-rolls back; async resume reuses original Job UID/Pod lineage without redispatch | Wave 7 durable stream/watchdog/manifest evidence, gate, contained regression and active hooks |
| D-23 | GTE retirement requires soak PASS and productive Qwen→GTE→Qwen drill with both smokes, restore/replay and zero loss/duplicates; snapshots remain | Wave 8 drill/reconciliation and final zero-workload readback |
| D-24 | Every wave ends in canonical fail-closed `59-WAVE-N-GATE.json` with hashes, pre/post readbacks, PASS/FAIL invariants, receipts, aliases, leases, rollback target and derived `next_wave_allowed`; missing/UNKNOWN metrics/evidence never pass | Strict Wave 0 CLI fixtures and canonical Gates 0–8 |
| D-25 | Every safety write uses Redis `>=7.2`, AOF primary+independent replica and same-connection `WAITAOF 1 1` before external effect/slot reuse; weaker acknowledgements do not pass | Wave 0 capability/topology gate; Wave 4 process/primary/host-loss governor+arbiter tests; Wave 7 durable stream/host-loss tests; Wave 8 replay-journal same-connection, short-ack, wrong-connection, primary-loss and independent-host-loss tests |
| D-26 | Qdrant alias control-plane belongs only to alias arbiter; a no-passthrough L7 data broker is sole native data credential/egress and Jobs have none. A separate issuer uses CA/SPKI-pinned server TLS, nonce+CSR PoP, then independently TokenReviews and reads live Pod→owner Job before signing the broker-mTLS certificate; fixed Qwen operations bind runner/namespace/SA/Job UID/resourceVersion/Pod UID/image/nonce/TTL and deny aliases/deletes/GTE/admin | Wave 0 transport/permission inventory; Wave 5 plaintext/replay/wrong-cert/token-logging plus broker/issuer RBAC/owner/network/TTL/revocation tests and delivered replay image; Wave 8 AOF journal, independent finalizer crash recovery, UID deletion and negative TokenReview/broker/network; Waves 6/8 arbiter-only aliases |
| D-27 | Graphify has one root fixed-operation UDS publisher as sole serving mutator, including `heartbeat-current`; the no-argv heartbeat is an unprivileged client without serving `ReadWritePaths`, and executor/users/client/hooks/watchdog cannot directly alter bytes or metadata | Wave 6 publisher+client installer/systemd/peer/path/operation/fsync/utimensat/positive-negative tests; Wave 7 continuity; Wave 8 publisher-only restore drill |
| D-28 | Reranker lock graph is fully audited and installed with `npm ci --ignore-scripts`; zero lifecycle child and CPU/offline startup are mandatory | Wave 1 transitive lock fixtures, clean ignored-script install observation, offline startup, image audit and gate |
| D-29 | Arbiter outage uses same-active restart first; clean cold handoff requires revoke old credential, block old egress/socket/token, negative old-host/partition-heal probe, then issue new/start standby; ambiguous INFLIGHT stays drained/BLOCK | Waves 4/7 ordered-handoff permutation tests, old-host rejoin denial, clean compensation and ambiguous containment |
| D-30 | Qwen model envelope is steady 4/2000m, degraded floor 2/1000m, transient maximum 5/2500m only as serialized post-GTE rollout surge; PDB preserves one per service, quota denies the sixth, governor remains max two and no fifth survives PASS | Wave 3 coexistence quota/rollout/PDB/fifth denial; Wave 8 headroom gate, quota/strategy transition, simultaneous-surge race, sixth denial, failed-transition compensation and zero-final-surge readback |

## Final Gate: Actual Removal and Graphify 1024

`59-WAVE-8-GATE.json` cannot PASS on intent, scale target or documentation
alone. It must bind and independently verify all of the following:

- Wave 7 PASS and original soak UID lineage;
- productive drained/CAS Qwen→GTE→Qwen round trip;
- zero missing writes, zero conflicting duplicates and idempotent second replay;
- final Qwen titular state, zero leases, healthy writers and exact 2+2 at 500m;
- `.planning/config.json` and live Graphify both use
  `embedding-qwen3-0.6b-int8-1024-v1` with `dimensions=1024`;
- immutable Wave 6 `graphify_source_commit`, its root-owned detached serving
  worktree, active writer exclusion, config/index byte hashes, ≤12h heartbeat
  lineage and successful actual fresh/commit-current query without a Wave 8 rebuild;
- GBrain, Obsidian and Graphify source/count/checksum/high-water parity from
  independent file/DB/index planes;
- `59-RETIREMENT-EVIDENCE.json` with `workloads_removed=true`;
- zero live matching GTE Deployments, StatefulSets, DaemonSets, Jobs,
  CronJobs, Pods and HPA in `ebeddings-local`, and no production-default route
  or endpoint backed by GTE;
- retained GTE snapshots, Router DB/Qdrant exports and executable restore docs;
- redacted Obsidian/GBrain closeout receipts read back through authoritative
  connectors.

Any partial plane, scaled-but-existing controller, stale Graphify index,
dimension/model disagreement, missing metric or snapshot, or non-zero GTE
workload/pod count sets BLOCK and prevents phase completion.

## Sign-Off Checklist

- [ ] All 30 task `<automated>` commands exited zero and every acceptance
      criterion has corresponding behavioral evidence.
- [ ] All nine plan verifications passed.
- [ ] `59-WAVE-0-GATE.json` through `59-WAVE-8-GATE.json` use canonical
      hyphenated names, strict schema and PASS status.
- [ ] Self-contained secondary `bash scripts/gsd-wave-regression.sh` passed
      before every active hook/parser-conformance/final gate and proved srv1
      20% containment.
- [ ] Every active `execute:wave:post` hook ran after regression and before
      completed-producer parser conformance/final gate; every blocking or
      `onError=halt` result passed.
- [ ] If autopilot was selected, `59-AUTOPILOT-BOOTSTRAP.md` validated the
      post-planning bundle, dynamic final execution commit, clean dedicated
      srv1 worktree, plan visibility, Graphify freshness/query and doctor
      before invocation. If doctor remained blocked, local execute-phase was
      used without adding bootstrap state to Wave 0.
- [ ] Every runtime pod is 500m/500m and final Qwen state is exactly 2+2
      (`2000m`); the Wave8 cleanup-authority and data-replay Jobs were each
      temporary 500m, scheduled outside Horistic, and are zero after Gate 8.
      (2000m total).
- [ ] Every evaluation/soak/replay Job is exactly 500m, external and not on Horistic;
      the replay Job uses the frozen digest and leaves zero Job/Pod/token state.
- [ ] Every build/heavy suite/rebuild has a passing doctor and recorded 20%
      containment.
- [ ] Redis live authority is `>=7.2` with AOF primary+independent replica;
      pipeline, alias-arbiter and soak safety writes each have same-connection
      `WAITAOF 1 1` receipts plus process/primary/host-loss evidence.
- [ ] The complete reranker npm lock graph passed immutable
      origin/integrity/lifecycle audit; clean `npm ci --ignore-scripts`
      observed zero lifecycle children and the resulting CPU/offline runtime
      started successfully.
- [ ] Metrics have finite values and Prometheus or cgroup/container provenance;
      no required metric is unavailable.
- [ ] Wave 7 used one original Job UID, complete Pod lineage, zero redispatches,
      independent watchdog and at least 72 continuous hours before PASS.
- [ ] Rollback/compensation receipts exist for every mutation wave; no
      ROLLED_BACK result was treated as PASS.
- [ ] Qdrant alias writes came only from the alias arbiter; a separate L7 data
      broker was the sole native data-management credential/egress holder,
      exposed no passthrough, and a separate least-privilege issuer proved live
      TokenReview→Pod UID→ownerReference→Job UID/resourceVersion→runner/image
      before signing private-mTLS clients. The Wave 8 replay ran in one frozen
      500m anti-Horistic Job; aliases/deletes/GTE/admin were denied before send;
      every temporary client was revoked, exact Job/Pods were deleted by UID,
      and TokenReview/broker/network negatives passed.
- [ ] Stale-heartbeat tests covered arbiter process/host loss: clean cold
      handoff revoked/blocked/negative-probed the old host (including rejoin)
      before issuing the new generation and compensating to GTE; ambiguous
      INFLIGHT remained drained/BLOCK.
- [ ] Quality/capacity, functional, failure, private-network and replay gates
      passed from frozen inputs.
- [ ] Graphify repo/live model and dimension are Qwen/1024; the Wave 6
      root-owned serving worktree remains pinned to `graphify_source_commit`,
      writer-excluded, graph-byte stable and actual-reader fresh/queryable
      through the ≤12h no-argv heartbeat client without Wave 8 rebuild; that
      client has no serving filesystem write authority and requests only
      publisher `heartbeat-current`. The fixed-operation root publisher is the
      sole byte/metadata mutator for publish/restore/heartbeat; executor/client/
      direct mutations are denied, and all knowledge consumers have independent
      parity readbacks.
- [ ] `59-RETIREMENT-EVIDENCE.json` proves actual zero GTE workload/controller/
      pod state while snapshots and restore material remain retained.
- [ ] Final redaction, dirty-overlap and authoritative connector readbacks pass.
- [ ] Real Wave 0 completion exists only in `59-WAVE-0-GATE.json` and mutable
      `STATE.md`; this signed validation strategy was never edited to fabricate
      execution status.

**Execution sign-off:** pending automated evidence
