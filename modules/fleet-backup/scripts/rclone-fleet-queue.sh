#!/bin/bash
# ============================================================================
# rclone-fleet-queue.sh
# ----------------------------------------------------------------------------
# Fila SERIAL de backups rclone. 1 job por vez, com cooldown entre servers.
# Resolve o problema de Google Drive API rate limit que detonou em 2026-06-11.
#
# Uso:
#   rclone-fleet-queue.sh enqueue <srv-num> [snapshot-name]
#   rclone-fleet-queue.sh run              # processa fila inteira
#   rclone-fleet-queue.sh status           # mostra fila
#   rclone-fleet-queue.sh clear            # limpa fila
#
# Lock:
#   - flock em /tmp/rclone-fleet.lock (global, 1 worker)
#   - 1 job por server via /tmp/rclone-srv{N}.lock
#   - Cooldown 5min entre servers (rate limit Google Drive)
#
# Vault:
#   - Log em /home/ubuntu/.logs/rclone-fleet.log
#   - Status em /home/ubuntu/.logs/rclone-fleet-queue.json
# ============================================================================
set -uo pipefail
IFS=$'\n\t'

# === CONFIG ===
FLEET_LOCK="/tmp/rclone-fleet.lock"
QUEUE_DIR="/home/ubuntu/.cache/rclone-fleet-queue"
LOG="/home/ubuntu/.logs/rclone-fleet.log"
STATUS_FILE="/home/ubuntu/.logs/rclone-fleet-queue.json"
COOLDOWN_SECONDS=300   # 5min entre servers (Google Drive quota)
MAX_JOB_RUNTIME=1800   # 30min max por job (kill se passar — rate limit recovery)
SRV_HOSTS=(
  "1:atius-srv-1:137.131.190.161"
  "2:atius-srv-2:129.148.47.32"
  "3:atius-srv-3:136.248.126.12"
)
SSH_KEY="/home/ubuntu/.ssh/id_ed25519"

mkdir -p "$QUEUE_DIR" "$(dirname "$LOG")" "$(dirname "$STATUS_FILE")"

# === CORES ===
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'

