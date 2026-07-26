---
phase: 53-primary-relay-and-public-edge
plan: 05D2A
subsystem: infra
tags: [rustdesk, nftables, dnat, conntrack, cloudflare-dns, ops-api]

requires:
  - phase: 53-05D2T
    provides: "D-06 topology truth binding the public edge on atius-srv-1 to the Horistic backend."
provides:
  - "Cross-host DNAT, forward and deterministic SNAT policy for the public RustDesk edge."
  - "Exact three-record DNS CAS transaction and two-origin/four-target probe semantics."
  - "Separate public-edge and backend-listener projections in the ops API and strict evidence validator."
affects: [53-05D2B, 53-05E, 53-05F, rustdesk-fleet]

tech-stack:
  added: []
  patterns:
    - "Owned nftables chains with contract-digest binding and independent semantic readback."
    - "Cross-host authority modeled as disjoint public_edge and backend objects."
    - "Exact-set DNS CAS with snapshot, readback and guarded rollback."

key-files:
  created: []
  modified:
    - modules/rustdesk-fleet/contracts/phase53-edge.json
    - modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    - modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
    - modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service
    - modules/rustdesk-fleet/tools/apply-phase53-edge.py
    - modules/rustdesk-fleet/tools/probe-phase53-edge.py
    - modules/rustdesk-fleet/tools/rustdesk-ops-api.py
    - modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py

key-decisions:
  - "Keep the additive edge contract at schema_version 2 so the strict Phase 53 installer remains compatible while all consumers enforce the new cross-host semantics."
  - "Apply and semantically read back the owned nftables transaction in one ExecStart; use ExecStop only for guarded snapshot restore."
  - "Treat all three DNS-only A records as one CAS generation and require the public IP plus all three hostnames from two origins."

patterns-established:
  - "Translated flows must prove ct status dnat and original external destination before forwarding."
  - "Backend native listeners are distinct from public external ports and accept the deterministic 10.11.1.11 edge identity."

requirements-completed: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]

coverage:
  - id: D1
    description: "Owned public-edge DNAT/forward/SNAT policy maps 34099/34100/34101 to Horistic while direct native 21114-21119 remains closed."
    requirement: SRV-03
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#complete governed test file"
        status: pass
    human_judgment: false
  - id: D2
    description: "The systemd boot transaction syntax-checks, snapshots, applies, independently reads back and automatically restores the owned nftables policy."
    requirement: SRV-06
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#D-06 boot transaction and rollback tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "DNS publication is an exact three-record CAS unit and external proof covers two origins by public IP and all three hostnames, including UDP 34100 to 21116."
    requirement: SRV-04
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#DNS, hostname, origin and UDP correlation tests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Ops readiness and admitted-evidence validation expose and enforce public-edge forwarding separately from backend listener ownership."
    requirement: OPS-01
    verification:
      - kind: integration
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#ops API and strict validator tests"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-26
status: complete
---

# Phase 53 Plan 05D2A: D-06 Cross-Host Public Edge Summary

**Contract-bound nftables DNAT/forward/SNAT on atius-srv-1, exact three-record DNS CAS, and topology-derived ops/evidence projections for the Horistic RustDesk backend**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-26T04:53:28Z
- **Completed:** 2026-07-26T05:13:37Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Replaced local filter-input assumptions with owned cross-host prerouting DNAT, forward and postrouting SNAT chains, including conntrack/original-destination gates and direct-native IPv4/IPv6 denial.
- Made boot application transactional and rollback-safe, and made DNS/probe evidence exact across three records, two origins, four target forms and UDP 34100 to backend 21116.
- Derived ops readiness and strict admitted-evidence validation from the shared edge authority; the complete governed test file now exits zero with 198 passed and one pre-existing explicit xfail.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Add failing D-06 edge transaction tests** - `3d054fe58` (test)
2. **Task 1 GREEN: Implement cross-host primary edge** - `d5af9abea` (feat)
3. **Task 2: Reconcile edge authority consumers and broad suite** - `6ff49c1aa` (fix)

## Files Created/Modified

