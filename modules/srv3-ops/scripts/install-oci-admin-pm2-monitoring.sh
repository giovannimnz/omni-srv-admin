#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODULE="$ROOT/modules/srv3-ops"

sudo install -o root -g root -m 0755 \
  "$MODULE/scripts/oci-admin-watchdog.sh" \
  /usr/local/sbin/oci-admin-pm2-watchdog
sudo install -o root -g root -m 0755 \
  "$MODULE/scripts/oci-admin-pm2-save.sh" \
  /usr/local/sbin/oci-admin-pm2-save
sudo install -o root -g root -m 0755 \
  "$MODULE/scripts/oci-admin-pm2-start.sh" \
  /usr/local/sbin/oci-admin-pm2-start
sudo install -o root -g root -m 0644 \
  "$MODULE/systemd/oci-admin-watchdog.service" \
  /etc/systemd/system/oci-admin-watchdog.service
sudo install -o root -g root -m 0644 \
  "$MODULE/systemd/oci-admin-watchdog.timer" \
  /etc/systemd/system/oci-admin-watchdog.timer
sudo install -d -o root -g root -m 0755 /etc/systemd/system/pm2-ubuntu.service.d
sudo install -o root -g root -m 0644 \
  "$MODULE/systemd/pm2-ubuntu-oci-admin.conf" \
  /etc/systemd/system/pm2-ubuntu.service.d/oci-admin.conf
sudo install -o root -g root -m 0644 \
  "$MODULE/configs/oci-admin-pm2.logrotate" \
  /etc/logrotate.d/oci-admin-pm2
sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/.logs/oci-admin
sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/.logs/omni
sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/.local/state/omni/oci-admin-watchdog
sudo chown -R ubuntu:ubuntu /home/ubuntu/.pm2
sudo chmod 0700 /home/ubuntu/.pm2
sudo find /home/ubuntu/.pm2 -maxdepth 1 -type f -exec chmod 0600 {} +
sudo systemctl daemon-reload

echo "Artefatos instalados. Ative o timer somente após o namespace PM2 estar saudável:"
echo "  sudo systemctl enable --now oci-admin-watchdog.timer"
