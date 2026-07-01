# Samba FreeIPA Cutover

**Phase:** 35  
**Updated:** 2026-06-26

## Final state

| Item | Value |
|---|---|
| Samba serving host | `atius-srv-1` |
| Host FQDN | `atius-srv-1.atius.internal` |
| Share name | `Shared` |
| Share path | `/srv/Shared` |
| Stable local path on `srv1` | `/home/ubuntu/Shared_smb` (bind mount) |
| Auth model | FreeIPA / Kerberos |
| CIFS principal | `cifs/atius-srv-1.atius.internal@ATIUS.INTERNAL` |
| Keytab | `/etc/samba/samba.keytab` |

## Service posture

On `atius-srv-1`:

- `smbd`: active
- `winbind`: active
- `nmbd`: intentionally disabled

On `atius-srv-2`:

- `smbd`: disabled
- `nmbd`: disabled

## Share semantics

The cutover preserved the existing practical access model:

- share data copied from `/home/ubuntu/Shared` on `srv2`
- destination share at `/srv/Shared` on `srv1`
- local mount path on `srv1` switched from remote CIFS to local bind mount
- Samba still forces created files to `ubuntu:ubuntu`

This avoids a POSIX ownership redesign during the first Kerberos migration.

## First successful Kerberos smoke

```bash
kinit giovanni
smbclient //atius-srv-1.atius.internal/Shared -k -U ATIUS\\giovanni -c ls
```

## Rollback anchors

- `srv1` Samba backup:
  `/etc/samba/smb.conf.pre-phase35-*`
- `srv2` Samba backup:
  `/root/phase35-srv2-*/`
- `srv1` migration bundle:
  `/root/freeipa-35-srv1-20260626T104612Z/`

## Caveats

- `ubuntu` and `horistic` were not added to FreeIPA in this phase to avoid
  local/domain username collisions on `srv1`.
- The FreeIPA private gateway on `srv3` was expanded for Samba member-server
  discovery and trust-controller traffic; keep it private to WireGuard only.
