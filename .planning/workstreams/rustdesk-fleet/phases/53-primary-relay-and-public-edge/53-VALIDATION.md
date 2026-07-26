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
> source-bound authority, recoverable stale-output housekeeping, explicit owner checkpoint, single 05F live
> transaction and read-only 06 closeout. The 05D broad diagnostic result is
> `51 failed, 145 passed, 1 xfailed`; 05D2T/A/B/C close topology, semantics,
> transaction/binding, truthful SCP-01 ledger ownership and historical source
> sealing before authority. The 05D2C selector completed at 14 passed, but
> after the Phase 51 ledger repair the raw broad suite still contains the
> canonical nine legacy Gate-B refusals. 05D2C therefore requires a closed
> current lane plus an independently classified exact-nine legacy lane; it
> never treats the raw result as green or rewrites historical Gate A evidence.
> Runtime discovery produced `902 passed, 9 deselected, 1 xfailed`, rc 0. The
> frozen Phase 52 two-xfail current-lane set is not current Phase 53
> authority because the deploy-transaction xfail was legitimately closed;
> current JUnit is instead bound to the sole remaining validate_phase53.py
> owner xfail.

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
| **05D2C current broad lane** | Observed `902 passed, 9 deselected, 1 xfailed`, rc 0. The literal governed command in Task 53-05D2C-03 uses temporary JUnit/output, exactly nine explicit `--deselect` nodeids, inline parsing for zero failures/errors and a complete skipped list of exactly one `pytest.xfail` at `modules.rustdesk-fleet.tests.test_phase53_primary_edge::test_future_implementation_symbol_is_red_only_for_owner_plan[tools/validate_phase53.py-53-06]`, plus terminal count exactly `9 deselected` |
| **05D2C legacy exact-nine lane** | Literal governed command in Task 53-05D2C-03 runs exactly the same nine nodeids into `/tmp` JUnit, requires pytest rc 1 and calls read-only `lane_legacy()` to prove nine failures, eight managed-source drift and one local-only/no-network CLI case |
| **05D2C post-seal Git-object structure** | Task 53-05D2C-03 derives SOURCE=`HEAD^` and SUMMARY=`HEAD`, uses unfiltered `git diff-tree` for the exact six-path/summary-only sets, proves direct parentage, recalculates ROADMAP's last path commit and checks it plus 05D/05D2T/05D2A/05D2B ancestry with `git merge-base --is-ancestor` |
| **05D2C post-seal binding recomputation** | Task 53-05D2C-03 passes the JSON payload through `validate_execution_source_scope_payload`, then recomputes `compute_execution_source_binding` at SOURCE and HEAD over the returned exact 33 paths, compares digest/blobs/paths and calls `require_clean_execution_source` |
| **05D2D exact source selector** | Sixteen exact nodeids: eight authority/strict-validator/housekeeping-receipt generation, three owner-decision and five 05F pre-write/transaction/exclusion contracts; missing nodeids cannot collapse to rc5 |
| **05D2D current/legacy and seal gates** | Governed broad lane retains only the exact nine historical deselections and sole validate_phase53.py xfail; legacy remains exact eight drift plus one local-only; source commit is exact seven paths, summary descendant one path, aggregate exactly 34 paths |
| **05D2H recoverable housekeeping** | Exact seven-path inventory; prepared/per-move/completed mode-0600 manifest below mode-0700 `/var/tmp/omni-rustdesk-phase53-quarantine`; stable digest pointer written last; every canonical path absent before 05E; zero provider/live writes |
| **Read-only authority command** | `build-phase53-authority-plan.py collect-observation --repo . --output "$AUTHORITY_OBSERVATION"` to a `/tmp` file, then governed `run-phase53-live-gate.py --repo . --authority-observation "$AUTHORITY_OBSERVATION" --housekeeping-receipt .../53-05D2H-SUMMARY.md --quarantine-pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json --live-backend phase53-production --mode plan --stage full --operation-plan .../edge-forwarder-operation-plan.json` |
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
  classification. Inline current-JUnit parsing must prove zero
  failures/errors and that the complete skipped-case list is exactly the sole
  current validate_phase53.py `pytest.xfail`; the terminal output proves
  exactly nine and no other deselections. Do not call the frozen Phase 52
  two-xfail current-lane helper here: its removed deploy-transaction xfail describes the
  earlier frozen source, not current Phase 53. The legacy lane must contain
  only the canonical eight drift refusals plus one local-only/no-network CLI
  refusal. All commands run under the `builds` governor before the clean
  closed source scope and six explicit pathspecs may be sealed.
