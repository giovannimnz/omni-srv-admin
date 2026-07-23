---
phase: 53-primary-relay-and-public-edge
plan: 01
subsystem: infra
tags: [rustdesk, podman, quadlet, nftables, cloudflare, security, tdd]

requires:
  - phase: 52-supply-chain-capacity-and-recoverable-placement
    provides: immutable ARM64 server digest, selected Horistic primary, Vault contract and recoverable placement PASS
provides:
  - strict Phase 53 runtime, public-edge and operations-API contracts
  - adversarial contract and security tests with explicit later-plan RED ownership
  - fail-closed live-gate state machine and value-free stage receipt interface
affects: [53-02, 53-03, 53-04, 53-05, 53-06, phase54-canary]

tech-stack:
  added: []
  patterns: [strict-json-contracts, red-green-tdd, digest-bound-live-gate, value-free-stage-receipts]

key-files:
  created:
    - modules/rustdesk-fleet/contracts/phase53-runtime.json
    - modules/rustdesk-fleet/contracts/phase53-edge.json
    - modules/rustdesk-fleet/contracts/phase53-ops-api.json
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
    - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  modified: []

key-decisions:
  - "Local upstream sockets 21118/21119 are required and owner-checked while remaining forbidden on the public edge."
  - "The Phase 53 aggregate is fixed at 80% CPU and 1 GiB, split 35/35/10 and 448/384/192 MiB."
  - "A live mutation requires the exact flag, current Git HEAD, current contract digests, pre-state, unambiguous ownership and rollback readiness."

patterns-established:
  - "Contract verdicts derive from current observations and digests; persisted PASS text is invalid input."
  - "Secret-capable argv, env, headers, stdout, stderr and nonce payloads are discarded or redacted before receipts."

requirements-completed: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]

coverage:
  - id: D1
    description: Strict runtime, edge and operations-API contracts encode immutable supply, socket layers, resource arithmetic, DNS-last and OSS API boundaries.
    requirement: SRV-02
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#contract_schema_and_mutation"
        status: pass
      - kind: other
        ref: "omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'contract or schema or mutation'"
        status: pass
    human_judgment: false
  - id: D2
    description: Fail-closed live-gate interface binds authorization to current inputs, rejects ambiguous receipts and produces no evidence without the exact live flag.
    requirement: OPS-01
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#live_flag_stage_receipt_secret_auth"
        status: pass
      - kind: other
        ref: "omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'secret or redact or auth or live_flag or stage_receipt'"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-23
status: complete
---

# Phase 53 Plan 01: Executable Contracts and Fail-Closed Live Gate Summary

**Strict runtime/edge/API contracts and a digest-bound, value-free live transaction interface now block drift before any Horistic mutation.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-23T00:11:07Z
- **Completed:** 2026-07-23T00:23:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Fixed exact immutable runtime, local-versus-public socket, path, identity, log and aggregate-resource contracts.
- Fixed DNS-last A-only edge, effective OCI union audit, two-origin TCP and correlated UDP evidence contracts.
- Added a live-gate skeleton that rejects stale HEAD/contracts, missing pre-state, weak rollback, ambiguous receipts, stored verdicts and secret-bearing evidence.

## Task Commits

1. **Task 53-01-01 RED: contract behavior suite** - `9d4233be0` (test)
2. **Task 53-01-01 GREEN: executable contracts** - `821bd819f` (feat)
3. **Task 53-01-02 RED: live-gate security suite** - `91eb69e68` (test)
4. **Task 53-01-02 GREEN: fail-closed runner interface** - `d94f7aede` (feat)

## Files Created/Modified

- `modules/rustdesk-fleet/contracts/phase53-runtime.json` - Immutable rootless runtime, identity, resources, logs and rollback schema.
- `modules/rustdesk-fleet/contracts/phase53-edge.json` - Exact IPv4/IPv6, DNS-last, effective-ingress and external-probe schema.
- `modules/rustdesk-fleet/contracts/phase53-ops-api.json` - Versioned endpoint, backend auth, redaction and derived-readiness schema.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` - 44 green tests plus five intentional later-plan REDs.
- `modules/rustdesk-fleet/tools/run-phase53-live-gate.py` - Explicit-live and current-input authorization with typed ordered receipts.

## Decisions Made

- Interpreted upstream TCP 21118/21119 as required local sockets but forbidden public exposure, matching the three-round research convergence.
- Included the operations backend inside the 80% CPU/1 GiB parent slice while keeping existing Apache outside the slice and subject to later regression measurement.
- Kept all live handlers unavailable in Wave 0; only typed, validated interfaces exist until their owning plans implement them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the Phase 52 replay boundary assertion**
- **Found during:** Task 53-01-01 GREEN
- **Issue:** The first test rejected even a prohibition string naming the forbidden Gate B replay.
- **Fix:** Asserted the exact prohibition entries instead of banning the identifying text.
- **Files modified:** `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py`
- **Verification:** contract selector passed 17/17.
- **Committed in:** `821bd819f`

**2. [Rule 2 - Missing Critical] Bound source currentness to the actual Git HEAD**
- **Found during:** Task 53-01-02 GREEN
- **Issue:** A syntactically valid 40-hex source field alone did not prove current source.
- **Fix:** Added bounded `git rev-parse HEAD` comparison before authorizing mutation.
- **Files modified:** `modules/rustdesk-fleet/tools/run-phase53-live-gate.py`, `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py`
- **Verification:** security selector passed 27/27 and full module passed 44 with five expected xfails.
- **Committed in:** `d94f7aede`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical control).  
**Impact on plan:** Both tighten the intended boundary; no live scope or later-plan implementation was added.

## Issues Encountered

- The resource governor reported high swap as an operational warning, but `structural_ok=true`, the builds slice existed and `CPUQuota=80%` matched the 20% total-host policy on four vCPU.
- The first GBrain `put` attempt did not persist because its disconnect timed out; `gbrain capture --file` succeeded and `gbrain get` verified the page.

## Authentication Gates

None.

## Known Stubs

- `modules/rustdesk-fleet/tools/run-phase53-live-gate.py`: `run_stage()` deliberately raises `LiveStageNotImplemented`; Plans 53-02 through 53-06 own the live handlers.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py`: five strict `xfail` cases track the later-plan runtime, API, edge, deploy-evidence and validator artifacts.

These stubs are the explicit Wave 0 boundary and do not prevent Plan 53-01 from meeting its contract-foundation goal.

## User Setup Required

None - no external service configuration was performed.

## Next Phase Readiness

- Ready for `53-02-PLAN.md` to implement the rootless Quadlets, identity hydration, resource/log enforcement and server-domain rollback behind the frozen interfaces.
- Global SRV-02/SRV-03/SRV-04/SRV-06/OPS-01 ledger status must remain pending until the Phase 53 live closeout; this summary records plan coverage, not final phase promotion.
- Graphify terminal freshness remains owned by the Phase 53 orchestrator after integrating all plan commits.

## Self-Check: PASSED

- All five key files exist and are tracked.
- Four `53-01` TDD commits exist in Git history with no tracked-file deletion.
- Governed full module: `44 passed, 5 xfailed`.
- Unflagged CLI: `BLOCKED`, `mutation_performed=false`, no evidence created.
- Obsidian note and GBrain page were verified without secret values.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-23*
