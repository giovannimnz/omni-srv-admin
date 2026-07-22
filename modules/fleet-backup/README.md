# fleet-backup — Backup serial multi-server para GDrive

Fila serial de backups rclone (1 por vez, cooldown entre servers) para evitar
Google Drive API rate limit. Suporta 3 servers ATIUS (SRV-1, SRV-2, SRV-3).

O módulo também contém um canal separado, copy-only, para o Backup B da
Phase 52 no `horistic-srv`. Esse canal não entra na fila legada e não instala
timer.

## Componentes

- `scripts/rclone-fleet-queue.sh` — daemon de fila (enqueue/run/status/clear/drain)
- `scripts/install-fleet-backup.sh` — idempotente, instala num server
- `scripts/sync-backup-script.sh` — replica `backup-srv{N}-to-gdrive.sh` pros outros servers
- `systemd/rclone-fleet-queue.service` — service oneshot
- `systemd/rclone-fleet-queue.timer` — timer a cada 30min
- `configs/fleet-backup-map.yaml` — mapeamento srv_num → host
- `scripts/rclone-copy-verified-phase52.sh` — copia um archive state-only e
  confirma o SHA-256 relendo o objeto com `rclone cat`
- `scripts/atius-rclone-vault-hydrate` — hydrator fail-closed da config efêmera
  em tmpfs; permanece bloqueado enquanto não existir binding Vault aprovado
- `scripts/phase52-install-state.py` — captura, install e rollback transacionais
  do modo Phase 52, com manifest versionado, hashes e generation ID

## Instalação

Num server novo:
```
cd ~/GitHub/omni-srv-admin
./modules/fleet-backup/scripts/install-fleet-backup.sh
```

### Horistic, Phase 52 somente

O dry-run não escreve no host:

```bash
./modules/fleet-backup/scripts/install-fleet-backup.sh \
  --host horistic-srv --phase52-only --dry-run
```

A instalação efetiva copia apenas os dois scripts e o mapa para paths sob
`$HOME`, grava um snapshot de rollback e não cria, habilita ou inicia timer:

```bash
./modules/fleet-backup/scripts/install-fleet-backup.sh \
  --host horistic-srv --phase52-only
```

O output informa o `rollback_state`, que pode ser aplicado com
`--rollback <state-dir>`. Targets preexistentes são preservados antes da
substituição. O rollback valida o manifest completo, generation marker,
allowlist exata de targets, basenames e hashes dos backups e identidade/hash
dos targets instalados antes da primeira mutation. Estado stale bloqueia; um
rollback concluído marca a geração como `consumed` e não pode ser repetido.

Install e rollback usam arquivos temporários no parent final, `os.replace`,
stashes transacionais e handlers para `INT`, `TERM` e `HUP`. Em interrupção,
os targets retornam ao estado anterior ou o estado de recuperação é preservado
fail-closed.

O upload live continua fail-closed até haver aprovação separada para o binding
Vault da configuração rclone. Nenhum profile, path ou valor é presumido por
este módulo.

O uploader aceita na interface pública somente o archive regular mode `0600`
contendo exatamente `db_v2.sqlite3` mode `0600` e o objeto `.tar` diretamente
sob:

```text
giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/
```

Ele executa `copyto` com `--immutable`, `transfers=1`, `checkers=1`, timeout e
bwlimit; depois relê o objeto com `rclone cat` e compara SHA-256. Não há
`delete`, `purge`, `move`, `sync` ou cleanup remoto. Retenção: Phase 57 PASS +
30 dias; qualquer remoção exige nova aprovação explícita.

Não existe flag pública `--config`, path alternativo ou override por environment.
O uploader cria o diretório privado `0700` em tmpfs e chama exclusivamente o
hydrator sibling canônico `atius-rclone-vault-hydrate`; hash e identidade desse
sibling são verificados antes e depois. Source archive, config materializada e
provenance marker são então usados como snapshots privados `0600`. Owner,
link count, parents canônicos, inode/device e digest são verificados antes do
uso; a operação nunca reabre os paths originais. A config só é aceita quando o
marker `.atius-rclone-vault-provenance.json` vincula exatamente o digest/inode,
o remote `giovanni-drive` e `materialized_by=atius-rclone-vault-hydrate`.
Enquanto o binding Vault não estiver aprovado, o hydrator não cria config nem
marker e o upload permanece BLOCKED.

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
- 2026-07-22: canal Horistic Phase 52 copy-only, sem timer e sem retenção destrutiva
