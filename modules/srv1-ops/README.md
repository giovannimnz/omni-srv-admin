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
| `scripts/resource-governor-snapshot.py` | Snapshot leve de PSI/memória/disco/top consumers | `resource-governor-snapshot.timer` |
| `scripts/resource-governor-audit.py` | Audit diário de hotspots de build/caches/imagens | `resource-governor-audit.timer` |
| `scripts/resource-governor-watchdog.py` | Watchdog contínuo com auto-cleanup e runtime override | `resource-governor-watchdog.timer` |
| `scripts/resource-governor-status.py` | Status atual do resource governor | manual |
| `scripts/backup-to-smb.sh` | Backup fallback SMB | `backup-smb-daily.timer` |
| `scripts/atius-web-healthcheck.sh` | Healthcheck legado Atius Web | manual/legacy |

## CLI

```bash
omni srv1-ops list
omni srv1-ops status
omni srv1-ops logs --limit 30
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources install
omni srv1-ops resources logs
omni srv1-ops resources watchdog
omni srv1-ops resources run builds -- podman build -t my-app .
omni srv1-ops run sync-vault
omni srv1-ops run cleanup-local --dry-run
omni srv1-ops run backup-gdrive
omni srv1-ops run offload-dotbackups
```

## Resource governor

- Perfis: `builds`, `interactive`, `transfers`
- Fonte de verdade: `configs/resource-governor.env`
- Runbook: `docs/operations/resource-governor.md`
- Logs: `~/.logs/resource-governor/`
- Runtime override live: `~/.config/omni/resource-governor.runtime.env`
- Gatilho pós-build: `omni srv1-ops resources run builds -- ...` agenda automaticamente:
  - `cleanup-local.sh` em `CLEANUP_MODE=build-hygiene` após 5 min
  - snapshot após 15 min
  - audit após 35 min
- Watchdog contínuo: `resource-governor-watchdog.timer` roda a cada 2 min, aplica override conservador e dispara cleanup/audit quando o host entra em estado crítico.

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
