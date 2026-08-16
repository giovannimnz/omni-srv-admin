---
phase: 54-heterogeneous-canary-horistic-windows
status: planned-blocked-on-phase53
---

# Phase 54 Context

Phase 54 is the heterogeneous canary for `horistic-srv` (Ubuntu ARM64) and
`GIOVANNI-W11-PC` (Windows x86-64). It may be planned before Phase 53 closes,
but it must not execute until an independent Phase 53 verifier accepts current
server, edge, rollback and Ops API evidence.

## Scope

- Install and configure RustDesk Client 1.4.9 serially on Horistic and W11.
- Keep server/client identities, resources and rollback domains separate.
- Prove package/service/config/ID persistence, direct-first, one controlled
  forced-relay path, permission negatives, reboot/reconnect and existing
  fallback regressions.
- Prove Horistic active LXDE/X11, lock/logout and LightDM pre-login without
  changing LightDM, autologin or creating a dummy seat.
- Prove W11 target identity, lock/logon, UAC secure desktop, console/RDP and
  service recovery. Existing inventory says the RDP credential path is not yet
  proven; a human credential checkpoint or an explicit BLOCKED result is
  mandatory.

## Prohibitions

- No WSL or `GIOVANNI-S23` installation.
- No Phase 53 server Quadlet/state/identity/port/ops-api writes from client
  transactions.
- No password in argv, environment dumps, shell history, PowerShell transcript,
  stdout, journal, Git, Obsidian or GBrain.
- No PASS based only on service-active, ID, requested permission policy or a
  summary; every capability needs effective observed proof.
- No public RustDesk servers; direct-first is default and forced relay is only a
  controlled validation/fallback.

## Prerequisite gate

`phase53` current PASS, owner-bound admission, fresh capacity/pre-state,
independent verifier and Graphify freshness are required before any Phase 54
task that mutates a host. If any prerequisite is absent, plans end in a
value-free BLOCKED receipt.
