---
phase: 53
slug: primary-relay-and-public-edge
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-22
---

# Phase 53 — Validation Strategy

> Per-phase validation contract for the RustDesk OSS primary, public edge and
> authenticated ATIUS operational API.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Python `pytest` plus shell/PowerShell external probes |
| **Config file** | Existing `modules/rustdesk-fleet/tests`; Phase 53 test module is Wave 0 |
| **Quick run command** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'contract or schema or report'` |
| **Full suite command** | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests` |
| **Live gate command** | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py` |
| **Estimated runtime** | quick/task selector <30 seconds; full ~4 minutes; live restart/reboot/rollback ~20 minutes |

---

## Sampling Rate

- **After every task commit:** run the narrow Phase 53 selector mapped below.
- **After every plan wave:** run the complete RustDesk module suite.
- **Before live mutation:** contracts, fault injection, secret scan and rollback
  dry-run must be green from the same source HEAD.
- **Before `$gsd-verify-work`:** full suite and the current live gate must be
  green; canonical report must be derived from current raw evidence.
- **Max feedback latency:** below 30 seconds for task-level contract/unit selectors. Long live gates
  occur only at the explicit deployment and lifecycle waves.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 53-01-01 | 01 | 0 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53-CONTRACT | Strict schemas, exact sockets/resources and stored-verdict rejection | unit/contract | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'contract or schema or mutation'` | ✅ | ✅ green |
| 53-01-02 | 01 | 0 | SRV-02, OPS-01 | T53-SECRET, T53-EXEC | Secret-bearing argv/env/evidence/API/log fixtures and unflagged/ambiguous live stages fail closed | unit/security | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'secret or redact or auth or live_flag or stage_receipt'` | ✅ | ✅ green |
| 53-02-01 | 02 | 1 | SRV-02 | T53-RUNTIME | Rootless digest-pinned Quadlets, exact mounts/caps and aggregate cgroup budget | unit/integration | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'quadlet or runtime or cgroup'` | ❌ W0 | ⬜ pending |
| 53-02-02 | 02 | 1 | SRV-06 | T53-IDENTITY, T53-ROLLBACK-SRV | Hydration is tmpfs/no-output; fingerprint, SQLite and bounded logs persist; rollback is terminal | integration/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'identity or sqlite or rollback or linger or log_bound'` | ❌ W0 | ⬜ pending |
| 53-03-01 | 03 | 2 | OPS-01 | T53-API-AUTH, T53-API-LEAK, T53-READINESS, T53-APACHE | Backend auth/redaction/readiness plus reversible Apache publication and no TCP 21114 | unit/integration | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'ops_api or apache or readiness'` | ❌ W0 | ⬜ pending |
| 53-04-01 | 04 | 3 | SRV-03, SRV-04 | T53-EDGE | nft/OCI effective policy permits only approved public ports and preserves k3s | unit/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'nft or oci or listener or ipv6'` | ❌ W0 | ⬜ pending |
| 53-04-02 | 04 | 3 | SRV-04 | T53-DNS, T53-PROBE | DNS is last/exactly rollbackable and two-origin TCP/UDP proof is correlated | unit/fault | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'dns or cloudflare or address or external_probe or udp'` | ❌ W0 | ⬜ pending |
| 53-05-01 | 05 | 4 | SRV-03, SRV-04 | T53-LIVE, T53-PUBLIC | Ordered transaction and two origins prove TCP positives/negatives plus correlated UDP | live/external | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage edge-probes` | ❌ W0 | ⬜ pending |
| 53-05-02 | 05 | 4 | OPS-01 | T53-OPS-PUBLIC | Exact Apache/backend/auth transaction precedes redacted public HTTPS probes | live/external | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage ops-api` | ❌ W0 | ⬜ pending |
| 53-06-01 | 06 | 5 | SRV-06 | T53-LIFECYCLE | Three restarts and boot preserve identity/data/sockets/resources/logs/API | live/lifecycle | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage lifecycle` | ❌ W0 | ⬜ pending |
| 53-06-02 | 06 | 5 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53-ROLLBACK | Containment-first rollback closes edge and preserves every legacy fallback | live/rollback | `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage rollback` | ❌ W0 | ⬜ pending |
| 53-06-03 | 06 | 5 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53-ROLLBACK, T53-PUBLIC | Rollback PASS is preserved and production is restored/reproved | contract/live | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'restore_production or desired_state'` | ❌ W0 | ⬜ pending |
| 53-06-04 | 06 | 5 | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | T53-REPORT, T53-BOUNDARY | Current raw evidence drives report/ledger; verifier remains independent and Graphify terminal | contract/full | `omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'report or ledger or final_gate'` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` — strict
  contracts, mutation fixtures, redaction tests and live-runner fakes.
- [x] `modules/rustdesk-fleet/contracts/phase53-runtime.json` — exact local
  socket, paths, identity, resource and log contract.
- [x] `modules/rustdesk-fleet/contracts/phase53-edge.json` — effective
  host/OCI/DNS/IPv4/IPv6 contract.
- [x] `modules/rustdesk-fleet/contracts/phase53-ops-api.json` — endpoint,
  authentication, redaction and readiness schema.
- [x] `modules/rustdesk-fleet/tools/run-phase53-live-gate.py` — explicit-live,
  resumable transaction with stage receipts and terminal rollback.

---

## Manual-Only Verifications

All phase behaviors are automated. The real host reboot is disruptive but is
performed only by the explicit live runner after pre-state backup, active-user
check, rollback readiness and operator authorization already recorded for this
autonomous lifecycle. A reboot without those gates must be refused.

---

## Validation Sign-Off

- [x] All planned tasks have an automated command or explicit Wave 0 dependency.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 lists every missing Phase 53 test/contract/runner artifact.
- [x] No watch-mode flags are used.
- [x] Fast feedback target is below 30 seconds.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** approved for planning 2026-07-22; live PASS remains pending execution.
