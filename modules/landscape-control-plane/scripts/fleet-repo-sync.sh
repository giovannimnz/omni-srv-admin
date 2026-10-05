#!/usr/bin/env bash
# omni::fleet-repo-sync v2.0.0
# Synchronizes git repositories in ~/GitHub across ATIUS fleet with declarative policy enforcement
set -u

TARGET_REPO="${1:-all}"
TARGET_USER="ubuntu"
if id "horistic" >/dev/null 2>&1; then
  TARGET_USER="horistic"
elif id "muniz" >/dev/null 2>&1; then
  TARGET_USER="muniz"
fi

REPO_DIR="/home/$TARGET_USER/GitHub/omni-srv-admin"

# Self-update local binary and system policy if omni-srv-admin exists on this host
mkdir -p /etc/omni
if [ -f "$REPO_DIR/inventory/fleet-repositories.json" ]; then
  cp "$REPO_DIR/inventory/fleet-repositories.json" /etc/omni/fleet-repositories.json
fi

if [ -f "$REPO_DIR/scripts/omni-fleet-sync.sh" ]; then
  cp "$REPO_DIR/scripts/omni-fleet-sync.sh" /usr/local/bin/omni-fleet-sync.sh
  chmod +x /usr/local/bin/omni-fleet-sync.sh
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting fleet-repo-sync on $(hostname) as user $TARGET_USER (target: $TARGET_REPO)"

if [ -x /usr/local/bin/omni-fleet-sync.sh ]; then
  su - "$TARGET_USER" -c "/usr/local/bin/omni-fleet-sync.sh '$TARGET_REPO'"
else
  echo "[WARN] omni-fleet-sync.sh not found on $(hostname)"
fi