- `modules/rustdesk-fleet/contracts/phase53-edge.json` - Sole edge/backend, port, DNS and probe authority.
- `modules/rustdesk-fleet/contracts/phase53-provider-manifest.json` - Disjoint edge and backend execution targets and capabilities.
- `modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft` - Owned DNAT, forward, SNAT and native-public deny chains.
- `modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service` - Transactional boot apply and guarded restore.
- `modules/rustdesk-fleet/tools/apply-phase53-edge.py` - Exact candidate validation, host/OCI/DNS transaction and semantic readback.
- `modules/rustdesk-fleet/tools/probe-phase53-edge.py` - Two-origin IP/hostname/native-negative and mapped-UDP proof.
- `modules/rustdesk-fleet/tools/rustdesk-ops-api.py` - Contract-derived separate edge and backend readiness/status.
- `modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py` - Strict translated-edge admitted-evidence validation.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` - Production-backed D-06, compatibility and adversarial regression coverage.

## Decisions Made

- Preserved schema version 2 because the change is additive and the existing strict installer is a production consumer; semantic strictness now comes from the explicit `public_edge`, `backend`, translation and probe fields.
- Consolidated apply plus semantic readback in `ExecStart`, eliminating the fail-open gap between a raw nft apply and a later verifier.
- Normalized semantic receipts to JSON-native lists so in-process and subprocess verifier results are byte-semantically equivalent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved compatibility with the strict Phase 53 installer**

- **Found during:** Task 2 broad verification
- **Issue:** Bumping the additive edge contract to schema version 3 caused the existing installer to reject the otherwise valid cross-host authority.
- **Fix:** Retained schema version 2, kept all new required fields, and rebound the nftables contract digest.
- **Files modified:** `phase53-edge.json`, `atius-rustdesk-phase53.nft`, `probe-phase53-edge.py`, `rustdesk-ops-api.py`, `test_phase53_primary_edge.py`
- **Verification:** Complete governed test file: 198 passed, 1 xfailed, exit 0.
- **Committed in:** `6ff49c1aa`

**2. [Rule 1 - Bug] Made verifier receipts stable across the JSON process boundary**

- **Found during:** Task 2 broad verification
- **Issue:** Hook tuples compared unequal to their JSON-decoded list representation in subprocess verification.
- **Fix:** Emit JSON-native hook lists from the semantic validator and assert that canonical form.
- **Files modified:** `apply-phase53-edge.py`, `test_phase53_primary_edge.py`
- **Verification:** Boot verifier subprocess and complete governed suite both pass.
- **Committed in:** `6ff49c1aa`

**3. [Rule 1 - Bug] Reconciled obsolete single-record and ExecStartPost assertions**

- **Found during:** Task 2 broad verification
- **Issue:** Two historical assertions still modeled one DNS record and a separate post-apply verifier.
- **Fix:** Assert the exact three-record set and the single transactional `ExecStart` contract without deleting adversarial coverage.
- **Files modified:** `test_phase53_primary_edge.py`
- **Verification:** Complete governed test file: 198 passed, 1 xfailed, exit 0.
- **Committed in:** `6ff49c1aa`

---

**Total deviations:** 3 auto-fixed (3 Rule 1 bugs)
**Impact on plan:** All fixes were required to keep historical production consumers and safety gates compatible with D-06; no scope expansion or live mutation occurred.

## Issues Encountered

- The governed runner reported `doctor_ok: false` only because host swap usage exceeded its warning threshold; containment remained structurally healthy with `CPUQuota=80%`, zero escaped builds and pytest exit 0.
- The single xfail is pre-existing, strict and explicitly assigned to a later Phase 53 plan.

## Known Stubs

None - no placeholder, mock-only or unwired production path was introduced.

## Verification

- `omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -q` — **198 passed, 1 xfailed, exit 0**.
- `git diff --check` on all nine owned files — **passed**.
- Graphify rebuilt at `6ff49c1` with `commit_stale: false` before summary creation.
- No live host, OCI, Cloudflare, DNS or provider mutation was performed.

## User Setup Required

None - this plan changed repository authority and hermetic validation only.

## Next Phase Readiness

- D-06 cross-host edge semantics and the complete Phase 53 broad suite are ready for `53-05D2B`.
- Live promotion remains gated by the downstream approved transaction/evidence plans; this summary is not live-install evidence.

## Self-Check: PASSED

- All nine owned files exist.
- Commits `3d054fe58`, `d5af9abea` and `6ff49c1aa` exist.
- The exact required test file exits zero.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-26*
