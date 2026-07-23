---
phase: 35
status: passed
verified: 2026-06-26T09:40:00-03:00
requirements:
  - DOM-05
---

# Phase 35 Verification

## Passed Checks

| Check | Result |
|---|---|
| `atius-srv-1` enrolled in `ATIUS.INTERNAL` | PASS |
| `cifs/atius-srv-1.atius.internal` principal present | PASS |
| `/etc/samba/samba.keytab` refreshed and valid on `srv1` | PASS |
| `ipa-client-samba` completed on `srv1` | PASS |
| `smbd` and `winbind` active on `srv1` | PASS |
| `nmbd` intentionally disabled on `srv1` | PASS |
| `/srv/Shared` on `srv1` matches source share size (`8.8G`) | PASS |
| `/home/ubuntu/Shared_smb` on `srv1` now points to local data | PASS |
| `smbd` and `nmbd` stopped/disabled on `srv2` | PASS |
| `smbclient //atius-srv-1.atius.internal/Shared -k -U ATIUS\\giovanni -c ls` | PASS |

## Requirement Closure

DOM-05 is complete:

- Samba now authenticates through FreeIPA/Kerberos on the destination host
  `atius-srv-1`
- the existing share data was copied locally before cutover
- the old Samba service on `atius-srv-2` was disabled after the new host was
  serving successfully

## Residual Notes

- The cutover preserved share semantics by forcing local ownership to
  `ubuntu:ubuntu`, not by remapping existing files to FreeIPA POSIX owners.
- `ubuntu` and `horistic` were not created in FreeIPA during this phase to
  avoid local/domain collision on `srv1`.
- `giovanni` and `sambauser` were created in FreeIPA as domain-backed share
  users for the first successful Kerberos smoke path.
