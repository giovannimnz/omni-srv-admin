---
phase: 52-supply-chain-capacity-and-recoverable-placement
plan: 01
subsystem: infra
tags: [rustdesk, supply-chain, podman, sha256, arm64, windows]
requires:
  - phase: 51-contract-threat-model-and-workstream-isolation
    provides: approved scope, Vault references, threat model, and workstream isolation
provides:
  - immutable RustDesk server 1.1.15 and client 1.4.9 supply contract
  - fresh official-source P52-SUPPLY-001 PASS observation
  - verified OCI, ZIP, DEB, and MSI cache outside Git without installation
affects: [52-capacity, 53-primary-relay, 54-canary, 55-linux-rollout]
tech-stack:
  added: []
  patterns: [immutable expectation plus fresh observation, metadata-only evidence, quarantine on byte drift]
key-files:
  created:
    - modules/rustdesk-fleet/contracts/supply-chain.json
    - modules/rustdesk-fleet/tools/validate_phase52.py
    - modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py
    - modules/rustdesk-fleet/tests/fixtures/invalid/phase52-supply-mutations.json
    - modules/rustdesk-fleet/evidence/phase52/supply-observation.json
  modified: []
key-decisions:
  - "Expected pins never auto-refresh; official drift blocks without rewriting the contract."
  - "Phase 52 stages the verified Windows MSI but does not install it or claim Windows access."
  - "Supply PASS does not admit a primary; SRV-01, SRV-05, and SRV-07 remain pending full-gate dependencies."
patterns-established:
  - "Supply proof: reviewed exact contract plus fresh official network observation and cached-byte verification."
  - "Binary boundary: managed cache outside Git with mode 0600; repository evidence stores metadata only."
requirements-completed: [SCP-04]
coverage:
  - id: D1
    description: Exact server/client tags, commits, digests, checksums, architectures, and phase boundaries are fail-closed.
    requirement: SCP-04
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#supply contract tests (27 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: Fresh official refs, registry manifests, release bytes, and architectures match the reviewed contract.
    requirement: SCP-04
    verification:
      - kind: integration
        ref: "omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/validate_phase52.py --repo . --only supply --evidence-dir modules/rustdesk-fleet/evidence/phase52"
        status: pass
    human_judgment: false
  - id: D3
    description: Windows MSI is verified and staged only; no install, candidate admission, target build, or public runtime occurred.
    requirement: SCP-04
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py#test_windows_msi_is_stage_only"
        status: pass
    human_judgment: false
duration: 12min
completed: 2026-07-22
status: complete
---

# Phase 52 Plan 01: Immutable Supply Chain Summary

**RustDesk Server OSS 1.1.15 and clients 1.4.9 are pinned, freshly re-resolved, byte-verified, architecture-checked, and staged outside Git without installation or host admission.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-22T01:53:56Z
- **Completed:** 2026-07-22T02:05:15Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Bound the official server tag/commit, multiarch and ARM64 child digests, release ZIP, ARM64 DEB, and Windows x86-64 MSI to exact reviewed expectations.
- Re-resolved official Git, GitHub Releases, and Docker Hub sources and produced current `P52-SUPPLY-001=PASS` evidence.
- Preserved verified OCI/ZIP/DEB/MSI bytes in a mode-0600 managed cache outside the repository; Windows installation remains Phase 54.

## Task Commits

1. **Task 52-01-01 RED:** `b0cf323f7` — failing immutable supply contract tests.
2. **Task 52-01-01 GREEN:** `b561e56e1` — exact contract and fail-closed validator seam.
3. **Task 52-01-02 RED:** `b83a897d5` — failing live observation, mutation, quarantine, and no-install tests.
4. **Task 52-01-02 GREEN:** `2d297e311` — official acquisition, verified managed cache, mutation catalog, and redacted evidence.

## Verification

- `27 passed` for the focused supply suite under `omni-builds.slice`.
- `P52-SUPPLY-001=PASS` from the governed live official-source validator.
- `py_compile` passed under the governed builds profile.
- `git diff --check` passed; no RustDesk binary extension is tracked under `modules/rustdesk-fleet`.
- `windows_install_performed=false`, `candidate_admission_performed=false`, and `secret_material_present=false`.

## Decisions Made

- Immutable pins are reviewed expectations. The live resolver quarantines unexpected bytes and never updates a pin automatically.
- The ARM64 server artifact is shared by all three authorized candidates without selecting any candidate.
- Horistic server/client identity domains remain distinct and its co-location flag is explicit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Correctness] Avoided premature SRV requirement closure**

- **Found during:** Plan closeout.
- **Issue:** Plan frontmatter lists SRV-01/SRV-05/SRV-07 as integrated dependencies, but this supply-only wave cannot honestly mark their live gates complete.
- **Fix:** `requirements-completed` records only `SCP-04`; the remaining requirements stay pending for Plans 02-06.
- **Verification:** ROADMAP advance gate and plan truths explicitly prohibit supply-only admission.
- **Committed in:** plan metadata commit.

**Total deviations:** 1 auto-fixed correctness issue. **Impact:** prevents summary-only advancement and preserves the Phase 52 full gate.

## Issues Encountered

- One final governed test attempt was refused when the resource doctor transiently observed one escaped hot process. A fresh doctor check reported `structural_ok=true`, and the governed retry passed 27/27. No guardrail was bypassed.

## User Setup Required

None. No target package, Windows MSI, listener, or service was installed.

## Next Phase Readiness

Ready for `52-02-PLAN.md` capacity/placement contracts. Supply PASS alone does not select a primary, and the Windows client remains uninstalled until Phase 54.

## Self-Check: PASSED

- All five key files exist.
- All four TDD commits exist.
- Focused tests and live supply validation passed under the builds profile.
- No target build, install, public listener, Vault value access, or secret-bearing evidence occurred.

---
*Phase: 52-supply-chain-capacity-and-recoverable-placement*
*Completed: 2026-07-22*