- **After 05D2C seal:** use unfiltered Git-object checks over `HEAD^` and
  `HEAD`, not path-filtered worktree diffs: prove exact six-path source and
  summary-only commit sets, direct parentage, ROADMAP plus predecessor
  ancestry, validated-scope identical 33-path bindings at SOURCE/HEAD and a
  clean execution source. This seal is now a historical predecessor, not
  current authority.
- **Before/after 05D2D seal:** require a planning-only commit first. Add the
  explicit collector/producer/strict-validator/housekeeping-receipt/approval/05F nodeids and run all sixteen exact
  nodeids under the governor; then run the same governed current and exact-nine
  legacy lanes. Commit exactly manifest/checker/backend/builder/runner/validator/test,
  create a summary-only descendant and prove identical clean 34-path bindings
  at SOURCE/HEAD. No evidence/owner/live write occurs.
- **Before 05E collection:** execute 05D2H only after 05D2D. Inventory the exact
  seven canonical 05F outputs, persist a recoverable prepared/per-move/complete
  manifest and stable digest pointer outside Git, quarantine every existing
  regular byte without parsing it as authority, prove all seven destinations
  absent and commit only the value-free 05D2H summary.
- **After each code-producing wave:** use focused selectors first and, where a
  broad gate is required, the closed current/legacy lane contract through the
  `builds` profile; never interpret a raw broad suite as green.
- **Before 05E authority:** require the current 05D2D
  `execution_source_commit`, prove it includes 05D2C/05D as ancestors, require
  the exact 34-path execution-source allowlist plus completed 05D2H absent-state
  receipt, collect an explicit current read-only observation and reject
  source-scope/observation dirt.
- **Before 05F mutation:** require a new process plus current source tree,
  admission, prestate, typed confirmations and unexpired owner approval.
- **Before 06 writes:** invoke only the strict explicit-path
  `verify-phase53-binding-chain.py` preflight. It requires independent
  `status: passed`, proves the evidence-only live parent, direct summary-only
  descendant and later verification ancestry, checks `git show` manifest
  bytes, and recomputes the allowlisted Git aggregate at source/live/current.
