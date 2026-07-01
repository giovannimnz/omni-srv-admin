# Production Guard

## Scope

`production-guard` validates and, in Phase 25, plans narrowly allowlisted repairs for ATS/Horistic without turning into a generic recovery shell.

Supported commands:

- `omni srv1-ops production-guard status --json`
- `omni srv1-ops production-guard doctor --json`
- `omni srv1-ops production-guard repair --dry-run --json`
- `omni srv1-ops production-guard repair --apply --scope <scope> --target <target> --yes-i-understand-production-risk --json`

## Dry Run

`repair` is dry-run by default.

The dry-run report includes:

- `reason`
- `risk`
- `side_effect`
- `command_preview`
- `rollback_hint`
- `blocked_reason`

If Phase 24 health is still critical, the planner still emits candidates, but marks them as blocked and keeps `apply_ready=false`.

## Apply Checkpoint

`--apply` is intentionally hard to cross. It requires:

- explicit `--scope`
- explicit `--target`
- explicit `--yes-i-understand-production-risk`
- snapshot written before the command runs
- audit event appended in machine-readable JSONL

Apply only works for exact allowlisted actions:

- `podman start <known-container>`
- `systemctl --user start <allowlisted-service>`
- `systemctl --user start <allowlisted-timer>`
- `pm2 start <canonical-ecosystem> --only <known-app>` when PM2 health permits it

## Forbidden Actions

The guard must reject or block these classes of action:

- PM2 daemon teardown
- PM2 restart-wide recovery
- XRDP/RDP service intervention
- Apache mutation
- webhook POST execution

## Snapshot And Audit

Snapshots are written under `~/.local/state/omni/production-guard/snapshots/`.

Audit events are appended to:

- `~/.local/state/omni/production-guard/audit.jsonl`

Audit payloads are redacted using the same sensitive-field list already used by `status` and `doctor`.

## Abort Criteria

Do not run `--apply` when any of these are true:

- `pm2_live_dump_parity` is blocked
- namespace drift still exists
- launchers are blocked
- ecosystem findings are blocked
- container/systemd findings would require out-of-scope recovery steps

## Rollback

Rollback is action-specific and must be shown in the dry-run output before apply:

- container start -> stop the same container
- user service/timer start -> stop the same unit
- PM2 app start -> stop the same app

If the dry-run cannot name a rollback, the action should remain blocked.

## Boot/Login protocol (versionado)

Os arquivos abaixo foram versionados para verificacao read-only em boot e login/session:

- `modules/srv1-ops/systemd/production-guard.service`
- `modules/srv1-ops/systemd/production-guard.timer`
- `modules/srv1-ops/systemd/production-guard-login.service`

### Comandos de validação offline

Antes de habilitar qualquer unidade no host de produção, rode:

```bash
systemd-analyze verify --user \
  modules/srv1-ops/systemd/production-guard.service \
  modules/srv1-ops/systemd/production-guard.timer \
  modules/srv1-ops/systemd/production-guard-login.service

PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "boot or login or systemd"

rg -n "pm2 kill|systemctl (restart|stop) xrdp|xrdp-sesman|repair --apply" modules/srv1-ops/systemd/production-guard*.service modules/srv1-ops/systemd/production-guard*.timer

node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status
```

### Impacto operacional

- As unidades executam **somente** `production-guard status --json` ou `production-guard doctor --json`.
- Nenhum `repair --apply` é chamado por padrão.
- Não há restart/parada de PM2, RDP/XRDP ou Apache nessas unidades.

### Checkpoint de live install (obrigatório)

Não habilite nem instale estas unidades em produção sem aprovação explícita do operador.

```bash
# Checkpoint manual antes do primeiro enable
read -p "Confirmar habilitação de verificação automática no boot/login? (sim/nao): " confirm
if [[ "$confirm" != "sim" ]]; then
  echo "Abortado: sem aprovação explícita."
  exit 1
fi

systemctl --user daemon-reload
systemctl --user enable --now production-guard.timer
systemctl --user enable --now production-guard-login.service
```

Não habilite `production-guard.service` no `--now`; ele deve rodar como unidade disparada pelo timer.

### Troubleshooting e rollback

Para leitura de evidência sem perturbar sessão:

```bash
systemctl --user status production-guard.timer
systemctl --user status --full production-guard.service
systemctl --user status --full production-guard-login.service
journalctl --user -u production-guard.service -n 200
journalctl --user -u production-guard-login.service -n 200
```

Rollback seguro (sem restart de serviço principal):

```bash
systemctl --user stop production-guard-login.service
systemctl --user stop production-guard.timer
systemctl --user disable production-guard-login.service
systemctl --user disable production-guard.timer
```

## Fase 27: Verificação remota do Horistic

O `production-guard` passou a validar o proxy Apache remoto do Horistic por SSH somente leitura.

Checks remotos de fase 27:

- `systemctl show apache2 -p FragmentPath -p DropInPaths -p NeedDaemonReload`
- `systemctl is-enabled apache2`
- `systemctl is-active apache2`
- `ss -tlnp` para portas 80/443
- `apache2ctl -S`
- `find /etc/apache2/sites-enabled -maxdepth 1 -type l -o -type f`

Todo retorno é tratado como evidência; não há comandos de restart/mutation no host remoto.

### Critérios de risco remotos

- `FragmentPath` diferente do package default, drop-ins fora da allowlist ou comandos de erro passam a `block`.
- `apache2` não habilitada/ativa ou porta 80/443 ausente geram `block`.
- `apache2ctl -S` com falha também gera `block`.
- Vhosts ativos com alias legado fora da allowlist geram `block`.

### Webhook/endpoint safety

`production_guard` mantém validações web de apenas leitura para endpoints com método `GET` ou `HEAD`.

- `trade.horistic.com` (HEAD)
- `api.horistic.com` (GET)
- `webhook.horistic.com/` (HEAD)

Não use `requests.post`, `urllib` com `POST` ou `curl -X POST` nos path de saúde.

### Rename drift detector (sem mutação)

O detector de drift classifica por severidade, sem renomear, sem criação de symlink e sem editar vhosts:

- **Benign**: referência documental/histórica ainda necessária (ex.: `horistic-srv-1` em inventário e histórico).
- **Warn**: caminhos de backup/GDrive ainda legacy.
- **Block**: referência ativa em runtime (PM2 cwd/script), Apache remoto ou symlink legado fora de alvo.

Exemplos de ação proposta no output:

- `sugestao: sincronizar caminho para a base atual da stack`
- `sugestao: substituir referência ativa por novo host apelido`
- `sugestao: normalizar symlink legado para destino atual`
