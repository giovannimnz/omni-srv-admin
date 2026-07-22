# Phase 52-07 Authorization Record

- `accountable`: Giovanni Muniz
- `recorded_at`: 2026-07-22T03:19:28-03:00
- `scope`: Gate A managed sources and the Gate B srv3 Vault control-plane transaction described by Plan 52-07
- `secret_values_recorded`: false
- `existing_horistic_transport_key_reused`: true
- `transport_key_rotation_or_generation_authorized`: false

## Approved RustDesk Vault paths

1. `kv/atius/rustdesk/server`
2. `kv/atius/rustdesk/targets/atius-srv-1`
3. `kv/atius/rustdesk/targets/atius-srv-2`
4. `kv/atius/rustdesk/targets/atius-srv-3`
5. `kv/atius/rustdesk/targets/horistic-srv`
6. `kv/atius/rustdesk/targets/giovanni-w11-pc`

Approved fields are names only: `private_key`, `public_key`, and one `permanent_password` per target path.

## Approved rclone binding

- Profile: `rclone-giovanni-drive-phase52`
- Vault reference: `kv/atius/fleet-backup/rclone/giovanni-drive#rclone_conf`
- Approved remote stanza: `[giovanni-drive]`
- Persistence outside caller-owned tmpfs: prohibited

## Authorized srv3 control-plane scope

The future Gate B transaction may install only the reviewed backend, exact forced-command dispatcher, two exact profile readers, one sudoers allowlist, and one unique restricted `authorized_keys` entry. It must verify the full existing Horistic key fingerprint before writing, use `restrict,no-user-rc`, and provide tested rollback. This record authorizes no Vault value disclosure, no data-plane mutation on srv2/srv3, no public listener, no remote backup deletion, and no Windows client installation.
