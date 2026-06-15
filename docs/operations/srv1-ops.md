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


## Post-Boot Verification Checklist

**Phase:** 14-04
**When:** after any SRV-1 reboot, or after running `omni srv1-ops resources install --apply`, or after manual changes to the governor/inviolable units.

Run this sequence and confirm all checks pass:

```bash
# 1. Linger is enabled for ubuntu
loginctl show-user ubuntu -p Linger
# Expected: Linger=yes

# 2. No critical jobs stuck in user session
systemctl --user list-jobs
# Expected: no ats-pm2.service, horistic-pm2.service, or default.target in "start waiting" state
# (acceptable: gdrive-mount.service waiting briefly during boot)

# 3. Critical governor/inviolable services are active
systemctl --user is-active resource-governor-patcher.service
systemctl --user is-active resource-governor-watchdog.service
systemctl --user is-active resource-governor-cgroup-init.service
systemctl --user is-active inviolable-watchdog.timer
# All four: active

# 4. Cgroup profile is consistent
python3 /home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/resource-governor-status.py
# Expected: runtime_mode=base or conservative; slices + direct cgroups match
# Look for: "WARN stale ecosystem reference detected" → OK if it's about pm2-ubuntu.service
# Look for: NO WARN lines about cgroup drift between slice and direct cgroup

# 5. PM2 daemon + critical apps
/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2 ls | head -20
# Expected: atius-api, atius-web, horistic-api online; rest online or waiting briefly
nc -z 127.0.0.1 3015 && echo "atius-web OK"
nc -z 127.0.0.1 8050 && echo "horistic-api OK"
nc -z 127.0.0.1 8015 && echo "atius-api OK"
nc -z 127.0.0.1 8199 && echo "atius-webhook-signals OK"

# 6. Patcher health
cat /home/ubuntu/.local/state/omni/resource-governor-patcher.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"moves={d['moved_total']} healthy_streak={d['healthy_streak']} mode={d.get('runtime_mode', 'unknown')}\)"
# Expected: healthy_streak > 0; if 0, watchdog may be misbehaving

# 7. XRDP/SSHD leftover in watchdog cgroup
find /sys/fs/cgroup -path "*inviolable-watchdog*" -name cgroup.procs
# Expected: empty
```

If any check fails:

| Check | First action |
|---|---|
| 1. Linger not enabled | `sudo loginctl enable-linger ubuntu` (safe, no service restart) |
| 2. Stuck jobs | See `docs/operations/pm2-canonical.md` Recovery section. Do NOT `pm2 kill` or `systemctl restart pm2-ubuntu.service` without user gate. |
| 3. Service not active | `systemctl --user daemon-reload && systemctl --user start <unit>` (daemon is safe; only restart specific unit) |
| 4. Cgroup drift | `omni srv1-ops resources install --dry-run` first, then `--apply` after diff. Read `docs/operations/resource-governor.md` for the full procedure. |
| 5. PM2 apps offline | **GATE REQUIRED.** Follow `pm2-canonical.md` Recovery. Do NOT auto-restart PM2 daemon. |
| 6. Patcher unhealthy | Read `~/.logs/resource-governor/watchdog.log` and `~/.local/state/omni/resource-governor-watchdog.json`. If the patcher is in a recovery loop, `systemctl --user restart resource-governor-patcher.service` is the safe action. |
| 7. XRDP/SSHD in watchdog cgroup | DO NOT kill those PIDs. Plan a maintenance window: `systemctl --user restart inviolable-watchdog.timer` + manual cgroup move. |

## Rollback Procedure

**Pre-live backup:** `/home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527`

To roll back governor/inviolable to pre-2026-06-13 state:

```bash
# 1. Snapshot current state
TS=$(date +%Y%m%d_%H%M%S)
SNAP=/home/ubuntu/.backups/omni-srv-admin-rollback-$TS
mkdir -p $SNAP
cp -a /home/ubuntu/.config/systemd/user/ $SNAP/user-systemd/
cp -a /home/ubuntu/.config/omni/ $SNAP/omni-config/ 2>/dev/null || true
cp -a /home/ubuntu/.local/state/omni/ $SNAP/omni-state/

# 2. Disable current units
systemctl --user disable --now resource-governor-patcher.service resource-governor-watchdog.service resource-governor-cgroup-init.service inviolable-watchdog.timer

# 3. Restore from backup (only if user has confirmed gate)
rsync -av /home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527/configs/ /home/ubuntu/.config/omni/
rsync -av /home/ubuntu/.backups/omni-srv-admin-resource-governor-20260613_050527/systemd/ /home/ubuntu/.config/systemd/user/
systemctl --user daemon-reload

# 4. Re-enable old units
systemctl --user enable --now resource-governor-patcher.service resource-governor-watchdog.service inviolable-watchdog.timer
```

**Abort criteria for live execution of any Phase 14 plan:**

- Critical app (atius-api, atius-web, horistic-api) offline
- Critical port (3015, 8050, 8015, 8199) not responding
- RDP session unstable or disconnected
- PM2 daemon duplicated (two `pm2-runtime` processes)
- OOM kill of resource-governor or inviolable-watchdog

**To abort:** `systemctl --user stop <unit>` (does not kill apps), capture diagnostic, revert from backup.
