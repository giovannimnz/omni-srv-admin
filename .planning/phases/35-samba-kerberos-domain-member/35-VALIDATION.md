---
phase: 35
title: "Validation - Samba Kerberos domain member"
date: 2026-06-26
status: passed
requirements:
  - DOM-05
---

# Phase 35 Validation

Phase 35 validates as complete.

## Evidence Reviewed

- `35-VERIFICATION.md` is marked `status: passed`.
- `atius-srv-1` is enrolled in `ATIUS.INTERNAL`.
- Samba services are active on `srv1`; `nmbd` is intentionally disabled there.
- Old Samba services on `srv2` are stopped/disabled.
- Kerberos `smbclient` smoke passed.

## Nyquist Gap Review

| Axis | Result | Notes |
|---|---|---|
| Functional | PASS | Domain member and share access are covered. |
| Integration | PASS | FreeIPA/Kerberos and Samba are integrated on `srv1`. |
| Cutover | PASS | Data was copied before old service shutdown. |
| Residual | WARN | POSIX ownership was preserved as `ubuntu:ubuntu`; not remapped to domain owners in this phase. |
