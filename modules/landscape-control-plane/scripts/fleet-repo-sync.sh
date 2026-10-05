#!/usr/bin/env bash
# omni::fleet-repo-sync v1.0.0
# Synchronizes oci-admin and omni-srv-admin in ~/GitHub across ATIUS fleet
set -u

TARGET_USER="ubuntu"
if id "horistic" >/dev/null 2>&1; then
  TARGET_USER="horistic"
elif id "muniz" >/dev/null 2>&1; then
  TARGET_USER="muniz"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting fleet-repo-sync on $(hostname) as user $TARGET_USER"

if [ -x /usr/local/bin/omni-fleet-sync.sh ]; then
  su - "$TARGET_USER" -c "/usr/local/bin/omni-fleet-sync.sh all"
elif [ -f "/home/$TARGET_USER/GitHub/omni-srv-admin/scripts/omni-fleet-sync.sh" ]; then
  chmod +x "/home/$TARGET_USER/GitHub/omni-srv-admin/scripts/omni-fleet-sync.sh"
  su - "$TARGET_USER" -c "/home/$TARGET_USER/GitHub/omni-srv-admin/scripts/omni-fleet-sync.sh all"
else
  echo "[WARN] omni-fleet-sync.sh not found on $(hostname)"
fi
