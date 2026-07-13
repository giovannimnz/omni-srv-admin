#!/usr/bin/env bash
# rust-zellij-fleet — gerencia rust (rustup) + zellij (cargo-binstall) simultaneamente
# nos 3 servers ATIUS-SRV-1/2/3.
#
# Inventário fonte (source of truth):
#   ~/GitHub/omni-srv-admin/inventory/hosts/atius-srv-{1,2,3}.yaml
#   Cada host tem app "rust-toolchain" e "zellij" sob apps:.
#
# Uso:
#   ./fleet-rust-zellij.sh status                       # versões atuais nos 3 servers
#   ./fleet-rust-zellij.sh update --dry-run             # simula update, sem alterar
#   ./fleet-rust-zellij.sh update                       # update rust + zellij nos 3 (paralelo)
#   ./fleet-rust-zellij.sh update rust                  # só rust
#   ./fleet-rust-zellij.sh update zellij                # só zellij
#   ./fleet-rust-zellij.sh audit                        # diff inventory vs real
#
# Segurança:
#   - Lock anti-concorrência via flock em /tmp/rust-zellij-fleet.lock (per-host).
#   - SSH timeout 30s por host; falha de um host não aborta os outros.
#   - Update do rust é idempotente (rustup update stable no-op se já na versão).
#   - Update do zellij baixa binário pré-compilado (~5MB), não compila nada.
#   - Dry-run mostra comandos que rodariam, sem alterar nada.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${OMNI_SRV_ADMIN:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
HOSTS_DIR="$REPO/inventory/hosts"
LOG_DIR="$HOME/.logs/rust-zellij-fleet"
LOCK_PREFIX="/tmp/rust-zellij-fleet.lock"
mkdir -p "$LOG_DIR"

HOSTS=(
  "atius-srv-1:srv1:10.11.1.11"
  "atius-srv-2:srv2:10.12.1.12"
  "atius-srv-3:srv3:10.13.1.13"
)

# Defina apenas no próprio servidor; vazio força operação remota no WSL/controlador.
LOCAL_ID="${RUST_ZELLIJ_LOCAL_ID:-}"

# ---------- helpers ----------

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_DIR/fleet.log" >&2; }

# Lê campo yaml simples de um host. Falha silenciosa retorna vazio.
yaml_get() {
  local host_id="$1" key="$2"
  python3 -c "
import sys, re
try:
    with open('$HOSTS_DIR/$host_id.yaml') as f:
        text = f.read()
    m = re.search(r'^\s{4}$key:\s*(.+)$', text, re.MULTILINE)
    if m:
        v = m.group(1).strip().strip('\"')
        print(v)
except Exception:
    pass
"
}

ssh_run() {
  local host="$1" cmd="$2" timeout="${3:-30}"
  ssh -o ConnectTimeout="$timeout" -o BatchMode=yes "ubuntu@$host" "$cmd" 2>&1
}

with_lock() {
  local lock="$1"
  exec 9>"$lock"
  if ! flock -n 9; then
    log "Outro processo segura $lock — saindo."
    exit 1
  fi
}

# ---------- comandos ----------