- **Wave chain:** `05D(w7) → 05D2T(w8) → 05D2A(w9) → 05D2B(w10) → 05D2C(w11 historical) → 05D2D(w12 current seal) → 05D2H(w13 recoverable housekeeping) → 05E(w14 checkpoint) → 05F(w15 live) → 06(w16 read-only)`.

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
| 53-05D2C-01/02/03 | 05D2C | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SCP01, T53C-LANES, T53C-OMIT, T53C-DIRT, T53C-SEAL | Planning-ancestor ownership, SCP-01 Phase 55/pending convergence, exact 33-path allowlist, focused/selector gates, current inline one-xfail JUnit plus exact-nine legacy lane, unfiltered Git-object proof of exact six-path seal and summary-only descendant | contract/integration/structural | Ledger 10 pass; source selector 14 pass; current 902 pass/9 deselected/1 xfail; legacy exact-nine; post-seal structural/binding PASS | ✅ | ✅ historical seal complete at 3ea1e58; superseded for current authority only by planned 05D2D |
| 53-05D2D-01/02/03 | 05D2D | 12 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53D2D-SYNTH, T53D2D-SOURCE, T53D2D-REPLAY, T53D2D-CAP, T53D2D-PARTIAL | Explicit read-only collector/seam, frozen Phase52 successor, six ordered capacity samples, current strict validator, symlink-safe explicit 05D2H receipt binding, last-written OperationPlan marker and superseding 34-path source seal | unit/security/integration/structural | Sixteen exact nodeids (8 authority/validator/receipt + 3 approval + 5 apply), governed current/legacy lanes and post-seal Git-object checks in 53-05D2D | ❌ RED | ⬜ planned |
| 53-05D2H-01/02 | 05D2H | 13 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53H-LOSS, T53H-LAUNDER, T53H-SCOPE, T53H-REPLAY | Exact recoverable quarantine transaction and seven-path absent proof before authority | local/recovery/structural | Literal pointer/manifest/hash/absence validator plus summary-only Git structural check in 53-05D2H | ✅ plan | ⬜ pending |
| 53-05E-01/02/03 | 05E | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53E-SOURCE, T53E-READONLY, T53E-APPROVAL | New OperationPlan from explicit current read-only observation plus sealed H receipt binding and exact owner-hash checkpoint | read-only/checkpoint | Literal collector+plan command with receipt/pointer, eight exact generation/validator/receipt nodeids and three exact approval nodeids in 53-05E | ❌ W0 | ⬜ pending |
| 53-05F-01/02 | 05F | 15 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53F-REPLAY, T53F-EDGE, T53F-ROLLBACK | One exact cross-host live transaction and immutable evidence handoff | live/structural | Literal apply, validator and broad commands in 53-05F | ❌ W0 | ⬜ pending |
| 53-06-PREFLIGHT | 06 | 16 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE | Sole explicit-path checker proves independent PASS and the complete 05F binding chain | structural/checkpoint | Literal `python3 modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py ... --json` command in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-01 | 06 | 16 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE, T53C-RECEIPT, T53C-CAPABILITY | Freeze exact sealed input outside live consumption | contract/read-only | Same literal binding-chain checker plus metadata assertion in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-02 | 06 | 16 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-REPORT, T53C-SECRET | Current validator result drives report parity and exactly five ledger rows | contract/read-only | `python3 -c 'import json; from pathlib import Path; root=Path(".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge"); j=json.loads((root/"53-GATE-REPORT.json").read_text()); assert j["status"]=="PASS" and j["requirements"]==["SRV-02","SRV-03","SRV-04","SRV-06","OPS-01"]'` | ❌ W0 | ⬜ pending |
| 53-06-03 | 06 | 16 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-RECEIPT, T53C-FRESHNESS | Five-path closeout parent and summary-only descendant with locally initialized SHAs | structural/read-only | Literal checker plus SHA initialization, exact parent/summary diff assertions and `git diff --check` in 53-06 | ❌ W0 | ⬜ pending |

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
- [x] 05D2C planning prerequisite: ROADMAP is clean in both index and
  worktree; a committed HEAD object removes SCP-01 from the Phase 51
  requirement list and assigns it to Phase 55; execution reads that object
  with `git show`, captures its last path commit and never modifies or stages
  `ROADMAP.md`.
- [x] 05D2C: traceability says exactly `SCP-01 | Phase 55 | Pending`; the
  ledger uses owner 55, `fleet-rollout-live`, pending/null, retains only the
  stable row reservation for `RDF-V19-SCP-01`, omits its catalog object and
  yields exactly seven current passes plus 29 pending rows.
- [x] 05D2C selector: 14 execution-source tests pass before ledger convergence;
  this selector alone does not authorize sealing.
- [x] 05D2C: `phase53-execution-source-scope.json` contains exactly 33
  Phase 53 live/test paths, includes all 05D/05D2
  code/contracts/tests and the hbbs Quadlet, explicitly naming both
  `install-phase53-server.py` and preexisting read-only
  `rustdesk-ops-api.py`, with ancestor/blob/dirt tests; it excludes
  REQUIREMENTS, ledger and the Phase 51 contract test even though those three
  paths share the exact six-path source-seal commit.
- [x] 05D2C: after the focused Phase 51 ledger gate and 05D2C selector, the
  current broad lane runs with exactly the canonical nine explicit
  deselections and exits zero; inline JUnit parsing proves zero
  failures/errors and a complete skipped list containing exactly the sole
  validate_phase53.py owner `pytest.xfail`, while terminal parsing proves no
  other deselections. The discovered baseline is 902 passed/9 deselected/1
  xfailed, rc 0.
- [x] 05D2C: the legacy lane runs exactly those nine nodeids under the
  governor, writes JUnit only to `mktemp` storage beneath `/tmp`, exits one,
  and read-only `lane_legacy()` proves eight `gate-a-managed-source-drift`
  refusals plus one CLI rc2/local-only/no-network refusal.
- [x] 05D2C: neither lane regenerates Phase 52 evidence, reseals Gate A nor
  reverts the legitimate successor/fixture paths; both temporary directories
  are removed by `trap` before the exact six-path source commit and direct
  summary-only descendant are created.
