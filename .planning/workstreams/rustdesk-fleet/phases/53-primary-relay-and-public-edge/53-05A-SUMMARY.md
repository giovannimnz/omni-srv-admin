---
phase: 53-primary-relay-and-public-edge
plan: 05A
subsystem: live-deployment-safety
tags: [rustdesk, candidate-admission, live-gate, journal, fail-closed]
requires:
  - phase: 53-04
    provides: hermetic edge/DNS-last transaction and probe harness
provides:
  - official RustDesk Server 1.1.16 candidate provenance with explicit NOT_ADMITTED state
  - adapter factory requiring current admission, rollback readiness and containment
  - atomic value-free resumable journal and failure containment seam
affects: [53-05, 53-06, phase54-heterogeneous-canary]
tech-stack:
  added: [phase53-live-adapters.py]
  patterns: [candidate-hash-admission, value-free-journal, containment-first-failure]
key-decisions:
  - "RustDesk Server 1.1.16 is evaluated from official tag/image/release digests but remains NOT_ADMITTED until fresh owner-bound approval and compatibility gates pass."
  - "A live backend is never inferred from ambient PATH, SSH or credentials; every ordered adapter and the containment callback must be explicit."
  - "Journal receipts store only stage, digest and timestamp metadata; adapter output, secrets and verdict text are never persisted."
requirements-completed: []
duration: approximately 35min
completed: 2026-07-23
status: complete
---

# Phase 53 Plan 05A: Candidate and live-runner safety closure

**Complete at the hermetic safety boundary.** This unit closes the runner
contract gap without authorizing or performing live publication.

## Implementation

- `phase53-live-adapters.py` now requires the explicit live flag, an admitted
  current candidate, rollback readiness, all ordered edge adapters and an
  explicit `contain_on_failure` callback.
- `run-phase53-live-gate.py` accepts the prescribed `edge-probes` sequence,
  opens a transaction-bound journal, and requests containment on any stage
  adapter failure before propagating the blocker.
- Journal files are atomically replaced with mode `0600` and contain only
  schema, transaction, stage digests, timestamps and containment metadata.
- The 1.1.16 evidence record binds the official commit, OCI index/ARM64
  digests and ARM64 ZIP checksum while recording `NOT_ADMITTED`, no mutation
  and approval required. Client baseline remains 1.4.9.

## Verification

- Narrow 53-05A selectors: `32 passed, 142 deselected` before the containment
  fault-injection addition, then `5 passed, 170 deselected` for the added
  factory/journal/containment lane.
- Full `test_phase53_primary_edge.py`: `173 passed, 2 xfailed`.
- All test runs used `omni srv1-ops resources run builds`; the governor proved
  `CPUQuota=80%` (20% total on the four-vCPU host), `structural_ok=true` and
  `doctor_ok=true`.
- No SSH, Vault, OCI, Cloudflare, DNS, firewall, Apache, listener, package or
  RustDesk live operation ran. No client was installed.

## Remaining gate

Plan 53-05 remains blocked before mutation. Concrete provider adapters, a
fresh current preflight/capacity-finalize and explicit owner approval bound to
the candidate hashes are still required. The preliminary capacity result is
PASS only for Horistic; srv2/srv3 remain projected-disk NO-GO. Plans 53-06 and
Phase 54 remain blocked until the current live gate is independently proven.

---
*Phase: 53-primary-relay-and-public-edge*
*Plan: 05A*
*Completed on 2026-07-23*
