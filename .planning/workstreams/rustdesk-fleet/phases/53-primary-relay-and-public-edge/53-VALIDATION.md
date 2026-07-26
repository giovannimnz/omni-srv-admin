---
phase: 53
slug: primary-relay-and-public-edge
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-22
updated: 2026-07-26
---

# Phase 53 — Validation Strategy

> Nyquist contract for the RustDesk OSS primary, translated public edge,
> source-bound authority, explicit owner checkpoint, single 05F live
> transaction and read-only 06 closeout. The 05D broad diagnostic result is
> `51 failed, 145 passed, 1 xfailed`; 05D2T/A/B/C close topology, semantics,
> transaction/binding, truthful SCP-01 ledger ownership and source sealing
> before authority. The 05D2C selector is currently green at 13 passed, but
> after the Phase 51 ledger repair the raw broad suite still contains the
> canonical nine legacy Gate-B refusals. 05D2C therefore requires a closed
> current lane plus an independently classified exact-nine legacy lane; it
> never treats the raw result as green or rewrites historical Gate A evidence.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `pytest` plus shell/PowerShell external probes |
| **Config file** | Existing `modules/rustdesk-fleet/tests`; Phase 53 test module is Wave 0 |
| **05D edge/backend/installer selector** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'edge_contract or translated_edge or hbbs_relay_announcement or phase53_server_installer or installer_tamper or runtime_installed_hbbs or read_only_backend or apply_backend'` |
| **05D2T topology selector** | `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_topology.py --disable-warnings` |
| **05D2A semantic selector** | `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py --disable-warnings` |
| **05D2B transaction/binding selector** | `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'cli_mode or stage_full or journal or immutable_rollback or restore_production or migration_handoff or binding_chain or zero_side_effect' --disable-warnings` |
| **05D2C planning-ancestor prerequisite** | Task 53-05D2C-01 requires ROADMAP clean in index/worktree, reads only `git show HEAD:.../ROADMAP.md`, captures its last path commit and proves Phase 51 omits SCP-01 while Phase 55 owns it; the executor does not modify `ROADMAP.md` |
| **05D2C Phase 51 ledger prerequisite** | `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase51_contracts.py -k 'requirement_ledger' --disable-warnings` |
| **05D2C execution-source selector** | `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'execution_source or source_scope or dirty_scope or source_tree_digest' --disable-warnings` |
| **05D2C current broad lane** | Literal governed command in Task 53-05D2C-03 runs all RustDesk tests with exactly nine explicit `--deselect` nodeids and temporary JUnit/output; pytest rc is 0, read-only `lane_current()` validates zero failures/errors/regular skips plus exact EXPECTED_XFAILS/count and `frozen_verifier: PASS`, and terminal count is exactly `9 deselected` |
| **05D2C legacy exact-nine lane** | Literal governed command in Task 53-05D2C-03 runs exactly the same nine nodeids into `/tmp` JUnit, requires pytest rc 1 and calls read-only `lane_legacy()` to prove nine failures, eight managed-source drift and one local-only/no-network CLI case |
| **05D2C post-seal Git-object structure** | Task 53-05D2C-03 derives SOURCE=`HEAD^` and SUMMARY=`HEAD`, uses unfiltered `git diff-tree` for the exact six-path/summary-only sets, proves direct parentage, recalculates ROADMAP's last path commit and checks it plus 05D/05D2T/05D2A/05D2B ancestry with `git merge-base --is-ancestor` |
| **05D2C post-seal binding recomputation** | Task 53-05D2C-03 passes the JSON payload through `validate_execution_source_scope_payload`, then recomputes `compute_execution_source_binding` at SOURCE and HEAD over the returned exact 33 paths, compares digest/blobs/paths and calls `require_clean_execution_source` |
| **Read-only authority command** | `omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode plan --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json` |
| **Live apply command** | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 ADMITTED_PHASE53=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json --owner-approval modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json` |
| **Estimated runtime** | task selectors below 30 seconds; current/legacy governed lanes replace the raw broad gate; live 05F is separately bounded; 06 is read-only |

