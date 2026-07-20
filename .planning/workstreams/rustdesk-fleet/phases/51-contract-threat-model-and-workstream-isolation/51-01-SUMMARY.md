---
phase: 51-contract-threat-model-and-workstream-isolation
plan: 01
subsystem: security-governance
tags: [rustdesk, contracts, threat-model, vault-references, pytest]
requires: []
provides:
  - exact five-host scope, two-host exclusion, five-fallback preservation and direct-first transport contract
  - deterministic OSS/Pro decision state machine and two explicit least-privilege profiles
  - T-01 through T-12 threat model plus reference-only Vault role inventory and metadata-only secret scanner
affects: [phase-52, rustdesk-fleet, evidence-ledger, operational-review]
tech-stack:
  added: [python-stdlib-validator]
  patterns: [strict-json, exact-set-validation, fail-closed-status, metadata-only-findings]
key-files:
  created:
    - modules/rustdesk-fleet/contracts/scope.json
    - modules/rustdesk-fleet/contracts/product-decision.json
    - modules/rustdesk-fleet/contracts/permission-profiles.json
    - modules/rustdesk-fleet/contracts/threat-model.json
    - modules/rustdesk-fleet/contracts/secret-roles.json
    - modules/rustdesk-fleet/tools/validate_phase51.py
    - modules/rustdesk-fleet/tests/test_phase51_contracts.py
    - .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-SECURITY.md
  modified: []
key-decisions:
  - "Product state remains BLOCKED until an accountable review records all six enterprise-control decisions."
  - "Phase 51 proves five unique Vault references only; value creation and distinctness proof remain Phase 52 work."
  - "OSS permission profiles are desired local policy with compensating verification, never claimed centralized RBAC."
patterns-established:
  - "Contract checks use stable P51 IDs and status precedence FAIL over BLOCKED over PASS."
  - "Secret findings contain category, path and location only; matched material is never retained."
requirements-completed: [SCP-01, SCP-02, SCP-03]
coverage:
  - id: D1
    description: "Exact fleet, exclusion, fallback and direct-first transport contracts"
    requirement: SCP-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase51_contracts.py#scope legacy transport tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Deterministic OSS Pro decision, least-privilege profiles and ASVS-mapped threat model"
    requirement: SCP-02
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase51_contracts.py#product permission threat tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Five reference-only target roles and metadata-only secret hygiene"
    requirement: SCP-03
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase51_contracts.py#secret redact tests"
        status: pass
    human_judgment: false
duration: 14min
completed: 2026-07-20
status: complete
---

# Phase 51 Plan 01: Scope, Product and Security Contracts Summary

**Strict RustDesk fleet contracts now fail closed on scope, product, permission, threat and secret-boundary drift without touching hosts or Vault values.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-20T04:20:25Z
- **Completed:** 2026-07-20T04:34:24Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Froze exactly five included hosts, two excluded environments, five preserved recovery tools and direct-first transport with forced relay prohibited as default.
- Added a deterministic OSS/Pro decision table, exact permission profiles, T-01 through T-12 and OWASP ASVS 5.0.0 mappings; the current product result intentionally remains `BLOCKED` pending accountable review.
- Reserved five unique target Vault references plus separate identity/recovery assets and proved metadata-only findings across seven runtime-generated secret classes.

## Task Commits

1. **Task 51-01-01: scope/transport RED** — `9e033e69e`
2. **Task 51-01-01: scope/transport GREEN** — `274e02635`
3. **Task 51-01-02: product/threat RED** — `b6d31a0cd`
4. **Task 51-01-02: product/threat GREEN** — `e0b9fd59f`
5. **Task 51-01-03: secret boundary RED** — `caa24a92a`
6. **Task 51-01-03: secret boundary GREEN** — `28a6c03e1`

## Files Created/Modified

- `modules/rustdesk-fleet/contracts/scope.json` — exact fleet, exclusion, fallback and transport contract.
- `modules/rustdesk-fleet/contracts/product-decision.json` — deterministic OSS/Pro decision inputs and current BLOCKED result.
- `modules/rustdesk-fleet/contracts/permission-profiles.json` — exact admin-maintenance and support-observe capability matrices.
- `modules/rustdesk-fleet/contracts/threat-model.json` — authoritative T-01 through T-12 and ASVS mapping.
- `modules/rustdesk-fleet/contracts/secret-roles.json` — server identity, five target references and recovery authority without values.
- `modules/rustdesk-fleet/tools/validate_phase51.py` — strict parser, stable check results, fail-closed CLI and redacted scanner.
- `modules/rustdesk-fleet/tests/test_phase51_contracts.py` — 25 positive/negative tests using runtime-generated sentinels.
- `modules/rustdesk-fleet/tests/fixtures/invalid/excluded-host.json` — excluded target negative.
- `modules/rustdesk-fleet/tests/fixtures/invalid/forced-relay-default.json` — forbidden transport default negative.
- `.planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-SECURITY.md` — human projection with unchecked operational sign-off.

## Decisions Made

- The product state cannot become `GO/oss` until all six missing centralized controls are explicitly reviewed and accepted; any mandatory control derives `NO-GO/pro`.
- The repository records Vault role/path/field names only. Reference uniqueness is current proof; secret-value distinctness is deferred to the Phase 52 live gate.
- Local permission profiles are tested desired state plus compensating controls, not a claim of OSS centralized RBAC.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The first dynamic import in RED did not register the module in `sys.modules`, causing a dataclass collection error. The test harness was corrected before the RED commit so the committed failure was caused by intentionally unimplemented behavior.
- Graphify became six commits stale after the production commits. The serialized owner rebuilt it in the foreground under `omni-builds.slice` with `CPUQuota=80%` on this four-vCPU host; final status was fresh at `28a6c03` with 9,746 nodes and 11,664 edges. Resource doctor remained structurally healthy and reported the pre-existing 100% swap warning.

## User Setup Required

None - no external service configuration or secret hydration is authorized in this plan.

## Automated Evidence

- `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q` — 25 passed.
- `python3 -m py_compile modules/rustdesk-fleet/tools/validate_phase51.py` — passed.
- Contract CLI — exit `2`, with `P51-PRODUCT-001=BLOCKED`, every other implemented check PASS and `secret_material_present=false`.
- `git diff --check` over Plan 01 scope — passed.
- Graphify — fresh, zero commits behind at production HEAD.

## Next Phase Readiness

Ready for Plan 51-02 workstream isolation, Phase 48 integrity and evidence-ledger implementation. Phase 52 remains blocked until Plan 51-03 obtains real operator and Vault-owner approval; this summary does not close that gate.

## Self-Check: PASSED

---
*Phase: 51-contract-threat-model-and-workstream-isolation*
*Completed: 2026-07-20*
