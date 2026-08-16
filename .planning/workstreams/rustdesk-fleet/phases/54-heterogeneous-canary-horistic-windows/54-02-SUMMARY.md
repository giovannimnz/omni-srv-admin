---
phase: 54-heterogeneous-canary-horistic-windows
plan: 02
status: code-only-blocked
completed: 2026-07-23
---

# Phase 54 Plan 02 Summary

## Delivered (hermetic only)

- Added `phase54_preflight.py` as the single read-only admission boundary for
  every client mutation. It dynamically runs the independent Phase 53
  validator, requires `ADMITTED_PHASE53`/independent `PASS`, exact current
  `HEAD`, matching Phase 53 contract digests, Giovanni Muniz owner binding,
  current capacity/pre-state/rollback/Graphify fields, exact target scope and
  an empty blocker list.
- Changed `install-phase54-client.py` to delegate to that shared validator;
  the old weaker receipt path no longer exists.
- Hardened `rustdesk-client-vault.py` so validated references retain the
  explicit non-durable marker while secret delivery remains injected and
  ephemeral (FD pipe or tmpfs only).
- Added hermetic tests for the blocked initial receipt, receipt drift before a
  backend call, Vault reference/channel cleanup and value-free output.
- Added fake transaction coverage for success ordering/FD delivery, rollback
  after backend failure, hash+architecture verification, client-only path
  guards and rejection of unscoped backends. The Linux verifier now reads the
  canonical target-level architecture and rejects path traversal/symlink or
  contract-policy relaxation.
- Bound Phase 54 receipts to the current Phase 53 admission authority and
  exact Phase 54 contract digests; raw Vault bytes are no longer returned to a
  caller.

## Verification

- Governed Plan 54-02 selector: `7 passed, 28 deselected`; full Phase 54 suite:
  `35 passed` under `CPUQuota=80%` no cgroup (20% do host de 4 vCPU)
  (`structural_ok=true`, `doctor_ok=true`).
- `git diff --check`: PASS.
- Current Phase 53 validator: `state=BLOCKED`,
  `candidate_status=NOT_ADMITTED`, `mutation_performed=false`.
- Installer against `evidence/phase54/initial-gate.json`: `BLOCKED` with
  `phase53-independent-pass-required`, exit `2`; no backend/package path was
  touched.
- Graphify remains fresh at `63bbb63`; no rebuild was started.

## Deliberately not executed

The Horistic install task and live evidence task remain pending. No SSH, Vault
fetch, package install, LightDM/X11 probe, GUI/UAC checkpoint, reboot, service
change or client mutation was attempted. Plan 54-02 is **not complete**.
