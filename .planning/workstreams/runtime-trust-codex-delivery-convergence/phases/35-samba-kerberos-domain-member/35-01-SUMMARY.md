---
phase: 35
plan: 35-01
status: complete
completed: 2026-06-26T09:40:00-03:00
requirements:
  - DOM-05
key-files:
  created:
    - docs/domain/samba-freeipa-cutover.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/35-samba-kerberos-domain-member/35-VERIFICATION.md
  modified:
    - inventory/remotes/srv1-shared-smb.yaml
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
metrics:
  srv2_share_size: 8.8G
  srv1_share_size: 8.8G
  kerberos_smoke: passed
  old_srv2_samba: disabled
---

# Summary: 35-01 Samba domain member, Kerberos auth, shares migration and smoke tests

## Outcome

Phase 35 passed.

The `Shared` Samba service moved from `atius-srv-2` to `atius-srv-1`, while
authentication moved to FreeIPA/Kerberos.

## What changed

| Item | Result |
|---|---|
| `atius-srv-1` FreeIPA enrollment | PASS |
| `cifs/atius-srv-1.atius.internal` service principal | PASS |
| Samba keytab on `srv1` | PASS |
| Share data copy from `srv2` to `srv1` | PASS (`8.8G` -> `8.8G`) |
| Local bind mount `/srv/Shared -> /home/ubuntu/Shared_smb` on `srv1` | PASS |
| Old Samba service on `srv2` | stopped and disabled |
| Kerberos SMB smoke with `giovanni@ATIUS.INTERNAL` | PASS |

## Important technical notes

- `ipa-client-samba` was required on `srv1` to make the host a supported Samba
  member server under FreeIPA.
- `ipa-adtrust-install` was required inside the FreeIPA container on `srv3` so
  the Samba member path had a usable trust controller.
- The private FreeIPA gateway on `10.1.1.3` had to be expanded to include the
  Samba/DC locator ports needed by the member server path.
- The CIFS keytab on `srv1` had to be refreshed after `ipa-adtrust-install`
  because the previous key version no longer matched the KDC-issued service
  ticket.

## Scope control

- No public Samba exposure was added.
- `nmbd` on `srv1` remains intentionally disabled; the Linux/Kerberos path is
  served by `smbd` and `winbind`.
- The share still forces local filesystem ownership to `ubuntu:ubuntu`, so the
  migration preserved access semantics before any POSIX ownership redesign.
- `ubuntu` and `horistic` were intentionally not duplicated in FreeIPA during
  this cutover to avoid local/domain name collisions on `srv1`.
