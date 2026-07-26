---
phase: 53-primary-relay-and-public-edge
plan: 05C
type: execute
gap_closure: true
status: blocked-until-authority
---

# Plan 53-05C Context

Plan 05C is the explicit continuation for the live remainder of 05B. It must
not rewrite Phase 52 or treat its historical 1.1.15 PASS as current authority.
The current candidate is 1.1.16, `NOT_ADMITTED` because provenance is unsigned
and the Giovanni Muniz owner-bound exception is still empty. Fresh capacity
read-only samples show srv2 and srv3 are NO-GO; Horistic is only preliminary
eligible until `capacity_finalize`, recovery and rollback evidence exist.

The only production path is one owner-bound transaction using the typed
provider bundle. It remains fail-closed when current preflight, contract/source
digests, admission, capacity, pre-state or rollback readiness are missing. A
blocked attempt must leave no provider call, journal or mutation.

## Scope

- Included: current supply/admission, serial capacity-finalize, explicit
  provider binding, one ordered Phase 53 transaction, and value-free evidence.
- Excluded: Phase 52 regeneration, srv2/srv3 cleanup, Windows/Linux client
  installation, Phase 54 canary work, and any default/ambient provider.
- Required owner: Giovanni Muniz for exact candidate hashes, risk disposition,
  expiry and any provenance exception.

## Current blockers

1. `candidate-admission.json` is `BLOCKED_PROVENANCE_UNSIGNED`/
   `NOT_ADMITTED`.
2. `capacity-current.json` is blocked; Horistic `capacity_finalize` is stale.
3. No current `preflight.json` exists and no provider backend is bound.

The plan may end in an explicit blocked receipt if any blocker remains. That is
safe progress, not a Phase 53 PASS.