cmd_status() {
  log "=== STATUS: rust + zellij fleet ==="
  printf "%-15s %-12s %-12s %-12s %-12s\n" "HOST" "RUSTC" "CARGO" "BINSTALL" "ZELLIJ"
  echo "---------------------------------------------------------------------"
  for entry in "${HOSTS[@]}"; do
    IFS=":" read -r host_id alias ip <<<"$entry"
    # Captura cada versão com || true pra não abortar em exit code não-zero de subshell
    if [ "$host_id" = "$LOCAL_ID" ]; then
      source "$HOME/.cargo/env" 2>/dev/null || true
      r=$(rustc --version 2>/dev/null | awk '{print $2}' || true)
      c=$(cargo --version 2>/dev/null | awk '{print $2}' || true)
      # binstall version: extrai do inventory YAML (cargo-binstall --version exige argumento)
      b=$(yaml_get "$host_id" "current_version" 2>/dev/null | grep -A 0 "" || true)
      # Pega só o current_version do bloco cargo-binstall especificamente
      b=$(python3 -c "
import re
try:
    with open('$HOSTS_DIR/$host_id.yaml') as f: t = f.read()
    m = re.search(r'- id: cargo-binstall.*?current_version:\s*\"?([^\"\s]+)', t, re.DOTALL)
    print(m.group(1) if m else 'N/A')
except Exception:
    print('N/A')
")
      z=$(zellij --version 2>/dev/null | awk '{print $2}' || true)
    else
      r=$(ssh_run "$ip" 'source "$HOME/.cargo/env" 2>/dev/null; rustc --version 2>/dev/null | awk "{print \$2}"' || true)
      c=$(ssh_run "$ip" 'source "$HOME/.cargo/env" 2>/dev/null; cargo --version 2>/dev/null | awk "{print \$2}"' || true)
      # binstall version: lookup local (versão é uniforme no fleet; inventory é source of truth)
      b=$(python3 -c "
import re
try:
    with open('$HOSTS_DIR/$host_id.yaml') as f: t = f.read()
    m = re.search(r'- id: cargo-binstall.*?current_version:\s*\"?([^\"\s]+)', t, re.DOTALL)
    print(m.group(1) if m else 'N/A')
except Exception:
    print('N/A')
")
      z=$(ssh_run "$ip" 'source "$HOME/.cargo/env" 2>/dev/null; zellij --version 2>/dev/null | awk "{print \$2}"' || true)
    fi
    printf "%-15s %-12s %-12s %-12s %-12s\n" "$alias" "${r:-N/A}" "${c:-N/A}" "${b:-N/A}" "${z:-N/A}"
  done
}

cmd_update_one_host() {
  local host_id="$1" alias="$2" ip="$3" target="$4" dry="${5:-no}"
  local log_file="$LOG_DIR/${alias}-$(date +%Y%m%d-%H%M%S).log"
  log "[$alias] update $target (dry=$dry) → $log_file"

  local cmds=()
  [ "$target" = "rust" ] || [ "$target" = "all" ] && cmds+=("source \"\$HOME/.cargo/env\" && rustup update stable")
  [ "$target" = "zellij" ] || [ "$target" = "all" ] && cmds+=("source \"\$HOME/.cargo/env\" && cargo binstall zellij --no-confirm")

  local remote_cmd
  remote_cmd=$(IFS=' && '; echo "${cmds[*]}")

  if [ "$dry" = "yes" ]; then
    log "[$alias] DRY-RUN: ssh ubuntu@$ip \"$remote_cmd\""
    return 0
  fi

  if [ "$host_id" = "$LOCAL_ID" ]; then
    bash -c "$remote_cmd" 2>&1 | tee -a "$log_file"
  else
    ssh_run "$ip" "$remote_cmd" 60 | tee -a "$log_file"
  fi
}

cmd_update() {
  local target="${1:-all}"
  local dry="no"
  [ "${2:-}" = "--dry-run" ] && dry="yes"

  log "=== UPDATE: $target (dry=$dry) — fleet paralelo ==="
  with_lock "$LOCK_PREFIX.update"

  for entry in "${HOSTS[@]}"; do
    IFS=":" read -r host_id alias ip <<<"$entry"
    (
      cmd_update_one_host "$host_id" "$alias" "$ip" "$target" "$dry"
    ) &
  done
  wait
  log "=== UPDATE completo — logs em $LOG_DIR/ ==="
  cmd_status
}

cmd_audit() {
  log "=== AUDIT: inventory vs real ==="
  for entry in "${HOSTS[@]}"; do
    IFS=":" read -r host_id alias ip <<<"$entry"
    local desired_rust desired_zellij actual_rust actual_zellij
    desired_rust=$(yaml_get "$host_id" "current_version" | head -1)
    desired_zellij=$(yaml_get "$host_id" "desired_version" | head -1)
    # current_version e desired_version iguais nos dois apps (versões fixadas)

    if [ "$host_id" = "$LOCAL_ID" ]; then
      source "$HOME/.cargo/env" 2>/dev/null || true
      actual_rust=$(rustc --version 2>/dev/null | awk '{print $2}')
      actual_zellij=$(zellij --version 2>/dev/null | awk '{print $2}')
    else
      actual_rust=$(ssh_run "$ip" 'source "$HOME/.cargo/env" 2>/dev/null; rustc --version 2>/dev/null | awk "{print \$2}"')
      actual_zellij=$(ssh_run "$ip" 'source "$HOME/.cargo/env" 2>/dev/null; zellij --version 2>/dev/null | awk "{print \$2}"')
    fi

    # desired_version em yaml tem múltiplas (uma por app). Pegamos o current_version do rust-toolchain e do zellij.
    desired_rust=$(python3 -c "
import re
with open('$HOSTS_DIR/$host_id.yaml') as f: t = f.read()
# Encontra bloco rust-toolchain e pega o current_version
m = re.search(r'- id: rust-toolchain.*?current_version:\s*\"?([^\"\s]+)', t, re.DOTALL)
print(m.group(1) if m else '')
")
    desired_zellij=$(python3 -c "
import re
with open('$HOSTS_DIR/$host_id.yaml') as f: t = f.read()
m = re.search(r'- id: zellij.*?current_version:\s*\"?([^\"\s]+)', t, re.DOTALL)
print(m.group(1) if m else '')
")

    printf "%-10s rust: actual=%s desired=%s %s | zellij: actual=%s desired=%s %s\n" \
      "$alias" \
      "${actual_rust:-MISSING}" "${desired_rust:-?}" \
      "$([ "${actual_rust:-}" = "${desired_rust:-}" ] && echo OK || echo DRIFT)" \
      "${actual_zellij:-MISSING}" "${desired_zellij:-?}" \
      "$([ "${actual_zellij:-}" = "${desired_zellij:-}" ] && echo OK || echo DRIFT)"
  done
}

# ---------- main ----------

case "${1:-status}" in
  status)
    cmd_status
    ;;
  update)
    shift
    cmd_update "${@}"
    ;;
  audit)
    cmd_audit
    ;;
  *)
    echo "Uso: $0 {status|update [rust|zellij|all] [--dry-run]|audit}" >&2
    exit 2
    ;;
esac
