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
| **05D2Q complete baseline gate** | `validate-phase53-dirty-baseline.py` and `test_phase53_dirty_baseline.py` recompute tracked/untracked, exact porcelain-v1 `-z` XY, confined regular lstat type/mode/size, O_NOFOLLOW 1 MiB streaming SHA-256, two-pass TOCTOU, RFC3339/captured HEAD, duplicate-key closed schema, self digest and create-only 0600/fsync/no-replace. `exact` governs capture/pre-source; `ancestor` governs R/V/S and D entry. Q source is validator+test+baseline, then direct summary child |
| **05D2R generic reader gates** | Standalone `test_phase53_provider_readers.py --literal-governor-smoke` invokes the wrapper exactly once and proves `omni→systemd-run→flock→launcher/target`, launcher PID retention, flock parent/lock lifetime, shared `omni-builds.slice` and allowlisted FD survival. Ordinary pytest then runs once inside the governor without nested semaphore acquisition |
| **05D2V source-only Vault route gates** | Hermetic `test_phase53_vault_continuity.py` covers exact Phase 52 key/fingerprint reuse, byte-preserving authorized_keys prefix transform, exact runtime modes/sudoers/forced-command protocols, no key/AppRole/token/ACL creation, closed metadata versus derived output, ordered future install/readback/rollback and strict-or-NO_GO validation. V performs zero install/live call |
| **05D2S provider-apply gates** | Literal tests reuse the shared MCP client and launcher; one-shot SSH sends a source-sealed worker and closed JSON payload over stdin to fixed `/usr/bin/sudo -n /usr/bin/python3 -I -`, with no scp/install/ambient shell. Template/payload/rendered digests, sudo inert preflight and atomic apply/rollback are checked. Cloudflare absent records use POST/create/readback/delete-if-current; present records use revision/ETag CAS update/readback/restore-if-current; mixed states, duplicates and drift fail closed. Source commit is exactly six paths and its child exactly one summary |
| **05D2D current/legacy and seal gates** | Run Q `ancestor` first, integrate R/V/S, implement `collect-and-plan`, `validate-generation` and `promote-generation`, prove Q/R/V/S direct chains and seal exactly seven D paths. One canonical helper derives the exact summary-bound Q/R/V/S plus D set; builder, live validator and both tests contain no hardcoded 34 assumption, and a non-34 fixture passes |
| **05D2W governed continuity gate** | Frozen-only assessment exits 0 eligibility/3 insufficient/2 invalid/1 internal and never claims currentness. Route OperationPlan/checkpoint precedes the only future writer; it binds Phase 52 key continuity and exact install/rollback order. Current fingerprint uses `data-read-derived-output`. Decision is only strict or NO_GO |
| **05D2H recoverable housekeeping** | Runs only after authorizing W decision. Exact seven-output inventory; recoverable quarantine/pointer; flags are `housekeeping_filesystem_mutation=true`, `recoverable=true`, provider/network/live-runtime false |
| **05E private authority generation** | Task 1 writes a private non-repo generation plus exclusive private orchestration state. Exact rc0 = valid current/admissible W/complete bundle; rc3 = valid current but mismatch/unproven and non-authorizing attestation; route unavailable/frozen-only missing is never rc3. Task 2 is rc0-only and leaves generation/canonical paths read-only while atomically binding the reviewed hash and private owner response in state. Task 3 loads only state-bound values and is sole canonical/summary writer; OperationPlan last for rc0, rc3 only attestation+blocked marker+summary |
| **Live apply command** | Task 53-05F-01 uses separate source-sealed apply policy and promoted current instance: `... phase53-credential-launcher.py --reader-policy .../phase53-reader-command-manifest.json --apply-policy .../phase53-apply-command-manifest.json -- .../run-phase53-live-gate.py --reader-command-manifest ... --apply-command-manifest .../phase53-apply-command-manifest.json --apply-instance .../preflight.json ...`. It recollects topology/supply/capacity/Vault/host/OCI/Cloudflare/Apache and W continuity immediately before import/factory/journal |
| **Estimated runtime** | task selectors below 30 seconds; current/legacy governed lanes replace the raw broad gate; live 05F is separately bounded; 06 is read-only |

## Revision 5 Blocker Gates

These gates separate planning structure from operational completion and exercise positive plus negative behavior without network, secret output or swallowed errors.

