---
status: complete
phase: 34-freeipa-dns-and-client-enrollment
source:
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/34-freeipa-dns-and-client-enrollment/34-VERIFICATION.md
updated: 2026-06-26T19:45:00-03:00
---

# Phase 34 UAT

## Tests

### 1. FreeIPA DNS Reachability

expected: `ipa.atius.internal` resolves through the FreeIPA/CoreDNS path.
result: [passed]
notes: Verification records `srv3` and `horistic-srv` resolving
`ipa.atius.internal` as `10.1.1.3`.

### 2. Real Host Enrollment

expected: A real Linux host can enroll to `ATIUS.INTERNAL` over WireGuard.
result: [passed]
notes: `atius-srv-3` enrollment succeeded as
`atius-srv-3.atius.internal`.

### 3. FreeIPA User and Sudo Smoke

expected: Domain user lookup and sudo policy smoke succeed on the enrolled host.
result: [passed]
notes: `getent passwd admin`, `id admin`, and `sudo -l -U admin` passed.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
blocked: 0