## Sampling Rate

- **After 05D code tasks:** run only the governed edge/backend selector.
- **After 05D2T:** run read-only topology discovery; drift blocks without a new checkpoint.
- **After 05D2A:** require the complete Phase 53 test file to exit zero.
- **After 05D2B:** run transaction/binding adversarial selectors.
- **Before 05D2C seal:** require ROADMAP clean in index/worktree, read its
  ownership only from `git show HEAD:...`, capture its last path commit and
  verify the committed planning ancestor assigns SCP-01 only to Phase 55
  without editing `ROADMAP.md`; then run, in order, the focused Phase 51
  ledger contracts and the 05D2C execution-source selector. Then run the
  current broad lane with exactly nine explicit deselections and the legacy
  exact-nine lane with expected rc 1 plus read-only `lane_legacy()` JUnit
  classification. Read-only `lane_current()` must prove zero
  failures/errors/regular skips, exact EXPECTED_XFAILS/count and
  `frozen_verifier: PASS`, while the terminal output proves exactly nine and
  no other deselections. The legacy lane must contain only the canonical eight
  drift refusals plus one local-only/no-network CLI refusal. All commands run
  under the `builds` governor before the clean closed source scope and six
  explicit pathspecs may be sealed.
- **After 05D2C seal:** use unfiltered Git-object checks over `HEAD^` and
  `HEAD`, not path-filtered worktree diffs: prove exact six-path source and
  summary-only commit sets, direct parentage, ROADMAP plus predecessor
  ancestry, validated-scope identical 33-path bindings at SOURCE/HEAD and a
  clean execution source.
- **After each code-producing wave:** use focused selectors first and, where a
  broad gate is required, the closed current/legacy lane contract through the
  `builds` profile; never interpret a raw broad suite as green.
- **Before 05E authority:** require the final 05D2C
  `execution_source_commit`, prove it includes 05D as ancestor, require the
  exact execution-source allowlist including the hbbs Quadlet, and reject
  source-scope dirt.
- **Before 05F mutation:** require a new process plus current source tree,
  admission, prestate, typed confirmations and unexpired owner approval.
- **Before 06 writes:** invoke only the strict explicit-path
  `verify-phase53-binding-chain.py` preflight. It requires independent
  `status: passed`, proves the evidence-only live parent, direct summary-only
  descendant and later verification ancestry, checks `git show` manifest
  bytes, and recomputes the allowlisted Git aggregate at source/live/current.
