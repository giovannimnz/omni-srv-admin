---
phase: 53-primary-relay-and-public-edge
plan: 05C
status: ready-for-plan-check
---

# Plan 53-05C Research

## Evidence routing

- `validate_phase53_live_evidence.py` is the read-only validator and must run
  before and after every attempt.
- `collect_capacity_sample()` is safe for bounded observation; the Phase 52
  `run_capacity_live` and supply refresh paths write historical artifacts and
  are not reusable as current authority.
- `phase53_production_adapters.py` is the only reviewed seam. It requires
  explicit callbacks, manifest routes, value-free output and an authorization
  decision supplied by the caller.
- `run-phase53-live-gate.py` must open the journal only after current
  preflight/admission/provider checks.

## Ordering

1. Prove exact source/contract/provider/runtime digests and owner-bound
   admission; otherwise stop.
2. Collect serial capacity samples in `srv2 -> srv3 -> horistic` order, retain
   predecessor NO-GO receipts and finalize Horistic only if all recovery gates
   pass; never clean srv2/srv3.
3. Bind the reviewed provider bundle and execute runtime/ops/edge/IP/DNS-last/
   hostname/report exactly once; containment is first on any failure.
4. Validate evidence, run the governed suite and produce an honest summary;
   only an independent verifier PASS can release Plan 06.

## Negative controls

- Unsigned candidate, stale capacity, digest drift, missing preflight, missing
  callback, non-255 W11 private failure, secret output and concurrent CAS drift
  all remain deterministic BLOCKED paths.
- No DNS, OCI, Apache, Vault, package, firewall or client mutation may occur
  before the preceding proof.
