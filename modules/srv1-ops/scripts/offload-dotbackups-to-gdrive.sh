#!/bin/bash
# offload-dotbackups-to-gdrive.sh — offload ~/.backups para GDrive após verify
# -------------------------------------------------------------------------
# Fonte:   /home/ubuntu/.backups/
# Destino: giovanni-drive:ATIUS-SRV/SRV-1/Backup/home/ubuntu/.backups/
# Managed by: ~/GitHub/omni-srv-admin/modules/srv1-ops/
# Regra:   copy -> verify -> delete local. Se verify falhar, NÃO apaga.
# Timer:   offload-dotbackups-to-gdrive.timer (05:30 BRT)
# -------------------------------------------------------------------------
set -uo pipefail

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    sed -n '1,12p' "$0"
    exit 0
fi

HOME_DIR="/home/ubuntu"
SRC_DIR="${HOME_DIR}/.backups"
REMOTE="giovanni-drive:"
BASE_PATH="ATIUS-SRV/SRV-1/Backup/home/ubuntu/.backups"
RCLONE_CONFIG="${HOME_DIR}/.config/rclone/rclone.conf"
LOG="${HOME_DIR}/.logs/offload-dotbackups-to-gdrive.log"
LOCK="/tmp/offload-dotbackups-to-gdrive.lock"
MIN_AGE_MINUTES="${MIN_AGE_MINUTES:-10}"
DELETE_AFTER_VERIFY="${DELETE_AFTER_VERIFY:-1}"
BWLIMIT_KBPS="${BWLIMIT_KBPS:-54000}"
TRANSFERS="${TRANSFERS:-1}"
CHECKERS="${CHECKERS:-1}"
ARCHIVE_THRESHOLD_FILES="${ARCHIVE_THRESHOLD_FILES:-20000}"
ARCHIVE_THRESHOLD_BYTES="${ARCHIVE_THRESHOLD_BYTES:-1073741824}"
TMP_DIR="/tmp/offload-dotbackups"
EXIT_CODE=0

mkdir -p "$TMP_DIR"

mkdir -p "$(dirname "$LOG")" "$SRC_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

retry_rclone() {
    local label="$1"
    shift
    local max_attempts=8
    local attempt=1
    local err_file err_msg wait_time rc

    while (( attempt <= max_attempts )); do
        err_file=$(mktemp)
        if rclone "$@" --config="$RCLONE_CONFIG" 2>"$err_file"; then
            rm -f "$err_file"
            return 0
        fi
        rc=$?
        err_msg=$(cat "$err_file")
        rm -f "$err_file"

        if echo "$err_msg" | grep -q "rateLimitExceeded\|storageQuotaExceeded\|Quota exceeded\|Rate Limit\|too_many_requests"; then
            wait_time=$((60 + (attempt - 1) * 30))
            log "RATE  $label attempt=$attempt/$max_attempts wait=${wait_time}s"
            sleep "$wait_time"
            ((attempt++))
        else
            log "FAIL  $label rc=$rc"
            log "DETAIL: $(echo "$err_msg" | head -3 | tr '\n' ' ')"
            return "$rc"
        fi
    done

    log "FAIL  $label exhausted_attempts=$max_attempts"
    return 1
}

remote_path_for_item() {
    local item="$1"
    local name
    name=$(basename "$item")
    printf '%s%s/%s' "$REMOTE" "$BASE_PATH" "$name"
}

local_count() {
    local item="$1"
    if [ -d "$item" ]; then
        find "$item" -type f | wc -l | tr -d ' '
    elif [ -f "$item" ]; then
        echo 1
    else
        echo 0
    fi
}

local_bytes() {
    local item="$1"
    if [ -d "$item" ]; then
        find "$item" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END{print s+0}'
    elif [ -f "$item" ]; then
        stat -c '%s' "$item"
    else
        echo 0
    fi
}

