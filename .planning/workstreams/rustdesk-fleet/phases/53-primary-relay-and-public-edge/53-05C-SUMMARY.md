---
phase: 53-primary-relay-and-public-edge
plan: 05C
status: blocked-before-live-mutation
completed: 2026-07-23
---

# Plan 53-05C Summary

## Atomic checkpoint

- Implemented only the hermetic `RuntimeProvider` in
  `modules/rustdesk-fleet/tools/phase53_production_adapters.py`.
- The provider accepts an explicit transaction id, pre-state/install/rollback
  callbacks, edge callbacks and containment callback. It does not discover
  `PATH`, environment, Vault, SSH or subprocesses and is not wired as a CLI
  default.
- `to_bundle()` validates the complete callback set before invocation; the
  runtime stage orders `prestate -> install_closed` and invokes rollback on an
  install fault. Receipts remain value-free through the existing binder.
- The independent evidence validator now validates admitted-state semantics,
  not only gate labels: candidate/runtime/evaluation hashes, compatibility
  vectors, parity digests/consumers, serial capacity samples and TTL,
  pre-state/rollback, edge/ops receipts and provider manifest invariants. Any
  stale or relaxed fixture remains `BLOCKED`.

## Verification

- Governed focused tests: admitted-state semantic negatives pass (`1 passed,
  191 deselected`); the earlier provider/runtime focus also passed (`2 passed,
  190 deselected`).
- Governed Phase 53 suite: `191 passed, 1 xfailed`; governor reported
  `CPUQuota=80%`, `doctor_ok=true` and `structural_ok=true`.
- Evidence validator remains `NOT_ADMITTED/BLOCKED` with
  `mutation_performed=false`; explicit live CLI probe remains blocked at
  `preflight-input-required` and creates no journal.
- At the initial 05C checkpoint `git diff --check` passed and Graphify was
  fresh for HEAD `63bbb63`; later external SSO commits require a new canonical
  attestation rather than reusing that measurement.

## Follow-up audit — hardening complete, currentness still blocked

- The four audited gaps were fixed within the owned validator/test files:
  exact serial capacity order, strict `sha256:` references, generic secret
  flag rejection and deterministic `Mapping` checks for provider/edge
  payloads. The semantic regression lane passed `1 passed, 191 deselected`
  under the builds governor.
- Unrelated SSO commits advanced HEAD from `63bbb637` through `cde5db912` to
  `ca4dbddd2` while the unit was running. The real validator therefore returns
  `INVALID:source-head-drift`; the evidence source-head was intentionally not
  rewritten. Graphify has auto-refreshed and is fresh at `ca4dbddd2`, but the
  commits are outside the Phase51 post-review allowlist and do not authorize a
  RustDesk attestation.
- This code-only unit is hardening-complete but remains
  `blocked-before-live-mutation` for currentness and external authority. No
  Phase 53/54 live action is authorized.

## Remaining blocker

The plan is not complete. Fresh owner-bound admission/provenance, capacity
finalize, current preflight and an authorized live provider backend are still
absent. No Phase 53/54 live mutation, Vault hydration, cleanup or client
installation was attempted.
