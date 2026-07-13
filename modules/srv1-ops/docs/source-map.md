# Source map — srv1-ops migration

## Migrated into module

| Source | Destination | Action |
|---|---|---|
| `/home/ubuntu/scripts/sync-vault.sh` | `modules/srv1-ops/scripts/sync-vault.sh` | copied + updated log path |
| `/home/ubuntu/.local/bin/backup-srv1-to-gdrive.sh` | `modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh` | copied + updated GDrive layout/log path |
| `/home/ubuntu/.local/bin/offload-dotbackups-to-gdrive.sh` | `modules/srv1-ops/scripts/offload-dotbackups-to-gdrive.sh` | copied + updated GDrive layout/log path |
| `/home/ubuntu/.local/bin/cleanup-local.sh` | `modules/srv1-ops/scripts/cleanup-local.sh` | copied + updated `.logs` retention |
| `/home/ubuntu/.local/bin/backup-to-smb.sh` | `modules/srv1-ops/scripts/backup-to-smb.sh` | copied |
| `/home/ubuntu/.local/bin/atius-web-healthcheck.sh` | `modules/srv1-ops/scripts/atius-web-healthcheck.sh` | copied as legacy |
| `/home/ubuntu/.config/systemd/user/*backup*/*cleanup*` | `modules/srv1-ops/systemd/` | copied for reference |

## Candidates not migrated yet

| Path | Reason |
|---|---|
| `/home/ubuntu/scripts/qbt-postprocess.sh` | qBittorrent-specific; needs qbt module decision |
| `/home/ubuntu/scripts/mount-gdrive.sh` | legacy; live mount appears managed by `gdrive-mount.service`/rclone wrapper |
| `/home/ubuntu/scripts/start-qbittorrent.sh` | qBittorrent-specific |
| `/home/ubuntu/scripts/start-aionui.sh` | AionUI-specific; already has AionUI skills/runbooks |
| `/home/ubuntu/scripts/fix-shared_smb.sh` | legacy one-shot; superseded by fstab/GVFS runbook |
| `/home/ubuntu/scripts/fix-abnt2.sh` | superseded by `modules/xrdp-abnt2/` |
| `/home/ubuntu/scripts/optimize_network.sh` | needs review before applying; network-impacting |
| `/home/ubuntu/bin/pm2ns` | utility; evaluate as `omni admin pm2` later |
| `/home/ubuntu/bin/setxkbmap-abnt2.sh` | superseded by `modules/xrdp-abnt2/files/setxkbmap-abnt2.sh` |

## Active external cron references found

```cron
0 13 * * * DISPLAY=:10 cd /home/ubuntu/docker/AtiusCapital/browserAutomation && /home/ubuntu/docker/AtiusCapital/browserAutomation/scripts/schedule-br-13.sh >> /home/ubuntu/docker/AtiusCapital/browserAutomation/logs/cron.log 2>&1
```

## Replaced cron references

```cron
*/5 * * * * /home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/sync-vault.sh >> /home/ubuntu/.logs/sync-vault.cron.log 2>&1
0 8 * * * /home/ubuntu/.local/bin/omni fork-sync sync aionui --repo-path /home/ubuntu/GitHub/forks/AionUi >> /home/ubuntu/.logs/fork-sync-aionui.log 2>&1
0 7 * * * /home/ubuntu/.local/bin/omni fork-sync manuals list >> /home/ubuntu/.logs/fork-sync-manuals.log 2>&1
```

`sync-vault.sh` tambem roda o sync incremental do GBrain depois do Git sync do repo. O comando GBrain usa o Git repo `/home/ubuntu/GitHub/obsidian-vault`, mas a memoria canonica das IAs fica em `AiSecondBrain/`. Nao criar um cron separado para `/home/ubuntu/.local/bin/gbrain sync`, para evitar overlap e ordem incorreta.

## Obsidian REST endpoint

```text
modules/srv1-ops/systemd/obsidian-aisecondbrain-rest.service
modules/srv1-ops/systemd/omni-obsidian-rest-access-guard.service
modules/srv1-ops/scripts/omni-obsidian-rest-access-guard.sh
```

`obsidian-aisecondbrain-rest.service` mantem o Obsidian AppImage aberto no SRV-1 para servir o plugin `obsidian-local-rest-api` em backend/raw path `https://10.11.1.11:27124` e `https://10.11.1.11:27124/mcp/`. O endpoint oficial/canonico para todos os hosts continua `https://mcp.atius.com.br/obsidian`; `wg100` fica apenas como origem permitida dos peers secundarios, nao como endpoint canonico. `omni-obsidian-rest-access-guard.service` aplica a allowlist iptables para `27124/tcp` em `lo`, nos peers `wg100` dos servidores (`10.100.100.2` e `10.100.100.3`), nos edge clients live (`10.100.100.8` e `10.100.100.9`), na compat legada temporaria (`10.100.100.5` e `10.100.100.6`) e nas faixas OCI privadas `10.12.0.0/16`, `10.13.0.0/16` e `10.21.0.0/16`. SRV-2/SRV-3/Horistic nao devem rodar tunnel local para esse endpoint.

## Disabled stale cron references

```cron
# 0 */6 * * * /home/ubuntu/docker/Atius/router-ai-atius/scripts/auto-sync-deploy.sh >> /home/ubuntu/docker/Atius/logs/auto-sync-deploy.log 2>&1
```

Reason: target script no longer exists.

Decision: do not auto-enable `omni fork-sync sync atius-router --deploy` without explicit production validation.