should_archive_item() {
    local item="$1"
    local files bytes
    files=$(local_count "$item")
    bytes=$(local_bytes "$item")
    [ "$files" -ge "$ARCHIVE_THRESHOLD_FILES" ] || [ "$bytes" -ge "$ARCHIVE_THRESHOLD_BYTES" ]
}

archive_remote_path() {
    local item="$1"
    local name
    name=$(basename "$item")
    printf '%s%s/%s.tar.gz' "$REMOTE" "$BASE_PATH" "$name"
}

manifest_remote_path() {
    local item="$1"
    local name
    name=$(basename "$item")
    printf '%s%s/%s.manifest.json' "$REMOTE" "$BASE_PATH" "$name"
}

remote_count() {
    local dest="$1"
    rclone lsf "$dest" --recursive --files-only --config="$RCLONE_CONFIG" 2>/dev/null | wc -l | tr -d ' '
}

remote_bytes() {
    local dest="$1"
    local bytes
    bytes=$(rclone size "$dest" --json --config="$RCLONE_CONFIG" 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("bytes",0))' 2>/dev/null || echo 0)
    if [ "$bytes" = "0" ]; then
        # Single-file remote path fallback
        bytes=$(rclone lsjson "$dest" --config="$RCLONE_CONFIG" 2>/dev/null \
            | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d[0].get("Size",0) if isinstance(d,list) and d else 0))' 2>/dev/null || echo 0)
    fi
    echo "$bytes"
}

archive_item() {
    local item="$1"
    local label archive_dest manifest_dest manifest_tmp local_files local_size
    label=$(basename "$item")
    archive_dest=$(archive_remote_path "$item")
    manifest_dest=$(manifest_remote_path "$item")
    manifest_tmp=$(mktemp "$TMP_DIR/${label}.manifest.XXXXXX.json")
    local_files=$(local_count "$item")
    local_size=$(local_bytes "$item")

    printf '{"name":"%s","local_files":%s,"local_bytes":%s,"created_at":"%s"}\n' \
      "$label" "$local_files" "$local_size" "$(date -Iseconds)" > "$manifest_tmp"

    log "ARCHIVE $label files=$local_files bytes=$local_size -> $archive_dest"
    if (cd "$(dirname "$item")" && ionice -c 2 -n 7 nice -n 19 tar cf - "$label" 2>/dev/null \
        | pigz --fast \
        | pv -q -L "${BWLIMIT_KBPS}k" -W \
        | rclone rcat "$archive_dest" --config="$RCLONE_CONFIG" --bwlimit="${BWLIMIT_KBPS}k" --retries=3 --low-level-retries=5 --log-level=ERROR); then
        if retry_rclone "manifest:$label" copyto "$manifest_tmp" "$manifest_dest" \
            --transfers=1 --checkers=1 --bwlimit="${BWLIMIT_KBPS}k" \
            --retries=3 --low-level-retries=5 --log-level=ERROR; then
            rm -f "$manifest_tmp"
            return 0
        fi
    fi
    rm -f "$manifest_tmp"
    return 1
}

verify_archive_item() {
    local item="$1"
    local label archive_dest manifest_dest archive_bytes manifest_bytes
    label=$(basename "$item")
    archive_dest=$(archive_remote_path "$item")
    manifest_dest=$(manifest_remote_path "$item")
    archive_bytes=$(remote_bytes "$archive_dest")
    manifest_bytes=$(remote_bytes "$manifest_dest")
    log "VERIFY-ARCHIVE $label archive_bytes=$archive_bytes manifest_bytes=$manifest_bytes"
    [ "$archive_bytes" -gt 0 ] && [ "$manifest_bytes" -gt 0 ]
}

copy_item() {
    local item="$1"
    local dest="$2"
    local label
    label=$(basename "$item")

    if [ -d "$item" ]; then
        retry_rclone "copy:$label" copy "$item" "$dest" \
            --transfers="$TRANSFERS" --checkers="$CHECKERS" --bwlimit="${BWLIMIT_KBPS}k" \
            --retries=3 --low-level-retries=5 --log-level=ERROR --create-empty-src-dirs
    elif [ -f "$item" ]; then
        retry_rclone "copy:$label" copyto "$item" "$dest" \
            --transfers="$TRANSFERS" --checkers="$CHECKERS" --bwlimit="${BWLIMIT_KBPS}k" \
            --retries=3 --low-level-retries=5 --log-level=ERROR
    else
        log "SKIP  missing_before_copy $item"
        return 0
    fi
}

