# Fleet Autoclean

## Commands

Read-only audit:

```bash
PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
OMNI_SRV_PUBLIC_FIRST=1 \
python3 -m omni srv storage-audit all
```

Dry-run cleanup:

```bash
PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
OMNI_SRV_PUBLIC_FIRST=1 \
python3 -m omni srv autoclean all
```

Apply safe cleanup:

```bash
PYTHONPATH=/home/ubuntu/GitHub/omni-srv-admin/cli \
OMNI_SRV_PUBLIC_FIRST=1 \
python3 -m omni srv autoclean all --apply
```

## What It Cleans

- `/tmp` top-level entries older than 3 days, preserving X11/systemd/snap
  sockets and active Hermes temp paths.
- Regenerable caches: go-build, Codex update/cache, Playwright browser cache,
  Copilot cache, node-gyp, pnpm store prune, pip cache purge and Bun install
  cache.
- Large/old local logs under `~/.logs` and `~/.pm2/logs`.
- XRDP/Xorg/LightDM session logs (`/var/log/xrdp*.log`,
  `/var/log/lightdm/*`, `~/.xorgxrdp.*.log`, `~/.Xorg.*.log`,
  `~/.xsession-errors`).
- Unused Podman images, stopped containers and unused networks.
- systemd journal down to 500M when `sudo -n journalctl` is available.

## What It Does Not Delete Automatically

- Container volumes, unless `--include-volumes` is explicitly passed.
- k3s/containerd images, snapshots and `/var/lib/rancher/k3s`.
- Backup/quarantine directories:
  - `~/pre-upgrade-24.04-backup`
  - `~/srv3-disk-relief-before-config-clone-*`
  - `~/.config-clone-backups`
  - `~/.backups`
- Project directories under `~/GitHub`.
- Live config directories such as `~/.config` and `~/.hermes`.

## Jobs

Versioned units:

```text
modules/fleet-autoclean/systemd/fleet-storage-audit.service
modules/fleet-autoclean/systemd/fleet-storage-audit.timer
modules/fleet-autoclean/systemd/fleet-autoclean.service
modules/fleet-autoclean/systemd/fleet-autoclean.timer
```

Install after reviewing dry-run:

```bash
mkdir -p ~/.config/systemd/user
cp modules/fleet-autoclean/systemd/fleet-*.service modules/fleet-autoclean/systemd/fleet-*.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fleet-storage-audit.timer
systemctl --user enable --now fleet-autoclean.timer
```

Live install on SRV-1:

```text
2026-06-13 08:37 BRT: timers enabled in /home/ubuntu/.config/systemd/user/
fleet-autoclean.timer next: 2026-06-14 04:37 BRT
fleet-storage-audit.timer next: 2026-06-14 08:24 BRT
```

Impact: `daemon-reload` + user timers only. Does not drop RDP/XRDP.

## 2026-06-13 Snapshot historico

| Host | OS | Disk | Main findings |
|---|---|---:|---|
| SRV-1 | Ubuntu 24.04.4 | 69% | Journal 470M, PM2 logs 63M, Podman 3.1G with ~734M reclaimable, `~/pre-upgrade-24.04-backup` 4.0G. |
| SRV-2 | Ubuntu 24.04.4 | 70% | Post-reboot OK, journal 450M, Docker volumes 25G active, 20G `srv3-disk-relief...` offloaded to GDrive and removed local, XRDP/LightDM/Xorg logs cleaned. |
| SRV-3 | Ubuntu 24.04.4 | 30% | Fresh reboot, journal 822M, no Docker/Podman pressure, `inviolable-watchdog` still failing because script is absent. |

## Pending Manual Decisions

- SRV-2: os volumes Docker de 25G pertencem ao snapshot historico anterior a
  migracao. Nao sao alvo do cleanup atual; qualquer retirada residual exige
  inventario e backup especificos.
- SRV-2: `router-ai-zentrius` lives at `/home/ubuntu/docker/Atius/router-ai-zentrius`.
  O nome do path e legado e nao define o runtime; nao tratar paths antigos de
  `router-ai-atius` como atuais neste host.
- SRV-3: fix or disable broken `inviolable-watchdog.timer`; current failure is
  `status=203/EXEC` because `/home/ubuntu/scripts/inviolable-watchdog.sh` is
  absent.
