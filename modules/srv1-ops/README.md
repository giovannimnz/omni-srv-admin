# srv1-ops — ATIUS-SRV-1 operational scripts

## Status

Centraliza automações operacionais antes espalhadas por `~/scripts`, `~/bin`, `~/.local/bin` e crontab.

## Regra

- Script operacional cross-projeto fica neste módulo.
- Script específico de repo fica no repo do projeto.
- Log operacional local fica em `~/.logs/`.
- Retenção local de logs: 15 dias.
- Backup/offload vai para GDrive em estrutura que recria o ambiente original.
- `~/scripts` e `~/bin` não devem receber novas automações.

## Scripts gerenciados

| Script | Função | Schedule |
|---|---|---|
| `scripts/sync-vault.sh` | Sync git do Obsidian vault | crontab a cada 5min |
| `scripts/backup-srv1-to-gdrive.sh` | Backup completo SRV-1 → GDrive | `backup-srv1-daily.timer` |
| `scripts/offload-dotbackups-to-gdrive.sh` | Offload `~/.backups` com verify/delete | `offload-dotbackups-to-gdrive.timer` |
| `scripts/cleanup-local.sh` | Cleanup semanal + retenção `~/.logs` 15d | `cleanup-local-weekly.timer` |
| `scripts/backup-to-smb.sh` | Backup fallback SMB | `backup-smb-daily.timer` |
| `scripts/atius-web-healthcheck.sh` | Healthcheck legado Atius Web | manual/legacy |

## CLI

```bash
omni srv1-ops list
omni srv1-ops status
omni srv1-ops logs --limit 30
omni srv1-ops run sync-vault
omni srv1-ops run cleanup-local --dry-run
omni srv1-ops run backup-gdrive
omni srv1-ops run offload-dotbackups
```

## GDrive layout

```text
giovanni-drive:ATIUS-SRV/SRV-1/Backup/
├── snapshots/
│   └── snapshot-YYYY-MM-DD_HHMMSS/
│       └── home/ubuntu/
│           ├── GitHub/
│           ├── docker/
│           ├── .hermes/
│           ├── .config/
│           ├── .local/bin/
│           ├── .logs/
│           └── Shared_smb/
└── home/ubuntu/
    ├── .backups/
    └── .logs/
```

## Migration notes

- `~/logs` foi migrado para `~/.logs`.
- `/home/ubuntu/docs` foi migrado para `docs/legacy-home-docs/home-docs-2026-06-06/` no repo `omni-srv-admin`.
- Crontab `sync-vault` agora aponta para `modules/srv1-ops/scripts/sync-vault.sh`.
- Systemd timers de backup/cleanup apontam para scripts deste módulo.

## Pitfalls

- Não usar `rclone move` direto para backup crítico. Usar copy → verify → delete.
- Não usar `~/GDrive` como caminho de destino para backup pesado; usar `rclone copy` direto no remote.
- Não apagar `~/scripts`/`~/bin` antes de validar crontab, systemd, PM2 e referências.
- `--delete` no rsync só com profile mirror e confirmação explícita.
- Backup que não foi testado não é backup.
