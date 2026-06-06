# Fleet architecture

## Principle

`omni-srv-admin` is the source of operational truth. Hosts are data. Modules are capabilities. The CLI binds host data + module capability + explicit operator intent.

## Layers

```text
hosts/*.yaml       -> inventory and constraints
modules/*          -> reusable or host-specific capability
cli/omni/*         -> command surface
~/.logs/           -> local operational logs per host
GDrive Backup/     -> off-host backup per host
vault              -> decisions, worklogs, postmortems
```

## Safety gates

| Operation | Gate |
|---|---|
| read-only status | allowed if host access is configured |
| file copy | dry-run + backup target first |
| service restart | explicit host + service + reason |
| package install | host profile + package manager detection |
| destructive cleanup | backup + `--yes` + documented scope |
| support external host | authorization + incident note + no secret persistence |

## Naming

- Host ids: kebab-case (`atius-srv-1`, `giovanni-s23-termux`).
- Module names: kebab-case (`srv1-ops`, `fleet`, `remote-manager`).
- Logs: `~/.logs/<module>/<operation>.log` where possible.

## Why not one script per computer

One script per computer duplicates logic and makes drift inevitable. The right shape is:

```text
fleet command + host profile + module capability
```

Example:

```bash
omni fleet run atius-srv-2 backup.status
omni fleet sync-module remote-manager --target dell-inspiron-3520 --dry-run
```