- [x] 05D2C post-seal: SOURCE=`HEAD^` and SUMMARY=`HEAD`; unfiltered
  `git diff-tree` proves exact six-path and summary-only sets, SUMMARY directly
  descends from SOURCE, ROADMAP's recalculated last path commit plus all four
  predecessor summary commits are SOURCE ancestors, and the scope payload
  passes `validate_execution_source_scope_payload` before SOURCE/HEAD
  recomputation over its exact 33 returned paths proves identical
  digest/blobs/paths and passes `require_clean_execution_source`.
- [ ] 05D2D planning prerequisite: one planning-only commit contains the
  superseding 05D2D and 05D2H plans plus aligned
  CONTEXT/ROADMAP/STATE/05E/05F/06 and validation bytes, while neither
  historical Phase 52 nor unrelated dirty Phase 53 paths are staged.
- [ ] 05D2D exact groups: eight authority/strict-validator/housekeeping-receipt nodeids, three
  owner-approval nodeids and five 05F nodeids all exist and pass; the authority
  OperationPlan adversarially rejects conflating public-VNIC owner
  `10.0.0.238` with DRG/SNAT/backend source `10.11.1.11`.
- [ ] 05D2D explicit collector writes only one value-free current observation
  beneath `/tmp`; no plan path may infer ambient readback or construct a
  write-capable provider.
- [ ] 05D2D verifies frozen Phase 52 only through the exact Git-object ancestry
  `6bb2e0a → e552c87 → 11fa627 → current`, preserving all historical bytes and
  both distinct review digests.
- [ ] 05D2D promotes five exact dependencies first and the OperationPlan last
  as the sole generation marker; fault injection after every boundary proves
  consumers reject all partial generations.
- [ ] 05D2D runs the literal governed current lane plus exact-nine legacy lane,
  then commits exactly seven source paths, a direct summary-only descendant and
  recomputes identical clean 34-path bindings at SOURCE/HEAD.
- [ ] 05D2H inventaria os sete paths canônicos com hash/size, persiste
  manifest recoverable antes/depois de cada move, escreve stable pointer por
  último, prova os sete ausentes e comita somente summary value-free; não há
  provider/live/authority write.
- [ ] 05D2D/05E/05F usam o mesmo sealed receipt verifier: summary commit,
  pointer/manifest digest, generation ID e canonical-seven absent digest são
  parâmetros explícitos e bindings do preflight/OperationPlan; lstat/lexists,
  unique rows, fixed-root confinement, owner/mode e O_NOFOLLOW rejeitam
  dangling symlink, escape, duplicata ou receipt ambient.
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
- [x] Waves and dependencies are `05D(w7) → 05D2T(w8) → 05D2A(w9) → 05D2B(w10) → 05D2C(w11 historical) → 05D2D(w12 current seal) → 05D2H(w13 recoverable housekeeping) → 05E(w14 checkpoint) → 05F(w15 live) → 06(w16 read-only)`.
- [x] Heavy commands use the 20% governed `builds` profile.
- [x] Broad verification separates only the closed exact-nine legacy set;
  current-lane extra deselections and every non-canonical failure/error/skip
  or xfail drift remain hard blockers via inline complete-JUnit parsing, with
  temporary JUnit outside the repository. The frozen Phase 52 current-lane helper
  remains unchanged and does not override current Phase 53 xfail truth.
- [x] Historical 05D2C post-seal checks derive SOURCE=`HEAD^` and
  SUMMARY=`HEAD`, inspect both commits unfiltered and preserve the exact
  33-path predecessor binding; current authority remains blocked until 05D2D
  repeats the same structural proof over its exact seven-path source commit,
  summary-only direct descendant and superseding clean 34-path binding.
- [x] `nyquist_compliant: true` describes planned coverage while `wave_0_complete: false` records the missing fixtures.

**Approval:** revised for planning 2026-07-26; the historical 14-pass 05D2C
selector and observed 902/9/1 current lane are preserved. The 05D2D Wave 12
producer/strict-validator 34-path seal and 05D2H Wave 13 recoverable
housekeeping are still pending, so Phase 53 remains blocked/in progress before
any authority or live mutation.
