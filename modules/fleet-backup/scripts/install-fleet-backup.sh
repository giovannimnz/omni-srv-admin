#!/bin/bash
# ============================================================================
# install-fleet-backup.sh
# ----------------------------------------------------------------------------
# Instala rclone-fleet-queue (módulo fleet-backup) no server atual.
# Idempotente: pode rodar N vezes sem quebrar.
#
# Detecta srv_num via hostname, copia script + systemd files, ativa timer.
# Referência: modules/fleet-backup/README.md
# ============================================================================
set -uo pipefail
IFS=$'\n\t'

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="$MODULE_DIR/scripts"
SYSTEMD_DIR="$MODULE_DIR/systemd"

# === Detecta srv_num via hostname ===
HOSTNAME=$(hostname)
case "$HOSTNAME" in
  *SRV-1*|*-1*|atius-srv-1) SRV_NUM=1 ;;
  *SRV-2*|*-2*|atius-srv-2) SRV_NUM=2 ;;
  *SRV-3*|*-3*|atius-srv-3) SRV_NUM=3 ;;
  *) echo "FAIL: hostname '$HOSTNAME' não casa com SRV-1/2/3" >&2; exit 1 ;;
esac
echo "Detectado: $HOSTNAME = SRV-$SRV_NUM"

# === Instala script ===
mkdir -p ~/scripts
install -m 755 "$SCRIPTS_DIR/rclone-fleet-queue.sh" ~/scripts/rclone-fleet-queue.sh
echo "OK: ~/scripts/rclone-fleet-queue.sh instalado"

# === Systemd files ===
mkdir -p ~/.config/systemd/user
install -m 644 "$SYSTEMD_DIR/rclone-fleet-queue.service" ~/.config/systemd/user/
install -m 644 "$SYSTEMD_DIR/rclone-fleet-queue.timer" ~/.config/systemd/user/
echo "OK: systemd files copiados"

# === Symlink em ~/.local/bin ===
mkdir -p ~/.local/bin
ln -sf ~/scripts/rclone-fleet-queue.sh ~/.local/bin/rclone-fleet-queue
echo "OK: symlink ~/.local/bin/rclone-fleet-queue"

# === Ativa timer ===
systemctl --user daemon-reload
systemctl --user enable rclone-fleet-queue.timer
systemctl --user start rclone-fleet-queue.timer
echo "OK: timer ativado"

echo ""
echo "Install completo em SRV-$SRV_NUM. Teste:"
echo "  ~/scripts/rclone-fleet-queue.sh status"
