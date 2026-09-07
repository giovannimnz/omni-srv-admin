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
| `scripts/sync-vault.sh` | Sync git do Obsidian vault + sync incremental do GBrain | crontab a cada 5min |
| `scripts/backup-srv1-to-gdrive.sh` | Backup completo SRV-1 → GDrive | `backup-srv1-daily.timer` |
| `scripts/offload-dotbackups-to-gdrive.sh` | Offload `~/.backups` com verify/delete | `offload-dotbackups-to-gdrive.timer` |
| `scripts/cleanup-local.sh` | Cleanup semanal + retenção `~/.logs` 15d | `cleanup-local-weekly.timer` |
| `scripts/server-analysis.py` | Análise de 15 min; remediation de disco com cooldown persistente de 6 h | `server-analysis.timer` |
| `scripts/resource-governor-snapshot.py` | Snapshot leve de PSI/memória/disco/top consumers | `resource-governor-snapshot.timer` |
| `scripts/resource-governor-audit.py` | Audit diário de hotspots de build/caches/imagens | `resource-governor-audit.timer` |
| `scripts/resource-governor-hygiene-queue.py` | Fila coalescente pós-build + métricas textfile | timers estáveis pós-build |
| `scripts/resource-governor-doctor.py` | Doctor preventivo, admission gate e métricas estruturais | `resource-governor-doctor.timer` |
| `scripts/resource-governor-reconcile-legacy.sh` | Remove scanner/cgroups/units legados com backup | manual |
| `scripts/resource-governor-watchdog.py` | Watchdog contínuo com auto-cleanup e runtime override | `resource-governor-watchdog.timer` |
| `scripts/resource-governor-status.py` | Status atual do resource governor | manual |
| `scripts/pm2-dump-sanitizer.py` | Remove secrets herdados da persistência PM2 sem reiniciar apps | `pm2-dump-sanitizer.path` + timer de 1 min |
| `scripts/backup-to-smb.sh` | Backup fallback SMB | `backup-smb-daily.timer` |
| `scripts/atius-web-healthcheck.sh` | Healthcheck Atius Web via PM2 app `atius-web`; nao depende do user unit legado `atius-web.service` | timer/manual |

## Runtime contracts de apps SRV-1

As units e compose files sanitizados de CloudBeaver, Jenkins, Plane e RustDesk
ficam em `apps/`. Dados, `.env`, credentials, identidade privada e volumes
permanecem fora do Git. Aplicação
e rollback seguem `docs/operations/srv1-service-recovery-2026-09-05.md`.

## CLI

