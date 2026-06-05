# PM2 e Cron — Serviço fork-sync

Este documento explica como rodar `fork-sync` como serviço persistente via PM2, com
tarefas agendadas (cron) e logs centralizados.

## Visão geral dos serviços

| Serviço | Função | Cron | Arquivo |
|---|---|---|---|
| `fork-sync-scheduler` | REPL persistente (long-lived) | — | `ecosystem.config.cjs` |
| `fork-sync-doctor` | Diagnóstico diário (7h UTC) | `0 7 * * *` | `ecosystem.doctor.cron.json` |
| `fork-sync-logrotate` | Rotação de logs (3h UTC) | `0 3 * * *` | `ecosystem.logrotate.cron.json` |
| `fork-sync-daily` | Sync de todos projetos (8h UTC) | `0 8 * * *` | `ecosystem.daily-sync.cron.json` |

> **Timezone:** PM2 roda em UTC. Cron `0 8 * * *` UTC = 5h BRT. Ajuste conforme
> preferência (`CRONTZ=America/Sao_Paulo` no shell se quiser horário local).

## Setup

```bash
# Instalar todos
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh install all

# Instalar só o que te interessa
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh install daily
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh install logrotate
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh install doctor

# Ver status
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh status

# Ver logs (últimas 50 linhas)
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh logs fork-sync-daily

# Remover tudo
/home/ubuntu/fork-sync/cli/scripts/pm2-setup.sh remove all
```

## Auto-start no boot

```bash
# Gerar init script (systemd, openrc, etc)
pm2 startup

# Salvar lista atual de processos
pm2 save

# Restaurar após reboot
pm2 resurrect
```

## Logs

Cada serviço escreve em `~/fork-sync/logs/pm2-<service>.log`. PM2 gerencia rotação
interna, mas o **fork-sync** também rotaciona seus próprios logs via
`fork-sync logs --rotate` (3h UTC).

## Cron PM2 vs crontab tradicional

Por que usar `cron_restart` do PM2 em vez de crontab?

| | crontab | PM2 cron_restart |
|---|---|---|
| Setup | `crontab -e` (manual, fácil errar) | `pm2 start ecosystem.X.json` |
| Logs | redirecionar manualmente | automático |
| Restart on boot | precisa de `@reboot` separado | `pm2 startup` cuida |
| Visibilidade | `crontab -l` | `pm2 status` |
| Múltiplos servers | cada um tem o seu | precisa replicar ecosystem.json |

Use crontab SE: (a) não tem PM2 no server, ou (b) precisa de schedule < 1min.

## Estrutura dos arquivos

```
~/fork-sync/
├── ecosystem.config.cjs              # REPL scheduler (long-lived)
├── ecosystem.doctor.cron.json        # cron: doctor diário
├── ecosystem.logrotate.cron.json     # cron: rotação de logs
├── ecosystem.daily-sync.cron.json    # cron: sync diário de todos
└── cli/scripts/
    ├── pm2-setup.sh                  # installer/remover
    ├── run_doctor.sh                 # wrapper: fork-sync doctor
    ├── run_logrotate.sh              # wrapper: fork-sync logs --rotate
    └── run_sync_all.sh               # wrapper: sync all projects
```

## Adicionar novo serviço PM2

1. Criar `ecosystem.<nome>.cron.json` (copiar de um existente)
2. Criar `cli/scripts/run_<nome>.sh` (wrapper)
3. Editar `pm2-setup.sh` para incluir o novo target
4. `pm2 start ecosystem.<nome>.cron.json`
5. `pm2 save`
6. Atualizar este doc

## Troubleshooting

### Serviço não inicia

```bash
pm2 logs fork-sync-daily --lines 100
# Comum: fork-sync não está no PATH ou permissões erradas
which fork-sync
ls -la /home/ubuntu/fork-sync/cli/scripts/run_*.sh
```

### Cron não dispara

```bash
# Ver schedule atual
pm2 conf

# Cron expressions suportadas: '* * * * *' (min hour day month weekday)
# NÃO suporta @reboot, @daily — use formato explícito
```

### Logs de PM2 lotando disco

```bash
# PM2 tem rotação interna:
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 50M
pm2 set pm2-logrotate:retain 30
```

Ou use o **fork-sync logrotate** (3h UTC) que cuida dos logs de sync E
do `logs/pm2-*.log`.