- **Wave chain:** `05D(w7) → 05D2T(w8) → 05D2A(w9) → 05D2B(w10) → 05D2C(w11) → 05E(w12 checkpoint) → 05F(w13 live) → 06(w14 read-only)`.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 53-01-01 | 01 | 0 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53-CONTRACT | Strict schemas, sockets/resources and stored-verdict rejection | unit/contract | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'contract or schema or mutation'` | ✅ | ✅ green |
| 53-01-02 | 01 | 0 | SRV-02, OPS-01 | T53-SECRET, T53-EXEC | Secret surfaces and ambiguous live stages fail closed | unit/security | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'secret or redact or auth or live_flag or stage_receipt'` | ✅ | ✅ green |
| 53-02-01 | 02 | 1 | SRV-02 | T53-RUNTIME | Rootless digest-pinned Quadlets and aggregate cgroup budget | unit/integration | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'quadlet or runtime or cgroup'` | ✅ | ✅ green |
| 53-02-02 | 02 | 1 | SRV-06 | T53-IDENTITY, T53-ROLLBACK-SRV | Tmpfs hydration, fingerprint/state/log preservation and terminal rollback | integration/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'identity or sqlite or rollback or linger or log_bound'` | ✅ | ✅ green |
| 53-03-01 | 03 | 2 | OPS-01 | T53-API-AUTH, T53-API-LEAK, T53-APACHE | API auth/redaction/readiness and reversible Apache publication | unit/integration | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'ops_api or apache or readiness'` | ✅ | ✅ green |
| 53-04-01 | 04 | 3 | SRV-03, SRV-04 | T53-EDGE | nft/OCI effective policy permits only approved public ports | unit/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'nft or oci or listener or ipv6'` | ✅ | ✅ green |
| 53-04-02 | 04 | 3 | SRV-04 | T53-DNS, T53-PROBE | DNS-last CAS and two-origin TCP/UDP correlation | unit/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'dns or cloudflare or address or external_probe or udp'` | ✅ | ✅ green |
| 53-05D-01 | 05D | 7 | SRV-02, SRV-03, SRV-04 | T53D-EDGE, T53D-RELAY, T53D-INSTALL | Sole translated-edge contract, exact hbbs relay announcement and canonical installer/runtime form with tamper/mismatch rejection | unit/contract | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'edge_contract or translated_edge or hbbs_relay_announcement or phase53_server_installer or installer_tamper or runtime_installed_hbbs or apply_edge_contract or probe_edge_contract'` | ❌ W0 | ⬜ pending |
| 53-05D-02 | 05D | 7 | SRV-02, OPS-01 | T53D-CAPABILITY | Capability-disjoint backend factories and strict provider manifest | unit/security | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'read_only_backend or apply_backend or provider_manifest'` | ❌ W0 | ⬜ pending |
| 53-05D2T-01/02 | 05D2T | 8 | SRV-03, SRV-04 | T53T-SPOOF, T53T-ROUTE, T53T-REPLAY | Exact read-only VNIC/edge/backend/DRG/return-path proof; stale OperationPlan rejected | unit/read-only | Topology selector plus literal discovery command in 05D2T | ❌ W0 | ⬜ pending |
| 53-05D2A-01/02 | 05D2A | 9 | SRV-02, SRV-03, SRV-04, OPS-01 | T53A-DIRECT, T53A-NAT, T53A-DNS, T53A-API | DNAT/forward/backend/DNS/probe/ops/validator semantic reconciliation | unit/integration | Complete `test_phase53_primary_edge.py` command above | ❌ W0 | ⬜ pending |
| 53-05D2B-01/02 | 05D2B | 10 | SRV-03, SRV-04, SRV-06, OPS-01 | T53B-CAP, T53B-ROLL, T53B-BIND, T53B-MIG | Full runner, distinct journals, binding checker and non-executable migration | unit/CLI/adversarial | Transaction/binding selector above | ❌ W0 | ⬜ pending |
| 53-05D2C-01/02/03 | 05D2C | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SCP01, T53C-LANES, T53C-OMIT, T53C-DIRT, T53C-SEAL | Planning-ancestor ownership, SCP-01 Phase 55/pending convergence, exact 33-path allowlist, focused/selector gates, closed current plus exact-nine legacy lanes, unfiltered Git-object proof of exact six-path seal and summary-only descendant | contract/integration/structural | Planning-ancestor assertion, Phase 51 ledger prerequisite, execution-source selector, current broad lane, temporary legacy lane_legacy classification, then post-seal Git-object/binding commands in 05D2C | ✅ | ⚠ selector 13 passed; ledger and dual-lane seal gates pending |
| 53-05E-01/02/03 | 05E | 12 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53E-SOURCE, T53E-READONLY, T53E-APPROVAL | New OperationPlan from current source/topology and exact owner-hash checkpoint | read-only/checkpoint | Literal plan command plus approval selectors in 53-05E | ❌ W0 | ⬜ pending |
| 53-05F-01/02 | 05F | 13 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53F-REPLAY, T53F-EDGE, T53F-ROLLBACK | One exact cross-host live transaction and immutable evidence handoff | live/structural | Literal apply, validator and broad commands in 53-05F | ❌ W0 | ⬜ pending |
| 53-06-PREFLIGHT | 06 | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE | Sole explicit-path checker proves independent PASS and the complete 05F binding chain | structural/checkpoint | Literal `python3 modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py ... --json` command in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-01 | 06 | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE, T53C-RECEIPT, T53C-CAPABILITY | Freeze exact sealed input outside live consumption | contract/read-only | Same literal binding-chain checker plus metadata assertion in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-02 | 06 | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-REPORT, T53C-SECRET | Current validator result drives report parity and exactly five ledger rows | contract/read-only | `python3 -c 'import json; from pathlib import Path; root=Path(".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge"); j=json.loads((root/"53-GATE-REPORT.json").read_text()); assert j["status"]=="PASS" and j["requirements"]==["SRV-02","SRV-03","SRV-04","SRV-06","OPS-01"]'` | ❌ W0 | ⬜ pending |
| 53-06-03 | 06 | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-RECEIPT, T53C-FRESHNESS | Five-path closeout parent and summary-only descendant with locally initialized SHAs | structural/read-only | Literal checker plus SHA initialization, exact parent/summary diff assertions and `git diff --check` in 53-06 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ W0 missing/unimplemented · ⚠️ flaky*

## Wave 0 Requirements

- [x] Existing strict runtime/edge/API/live-runner tests remain the green
  baseline and must not be weakened.
- [ ] 05D: strict `phase53-edge.json` for `137.131.140.20`, three DNS-only
  hostnames, public 34099-34101 translation, internal native listeners and
  exhaustive public negatives.
- [ ] 05D: hbbs Quadlet announces exactly
  `rustdesk-relay.atius.com.br:34101`, derived/asserted against the edge
  contract; native internal listeners remain unchanged.
- [ ] 05D: `install-phase53-server.py` derives the public relay announcement
  from the edge contract, validates the source Quadlet, materializes the
  equivalent runtime-installed command and rejects source/runtime tamper or
  contract/endpoint mismatch in hermetic fixtures.
- [ ] 05D: read-only/apply backend exports have negative capability tests.
- [ ] 05D2T: exact atius-srv-1 edge, Horistic backend, DRG/return path and stale-plan rejection are current read-only PASS.
- [ ] 05D2A: DNAT/forward/backend/DNS/probe/ops/validator production semantics make the complete Phase 53 test file exit zero.
- [ ] 05D2B: non-executable `10.31.1.31` migration handoff is created and
  provider manifest/backend tests reject the destination.
- [ ] 05D2C planning prerequisite: ROADMAP is clean in both index and
  worktree; a committed HEAD object removes SCP-01 from the Phase 51
  requirement list and assigns it to Phase 55; execution reads that object
  with `git show`, captures its last path commit and never modifies or stages
  `ROADMAP.md`.
- [ ] 05D2C: traceability says exactly `SCP-01 | Phase 55 | Pending`; the
  ledger uses owner 55, `fleet-rollout-live`, pending/null, retains only the
  stable row reservation for `RDF-V19-SCP-01`, omits its catalog object and
  yields exactly seven current passes plus 29 pending rows.
- [x] 05D2C selector: 13 execution-source tests pass before ledger convergence;
  this selector alone does not authorize sealing.
- [ ] 05D2C: `phase53-execution-source-scope.json` contains exactly 33
  Phase 53 live/test paths, includes all 05D/05D2
  code/contracts/tests and the hbbs Quadlet, explicitly naming both
  `install-phase53-server.py` and preexisting read-only
  `rustdesk-ops-api.py`, with ancestor/blob/dirt tests; it excludes
  REQUIREMENTS, ledger and the Phase 51 contract test even though those three
  paths share the exact six-path source-seal commit.
- [ ] 05D2C: after the focused Phase 51 ledger gate and 05D2C selector, the
  current broad lane runs with exactly the canonical nine explicit
  deselections and exits zero; read-only `lane_current()` proves zero
  failures/errors/regular skips, exact EXPECTED_XFAILS/count and
  `frozen_verifier: PASS`, while terminal parsing proves no other deselections.
- [ ] 05D2C: the legacy lane runs exactly those nine nodeids under the
  governor, writes JUnit only to `mktemp` storage beneath `/tmp`, exits one,
  and read-only `lane_legacy()` proves eight `gate-a-managed-source-drift`
  refusals plus one CLI rc2/local-only/no-network refusal.
- [ ] 05D2C: neither lane regenerates Phase 52 evidence, reseals Gate A nor
  reverts the legitimate successor/fixture paths; both temporary directories
  are removed by `trap` before the exact six-path source commit and direct
  summary-only descendant are created.
- [ ] 05D2C post-seal: SOURCE=`HEAD^` and SUMMARY=`HEAD`; unfiltered
  `git diff-tree` proves exact six-path and summary-only sets, SUMMARY directly
  descends from SOURCE, ROADMAP's recalculated last path commit plus all four
  predecessor summary commits are SOURCE ancestors, and the scope payload
  passes `validate_execution_source_scope_payload` before SOURCE/HEAD
  recomputation over its exact 33 returned paths proves identical
  digest/blobs/paths and passes `require_clean_execution_source`.
- [ ] 05D2B: runner tests cover `--live-backend`, `--mode plan|apply`,
  `--operation-plan`, `--owner-approval`, `--stage full`, exit 0/2/3/4 and
  zero-side-effect failures.
- [ ] 05D2B/C: `verify-phase53-binding-chain.py` exports
  `validate_phase53_binding_chain(...)`, requires every manifest path
  explicitly and rejects stale/missing/extra/mismatched manifests,
  source/tree/plan/transaction drift, self-hash, executor SHA in evidence,
  extra summary diff, ancestry/tree drift and dirty scope.
- [ ] 05E: OperationPlan/approval tests cover current
  hash/source/prestate/typed-confirmation/expiry and explicit owner response.
- [ ] 05F: full sequence covers apply journal, immutable rollback receipt and
  separate restore-production transaction ID/journal.
- [ ] 05F/06: commit fixtures cover seven-path evidence-only live parent,
  exact summary-only descendants, later verification descendants, `git show`
  digest parity and locally initialized commit SHAs.
- [ ] 06: read-only fixtures prove no runner/validator/contract/test or sealed
  receipt changes and exactly five closeout parent outputs.

## Manual-Only Verifications

The owner decision is intentionally manual and hash-bound. Giovanni must review
the current OperationPlan and respond with owner identity, explicit decision,
exact current hash and future expiry. Silence or generic approval keeps
`AWAITING_OWNER_HASH_APPROVAL`. The real reboot, rollback and production restore
occur only inside the approved 05F full live transaction. The 06 checkpoint
confirms independent verifier ownership after one deterministic preflight and
authorizes no live action.

## Validation Sign-Off

- [x] Every revised task has an automated command or explicit pending Wave 0 dependency.
- [x] The incomplete tail is split into topology, semantic reconciliation, transaction/binding and source-seal plans; 05D2C owns exactly seven paths including its summary, below the nine-path ceiling.
- [x] Waves and dependencies are `05D(w7) → 05D2T(w8) → 05D2A(w9) → 05D2B(w10) → 05D2C(w11) → 05E(w12) → 05F(w13) → 06(w14)`.
- [x] Heavy commands use the 20% governed `builds` profile.
- [x] Broad verification separates only the closed exact-nine legacy set;
  current-lane extra deselections and every non-canonical failure/error/skip
  or xfail drift remain hard blockers via `lane_current()`, with temporary
  JUnit outside the repository.
- [x] Post-seal checks derive SOURCE=`HEAD^` and SUMMARY=`HEAD`, inspect both
  commits unfiltered, prove direct/predecessor ancestry and recompute the exact
  33-path binding at both commits before accepting the summary descendant.
- [x] `nyquist_compliant: true` describes planned coverage while `wave_0_complete: false` records the missing fixtures.

**Approval:** revised for planning 2026-07-26; the 13-pass 05D2C selector is
preserved, Wave 0 remains incomplete at the truthful SCP-01 ledger and
closed current/legacy lane gates, and Phase 53 remains blocked/in progress
before authority or live mutation.