```bash
omni srv1-ops list
omni srv1-ops status
omni srv1-ops logs --limit 30
omni srv1-ops resources profiles
omni srv1-ops resources status
omni srv1-ops resources queue
omni srv1-ops resources doctor
omni srv1-ops resources reconcile-legacy
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
- Regra global de build: `builds` não pode passar de 20% do CPU total do host.
- Fonte de verdade: `configs/resource-governor.env`
- Runbook: `docs/operations/resource-governor.md`
- Logs: `~/.logs/resource-governor/`
- Runtime override live: `~/.config/omni/resource-governor.runtime.env`
- Wrapper padrão: `scripts/install-build-cpu-guard.sh` cria symlinks em `~/.local/bin` para comandos de build (`npm`, `pnpm`, `cargo`, `make`, `go`, `podman`, `docker`, etc.) entrarem automaticamente no profile `builds`.
- Gatilho pós-build: `omni srv1-ops resources run builds -- ...` agenda automaticamente:
  - `cleanup-local.sh` em `CLEANUP_MODE=build-hygiene` após 5 min
  - snapshot após 15 min
  - audit após 35 min
- Fila pós-build: no máximo um batch; solicitações simultâneas são coalescidas
  sem alterar o deadline original e sem criar units timestampadas.
- Semáforo: builds e hygiene compartilham
  `~/.local/state/omni/resource-governor-builds.lock`, capacidade 1, sempre sob
  `omni-builds.slice`/20% do CPU total.
- Reconciliação: `resources reconcile-legacy --apply` remove com backup o
  scanner per-PID e consolida cgroups plain antigos nas slices systemd.
- Watchdog contínuo: `resource-governor-watchdog.service` roda como daemon com
  poll de 5 s, aplica override conservador e dispara cleanup/audit quando o
  host entra em estado crítico. Swap só conta como pressão junto de memória
  disponível abaixo de 4096 MiB; disco usa trigger 95% e recovery 92%.
- `server-analysis.timer` continua observando a cada 15 min, mas não repete o
  cleanup completo. Em disco crítico, chama apenas a lane leve governada
  `resource-governor-post-build-cleanup.service`, com state/lock `0600` e
  cooldown persistente de 6 h. Disco em warning só inventaria candidates.
- `cleanup-local.sh` nunca auto-pruna volumes Podman; registra `SKIP` e exige
  revisão explícita. O cleanup semanal permanece separado no domingo 03:00.
- Doctor preventivo: `resource-governor-doctor.timer` roda a cada 2 min; o mesmo veredito estrutural bloqueia fail-closed a admissão de novos builds.
- Graphify automático: a unit versionada `gsd-graphify-auto-update.service` nasce em `omni-builds.slice` e usa o semaphore comum.
- PM2 boot canônico: `pm2-ubuntu.service` restaura `/home/ubuntu/.pm2/dump.pm2` com os namespaces `atius` e `horistic`. Os user units legados `ats-pm2.service` e `horistic-pm2.service` ficam desabilitados para não competir com o restore.
- PM2 secret hygiene: `pm2-dump-sanitizer.path` reconcilia `dump.pm2` e
  `dump.pm2.bak` após cada write; `pm2-dump-sanitizer.timer` é o backstop de
  1 min. O rewrite é JSON atômico/readback-validated, força `0600`, remove
  `GSD_WEB_LOGIN_*`/`DATABASE_URI` herdados e preserva `DB_PASSWORD` somente
  nos dois consumers explicitamente allowlisted. É SRV-1-only e não entra no
  install `--generic-host` do SRV-4.

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

### Backup resumível e serial

- `backup-srv1-daily.service` apenas enfileira; não chama `rclone` diretamente.
- `rclone-fleet-queue.timer` roda somente no SRV-1, orchestrator único.
- State `0600` atômico em
  `~/.local/state/omni/backup-gdrive/<snapshot>.json`.
- Cada source passa por `copy → rclone check → complete`; exit `75` preserva
  o mesmo job/snapshot para retry.
- Pacer default de recovery: `4 TPS`, burst `1`, sleep mínimo Drive `1s`.
- Config Vault deve conter OAuth Desktop client ATIUS próprio
  (`client_id/client_secret/token`). Sem isso, o backup sai 75 antes de chamar
  a API e a queue fica em hold externo `0600`, preservando o job.
- Durante uma janela de backup completo, mounts read-only do mesmo projeto
  Google Drive podem ser pausados após prova `open_files=0`; preservar
  enablement e backup checksummed e restaurar somente após o fleet lock liberar.
- O partial `snapshot-2026-09-05_042520`, criado antes da redação da credencial
  legacy, é quarantined e não será retomado nem purgado automaticamente.
- Retenção só considera state local `complete`.
- GitHub exclui derived outputs, runtime mutable dirs, PostgreSQL bind data e
  os dois `.env` caches allowlisted enquanto a rotação estiver pendente.
- Logs ativos e Hermes sessions/state DB não entram no verify de diretório vivo;
  configs, skills e cron continuam protegidos.

## Migration notes

- `~/logs` foi migrado para `~/.logs`.
- `/home/ubuntu/docs` foi migrado para `docs/legacy-home-docs/home-docs-2026-06-06/` no repo `omni-srv-admin`.
- Crontab `sync-vault` agora aponta para `modules/srv1-ops/scripts/sync-vault.sh`.
- O mesmo ciclo de 5min roda `gbrain sync --repo "$VAULT" --no-pull --yes --json` depois do Git sync bem-sucedido; não criar cron separado para GBrain.
- Systemd timers de backup/cleanup apontam para scripts deste módulo.

## Obsidian + GBrain sync

- Cron live: `*/5 * * * * /home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/sync-vault.sh >> /home/ubuntu/.logs/sync-vault.cron.log 2>&1`.
- Log do Git sync: `/home/ubuntu/.logs/sync-vault.log`.
- Log do GBrain sync: `/home/ubuntu/.logs/gbrain-vault-sync.log`.
- O GBrain exige o caminho do Git repo; por isso o comando usa `/home/ubuntu/GitHub/obsidian-vault`, mas o conteúdo canônico de memória fica em `AiSecondBrain/`.
- O script aborta antes de `git add` se `Ideaverse/` ou `ideaverse/` reaparecerem, para evitar duplicidade.
- Override seguro: `SYNC_VAULT_GBRAIN_REPO=/path/do/repo-git` troca somente a fonte GBrain.
- Override seguro: `SYNC_VAULT_GBRAIN_SYNC=0` desativa temporariamente só o GBrain sync sem remover o cron.
- Timeout padrão: `240s`, ajustável por `SYNC_VAULT_GBRAIN_TIMEOUT_SECONDS`.
- Hold operacional fail-closed:
  `~/.local/state/omni/sync-vault.hold` (override
  `SYNC_VAULT_HOLD_FILE`). Quando presente, o script sai `0` antes de abrir o
  vault ou executar Git/GBrain. Usar durante migrações/recovery de roots e
  remover apenas após auditorar o working tree que o cron poderia commitar.

## Obsidian REST endpoint

- SRV-1 mantem o Obsidian AppImage aberto via user unit `obsidian-aisecondbrain-rest.service`.
- O endpoint oficial/canonico do Obsidian MCP para todos os hosts e `https://mcp.atius.com.br/obsidian`.
- O plugin `obsidian-local-rest-api` fica no vault `AiSecondBrain` e escuta em backend/raw path `10.11.1.11:27124`.
- SRV-2/SRV-3 podem validar backend via `https://10.11.1.11:27124` e `https://10.11.1.11:27124/mcp/`, mas o caminho oficial continua `https://mcp.atius.com.br/obsidian`; `wg100` fica como reserve path.
- Nao criar tunnel systemd em SRV-2/SRV-3 para esse endpoint.
- SRV-1 usa a cadeia `OMNI-OBSIDIAN-REST` para permitir `27124/tcp` para `lo`, peers `wg100` dos servidores (`10.100.100.2` e `10.100.100.3`), edge clients live (`10.100.100.8` e `10.100.100.9`), compat legada temporaria (`10.100.100.5` e `10.100.100.6`) e faixas OCI privadas `10.12.0.0/16`, `10.13.0.0/16`, `10.14.0.0/16` e `10.21.0.0/16`.
- O certificado do plugin deve existir nos clientes em `/usr/local/share/ca-certificates/obsidian-local-rest-api.crt`; depois rodar `update-ca-certificates`.
- SAN obrigatorio do certificado: `127.0.0.1`, `10.11.1.11`, `10.100.100.1`, `atius-srv-1`, `atius-srv-1-vpn`, `atius-srv-1.atius.internal`.
- `https://mcp.atius.com.br/obsidian` e o endpoint oficial/canonico; `10.11.1.11` fica como backend/raw path via DRG e `wg100`/`10.100.100.0/24` fica como caminho secundario e nao deve ser publicado como endpoint canonico.
- Nao instalar Obsidian desktop nem sync Git do vault em SRV-2/SRV-3.
- Nao publicar o API key do plugin em docs ou repo.

## Pitfalls

- Não usar `rclone move` direto para backup crítico. Usar copy → verify → delete.
- Não habilitar `backup-srv1-daily.timer`, offloads SRV-1-only ou
  `rclone-fleet-queue.timer` em SRV-2/SRV-3.
- Não usar `~/GDrive` como caminho de destino para backup pesado; usar `rclone copy` direto no remote.
- Não apagar `~/scripts`/`~/bin` antes de validar crontab, systemd, PM2 e referências.
- `--delete` no rsync só com profile mirror e confirmação explícita.
- Backup que não foi testado não é backup.
