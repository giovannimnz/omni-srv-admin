# Configuration

## Environment variables

| Var | Default | Uso |
|---|---|---|
| `OMNI_SRV_ADMIN` | `/home/ubuntu/GitHub/omni-srv-admin` | root do repo usado pela CLI |
| `OMNI_LOG_DIR` | `~/.logs` | logs operacionais locais |

## Inventory paths

```text
inventory/hosts/
inventory/groups/
inventory/remotes/
```

## Host inventory

```yaml
id: atius-srv-1
aliases: [srv1, atius]
role: production
status: active
modules:
  - srv1-ops
  - xrdp-abnt2
```

## Remote inventory

```yaml
id: srv1-shared-smb
host_id: atius-srv-1
type: cifs
source: //10.1.1.2/Shared
mount_path: /home/ubuntu/Shared_smb
display_label: Shared_smb
```

## Systemd user units

Live:

```text
~/.config/systemd/user/
```

Versionado:

```text
modules/srv1-ops/systemd/
```

## Logs

```text
~/.logs/
```

Retenção padrão: 15 dias.

## Backup map

```text
modules/srv1-ops/configs/backup-map.yaml
```

## PCManFM/LXDE Places

GTK bookmarks:

```text
~/.config/gtk-3.0/bookmarks
```

Managed via:

```bash
omni remote-manager places
omni remote-manager rename-label srv1-shared-smb Shared
```

## Fleet config

```text
modules/fleet/configs/config.yaml
```

Campos principais:

```yaml
default_log_dir: ~/.logs/fleet
host_inventory_dir: inventory/hosts
remote_inventory_dir: inventory/remotes
require_explicit_host: true
require_backup_before_write: true
```