| Blocker | Positive gate | Negative gate |
|---|---|---|
| Metrics basis | `node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" query roadmap.analyze .planning/workstreams/rustdesk-fleet/ROADMAP.md` is reported only as structural projection; `python3 -c 'from pathlib import Path; ps=list(Path(".planning/workstreams/rustdesk-fleet").glob("phases/**/*-PLAN.md")); assert len(ps)==41'` proves physical inventory. Semantic claims are separately asserted as 40 current, 26 complete, 65%; Phase 53 22 current/12 complete + retained 53-05; Phase 54 1/5 | `python3 -c 'from pathlib import Path; t=Path(".planning/workstreams/rustdesk-fleet/STATE.md").read_text(); assert "30 summaries/41 = 73% is structural only" in t; assert "26 of 40 current plan units" in t'` rejects analyzer projection as completion |
| Q legal H→S→C sequence | Dedicated dirty-baseline suite captures H, runs exact only at H, creates one-parent S with the literal validator/test/baseline diff, validates source ancestor, creates one-parent summary C and validates paired summary ancestor from descendants | Same suite rejects exact after S, wrong/merge parents, extra diffs, stale ancestry, unpaired summary arguments and every dirty-field mismatch while ancestor does not require current HEAD=H |
| R real governed chain | Standalone `--literal-governor-smoke` invokes the wrapper exactly once and proves target PID=launcher PID, parent exe flock, systemd-run ancestor, shared `omni-builds.slice`, one launcher FD surviving and lock conflict/release | Governed pytest never invokes the wrapper recursively; ambient/unrelated FDs fail, missing ancestry/cgroup equality or premature lock release fails, and no governor/no-fork change is accepted |
| V exact Phase 52 continuity | Hermetic V suite proves exact authorized_keys prefix-only transform/current idempotence, suffix/unrelated-byte equality, runtime owner/mode/nlink, exact sudoers+visudo, forced protocols and ordered rollback | Same suite rejects every other prestate, key/AppRole/token/ACL creation, argv/stdin/command violations, symlink/hardlink/mode drift, readback mismatch and rollback drift; decision is strict or NO_GO only |
| Dynamic execution source | `derive_expected_execution_source_paths(...)` derives summary-bound Q/R/V/S source paths union exact seven D paths; builder/live validator consume the validated set and a non-34 valid fixture passes | Exact search proves all four numeric assumptions are removed; missing/extra/duplicate/crossed-summary paths fail |
| D/E rc contracts | Focused selectors `collect_and_plan`, `validate_generation`, `promote_generation`, `rc3`, `manifest_count_derived`, `vault_route_receipt`, `housekeeping_receipt`, `operation_plan_is_last` prove exact rc0/rc3 private and canonical sets | Missing/schema/route/W/H/stale-current inputs are rc2/rc1, rc3 has no OperationPlan/approval/apply instance/provider action, exclusive promotion never overwrites and cleans only invocation-created paths |
| E shell rc preservation | Literal collection and promotion wrappers use `set +e`, capture rc, restore `set -e`, then case on 0/3/other; orchestration state binds generation path, branch rc and reviewed SHA | Structural check rejects any promotion path that can abort before rc capture or loses rc3; exact branch validators reject forbidden/extra files |
| 53-06 checkpoint reachability | `node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" query verify.plan-structure .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-06-PLAN.md` must return `task_count: 4`; the first task is `checkpoint:human-verify`, runs the automated checker before `<human-check>`, and has resume signal exactly `approved` | `python3 -c 'from pathlib import Path; t=Path(".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-06-PLAN.md").read_text(); assert "<preflight_gate" not in t; assert t.index("<task type=\"checkpoint:human-verify\"") < t.index("<task type=\"auto\"")'` rejects the old out-of-tasks gate |

Decision coverage must report all D-01 through D-24 explicitly. Ranges such as `D-01..D-24` and pseudo-IDs are forbidden. Final planning validation also requires `git diff --check` with no watch mode and no `|| true`.

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
- **Before 05D2Q seal:** create and pass the reusable validator/dedicated test,
  capture the exact seven-path full baseline, commit validator+test+baseline
  and then the direct summary child.
- **Before 05D2R seal:** prove Q `ancestor` before and after the suite. The tests
  invoke the literal governor→launcher chain and exercise descriptor creation
  inside the governor, FD cleanup, full MCP lifecycle, Cloudflare GET-only,
  strict SSH and generic route denial. R does not implement Vault continuity.
  Commit exactly eight source paths followed by a direct summary-only child.
- **Before 05D2V seal:** prove Q `ancestor`; run the hermetic continuity route
  suite covering metadata versus derived-output, restricted bridge/policy,
  installer/readback/rollback and decision branches. Commit exactly eight
  source paths then a direct summary child; zero live/install call.
