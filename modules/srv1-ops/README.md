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
| `scripts/resource-governor-snapshot.py` | Snapshot leve de PSI/memória/disco/top consumers | `resource-governor-snapshot.timer` |
| `scripts/resource-governor-audit.py` | Audit diário de hotspots de build/caches/imagens | `resource-governor-audit.timer` |
| `scripts/resource-governor-hygiene-queue.py` | Fila coalescente pós-build + métricas textfile | timers estáveis pós-build |
| `scripts/resource-governor-doctor.py` | Doctor preventivo, admission gate e métricas estruturais | `resource-governor-doctor.timer` |
| `scripts/resource-governor-reconcile-legacy.sh` | Remove scanner/cgroups/units legados com backup | manual |
| `scripts/resource-governor-watchdog.py` | Watchdog contínuo com auto-cleanup e runtime override | `resource-governor-watchdog.timer` |
| `scripts/resource-governor-status.py` | Status atual do resource governor | manual |
| `scripts/backup-to-smb.sh` | Backup fallback SMB | `backup-smb-daily.timer` |
| `scripts/atius-web-healthcheck.sh` | Healthcheck Atius Web via PM2 app `atius-web`; nao depende do user unit legado `atius-web.service` | timer/manual |

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
- Watchdog contínuo: `resource-governor-watchdog.timer` roda a cada 2 min, aplica override conservador e dispara cleanup/audit quando o host entra em estado crítico.
- Doctor preventivo: `resource-governor-doctor.timer` roda a cada 2 min; o mesmo veredito estrutural bloqueia fail-closed a admissão de novos builds.
- Graphify automático: a unit versionada `gsd-graphify-auto-update.service` nasce em `omni-builds.slice` e usa o semaphore comum.
- PM2 boot canônico: `pm2-ubuntu.service` restaura `/home/ubuntu/.pm2/dump.pm2` com os namespaces `atius` e `horistic`. Os user units legados `ats-pm2.service` e `horistic-pm2.service` ficam desabilitados para não competir com o restore.

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

## Obsidian REST endpoint

- SRV-1 mantem o Obsidian AppImage aberto via user unit `obsidian-aisecondbrain-rest.service`.
- O endpoint oficial/canonico do Obsidian MCP para todos os hosts e `https://mcp.atius.com.br/obsidian`.
- O plugin `obsidian-local-rest-api` fica no vault `AiSecondBrain` e escuta em backend/raw path `10.11.1.11:27124`.
- SRV-2/SRV-3 podem validar backend via `https://10.11.1.11:27124` e `https://10.11.1.11:27124/mcp/`, mas o caminho oficial continua `https://mcp.atius.com.br/obsidian`; `wg100` fica como reserve path.
- Nao criar tunnel systemd em SRV-2/SRV-3 para esse endpoint.
- SRV-1 usa a cadeia `OMNI-OBSIDIAN-REST` para permitir `27124/tcp` para `lo`, peers `wg100` dos servidores (`10.100.100.2` e `10.100.100.3`), edge clients live (`10.100.100.8` e `10.100.100.9`), compat legada temporaria (`10.100.100.5` e `10.100.100.6`) e faixas OCI privadas `10.12.0.0/16`, `10.13.0.0/16` e `10.21.0.0/16`.
- O certificado do plugin deve existir nos clientes em `/usr/local/share/ca-certificates/obsidian-local-rest-api.crt`; depois rodar `update-ca-certificates`.
- SAN obrigatorio do certificado: `127.0.0.1`, `10.11.1.11`, `10.100.100.1`, `atius-srv-1`, `atius-srv-1-vpn`, `atius-srv-1.atius.internal`.
- `https://mcp.atius.com.br/obsidian` e o endpoint oficial/canonico; `10.11.1.11` fica como backend/raw path via DRG e `wg100`/`10.100.100.0/24` fica como caminho secundario e nao deve ser publicado como endpoint canonico.
- Nao instalar Obsidian desktop nem sync Git do vault em SRV-2/SRV-3.
- Nao publicar o API key do plugin em docs ou repo.

## Pitfalls

- Não usar `rclone move` direto para backup crítico. Usar copy → verify → delete.
- Não usar `~/GDrive` como caminho de destino para backup pesado; usar `rclone copy` direto no remote.
- Não apagar `~/scripts`/`~/bin` antes de validar crontab, systemd, PM2 e referências.
- `--delete` no rsync só com profile mirror e confirmação explícita.
- Backup que não foi testado não é backup.
