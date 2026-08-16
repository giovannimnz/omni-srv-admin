---
phase: 54-heterogeneous-canary-horistic-windows
plan: 01
status: contract-complete-live-blocked
completed: 2026-07-23
---

# Phase 54 Plan 01 Summary

## Delivered

- Added strict client runtime, canary topology, permission and transport
  contracts for the two allowed targets: `horistic-srv` and
  `GIOVANNI-W11-PC`.
- Bound the pinned 1.4.9 DEB/MSI hashes, Vault reference-only password/public
  key fields, client-only rollback domains, direct-first/controlled-relay
  policy and public-server prohibition.
- Added nine value-free negative fixtures covering excluded targets, server
  path writes, hash drift, secret surfaces, public servers, forced-relay
  default and unsupported controls.
- Added initial Phase 54 evidence as `BLOCKED/PENDING` with
  `mutation_performed=false`; no live PASS was manufactured.

## Verification

- All six JSON artifacts passed strict `json.tool` parsing.
- `test_phase54_canary.py`: `15 passed` under the builds governor
  (`CPUQuota=80%` no cgroup, equivalente a 20% do host de 4 vCPU;
  `doctor_ok=true`, `structural_ok=true`).
- Graphify remains `stale=false`, `commit_stale=false` at `63bbb63`.

## Remaining blocker

Phase 54 execution remains gated by an independent current Phase 53 PASS and
the shared preflight contract. No installer, SSH, Vault hydration, package,
GUI, reboot or client mutation was attempted.
