#!/bin/bash
# Offload retired artifacts to GDrive and remove local copies after verify.
# Targets: open-webui, hermes-pers, paperclip-pers legacy leftovers.
set -euo pipefail

HOME_DIR="/home/ubuntu"
REMOTE="giovanni-drive:ATIUS-SRV/SRV-1/Backup/retired-services"
RCLONE_CONFIG="$HOME_DIR/.config/rclone/rclone.conf"
LOG="$HOME_DIR/.logs/offload-retired-artifacts.log"
BWLIMIT_KBPS="${BWLIMIT_KBPS:-54000}"
LOCK="/tmp/offload-retired-artifacts.lock"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

retry_rclone() {
  local label="$1"; shift
  local attempt=1 max_attempts=6 wait_time err_file err_msg rc
  while (( attempt <= max_attempts )); do
    err_file=$(mktemp)
    if rclone "$@" --config="$RCLONE_CONFIG" 2>"$err_file"; then
      rm -f "$err_file"
      return 0
    fi
    rc=$?
    err_msg=$(cat "$err_file")
    rm -f "$err_file"
    if echo "$err_msg" | grep -q "rateLimitExceeded\|Quota exceeded\|too_many_requests\|storageQuotaExceeded"; then
      wait_time=$((60 + (attempt-1)*30))
      log "RATE $label attempt=$attempt/$max_attempts wait=${wait_time}s"
      sleep "$wait_time"
      ((attempt++))
    else
      log "FAIL $label rc=$rc detail=$(echo "$err_msg" | head -2 | tr '\n' ' ')"
      return "$rc"
    fi
  done
  log "FAIL $label exhausted_attempts=$max_attempts"
  return 1
}

remote_bytes() {
  local remote="$1"
  local bytes
  bytes=$(rclone size "$remote" --json --config="$RCLONE_CONFIG" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("bytes",0))' 2>/dev/null || echo 0)
  if [ "$bytes" = "0" ]; then
    bytes=$(rclone lsjson "$remote" --config="$RCLONE_CONFIG" 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d[0].get("Size",0) if isinstance(d,list) and d else 0))' 2>/dev/null || echo 0)
  fi
  echo "$bytes"
}

backup_volume() {
  local vol="$1"
  local remote="$REMOTE/docker-volumes/${vol}.tar.gz"
  if ! sudo docker volume inspect "$vol" >/dev/null 2>&1; then
    log "SKIP volume_missing $vol"
    return 0
  fi
  log "BACKUP volume $vol -> $remote"
  if sudo tar cf - -C /var/lib/docker/volumes "$vol" 2>/dev/null | pigz --fast | pv -q -L "${BWLIMIT_KBPS}k" -W | rclone rcat "$remote" --config="$RCLONE_CONFIG" --bwlimit="${BWLIMIT_KBPS}k" --retries=3 --low-level-retries=5 --log-level=ERROR; then
    local bytes
    bytes=$(remote_bytes "$remote")
    if [ "$bytes" -gt 0 ]; then
      sudo docker volume rm "$vol" >/dev/null
      log "DELETE volume $vol remote_bytes=$bytes"
      return 0
    fi
  fi
  log "KEEP volume $vol verify_failed"
  return 1
}

backup_path() {
  local path="$1"
  local name="$2"
  local remote="$REMOTE/paths/${name}.tar.gz"
  if [ ! -e "$path" ]; then
    log "SKIP path_missing $path"
    return 0
  fi
  log "BACKUP path $path -> $remote"
  if (cd "$(dirname "$path")" && tar cf - "$(basename "$path")" 2>/dev/null | pigz --fast | pv -q -L "${BWLIMIT_KBPS}k" -W | rclone rcat "$remote" --config="$RCLONE_CONFIG" --bwlimit="${BWLIMIT_KBPS}k" --retries=3 --low-level-retries=5 --log-level=ERROR); then
    local bytes
    bytes=$(remote_bytes "$remote")
    if [ "$bytes" -gt 0 ]; then
      rm -rf --one-file-system "$path"
      log "DELETE path $path remote_bytes=$bytes"
      return 0
    fi
  fi
  log "KEEP path $path verify_failed"
  return 1
}

main() {
  exec 9>"$LOCK"
  flock -n 9 || { log "SKIP already_running"; exit 0; }
  mkdir -p "$(dirname "$LOG")"
  log "=================================================="
  log "OFFLOAD RETIRED ARTIFACTS INICIO bwlimit=${BWLIMIT_KBPS}k"

  mkdir -p "$HOME_DIR/GDrive" || true

  # Volumes
  backup_volume open-webui_open-webui-data || true
  backup_volume openwebui_open-webui-data || true
  backup_volume hermes-pers_hermes-pers-data || true
  backup_volume hermes-pers-data || true

  # Legacy dirs
  backup_path /home/ubuntu/docker/Atius/open-webui open-webui-compose || true
  backup_path /home/ubuntu/docker/Atius/agente-ia-atius/paperclip-atius/open-webui openwebui-compose-paperclip-atius || true
  backup_path /home/ubuntu/docker/ai-apps/agent-pers/paperclip-pers paperclip-pers-dir || true
  backup_path /home/ubuntu/docker/ai-apps/hermes-pers hermes-pers-dir || true
  backup_path /home/ubuntu/docker/Outros/ai-apps/agent-pers/paperclip-pers paperclip-pers-outros-dir || true
  backup_path /home/ubuntu/docker/Outros/ai-apps/hermes-pers hermes-pers-outros-dir || true
  backup_path /home/ubuntu/docker/AtiusCapital/agent-pers/paperclip-pers paperclip-pers-atiuscapital-dir || true

  # Empty network cleanup (no backup needed)
  if sudo docker network inspect paperclip-hermes-shared >/dev/null 2>&1; then
    if sudo docker network inspect paperclip-hermes-shared 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin)[0]; import sys as s; s.exit(0 if not (d.get('Containers') or {}) else 1)"; then
      sudo docker network rm paperclip-hermes-shared >/dev/null 2>&1 || true
      log "DELETE network paperclip-hermes-shared"
    fi
  fi

  log "OFFLOAD RETIRED ARTIFACTS FIM"
  log "=================================================="
}

main "$@"
