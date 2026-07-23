---
phase: 53-primary-relay-and-public-edge
plan: 02
subsystem: infra
tags: [rustdesk, podman, quadlet, systemd, vault, rollback, tdd]

requires:
  - phase: 53-primary-relay-and-public-edge
    plan: 01
    provides: immutable runtime contract and fail-closed live-gate boundary
provides:
  - digest-pinned rootless hbbs/hbbr Quadlets under an aggregate resource slice
  - tmpfs-only Vault identity hydration with value-free evidence
  - transactional closed-ingress installation, conditional linger and idempotent rollback
  - authoritative bounded log rotation with 30-day retention
affects: [53-03, 53-04, 53-05, 53-06, phase54-canary]

tech-stack:
  added: []
  patterns: [rootless-quadlet, tmpfs-secret-hydration, exact-prestate-rollback, bounded-log-rotation]

key-files:
  created:
    - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
    - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container
    - modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice
    - modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.service
    - modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.timer
    - modules/rustdesk-fleet/tools/install-phase53-server.py
  modified:
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py

key-decisions:
  - "hbbs and hbbr use only the approved state, tmpfs identity and authoritative log mounts; stderr is suppressed to prevent a second unbounded log surface."
  - "The installer is importable for Plan 05 but its CLI exposes only bounded log rotation, so Plan 02 cannot accidentally perform a live install."
  - "Linger is disabled on rollback only when the current transaction changed it from no to yes."

patterns-established:
  - "Every server mutation boundary has deterministic fault injection and automatic rollback coverage."
  - "Remote command construction is argv-only, bounded and forces SSH batch mode with stdin disabled."

requirements-completed: [SRV-02, SRV-06]

coverage:
  - id: D1
    description: Rootless digest-pinned Quadlets enforce exact mounts, socket ownership, hardening and parent/child cgroup arithmetic.
    requirement: SRV-02
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#test_quadlets_are_digest_pinned_rootless_hardened_and_socket_exact"
        status: pass
      - kind: other
        ref: "omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'quadlet or runtime or cgroup'"
        status: pass
    human_judgment: false
  - id: D2
    description: Tmpfs identity, SQLite continuity, conditional linger, bounded logs and exact managed-file rollback survive every injected mutation-boundary fault.
    requirement: SRV-06
    verification:
      - kind: unit
        ref: "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py#identity_sqlite_rollback_linger_log_bound"
        status: pass
      - kind: other
        ref: "omni srv1-ops resources run builds -- pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'identity or sqlite or rollback or linger or log_bound'"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-07-23
status: complete
---

# Phase 53 Plan 02: Hardened Rootless Server and Transactional Rollback Summary

**The closed-ingress hbbs/hbbr domain is now reproducible, resource-bounded and terminally reversible without touching client or legacy access paths.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-23T00:50:46Z
- **Completed:** 2026-07-23T01:01:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added immutable ARM64 hbbs/hbbr Quadlets with rootless host networking, read-only rootfs, dropped capabilities, exact dedicated mounts and null stdout/stderr.
- Enforced 35%/448 MiB and 35%/384 MiB child budgets inside the 80%/1 GiB Phase 53 slice.
- Added an exclusive transaction with exact managed-file pre-state, tmpfs-only identity hydration through the existing seven-reference provider, SQLite continuity, conditional linger and idempotent rollback.
- Added actual daily archive bounds and 30-day retention for the single authoritative server log path.

## Task Commits

1. **Task 53-02-01 RED: rootless runtime contract tests** - `d2439beaa` (test)
2. **Task 53-02-01 GREEN: hardened Quadlets and parent slice** - `841624154` (feat)
3. **Task 53-02-02 RED: server transaction and rollback tests** - `4dbd9a784` (test)
4. **Task 53-02-02 GREEN: transactional installer and bounded logs** - `98ae9dc30` (feat)

## Files Created/Modified

- `modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container` - Hardened hbbs runtime and exact local sockets.
- `modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container` - Hardened hbbr runtime and exact local sockets.
- `modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice` - Aggregate CPU, memory, swap and task ceiling.
- `modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.service` - Restricted one-shot log-bound enforcement.
- `modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.timer` - Persistent hourly enforcement timer.
- `modules/rustdesk-fleet/tools/install-phase53-server.py` - Closed server transaction, hydration, verification and rollback.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` - Runtime and transaction RED/GREEN coverage.

## Decisions Made

- Kept local upstream 21118/21119 inside the server runtime while exposing no `PublishPort` and opening no public edge.
- Used the existing approved seven-reference Vault provider request exactly; only the two server identity values enter runtime tmpfs, and durable output contains only a public fingerprint and value-free metadata.
- Made the installer CLI refuse installation in this plan. Plan 05 must explicitly orchestrate `install_closed()` behind the live gate.

## Deviations from Plan

None - both tasks executed as planned with RED then GREEN commits.

## Issues Encountered

- The governor continued to report swap pressure as a warning; `structural_ok=true`, the build slice was present and the effective `CPUQuota=80%` matched the four-vCPU 20% host guardrail.
- The first full-suite output stream ended before pytest's summary line; a bounded continuation confirmed exit 0 and the exact result.

## Authentication Gates

None. No live Horistic, Vault write, DNS, OCI, Cloudflare, firewall or client mutation occurred.

## Known Stubs

- Live installation remains intentionally uninvoked. `install_closed()` is the Plan 05 integration surface.
- Effective cgroup/socket checks accept injected readbacks in unit tests; Plan 05 owns real generated-unit and live listener evidence.

## User Setup Required

None.

## Next Phase Readiness

- Ready for `53-03-PLAN.md` to implement the operations API inside the reserved 10% CPU/192 MiB budget.
- SRV-02 and SRV-06 remain pending in the global ledger until Phase 53 live deployment and closeout; this summary records Plan 02 coverage only.
- No Phase 52 Gate B create/write flow was invoked or made reachable.

## Self-Check: PASSED

- All seven plan artifacts exist and are tracked.
- Four atomic TDD commits exist for Plan 02.
- Narrow transaction gate: `14 passed, 46 deselected`.
- Full Phase 53 file: `56 passed, 4 xfailed`.
- Governed RustDesk module suite: `635 passed, 4 xfailed`.
- Public ingress, DNS, firewall, OCI, Cloudflare, client and legacy domains were not mutated.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-23*
