---
phase: 51
slug: contract-threat-model-and-workstream-isolation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-20
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. This file is the GSD Nyquist strategy; runtime reports use `51-CONTRACT-VALIDATION.json` and `51-CONTRACT-VALIDATION.md` and must never overwrite it.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.4 + Python 3.12 standard library |
| **Config file** | Existing repository pytest discovery; no Phase 51-specific config |
| **Quick run command** | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q` |
| **Full suite command** | `python3 -m pytest modules/rustdesk-fleet/tests -q` |
| **Contract gate** | `python3 modules/rustdesk-fleet/tools/validate_phase51.py --repo . --json-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.json --markdown-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.md` |
| **Estimated runtime** | <30 seconds for focused/full Phase 51 suite on current host |

---

## Sampling Rate

- **After every task commit:** Run the focused test node(s) named by the task, then the quick run command.
- **After every plan wave:** Run the full suite, contract gate, both explicitly scoped workstream state queries, `git diff --check`, and the Phase 51 secret-hygiene scan.
- **Before `$gsd-verify-work`:** All 11 validator check IDs and the operational review must be current PASS; JSON/Markdown report parity must pass.
- **Every GSD lifecycle transition:** Run `P51-WS-001` before the command and `P51-P48-001` after it; commands must explicitly use `--ws rustdesk-fleet`.
- **Max feedback latency:** 30 seconds for automated Phase 51 checks; operational review is a separate blocking gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 1 | SCP-01, SCP-03 | T51-SCOPE, T51-RELAY | Exact host/fallback sets and direct-first policy | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k 'scope or legacy or transport'` | ❌ W0 | ⬜ pending |
| 51-01-02 | 01 | 1 | SCP-02 | T51-AUTHZ, T51-PRODUCT | OSS/Pro GO/NO-GO and least-privilege profiles fail closed | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k 'product or permission or threat'` | ❌ W0 | ⬜ pending |
| 51-01-03 | 01 | 1 | SCP-01, SCP-02 | T51-SECRET | Only unique Vault refs/roles appear; no values leak | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k secret` | ❌ W0 | ⬜ pending |
| 51-02-01 | 02 | 2 | SCP-05 | T51-WORKSTREAM | Unscoped/wrong-workstream lifecycle commands are rejected | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k workstream` | ❌ W0 | ⬜ pending |
| 51-02-02 | 02 | 2 | SCP-05 | T51-INTEGRITY | Nine old-to-new Phase 48 mappings match blobs/hashes and reject drift | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k phase48` | ❌ W0 | ⬜ pending |
| 51-02-03 | 02 | 2 | SCP-01, SCP-02, SCP-03, SCP-05 | T51-EVIDENCE | Ledger has exactly 36 canonical IDs and rejects summary-only PASS | unit | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q -k ledger` | ❌ W0 | ⬜ pending |
| 51-03-01 | 03 | 3 | SCP-01, SCP-02, SCP-03, SCP-05 | all Phase 51 threats | JSON/Markdown parity, current input hashes and review gate produce final PASS/BLOCKED | integration | `python3 -m pytest modules/rustdesk-fleet/tests -q && python3 modules/rustdesk-fleet/tools/validate_phase51.py --repo . --json-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.json --markdown-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `modules/rustdesk-fleet/tools/validate_phase51.py` — standard-library parser, exact-set validators, redacted findings, deterministic report renderer and exit codes `0/1/2`.
- [ ] `modules/rustdesk-fleet/tests/test_phase51_contracts.py` — positive and negative coverage for all 11 check IDs.
- [ ] `modules/rustdesk-fleet/tests/fixtures/valid/` — complete secret-free positive contracts and Phase 48 temp-copy manifest.
- [ ] `modules/rustdesk-fleet/tests/fixtures/invalid/` — excluded host, duplicate ref, forced-relay default, missing fallback, unscoped command, Phase 48 drift and summary-only ledger fixtures.
- [ ] Phase 51 contract JSON files, `51-SECURITY.md`, `51-OPERATIONAL-REVIEW.md`, and generated `51-CONTRACT-VALIDATION.{json,md}`.

No framework or package installation gap exists.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Declare whether SSO/OIDC, RBAC, MFA, centralized API/device policy, or human-attributed audit is mandatory | SCP-02 | Business/security acceptance cannot be inferred by code | Review `product-decision.json`; record OSS risk acceptance or `NO-GO`/Pro selection with reviewer, timestamp and source HEAD, without secrets |
| Review STRIDE/ASVS coverage and unresolved high threats | SCP-02, SCP-05 | Threat disposition requires accountable operational judgment | Review `51-SECURITY.md`; any unresolved high threat makes overall result BLOCKED |
| Approve legitimate Phase 48 re-baseline, if any | SCP-05 | Hash drift may be authorized only by the serialized owner | Compare old Git blobs and new SHA-256 manifest; document provenance and never auto-accept drift |

---

## Validation Sign-Off

- [x] All planned task slots have automated verification or Wave 0 dependencies.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers every missing executable/test/fixture reference.
- [x] No watch-mode flags are used.
- [x] Feedback latency target is below 30 seconds.
- [x] `nyquist_compliant: true` is set; `wave_0_complete` remains false until execution creates the files.

**Approval:** strategy approved 2026-07-20; runtime evidence pending
