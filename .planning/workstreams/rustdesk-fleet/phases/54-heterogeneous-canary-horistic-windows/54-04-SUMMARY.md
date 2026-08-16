---
phase: 54-heterogeneous-canary-horistic-windows
plan: 04
status: code-only-blocked
completed: 2026-07-23
---

# Plan 54-04 Summary

## Atomic checkpoint

- Implemented the hermetic permission projection in
  `modules/rustdesk-fleet/tools/phase54_permission_matrix.py`. Requested
  policy is never treated as effective proof; allow/deny results require
  explicit observed markers and unsupported controls remain `BLOCKED`.
- Implemented the direct-first/controlled-forced-relay projection in
  `modules/rustdesk-fleet/tools/phase54_transport_matrix.py`. The relay path
  requires an injected controlled purpose, direct-first ordering, UI/pairing
  markers and a positive `hbbr` byte delta; public RustDesk servers, WAN retry
  and default-policy changes are rejected.
- Implemented value-free LightDM/X11, UAC/RDP and pre-login checkpoint
  projection in `modules/rustdesk-fleet/tools/phase54_checkpoint_redaction.py`.
  `PASS` requires explicit observed and human-verified markers; missing or raw
  GUI/identity material remains `PENDING`/`BLOCKED`.
- Every mutating entrypoint remains behind the shared Phase 54 preflight. The
  new modules perform no SSH, socket, RustDesk, GUI, Vault or filesystem I/O
  beyond loading checked-in contracts in their CLI mode.

## Verification

- Governed Plan 54-04-01 selector: `11 passed, 40 deselected`.
- Governed full Phase 54 suite: `51 passed` under the builds governor with
  `CPUQuota=80%` (20% of the 4-vCPU host), `doctor_ok=true` and
  `structural_ok=true`.
- `py_compile` and the value-free negative fixtures passed; no live evidence
  file was created or promoted.
- Current independent Phase 53 validator remains
  `state=BLOCKED`, `candidate_status=NOT_ADMITTED`,
  `mutation_performed=false`.

## Deliberately not executed

Plan 54-04-02 remains blocked. No Horistic/W11 session, permission readback,
forced-relay connection, `hbbr` probe, GUI/UAC checkpoint, fallback smoke,
reboot or client mutation was attempted. The live matrix cannot start until
Phase 53 independently returns `PASS/ADMITTED_PHASE53` and a current,
owner-bound Phase 54 receipt exists.
