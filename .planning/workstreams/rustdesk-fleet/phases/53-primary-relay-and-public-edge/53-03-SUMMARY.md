---
phase: 53-primary-relay-and-public-edge
plan: 03
subsystem: infra
tags: [rustdesk, operations-api, apache, authentication, redaction, tdd]
requires:
  - phase: 53-primary-relay-and-public-edge
    plan: 02
    provides: rootless server runtime and aggregate resource slice
provides:
  - authenticated read-only ATIUS operations API on loopback
  - current-input readiness and observational metrics summaries
  - hardened 10% CPU/192 MiB user service
  - HTTPS-only ownership-marked Apache candidate with exact file rollback
affects: [53-04, 53-05, 53-06]
tech-stack:
  added: []
  patterns: [uniform-auth-denial, current-input-readiness, allowlisted-metrics, configtest-first-apache]
key-files:
  created:
    - modules/rustdesk-fleet/tools/rustdesk-ops-api.py
    - modules/rustdesk-fleet/systemd/atius-rustdesk-ops-api.service
    - modules/rustdesk-fleet/apache/rustdesk-ops.atius.com.br.conf
  modified:
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
key-decisions:
  - "Unknown methods/routes return one not-found shape; missing, malformed and wrong backend auth return one unauthorized shape."
  - "Direct and relay byte counters are labeled observational-only and cannot assert session transport."
  - "The Apache candidate is HTTPS-only and remains unapplied until the Plan 05 live transaction."
patterns-established:
  - "Readiness is recomputed from seven raw current checks and never trusts stored PASS text."
requirements-completed: [OPS-01, SRV-02]
duration: 15min
completed: 2026-07-23
status: complete
---

# Phase 53 Plan 03: Authenticated Operations API Summary

**A private, resource-bounded ATIUS operations API now exposes four strict read-only endpoints with backend auth, source redaction and reversible HTTPS publication.**

## Performance

- **Duration:** 15 min
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Implemented `GET /v1/health`, `/v1/readiness`, `/v1/status` and `/v1/metrics/summary` with mandatory bearer authentication in the backend.
- Derived readiness from immutable digest, exact listeners, public fingerprint, effective edge, cgroups, disk/log bounds and restart limits.
- Added allowlisted metrics that exclude secret-capable input fields and explicitly refuse session-transport claims.
- Added a hardened loopback-only service in the Phase 53 parent slice and an HTTPS-only Apache candidate with sanitized logs.
- Added configtest/reload/regression failure fixtures that restore exact vhost bytes and mode.

## Task Commits

1. **Task 53-03-01 RED: API/Apache contract tests** - `284773ea8` (test)
2. **Task 53-03-01 GREEN: operations API and reversible publication** - `03a2d4707` (feat)

## Verification

- Narrow API/Apache/readiness gate: `16 passed, 57 deselected`.
- Full Phase 53 file: `70 passed, 3 xfailed`.
- Governed RustDesk module suite: `649 passed, 3 xfailed`.
- Python compile check passed.
- Governor: `structural_ok=true`, effective `CPUQuota=80%`; swap/audit remained warnings only.

## Security Boundary

- Backend binds only `127.0.0.1:32113`; no `0.0.0.0`, TCP 21114 or client `API Server` semantics exist.
- The credential arrives through a private systemd credential file; token/header values are absent from responses and logging formats.
- Apache was not reloaded and no live Vault, DNS, OCI, firewall, client or server mutation occurred.

## Deviations from Plan

None.

## Next Phase Readiness

- Ready for `53-04-PLAN.md` to implement and fault-test the ownership-scoped nft/OCI/DNS-last edge and two-origin probes.
- OPS-01/SRV-02 remain pending in the global ledger until live Plan 05 and closeout Plan 06.

## Self-Check: PASSED

- All four artifacts exist and are tracked.
- RED and GREEN commits exist.
- Three later-plan xfails remain ownership-correct.
- No live mutation or Phase 52 Gate B replay occurred.

---
*Phase: 53-primary-relay-and-public-edge*
*Completed: 2026-07-23*
