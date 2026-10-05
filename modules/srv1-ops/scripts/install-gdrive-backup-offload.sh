#!/usr/bin/env bash
# Instala/reconcilia a rotina de backup GDrive do SRV-1 com rollback local.
set -euo pipefail
umask 077

APPLY=0
case "${1:-}" in
  ""|--dry-run) ;;
  --apply) APPLY=1 ;;
  -h|--help)
    echo "Usage: $0 [--dry-run|--apply]"
    exit 0
    ;;
  *) echo "Usage: $0 [--dry-run|--apply]" >&2; exit 2 ;;
esac

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MODULE_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
LIVE_DIR="$HOME/.config/systemd/user"
STAMP=$(date +%Y%m%dT%H%M%S%z)
ROLLBACK="$HOME/.backups/gdrive-backup-offload-install-$STAMP"
UNITS=(
  backup-srv1-daily.service
  backup-srv1-daily.timer
  offload-dotbackups-to-gdrive.service
  offload-dotbackups-to-gdrive.timer
)

for unit in "${UNITS[@]}"; do
  test -f "$MODULE_DIR/systemd/$unit"
done
bash -n "$MODULE_DIR/scripts/offload-dotbackups-to-gdrive.sh" "$MODULE_DIR/scripts/backup-srv1-to-gdrive.sh"
systemd-analyze --user verify "${UNITS[@]/#/$MODULE_DIR/systemd/}"

if [ "$APPLY" -eq 0 ]; then
  echo "DRY-RUN: backup live units to $ROLLBACK"
  echo "DRY-RUN: install ${#UNITS[@]} user units, daemon-reload, enable timers"
  echo "DRY-RUN: stop and runtime-mask duplicate system rclone-gdrive.service if present"
  exit 0
fi

mkdir -p "$LIVE_DIR" "$ROLLBACK"
chmod 700 "$ROLLBACK"
for unit in "${UNITS[@]}"; do
  if [ -f "$LIVE_DIR/$unit" ]; then
    cp --preserve=mode,timestamps "$LIVE_DIR/$unit" "$ROLLBACK/$unit"
  fi
  install -m 0644 "$MODULE_DIR/systemd/$unit" "$LIVE_DIR/$unit"
done

if systemctl cat rclone-gdrive.service >/dev/null 2>&1; then
  sudo -n cp --preserve=mode,ownership,timestamps /etc/systemd/system/rclone-gdrive.service "$ROLLBACK/rclone-gdrive.system.service" 2>/dev/null || true
  sudo -n systemctl stop rclone-gdrive.service
  sudo -n systemctl mask --runtime rclone-gdrive.service
fi
sudo -n chmod -R go-rwx "$ROLLBACK"
systemctl --user daemon-reload
systemctl --user reset-failed backup-srv1-daily.service offload-dotbackups-to-gdrive.service
systemctl --user enable backup-srv1-daily.timer offload-dotbackups-to-gdrive.timer

test "$(systemctl --user is-active rclone-gdrive-mount.service)" = active
mountpoint -q "$HOME/GDrive"
test "$(systemctl is-active rclone-gdrive.service 2>/dev/null || true)" != active
echo "PASS rollback=$ROLLBACK"
