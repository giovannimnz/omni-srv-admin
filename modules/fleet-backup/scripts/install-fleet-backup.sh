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

PHASE52_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$PHASE52_MODULE_DIR/scripts"
SYSTEMD_DIR="$PHASE52_MODULE_DIR/systemd"

requested_host=''
phase52_only=false
dry_run=false
rollback_state=''

usage() {
  cat >&2 <<'EOF'
usage:
  install-fleet-backup.sh
  install-fleet-backup.sh --host horistic-srv --phase52-only [--dry-run]
  install-fleet-backup.sh --rollback STATE_DIR
EOF
  exit 2
}

while (($#)); do
  case "$1" in
    --host)
      (($# >= 2)) || usage
      requested_host=$2
      shift 2
      ;;
    --phase52-only)
      phase52_only=true
      shift
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --rollback)
      (($# >= 2)) || usage
      rollback_state=$2
      shift 2
      ;;
    *) usage ;;
  esac
done

readonly HOME_DIR="${HOME:?HOME is required}"
readonly PHASE52_STATE_ROOT="$HOME_DIR/.local/state/atius-fleet-backup"
readonly PHASE52_STATE_HELPER="$PHASE52_MODULE_DIR/scripts/phase52-install-state.py"

canonical_home=$(realpath -e -- "$HOME_DIR" 2>/dev/null) || {
  echo 'FAIL: HOME ausente ou não canônico' >&2
  exit 2
}
[[ "$canonical_home" == "$HOME_DIR" && ! -L "$HOME_DIR" && $(stat -c '%u' -- "$HOME_DIR") == "$(id -u)" ]] || {
  echo 'FAIL: HOME deve ser canônico, owned e não symlink' >&2
  exit 2
}

if [[ -n "$rollback_state" ]]; then
  [[ -z "$requested_host" && "$phase52_only" == false && "$dry_run" == false ]] || usage
  exec python3 "$PHASE52_STATE_HELPER" rollback --home "$HOME_DIR" --state-dir "$rollback_state"
fi

install_phase52_horistic() {
  set -e
  umask 077
  [[ "$requested_host" == 'horistic-srv' ]] || {
    echo 'FAIL: --phase52-only é permitido somente para horistic-srv' >&2
    exit 2
  }
  [[ -f "$PHASE52_STATE_HELPER" && ! -L "$PHASE52_STATE_HELPER" ]] || {
    echo 'FAIL: helper transacional Phase 52 ausente' >&2
    exit 2
  }
  local preflight_output
  if ! preflight_output=$(python3 "$PHASE52_STATE_HELPER" preflight --home "$HOME_DIR" --module-dir "$PHASE52_MODULE_DIR"); then
    printf '%s\n' "$preflight_output"
    exit 2
  fi

  if [[ "$dry_run" == true ]]; then
    echo "DRY-RUN: install $HOME_DIR/.local/bin/rclone-copy-verified-phase52"
    echo "DRY-RUN: install $HOME_DIR/.local/bin/rclone-fetch-verified-phase52"
    echo "DRY-RUN: install $HOME_DIR/.local/bin/atius-rclone-vault-hydrate"
    echo "DRY-RUN: install $HOME_DIR/.config/atius/fleet-backup/fleet-backup-map.yaml"
    echo 'DRY-RUN: timer_action=none'
    echo 'DRY-RUN: vault_binding=rclone-giovanni-drive-phase52'
    echo 'DRY-RUN: persistent_rclone_config=false'
    return
  fi

  local generation state_dir=''
  generation=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  state_dir="$PHASE52_STATE_ROOT/phase52-$generation"

  # shellcheck disable=SC2317  # invoked indirectly by traps
  phase52_install_abort() {
    local rc=$?
    trap - ERR INT TERM HUP
    if [[ -n "$state_dir" && -d "$state_dir" && ! -L "$state_dir" ]]; then
      python3 "$PHASE52_STATE_HELPER" discard --home "$HOME_DIR" --state-dir "$state_dir" >/dev/null 2>&1 || true
    fi
    exit "$rc"
  }
  trap phase52_install_abort ERR
  trap 'exit 130' INT
  trap 'exit 143' TERM
  trap 'exit 129' HUP

  python3 "$PHASE52_STATE_HELPER" capture \
    --home "$HOME_DIR" --module-dir "$PHASE52_MODULE_DIR" \
    --state-dir "$state_dir" --generation "$generation" >/dev/null
  python3 "$PHASE52_STATE_HELPER" install \
    --home "$HOME_DIR" --module-dir "$PHASE52_MODULE_DIR" --state-dir "$state_dir" >/dev/null
  trap - ERR INT TERM HUP
  echo "OK: Phase 52 copy-only instalado; rollback_state=$state_dir"
  echo 'OK: timer_action=none'
  echo 'OK: rclone Vault binding efêmero instalado'
}

if [[ "$phase52_only" == true ]]; then
  install_phase52_horistic
  exit 0
fi

[[ -z "$requested_host" && "$dry_run" == false ]] || usage

# === Detecta srv_num via hostname ===
HOSTNAME=$(hostname)
# The explicit canonical names below document the accepted inventory contract.
# shellcheck disable=SC2221,SC2222
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