log()  { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
ok()   { log "${GRN}OK${NC}  $*"; }
warn() { log "${YEL}WARN${NC} $*"; }
err()  { log "${RED}ERR${NC} $*"; }
hdr()  { log "${BLU}=== $* ===${NC}"; }

# === HELP ===
usage() {
  cat <<EOF
Usage: $0 <command> [args]

Commands:
  enqueue SRV_NUM [SNAPSHOT]   Adiciona job à fila (SRV_NUM=1|2|3)
  run                          Processa fila inteira (1 por vez, cooldown 5min)
  status                       Mostra fila atual
  clear                        Limpa fila
  drain SRV_NUM                Força execução imediata (pula cooldown)
  -h, --help                   Esta ajuda

Exemplos:
  $0 enqueue 1
  $0 enqueue 2 snapshot-pre-cutover
  $0 run                       # processa SRV-1, espera 5min, SRV-2, espera 5min, SRV-3
  $0 status

EOF
  exit 0
}

# === ENQUEUE ===
cmd_enqueue() {
  local srv_num="$1"
  local snap="${2:-manual-$(date +%Y%m%d_%H%M%S)}"

  if [[ ! "$srv_num" =~ ^[123]$ ]]; then
    err "SRV_NUM deve ser 1, 2 ou 3 (recebido: $srv_num)"
    return 1
  fi

  # Verifica mount antes de enfileirar
  if ! mountpoint -q ~/GDrive 2>/dev/null; then
    err "GDrive mount não está ativo em $(hostname). Mount primeiro."
    return 2
  fi

  local job_file="$QUEUE_DIR/srv${srv_num}-${snap}.job"
  cat > "$job_file" <<EOJ
{
  "srv_num": $srv_num,
  "snapshot": "$snap",
  "enqueued_at": "$(date -Iseconds)",
  "host": "$(hostname)",
  "status": "pending"
}
EOJ
  ok "Enfileirado: SRV-$srv_num snapshot=$snap"
  return 0
}

# === STATUS ===
cmd_status() {
  hdr "Fila rclone-fleet-queue ($(hostname))"
  local pending=0
  for job_file in "$QUEUE_DIR"/*.job; do
    [ -f "$job_file" ] || continue
    echo "---"
    cat "$job_file"
    pending=$((pending + 1))
  done
  if [ "$pending" -eq 0 ]; then
    echo "(fila vazia)"
  else
    echo "---"
    echo "Total: $pending jobs pendentes"
  fi

  echo
  hdr "Status mounts remotos"
  for entry in "${SRV_HOSTS[@]}"; do
    IFS=':' read -r num host ip <<< "$entry"
    local ssh_target="${host}-VPN"
    local mp=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" "mountpoint ~/GDrive 2>&1" 2>/dev/null | head -1)
    echo "  SRV-$num ($ssh_target): $mp"
  done
}

# === CLEAR ===
cmd_clear() {
  hdr "Limpando fila"
  rm -f "$QUEUE_DIR"/*.job
  ok "Fila limpa"
}

# === DRAIN (pula cooldown) ===
cmd_drain() {
  local srv_num="$1"
  local job_file="$QUEUE_DIR/srv${srv_num}-manual-drain.job"
  cat > "$job_file" <<EOJ
{"srv_num": $srv_num, "snapshot": "manual-drain-$(date +%Y%m%d_%H%M%S)", "enqueued_at": "$(date -Iseconds)", "host": "$(hostname)", "status": "pending", "drain": true}
EOJ
  ok "Drain enfileirado: SRV-$srv_num"
  cmd_run
}

# === RUN: processa fila ===
cmd_run() {
  hdr "Iniciando worker rclone-fleet-queue"

  # Lock global: garante 1 worker por vez em qualquer server
  exec 9>"$FLEET_LOCK"
  if ! flock -n 9; then
    err "Outro worker já está rodando (lock $FLEET_LOCK ocupado)"
    return 1
  fi

  local last_srv=""
  while true; do
    # Pega próximo job (ordem numérica: SRV-1, SRV-2, SRV-3)
    local job_file
    job_file=$(ls -1 "$QUEUE_DIR"/srv*.job 2>/dev/null | sort | head -1)
    if [ -z "$job_file" ]; then
      ok "Fila vazia, encerrando worker"
      break
    fi

    # Extrai srv_num
    local srv_num
    srv_num=$(basename "$job_file" | sed 's/^srv\([0-9]\)-.*/\1/')
    local snap
    snap=$(basename "$job_file" | sed 's/^srv[0-9]-\(.*\)\.job$/\1/')
    local drain
    drain=$(grep -o '"drain": *true' "$job_file" || true)

    # Cooldown entre servers
    if [ -n "$last_srv" ] && [ "$last_srv" != "$srv_num" ] && [ -z "$drain" ]; then
      hdr "Cooldown ${COOLDOWN_SECONDS}s entre SRV-$last_srv e SRV-$srv_num (Google Drive rate limit)"
      sleep "$COOLDOWN_SECONDS"
    fi

    hdr "Processando SRV-$srv_num snapshot=$snap"
    if process_job "$srv_num" "$snap"; then
      ok "SRV-$srv_num OK"
      rm -f "$job_file"
    else
      err "SRV-$srv_num FAIL — re-enfileirando com backoff"
      # Cap retries em 5 para evitar filename bloat
      local retry_count=$(grep -o 'retry[0-9]\+' "$job_file" | head -1 | grep -o '[0-9]\+')
      retry_count=${retry_count:-0}
      local next_count=$((retry_count + 1))
      if [ "$next_count" -gt 5 ]; then
        err "SRV-$srv_num excedeu max retries — abandonando job"
        mv "$job_file" "$QUEUE_DIR/srv${srv_num}-${snap}-ABANDONED.job"
        sleep 60
        return 0
      fi
      # Re-enfileira com counter (NÃO concatena timestamp)
      local retry_snap="${snap}-retry${next_count}"
      mv "$job_file" "$QUEUE_DIR/srv${srv_num}-${retry_snap}.job"
      # Cooldown extra para dar tempo do rate limit resetar
      sleep 60
    fi

    last_srv="$srv_num"
  done

  flock -u 9
  ok "Worker encerrado"
}

# === PROCESS_JOB: roda backup num server ===
process_job() {
  local srv_num="$1"
  local snap="$2"

  # Encontra entry do server
  local entry
  for e in "${SRV_HOSTS[@]}"; do
    if [[ "$e" =~ ^${srv_num}: ]]; then
      entry="$e"
      break
    fi
  done
  if [ -z "$entry" ]; then
    err "SRV-$srv_num não está em SRV_HOSTS"
    return 1
  fi

  IFS=':' read -r num host ip <<< "$entry"
  local ssh_target="${host}-VPN"
  local srv_lock="/tmp/rclone-srv${srv_num}.lock"

  # Verifica mount remoto
  log "Verificando mount em $ssh_target..."
  local mp
  mp=$(ssh -o ConnectTimeout=8 -o BatchMode=yes -i "$SSH_KEY" "$ssh_target" "mountpoint ~/GDrive 2>&1" 2>/dev/null | head -1)
  if [[ "$mp" != *"é um ponto de montagem"* ]] && [[ "$mp" != *"is a mountpoint"* ]]; then
    err "$ssh_target GDrive mount não ativo: $mp"
    return 1
  fi
  ok "Mount $ssh_target OK"

  # Lock por server: 1 backup por server
  ssh -o BatchMode=yes -i "$SSH_KEY" "$ssh_target" "flock -n /tmp/rclone-srv${srv_num}.lock -c 'echo locked'" 2>/dev/null
  if [ $? -ne 0 ]; then
    err "Outro backup já está rodando em $ssh_target"
    return 1
  fi

  # Roda backup remoto (com flock remoto para garantir 1 só job por server)
  # timeout MAX_JOB_RUNTIME mata se rclone ficar em loop de retry
  log "Executando backup em $ssh_target snapshot=$snap (max ${MAX_JOB_RUNTIME}s)..."
  # Em SRV-1 é symlink em ~/.local/bin/. Em SRV-2/3 foi scp'd direto pra ~/
  # Tenta os 2 paths
  local cmd="flock -n /tmp/rclone-srv${srv_num}.lock timeout $MAX_JOB_RUNTIME bash -c '
    SCRIPT=
    for p in ~/backup-srv${srv_num}-to-gdrive.sh ~/.local/bin/backup-srv${srv_num}-to-gdrive.sh; do
      if [ -f \"\$p\" ]; then SCRIPT=\"\$p\"; break; fi
    done
    if [ -z \"\$SCRIPT\" ]; then
      echo \"NO_BACKUP_SCRIPT\"
      exit 1
    fi
    echo \"USING: \$SCRIPT\"
    bash \"\$SCRIPT\" 2>&1 | tail -25
  '"

  local result
  result=$(ssh -o BatchMode=yes -i "$SSH_KEY" "$ssh_target" "$cmd" 2>&1)
  local rc=$?

  if [ $? -ne 0 ] || [[ "$result" == *"NO_BACKUP_SCRIPT"* ]]; then
    err "Backup em $ssh_target falhou (rc=$rc): $result"
    return 1
  fi

  # Verify com rclone check (via rclone direto, não mount)
  log "Verificando backup com rclone check..."
  local check
  check=$(ssh -o BatchMode=yes -i "$SSH_KEY" "$ssh_target" "
    rclone check --size-only --one-way \
      ~/docker \
      giovanni-drive:ATIUS-SRV/SRV-${srv_num}/Backup/snapshots/snapshot-${snap}/home/ubuntu/docker \
      2>&1 | tail -5
  ")
  if [[ "$check" == *"ERROR"* ]] && [[ "$check" != *"0 errors"* ]]; then
    err "Verify FAIL: $check"
    return 1
  fi

  ok "Backup $ssh_target snapshot=$snap OK e verified"
  return 0
}

# === MAIN ===
case "${1:-}" in
  enqueue) shift; cmd_enqueue "${1:-}" "${2:-}" ;;
  run)     cmd_run ;;
  status)  cmd_status ;;
  clear)   cmd_clear ;;
  drain)   shift; cmd_drain "${1:-}" ;;
  -h|--help|help) usage ;;
  *)       usage ;;
esac
