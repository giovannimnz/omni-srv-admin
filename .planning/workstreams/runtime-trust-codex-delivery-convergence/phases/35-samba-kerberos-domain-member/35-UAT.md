---
status: complete
phase: 35-samba-kerberos-domain-member
source:
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/35-samba-kerberos-domain-member/35-VERIFICATION.md
updated: 2026-06-26T19:45:00-03:00
---

# Phase 35 UAT

## Tests

### 1. Samba Domain Member on srv1

expected: `atius-srv-1` is enrolled in `ATIUS.INTERNAL` and Samba has a valid
Kerberos principal/keytab.
result: [passed]
notes: Verification records `cifs/atius-srv-1.atius.internal`,
`/etc/samba/samba.keytab`, and successful `ipa-client-samba`.

### 2. Share Cutover

expected: `/srv/Shared` is served from `srv1` and old Samba on `srv2` is
disabled after cutover.
result: [passed]
notes: Verification records matching share size and `smbd`/`nmbd` disabled on
`srv2`.

### 3. Kerberos SMB Smoke

expected: Kerberos-authenticated `smbclient` can list the `Shared` share.
result: [passed]
notes: `smbclient //atius-srv-1.atius.internal/Shared -k` passed.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
blocked: 0