verify_item() {
    local item="$1"
    local dest="$2"
    local label local_files remote_files local_size remote_size
    label=$(basename "$item")
    local_files=$(local_count "$item")
    remote_files=$(remote_count "$dest")
    local_size=$(local_bytes "$item")
    remote_size=$(remote_bytes "$dest")

    log "VERIFY $label local_files=$local_files remote_files=$remote_files local_bytes=$local_size remote_bytes=$remote_size"

    if [ "$local_files" != "$remote_files" ]; then
        log "FAIL  verify-count $label"
        return 1
    fi
    if [ "$local_size" != "$remote_size" ]; then
        log "FAIL  verify-bytes $label"
        return 1
    fi

    if [ -d "$item" ] && [ "$local_files" != "0" ]; then
        retry_rclone "check:$label" check "$item" "$dest" --one-way --log-level=ERROR
    else
        return 0
    fi
}

main() {
    exec 9>"$LOCK"
    if ! flock -n 9; then
        log "SKIP  already_running lock=$LOCK"
        exit 0
    fi

    log "=================================================="
    log "OFFLOAD .backups INICIO src=$SRC_DIR dest=${REMOTE}${BASE_PATH} min_age=${MIN_AGE_MINUTES}m delete=$DELETE_AFTER_VERIFY"
    log "Disco antes: $(df -h /home | tail -1 | awk '{print $4}') livre"

    if [ ! -d "$SRC_DIR" ]; then
        log "SKIP  source_missing $SRC_DIR"
        exit 0
    fi

    mapfile -d '' ITEMS < <(find "$SRC_DIR" -mindepth 1 -maxdepth 1 -mmin +"$MIN_AGE_MINUTES" -print0 2>/dev/null | sort -z)
    if [ "${#ITEMS[@]}" -eq 0 ]; then
        log "OK    nothing_to_offload"
        log "OFFLOAD .backups FIM exit=0"
        exit 0
    fi

    for item in "${ITEMS[@]}"; do
        [ -e "$item" ] || continue
        label=$(basename "$item")
        dest=$(remote_path_for_item "$item")
        log "COPY  $label -> $dest"
        if [ -d "$item" ] && should_archive_item "$item"; then
            if archive_item "$item" && verify_archive_item "$item"; then
                log "OK    verified-archive $label"
                if [ "$DELETE_AFTER_VERIFY" = "1" ]; then
                    rm -rf --one-file-system "$item"
                    if [ ! -e "$item" ]; then
                        log "DELETE local $label"
                    else
                        log "FAIL  delete-local $label"
                        EXIT_CODE=1
                    fi
                else
                    log "KEEP  local $label delete_after_verify=0"
                fi
            else
                log "KEEP  local $label archive_verify_failed"
                EXIT_CODE=1
            fi
        elif copy_item "$item" "$dest" && verify_item "$item" "$dest"; then
            log "OK    verified $label"
            if [ "$DELETE_AFTER_VERIFY" = "1" ]; then
                rm -rf --one-file-system "$item"
                if [ ! -e "$item" ]; then
                    log "DELETE local $label"
                else
                    log "FAIL  delete-local $label"
                    EXIT_CODE=1
                fi
            else
                log "KEEP  local $label delete_after_verify=0"
            fi
        else
            log "KEEP  local $label verify_or_copy_failed"
            EXIT_CODE=1
        fi
    done

    log "Disco depois: $(df -h /home | tail -1 | awk '{print $4}') livre"
    log "OFFLOAD .backups FIM exit=$EXIT_CODE"
    log "=================================================="
    exit "$EXIT_CODE"
}

main "$@"
