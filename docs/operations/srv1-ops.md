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
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources install --dry-run
omni srv1-ops resources install
omni srv1-ops resources logs
omni srv1-ops resources watchdog
omni srv1-ops resources run builds -- podman build -t my-app .
omni srv1-ops run sync-vault
omni srv1-ops run cleanup-local --dry-run
omni srv1-ops run backup-gdrive
omni srv1-ops run offload-dotbackups
omni srv storage-audit all
omni srv autoclean all
omni srv autoclean all --apply
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
| `resource-status` | `scripts/resource-governor-status.py` |
| `resource-snapshot` | `scripts/resource-governor-snapshot.py` |
| `resource-audit` | `scripts/resource-governor-audit.py` |
| `resource-watchdog` | `scripts/resource-governor-watchdog.py` |
| `backup-smb` | `scripts/backup-to-smb.sh` |
| `atius-web-health` | `scripts/atius-web-healthcheck.sh` |

## Resource governor

- Perfis: `builds`, `interactive`, `transfers`
- Config: `modules/srv1-ops/configs/resource-governor.env`
- Slices versionadas: `modules/srv1-ops/systemd/omni-*.slice`
- Timers versionados: `modules/srv1-ops/systemd/resource-governor-*.timer`
- Runtime override live: `~/.config/omni/resource-governor.runtime.env`
- Runbook detalhado: `docs/operations/resource-governor.md`
- Gatilho pós-build: o wrapper `omni srv1-ops resources run builds -- ...` agenda cleanup leve após 5 min e revalida snapshot/audit depois.
- Watchdog contínuo: observa thresholds críticos e ajusta os profiles live para modo conservador quando necessário.
- Status: reporta units repo/live, services/timers, jobs presos, refs PM2 legadas e cgroups diretos.

## Timers

Referência versionada:

```text
modules/srv1-ops/systemd/*.service
modules/srv1-ops/systemd/*.timer
modules/fleet-autoclean/systemd/*.service
modules/fleet-autoclean/systemd/*.timer
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
- `omni srv1-ops resources install --dry-run` deve preceder instalação live.
- `resources install` não para PM2, XRDP ou SSHD; ações de restart/stop continuam gateadas.
- `omni srv autoclean` roda dry-run por padrão; execução real exige `--apply`.
- `offload-dotbackups` usa copy → verify → delete.
- Não aplicar delete-after-verify em diretórios vivos (`~/GitHub`, `~/.hermes`, `~/.config`).