- **Before 05D2S seal:** prove Q equality before and after the literal shared
  MCP/one-shot worker/apply-manifest suite and inert `preflight-only`. Cover
  absent/present/mixed Cloudflare branches and atomic rollback. Commit exactly
  six source paths followed by a direct summary-only child; preflight records
  zero provider construction/calls/writes.
- **Before/after 05D2D seal:** require Q `ancestor` as the literal first action,
  intentionally consume the seven partial dirty source paths. Integrate R/S
  plus V manifests/transports, add strict
  receipt/policy and pre-import revalidation nodes, prove exact direct
  Q/R/V/S source-summary chains, run focused suites plus governed current
  baseline `918 passed, 9 deselected, 1 xfailed` and exact-nine legacy lane.
  Commit exactly the preserved seven source paths, create a direct summary-only
  descendant and prove identical clean bindings at SOURCE/HEAD over the actual
  sorted Git path set. No evidence/owner/live write occurs.
- **Before 05D2W:** run the frozen-only assessment first. Known state is
  insufficient. Any route install/current observation requires the separate
  W OperationPlan and exact future approval. Only strict equivalence can
  authorize downstream; every other result is NO_GO.
- **Before 05E collection:** execute 05D2H only after W authorizes continuity.
  Inventory the exact
  seven canonical 05F outputs, persist a recoverable prepared/per-move/complete
  manifest and stable digest pointer outside Git, quarantine every existing
  regular byte without parsing it as authority, prove all seven destinations
  absent and commit only the value-free 05D2H summary.
- **After each code-producing wave:** use focused selectors first and, where a
  broad gate is required, the closed current/legacy lane contract through the
  `builds` profile; never interpret a raw broad suite as green.
- **Before 05E authority:** Task 1 generates only in private non-repo storage
  and enforces exact rc0/rc3/rc2/rc1 semantics. Task 2 is rc0-only, leaves the
  generation and canonical paths read-only, and atomically binds the reviewed
  hash plus private owner response in orchestration state. Task 3 alone promotes canonical artifacts/summary; rc0 writes the
  OperationPlan last before owner record/summary, while rc3 promotes only the
  non-authorizing successor attestation, blocked marker and summary.
- **Before 05F mutation:** require a new process carrying reader manifest,
  source-sealed apply policy and promoted current apply instance.
  Before apply-module import, provider-factory construction or journal I/O,
  recompute OperationPlan/generation/dependencies/manifests/preflight/source/H,
  recollect topology/supply/capacity/Vault/host/OCI/Cloudflare/Apache and W
  continuity immediately before import; validate owner confirmations. Drift
  blocks with zero import/factory/journal/provider side effect and requires a
  new OperationPlan plus new exact Giovanni approval.
- **Before 06 writes:** invoke only the strict explicit-path
  `verify-phase53-binding-chain.py` preflight. It requires independent
  `status: passed`, proves the evidence-only live parent, direct summary-only
  descendant and later verification ancestry, checks `git show` manifest
  bytes, and recomputes the allowlisted Git aggregate at source/live/current.
