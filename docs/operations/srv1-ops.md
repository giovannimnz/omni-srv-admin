# SRV-1 Ops Operations

## Objetivo

Centralizar scripts operacionais locais do ATIUS-SRV-1 em um módulo versionado.

```text
modules/srv1-ops/
├── configs/backup-map.yaml
├── docs/source-map.md
├── scripts/
└── systemd/
```

## Comandos

```bash
omni srv1-ops list
omni srv1-ops status
omni srv1-ops logs --limit 30
omni srv1-ops run sync-vault
omni srv1-ops run cleanup-local --dry-run
omni srv1-ops run backup-gdrive
omni srv1-ops run offload-dotbackups
```

## Logs

```text
/home/ubuntu/.logs/
```

Retenção local: 15 dias.

## Scripts

| Nome CLI | Script |
|---|---|
| `sync-vault` | `scripts/sync-vault.sh` |
| `backup-gdrive` | `scripts/backup-srv1-to-gdrive.sh` |
| `offload-dotbackups` | `scripts/offload-dotbackups-to-gdrive.sh` |
| `cleanup-local` | `scripts/cleanup-local.sh` |
| `backup-smb` | `scripts/backup-to-smb.sh` |
| `atius-web-health` | `scripts/atius-web-healthcheck.sh` |

## Timers

Referência versionada:

```text
modules/srv1-ops/systemd/*.service
modules/srv1-ops/systemd/*.timer
```

Instalação live fica em:

```text
~/.config/systemd/user/
```

## Backup GDrive

Base:

```text
giovanni-drive:ATIUS-SRV/SRV-1/Backup/
```

Mapa:

```text
modules/srv1-ops/configs/backup-map.yaml
```

## Segurança

- `cleanup-local` deve ter `--dry-run` antes de execução real.
- `offload-dotbackups` usa copy → verify → delete.
- Não aplicar delete-after-verify em diretórios vivos (`~/GitHub`, `~/.hermes`, `~/.config`).
