---
phase: 53-primary-relay-and-public-edge
plan: 05D
subsystem: infra
tags: [rustdesk, edge, dns, quadlet, capability-boundary]
requires:
  - phase: 53-05C
    provides: fail-closed live admission and current blocker evidence
provides:
  - strict translated edge authority for 34099/34100/34101
  - contract-derived hbbs relay announcement at rustdesk-relay.atius.com.br:34101
  - capability-disjoint read-only and apply backend factories
affects: [53-05D2, 53-05E, 53-05F, 53-06]
tech-stack:
  added: []
  patterns:
    - sole machine-readable edge authority
    - typed capability-disjoint backend factories
key-files:
  created:
    - modules/rustdesk-fleet/tools/phase53-live-backend.py
  modified:
    - modules/rustdesk-fleet/contracts/phase53-edge.json
    - modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
    - modules/rustdesk-fleet/tools/install-phase53-server.py
    - modules/rustdesk-fleet/tools/apply-phase53-edge.py
    - modules/rustdesk-fleet/tools/probe-phase53-edge.py
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
key-decisions:
  - "External authority is 34099/TCP, 34100/TCP+UDP and 34101/TCP; native listeners remain internal."
  - "Read-only construction exposes no runtime, provider, containment, rollback or restore capability."
patterns-established:
  - "Edge values are loaded from phase53-edge.json and rejected on duplicate/stale schema."
  - "The canonical installer compares effective hbbs argv in source and installed Quadlets."
requirements-completed: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
coverage:
  - id: D1
    description: Strict translated edge, three DNS-only records and hbbs relay announcement
    requirement: SRV-03
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#translated edge and hbbs selectors"
        status: pass
    human_judgment: false
  - id: D2
    description: Capability-disjoint read-only and apply backend factories
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#read_only_backend apply_backend provider_manifest"
        status: pass
    human_judgment: false
duration: 15min
completed: 2026-07-26
status: complete
---

# Phase 53 Plan 05D: Edge and Backend Summary

**Translated RustDesk edge authority, contract-derived hbbs relay announcement and capability-disjoint backend factories, with no authority or live mutation**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-26T03:29:08Z
- **Completed:** 2026-07-26T03:44:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Replaced the historical direct-public native edge with the exact translated `34099/34100/34101` contract, three DNS-only A records and exhaustive direct-public native negatives.
- Made the hbbs source and runtime-installed effective argv announce `rustdesk-relay.atius.com.br:34101`, rejecting source, endpoint and installed-unit tamper.
- Added separate read-only/apply backend types; read-only previews remain value-free and cannot expose mutation, containment, rollback or restore.

## Task Commits

1. **Task 53-05D-01: Fixar edge traduzido e anúncio público do hbbs** - `7ed7cfe78`
2. **Task 53-05D-02: Implementar capability boundary do backend** - `e1b6d3742`

## Verification

- Governed 05D selectors: `6 passed, 191 deselected`.
- `git diff --check`: PASS.
- Full diagnostic suite: `145 passed, 1 xfailed, 51 failed`. The failures are retained as an explicit downstream blocker: historical transaction/validator/ops fixtures still encode the superseded direct-public `21115-21117` model or the pre-change edge digest. No failure was hidden, waived or converted to PASS.
- Resource governor: structural containment PASS at `CPUQuota=80%`, equal to 20% total host CPU. Swap pressure remained warning-only near 100%.

## Deviations from Plan

None in the declared nine-file ownership or live-safety boundary.

## Issues Encountered

The broad diagnostic suite is intentionally not a 05D acceptance command, but it exposed 51 concrete compatibility failures after the authority change. `53-05D2` must reconcile those downstream consumers/tests before capturing `execution_source_commit`; sealing the source while any of them remain red is forbidden.

## User Setup Required

None. This plan performed no external service configuration and no live/provider call.

## Next Phase Readiness

`53-05D2` may start only as a hermetic reconciliation/binding unit. It is blocked from sealing `execution_source_commit` until the 51 broad-suite failures are reduced to zero or deterministically classified outside Phase 53 scope. `53-05E`, `53-05F` and every live mutation remain blocked.

## Self-Check: PASSED

- All nine declared files are present.
- Both task commits exist.
- The exact plan-level selectors and structural diff gate pass.
- No authority, OperationPlan, approval, evidence or infrastructure mutation occurred.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-26*