- **Wave chain:** `05D2Q(w12) → 05D2R(w13) → 05D2V(w14) → 05D2S(w15) → 05D2D(w16) → 05D2W(w17) → 05D2H(w18) → 05E(w19) → 05F(w20) → 06(w21)`.

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
| 53-05D2Q-01/02 | 05D2Q | 12 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53Q-DIRT, T53Q-TOCTOU | Reusable complete seven-path validator/test, baseline and direct summary child | structural/unit | `test_phase53_dirty_baseline.py`, literal exact/ancestor and exact three-source/one-summary checks | ❌ RED | ⬜ planned |
| 53-05D2R-01/02/03 | 05D2R | 13 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53R-FD, T53R-MCP, T53R-ROUTE | Generic direct governed launcher, full MCP lifecycle and bounded readers without invented Vault route | unit/security/integration | Literal `test_phase53_provider_readers.py`, exact eight-source/one-summary | ❌ RED | ⬜ planned |
| 53-05D2V-01/02/03 | 05D2V | 14 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53V-DATA, T53V-ROUTE, T53V-INSTALL | Source-only restricted Vault route/policy/bridge/installer/validator | unit/security/structural | `test_phase53_vault_continuity.py`, zero live/install counters, exact eight-source/one-summary | ❌ RED | ⬜ planned |
| 53-05D2S-01/02/03 | 05D2S | 15 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53S-EARLY, T53S-ROUTE, T53S-OCI, T53S-ROLLBACK | Shared MCP, stdin worker and branch-complete Cloudflare apply | unit/security/integration | `test_phase53_provider_apply.py`, inert preflight, exact six-source/one-summary | ❌ RED | ⬜ planned |
| 53-05D2D-01/02/03 | 05D2D | 16 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53D2D-SOURCE, T53D2D-RECEIPT, T53D2D-TOCTOU | Q-first entry, collect-and-plan exits, Q/R/V/S chains and Git-derived aggregate | unit/security/structural | R/V/S suites, focused selectors, current/legacy lanes and exact-seven seal | ❌ RED | ⬜ partial source, zero commits |
| 53-05D2W-01/02/03/04 | 05D2W | 17 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53W-HISTORY, T53W-WRITE, T53W-GAP | Frozen assessment, route checkpoint/writer, current observation and strict-or-NO_GO decision | checkpoint/live-conditional | Closed exit tests, exact plan/approval/readback/rollback and decision validator | ❌ W0 | ⬜ known NO_GO |
| 53-05D2H-01/02 | 05D2H | 18 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53H-LOSS, T53H-LAUNDER, T53H-SCOPE | W-gated recoverable quarantine with honest flags | local/recovery | W eligibility plus pointer/manifest/hash/absence validator | ✅ plan | ⬜ pending |
| 53-05E-01/02/03 | 05E | 19 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53E-RC, T53E-PARTIAL, T53E-APPROVAL | Private generation, rc0-only checkpoint and single canonical writer | read-only/checkpoint | result-table/single-writer tests and literal generation promotion | ❌ W0 | ⬜ pending |
| 53-05F-01/02 | 05F | 20 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53F-REPLAY, T53F-EDGE, T53F-ROLLBACK, T53F-TOCTOU | Fresh all-surface recollection, exact W branch, metrics bases and one transaction | live/structural | Literal apply, drift/order/metrics nodes, validator and broad commands | ❌ W0 | ⬜ pending |
| 53-06-00/01/02/03 | 06 | 21 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE, T53C-REPORT | First in-tasks checkpoint then read-only closeout | checkpoint/read-only | task_count 4, full Q/R/V/S/D/W/H/E/F checker, reports and diff checks | ❌ W0 | ⬜ pending |

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
- [ ] 05D2Q creates validator/test, captures exactly the seven dirty D2D paths
  without content, commits validator+test+baseline and a direct summary child,
  and exposes complete exact/ancestor policies reused by R/V/S/D.
- [ ] 05D2R literal group: the tests invoke the real
  governor→credential-launcher chain. The direct governed launcher hydrates
  only allowlisted profiles, creates memfd/pipe/unlinked-known-host FDs itself,
  passes only the required descriptors to its target and proves cleanup on
  success, timeout and signal. The shared Streamable HTTP client proves
  initialize/session/initialized/tools-list/tool-call/close against the exact
  OCI Admin and Atius MCP identities; Cloudflare is GET-only and SSH uses an
  explicit identity/UserKnownHostsFile/fingerprint.
- [ ] 05D2R remains generic and rejects absent provider-specific routes. It
  does not implement, invoke or attest Vault continuity.
- [ ] 05D2V defines source-only the exact restricted server-side metadata and
  `data-read-derived-output` route. Tests prove no raw value output,
  exact Phase 52 key reuse, transactional install/readback/rollback and
  honest frozen/current/decision schemas with zero live/install calls.
- [ ] 05D2R receipt schema requires one unique observation ID, a distinct
  receipt ID per receipt, one common capacity-policy digest, raw counters plus
  derived result, revision/ETag/operation/timestamps/TTL/payload/semantic
  digests, and rejects unknown/raw stdout/stderr/secret fields.
- [ ] 05D2R seal commits exactly eight source paths followed by a direct
  summary-only descendant; it writes no authority/evidence/runtime/provider
  state and does not disturb the seven partial 05D2D paths.
- [ ] 05D2V seal commits exactly eight source paths followed by a direct
  summary-only descendant; route_installed/current_metadata/provider calls
  remain false/zero and Q still passes ancestor.
- [ ] 05D2S literal apply group provides apply-manifest builder, no-write
  `preflight-only`, shared MCP client and a one-shot remote worker delivered
  with a closed JSON payload over SSH stdin to fixed
  `/usr/bin/sudo -n /usr/bin/python3 -I -`; no scp, install or ambient shell is
  allowed. Exact template/payload/rendered digests, inert sudo preflight,
  atomic apply/rollback and distinct operation IDs/journals are required.
