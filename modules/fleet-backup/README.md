# fleet-backup — Backup serial multi-server para GDrive

Fila serial de backups rclone (1 por vez, cooldown entre servers) para evitar
Google Drive API rate limit. Suporta 3 servers ATIUS (SRV-1, SRV-2, SRV-3).

## Componentes

- `scripts/rclone-fleet-queue.sh` — daemon de fila (enqueue/run/status/clear/drain)
- `scripts/install-fleet-backup.sh` — idempotente, instala num server
- `scripts/sync-backup-script.sh` — replica `backup-srv{N}-to-gdrive.sh` pros outros servers
- `systemd/rclone-fleet-queue.service` — service oneshot
- `systemd/rclone-fleet-queue.timer` — timer a cada 30min
- `configs/fleet-backup-map.yaml` — mapeamento srv_num → host

## Instalação

Num server novo:
```
cd ~/GitHub/omni-srv-admin
./modules/fleet-backup/scripts/install-fleet-backup.sh
```

Ou, no master (SRV-1), replicar o `backup-srv1-to-gdrive.sh` pros outros:
```
./modules/fleet-backup/scripts/sync-backup-script.sh
```

## Uso

```
# Adicionar jobs
omni fleet-backup enqueue 1
omni fleet-backup enqueue 2 snapshot-name

# Enfileirar os 3 servers de uma vez
omni fleet-backup enqueue-all

# Processar fila (auto via timer a cada 30min, ou manual)
omni fleet-backup run
omni fleet-backup status
omni fleet-backup clear
```

## Comportamento

- 1 worker por host (flock em `/tmp/rclone-fleet.lock`)
- 1 backup por server (flock remoto em `/tmp/rclone-srv{N}.lock`)
- Cooldown 5min entre servers (Google Drive quota = 840k queries/min)
- Max runtime 30min por job (timeout mata loop de retry)
- Cap 5 retries por job (anti filename bloat)
- Após 5 retries, job vira ABANDONED (sem retry infinito)

## Variáveis

```
COOLDOWN_SECONDS=300        # entre servers
MAX_JOB_RUNTIME=1800        # por job
MAX_RETRIES=5               # por job antes de abandonar
```

## History

- 2026-06-11: criado para resolver rate limit 3 backups paralelos
- 2026-06-12: fix retry cap (filename bloat bug)
- 2026-06-12: integrado como módulo fleet-backup no omni-srv-admin
