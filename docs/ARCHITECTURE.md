# Architecture

> Fleet-first architecture for `omni-srv-admin`.

## Canonical doc

See:

```text
docs/architecture/overview.md
```

## Short version

```text
CLI (`omni`)
  -> inventory (`inventory/hosts`, `inventory/remotes`)
  -> modules (`modules/*`)
  -> live system (systemd, PM2, rclone, CIFS, GTK bookmarks)
```

## Key decisions

- Hosts moved from `hosts/` to `inventory/hosts/`.
- Remotes live in `inventory/remotes/`.
- Remote labels are separate from mount paths.
- `remote-manager` owns PCManFM/LXDE Places labels.
- `srv1-ops` owns SRV-1 local scripts.
- `fleet` owns multi-host inventory and future orchestration.

## Current modules

| Module | Path | CLI |
|---|---|---|
| Fleet | `modules/fleet/` | `omni fleet ...` |
| Remote Manager | `modules/remote-manager/` | `omni remote-manager ...` |
| SRV-1 Ops | `modules/srv1-ops/` | `omni srv1-ops ...` |
| XRDP ABNT2 | `modules/xrdp-abnt2/` | `omni xrdp-abnt2 ...` |
| Fork Sync | `modules/fork-sync/` | `omni fork-sync ...` |
