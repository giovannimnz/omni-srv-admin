#!/usr/bin/env bash
# omni::fleet-paseo-status v1.0.0
# Verificacao de status e saude do runtime Paseo na frota
set -uo pipefail

HOST=$(hostname 2>/dev/null || cat /etc/hostname)
TARGET_USER="ubuntu"
[ "$HOST" = "horistic-srv" ] && TARGET_USER="horistic"
TARGET_HOME="/home/$TARGET_USER"

case "$HOST" in
  *srv-1*) PORT=37815 ;;
  *srv-2*) PORT=37825 ;;
  *srv-3*) PORT=37835 ;;
  *srv-4*) PORT=37845 ;;
  *)       PORT=37899 ;;
esac

echo "== [host=$HOST, port=$PORT] =="

# 1. Versao da CLI
CLI_VER=$(sudo -u "$TARGET_USER" -H bash -c 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && paseo --version' 2>/dev/null || echo "FAIL")
echo "paseo_cli_version=$CLI_VER"

# 2. Systemd status
USER_UID=$(id -u "$TARGET_USER")
SVC_STATUS=$(sudo -u "$TARGET_USER" -H XDG_RUNTIME_DIR="/run/user/$USER_UID" systemctl --user is-active paseo-daemon.service 2>/dev/null || echo "inactive")
echo "systemd_service=$SVC_STATUS"

# 3. Probe local na porta dedicada
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$PORT/ 2>/dev/null || echo "000")
echo "local_port_http_code=$HTTP_CODE"

# 4. Status Paseo
PASEO_HEALTH=$(sudo -u "$TARGET_USER" -H bash -c 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && paseo status --format json 2>/dev/null | grep -o "\"localDaemon\":\"[^\"]*\""' || echo "unknown")
echo "paseo_local_daemon=$PASEO_HEALTH"

if [ "$SVC_STATUS" = "active" ] && [ "$HTTP_CODE" != "000" ]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
fi