- [ ] 05D2S Cloudflare tests cover absent→POST/create/readback/delete-if-current
  and present→revision/ETag CAS update/readback/restore-if-current for each of
  three records, including mixed states, duplicates and revision drift.
- [ ] 05D2S seal commits exactly six source paths followed by a direct
  summary-only descendant; hermetic production CLI tests pass while
  provider_constructed/provider_calls/provider_writes remain zero.
- [ ] 05D2D checkpoint baseline is preserved: seven exact dirty source paths,
  zero commits, sixteen exact nodes green, current lane 918 passed/9
  deselected/1 xfailed and legacy exact-nine expected. These facts do not
  constitute the D2D source seal.
- [ ] 05D2D exact groups preserve the carry-forward nodes and add literal
  reader/apply manifest input, unique receipt/policy validation, H
  before/after collection, OperationPlan-last, pre-import/factory/journal
  revalidation and revision drift requiring new approval; the authority
  OperationPlan adversarially rejects conflating public-VNIC owner
  `10.0.0.238` with DRG/SNAT/backend source `10.11.1.11`.
- [ ] 05D2D explicit collector writes only one value-free current observation
  beneath `/tmp`; 05F receives the same sealed reader manifest plus apply
  manifest, recollects current revisions/prestates and imports/constructs the
  write provider only after every D-20 check passes.
- [ ] 05D2D verifies frozen Phase 52 only through the exact Git-object ancestry
  `6bb2e0a → e552c87 → 11fa627 → current`, preserving all historical bytes and
  both distinct review digests.
- [ ] 05D2D implements and tests `collect-and-plan` but does not execute it.
  E Task 1 generates only in private storage; Task 3 alone promotes canonical
  outputs. OperationPlan is the last rc0 generation marker.
- [ ] 05D2D verifies exact Q, R, V and S source path sets, trees/digests, direct
  summary-only children and source→summary→D2D ancestry; requires Q equality
  at entry and binds the Q baseline into the final source aggregate; then runs current and
  legacy lanes, commits exactly seven preserved source paths, creates a direct
  summary-only descendant and recomputes identical clean bindings at
  SOURCE/HEAD for the actual sorted Git path set.
- [ ] 05D2H inventaria os sete paths canônicos com hash/size, persiste
  manifest recoverable antes/depois de cada move, escreve stable pointer por
  último, prova os sete ausentes e comita somente summary value-free; não há
  provider/network/live-runtime write, mas o receipt declara honestamente
  `housekeeping_filesystem_mutation=true` e `recoverable=true`.
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
- [ ] 05D2W known frozen-only result is insufficient/non-authorizing.
  Route action requires its own exact OperationPlan/approval. Only a mechanically
  proven `STRICT_EQUIVALENCE_PROVEN` decision may reach H; every other state is
  `NO_GO`, with no alternate continuity-acceptance path.
- [ ] 05E result-table tests prove rc0/rc3 exactness and single summary writer.
  Route unavailable/frozen-only missing never maps to rc3. rc3 has only
  non-authorizing attestation, blocked marker and summary; rc0 alone reaches
  checkpoint and OperationPlan-last promotion.
- [ ] 05F: before importing the apply module, constructing any provider factory
  or writing evidence/journal, validate both sealed manifests and apply
  preflight, recompute OperationPlan/generation/dependencies/expiry/source/H,
  recollect current revisions/prestates via D2R and check owner confirmations;
  drift returns to 05E for a new plan and exact Giovanni approval with zero
  import/factory/journal/provider side effect.
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
- [x] The incomplete tail is Q baseline, R generic transport, V source-only
  Vault route, S apply transport, D current seal, W governed route/decision,
  H housekeeping, E authority, F live and 06 closeout. Ownership is Q4, R9,
  V9, S7, D8, W7, H8, E8, F8 and 06-6; every plan is <=9 paths.
- [x] Waves/dependencies are exactly `Q(w12) → R(w13) → V(w14) → S(w15) → D(w16) → W(w17) → H(w18) → E(w19) → F(w20) → 06(w21)`.
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
  summary-only direct descendant and superseding clean binding derived from
  the actual sealed manifest.
- [x] `nyquist_compliant: true` describes planned coverage while `wave_0_complete: false` records the missing fixtures.

**Approval:** fifth planning revision authorized 2026-07-26 only to correct
the seven named blockers across Q→R→V→S→D→W→H→E→F→06. Historical D2D test truth
and seven dirty paths/zero commits are preserved. The known frozen assessment
is insufficient; no route write, continuity override, OperationPlan approval
or live mutation is authorized by this
revision. Without strict anchors, W remains NO_GO and H/E/F/06 are unreachable.
