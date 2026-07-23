---
phase: 53-primary-relay-and-public-edge
plan: 05
subsystem: live-deployment
tags: [rustdesk, live-gate, blocked, fail-closed]
requires:
  - phase: 53-04
    provides: hermetic edge/DNS-last transaction and probe harness
provides:
  - deterministic blocker evidence for the missing Phase 53 live runner
affects: [53-06, phase54-heterogeneous-canary]
tech-stack:
  added: []
  patterns: [explicit-live-flag, no-mutation-on-unimplemented-stage]
key-decisions:
  - "Do not fabricate live evidence or call infrastructure while the runner has no implemented handlers."
  - "Keep the Plan 05 command/runner stage mismatch explicit; revising it requires a code/plan closure, not a silent alias."
requirements-completed: []
duration: approximately 10min
completed: 2026-07-23
status: blocked
---

# Phase 53 Plan 05: Controlled live deployment and public proof

**Blocked before mutation.** The contract tests pass, but the live runner is
still the Phase 53-01 fail-closed interface and cannot execute this plan.

## Deterministic blocker

- The prescribed Plan 05 verification command uses `--stage edge-probes`, but
  `run-phase53-live-gate.py` accepts only `preflight`, `runtime`, `ops-api`,
  `host-edge`, `oci-edge`, `ip-probes`, `dns-publication`,
  `hostname-probes`, `lifecycle`, `rollback` and `report`.
- With the explicit `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1` flag and a valid stage,
  `main()` still returns `BLOCKED` with `preflight-input-required`.
- `Phase53LiveGate.run_stage()` always raises `stage-not-implemented`.
- `modules/rustdesk-fleet/evidence/phase53/` has no live transaction or probe
  evidence.

## Safe verification

- Phase 53 contract/live-boundary suite: `167 passed, 2 xfailed` under the
  builds governor (`structural_ok=true`, `CPUQuota=80%`).
- Narrow checkpoint suite covering the explicit-live flag, preflight/rollback
  barriers, ordered receipt schema, redaction/auth negatives and unflagged CLI:
  `27 passed, 142 deselected` under the same governor.
- Prescribed live command: exit `2` at argparse stage validation; no provider,
  SSH, Vault, DNS, OCI, firewall, Apache, listener or RustDesk operation ran.
- No evidence or secret material was produced.

## Checkpoint

The atomic Plan 53-05 verification unit is closed at the current fail-closed
boundary. No implementation or runtime mutation was started after the runner
gap was confirmed; the next unit must implement/review the handlers and align
the `edge-probes` stage contract before any live retry.

## Post-checkpoint continuation

After this checkpoint, the runner was extended to accept `edge-probes` and to
dispatch stages only through explicitly injected adapters with validated
receipts. The aggregate hermetic suite still passes (`167 passed, 2 xfailed`).
No concrete live adapter or preflight evidence was installed, so the CLI
continues to fail closed with `preflight-input-required` or
`stage-adapter-required:<stage>`. No provider, SSH, Vault, DNS, OCI, firewall,
Apache, listener or RustDesk live operation ran. Plan 53-05 therefore remains
blocked and the partial runner contract is preserved for the next session.

## Required closure

Implement and independently test the Plan 05 runner handlers/adapters, or
revise the plan to the actual staged interface with an equivalent explicit
contract. The implementation must preserve the current fail-closed flag,
source/contract/pre-state/rollback gates and produce redacted evidence before
any live mutation. Do not mark SRV-02/03/04 or OPS-01 complete from this state.

## Next Phase Readiness

Blocked. Plan 06 and Phase 54 remain gated. Resume with:

`$gsd-autonomous --resume-goal --ws rustdesk-fleet`

---
*Phase: 53-primary-relay-and-public-edge*
*Plan: 05*
*Blocked on 2026-07-23 before live mutation*
