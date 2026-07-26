---
phase: 53
slug: primary-relay-and-public-edge
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-22
updated: 2026-07-25
---

# Phase 53 — Validation Strategy

> Nyquist contract for the RustDesk OSS primary, translated public edge,
> source-bound authority, explicit owner checkpoint, single 05F live
> transaction and read-only 06 closeout. The existing baseline remains green;
> 05D/05D2 fixtures are still pending, so Wave 0 is not complete.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `pytest` plus shell/PowerShell external probes |
| **Config file** | Existing `modules/rustdesk-fleet/tests`; Phase 53 test module is Wave 0 |
| **05D edge/backend/installer selector** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'edge_contract or translated_edge or hbbs_relay_announcement or phase53_server_installer or installer_tamper or runtime_installed_hbbs or read_only_backend or apply_backend'` |
| **05D2 CLI/binding/migration selector** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'migration_handoff or migration_provider_rejection or execution_source or binding_chain or cli_mode or stage_full or immutable_rollback or summary_only or installer_in_scope or ops_api_in_scope'` |
| **Full suite command** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests` |
| **Read-only authority command** | `omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode plan --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json` |
| **Live apply command** | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 ADMITTED_PHASE53=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json --owner-approval modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json` |
| **Estimated runtime** | task selectors below 30 seconds; full suite approximately four minutes; live 05F is separately bounded; 06 is read-only |

## Sampling Rate

- **After 05D code tasks:** run only the governed edge/backend selector.
- **After 05D2 code tasks:** run only the governed CLI/binding selector.
- **After each code-producing wave:** run the complete RustDesk module suite
  through the `builds` profile; never run a raw broad suite.
- **Before 05E authority:** require the final 05D2
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
- **Wave chain:** `05D(w7) → 05D2(w8) → 05E(w9 checkpoint) → 05F(w10 live) → 06(w11 read-only)`.

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
| 53-05D2-01 | 05D2 | 8 | SRV-03, SRV-04, SRV-06, OPS-01 | T53D2-CLI, T53D2-BINDING, T53D2-ROLLBACK, T53D2-MIGRATION | Non-executable migration handoff/provider rejection, literal CLI, exact full state machine and public explicit-path checker | unit/CLI/adversarial | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'migration_handoff or migration_provider_rejection or cli_mode or live_backend or stage_full or binding_chain or immutable_rollback or restore_production'` | ❌ W0 | ⬜ pending |
| 53-05D2-02 | 05D2 | 8 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53D2-SOURCE | Final source commit includes 05D ancestor and a closed source scope naming Quadlet, canonical installer and preexisting read-only ops API | unit/structural | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'execution_source or source_scope or ancestor_binding or source_tree_digest or hbbs_quadlet_in_scope or installer_in_scope or ops_api_in_scope'` | ❌ W0 | ⬜ pending |
| 53-05E-01 | 05E | 9 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53E-SOURCE, T53E-READONLY | Frozen successor, current prestate/preview and OperationPlan with zero write capabilities | read-only/live-preview | `omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode plan --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json` | ❌ W0 | ⬜ pending |
| 53-05E-02 | 05E | 9 | SRV-03, SRV-04, OPS-01 | T53E-APPROVAL, T53E-TOCTOU | Missing approval is AWAITING exit 0; only explicit current hash+expiry can resume | checkpoint/security | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'awaiting_owner or owner_approval_explicit_response'` | ❌ W0 | ⬜ pending |
| 53-05E-03 | 05E | 9 | SRV-03, SRV-04, OPS-01 | T53E-APPROVAL, T53E-SECRET | Owner record revalidates hash/source/prestate/expiry and does not auto-apply | unit/security | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'owner_approval_hash or owner_approval_expiry or no_auto_apply'` | ❌ W0 | ⬜ pending |
| 53-05F-01 | 05F | 10 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53F-REPLAY, T53F-EDGE, T53F-ROLLBACK | New-process revalidation, one full transaction, immutable rollback and distinct restore | live/external/lifecycle | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 ADMITTED_PHASE53=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json --owner-approval modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json` | ❌ W0 | ⬜ pending |
| 53-05F-02 | 05F | 10 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53F-SOURCE, T53F-SECRET, T53F-VERIFIER | Evidence-only live parent and summary-only descendant with locally initialized SHAs | contract/structural | `python3 modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py --repo . --json` plus the SHA initialization and exact-diff assertion in 53-05F | ❌ W0 | ⬜ pending |
| 53-06-PREFLIGHT | 06 | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE | Sole explicit-path checker proves independent PASS and the complete 05F binding chain | structural/checkpoint | Literal `python3 modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py ... --json` command in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-01 | 06 | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-SOURCE, T53C-RECEIPT, T53C-CAPABILITY | Freeze exact sealed input outside live consumption | contract/read-only | Same literal binding-chain checker plus metadata assertion in 53-06 | ❌ W0 | ⬜ pending |
| 53-06-02 | 06 | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-REPORT, T53C-SECRET | Current validator result drives report parity and exactly five ledger rows | contract/read-only | `python3 -c 'import json; from pathlib import Path; root=Path(".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge"); j=json.loads((root/"53-GATE-REPORT.json").read_text()); assert j["status"]=="PASS" and j["requirements"]==["SRV-02","SRV-03","SRV-04","SRV-06","OPS-01"]'` | ❌ W0 | ⬜ pending |
| 53-06-03 | 06 | 11 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53C-RECEIPT, T53C-FRESHNESS | Five-path closeout parent and summary-only descendant with locally initialized SHAs | structural/read-only | Literal checker plus SHA initialization, exact parent/summary diff assertions and `git diff --check` in 53-06 | ❌ W0 | ⬜ pending |

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
- [ ] 05D2: non-executable `10.31.1.31` migration handoff is created and
  provider manifest/backend tests reject the destination.
- [ ] 05D2: `phase53-execution-source-scope.json` includes all 05D/05D2
  code/contracts/tests and the hbbs Quadlet, explicitly naming both
  `install-phase53-server.py` and preexisting read-only
  `rustdesk-ops-api.py`, with ancestor/blob/dirt tests.
- [ ] 05D2: runner tests cover `--live-backend`, `--mode plan|apply`,
  `--operation-plan`, `--owner-approval`, `--stage full`, exit 0/2/3/4 and
  zero-side-effect failures.
- [ ] 05D2: `verify-phase53-binding-chain.py` exports
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
- [x] Edge/backend/installer and CLI/binding/migration ownership are split into serial plans with exactly nine files each; `rustdesk-ops-api.py` is preexisting/read-only in 05D2.
- [x] Waves and dependencies are `05D(w7) → 05D2(w8) → 05E(w9) → 05F(w10) → 06(w11)`.
- [x] Heavy commands use the 20% governed `builds` profile.
- [x] Summary-only commit checks initialize their own parent/summary SHAs.
- [x] `nyquist_compliant: true` describes planned coverage while `wave_0_complete: false` records the missing fixtures.

**Approval:** revised for planning 2026-07-25; existing green baseline
preserved, Wave 0 incomplete, and Phase 53 remains blocked/in progress before
authority or live mutation.
