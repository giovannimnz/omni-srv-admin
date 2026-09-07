#!/bin/bash
# backup-srv1-to-gdrive.sh — Backup COMPLETO do SRV-1 para Google Drive
# ---------------------------------------------------------------
# Destino: giovanni-drive:ATIUS-SRV/SRV-1/Backup/snapshots/
# Managed by: ~/GitHub/omni-srv-admin/modules/srv1-ops/
# Política: NADA salvo localmente. Tudo direto pro GDrive.
# Throttle: 75MB/s (60000 kbps)
# Rotação: 14 snapshots
#
# Fontes:
#   ~/GitHub/     → 17GB (exclui node_modules, .venv, .git, __pycache__, dist, target)
#   ~/docker/     → 10GB (exclui data/ de postgres)
#   ~/.hermes/    → 8GB (skills, logs, sessions, backups)
#   ~/Shared_smb/ → <1GB  (snapshots SMB - mirror)
#   ~/.local/bin/ → 48MB (scripts)
#   ~/.config/    → configs do sistema (ignora caches)
#   ~/.logs/      → logs do sistema
#
# NÃO backupa:
#   - ~/GDrive/   (é o próprio destino montado)
#   - ~/GitHub/vault/*  (vault tem backup separado)
#   - node_modules, .venv, __pycache__, .cache, target, dist

set -euo pipefail

EXPECTED_HOST="${BACKUP_EXPECTED_HOST:-atius-srv-1}"
if [ "$(hostname -s)" != "$EXPECTED_HOST" ]; then
    echo "SKIP wrong-host current=$(hostname -s) expected=$EXPECTED_HOST" >&2
    exit 0
fi

# === CONFIG ===
REMOTE="giovanni-drive:"
BASE_PATH="ATIUS-SRV/SRV-1/Backup/snapshots"
LOCAL_LOG="$HOME/.logs/backup-srv1.log"
KEEP_SNAPSHOTS=14
BACKUP_SNAPSHOT_ID="${BACKUP_SNAPSHOT_ID:-$(date +%Y-%m-%d_%H%M%S)}"
[[ "$BACKUP_SNAPSHOT_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] || {
    echo "FAIL: unsafe BACKUP_SNAPSHOT_ID" >&2
    exit 2
}
DEST="${REMOTE}${BASE_PATH}/snapshot-$BACKUP_SNAPSHOT_ID"
STATE_DIR="${BACKUP_STATE_DIR:-$HOME/.local/state/omni/backup-gdrive}"
STATE_FILE="$STATE_DIR/$BACKUP_SNAPSHOT_ID.json"
SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(cd "$(dirname "$SCRIPT_PATH")" && pwd)
STATE_HELPER="${BACKUP_STATE_HELPER:-$SCRIPT_DIR/backup-gdrive-state.py}"
RCLONE_CONFIG_MODE="${RCLONE_CONFIG_MODE:-vault}"
PERSISTENT_RCLONE_CONFIG="${PERSISTENT_RCLONE_CONFIG:-$HOME/.config/rclone/rclone.conf}"
RCLONE_HYDRATOR="${RCLONE_HYDRATOR:-$SCRIPT_DIR/../../fleet-backup/scripts/atius-rclone-vault-hydrate}"
RCLONE_RUN_TMP=""
RCLONE_ATTEMPTS_PER_RUN="${RCLONE_ATTEMPTS_PER_RUN:-1}"
RCLONE_COMMAND_TIMEOUT_SECONDS="${RCLONE_COMMAND_TIMEOUT_SECONDS:-6500}"
RCLONE_TPSLIMIT="${RCLONE_TPSLIMIT:-4}"
RCLONE_PACER_MIN_SLEEP="${RCLONE_PACER_MIN_SLEEP:-1s}"
FLEET_LOCK="${FLEET_LOCK:-/tmp/rclone-fleet.lock}"
FLEET_LOCK_WAIT_SECONDS="${FLEET_LOCK_WAIT_SECONDS:-30}"
PRE_BACKUP_CLEANUP="${PRE_BACKUP_CLEANUP:-$HOME/.local/bin/cleanup-local.sh}"

[[ -f "$STATE_HELPER" && ! -L "$STATE_HELPER" ]] || {
    echo "FAIL: backup state helper missing or symlinked" >&2
    exit 2
}
[[ "$RCLONE_ATTEMPTS_PER_RUN" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "$RCLONE_COMMAND_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "$RCLONE_TPSLIMIT" =~ ^[1-9][0-9]*$ ]] || exit 2
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

python3 "$STATE_HELPER" --state "$STATE_FILE" init \
    --snapshot-id "$BACKUP_SNAPSHOT_ID" --destination "$DEST"
INITIAL_STATE=$(python3 "$STATE_HELPER" --state "$STATE_FILE" status)
if [ "$INITIAL_STATE" = "complete" ]; then
    echo "BACKUP_ALREADY_COMPLETE snapshot=$BACKUP_SNAPSHOT_ID state=$STATE_FILE"
    exit 0
fi
if [ "$INITIAL_STATE" = "quarantined" ]; then
    echo "FAIL quarantined snapshot=$BACKUP_SNAPSHOT_ID state=$STATE_FILE" >&2
    exit 2
fi

cleanup_rclone_config() {
    if [ -n "$RCLONE_RUN_TMP" ] && [ -d "$RCLONE_RUN_TMP" ]; then
        find "$RCLONE_RUN_TMP" -depth -delete 2>/dev/null || true
    fi
}
trap cleanup_rclone_config EXIT
trap 'exit 75' INT TERM HUP

case "$RCLONE_CONFIG_MODE" in
    vault)
        RCLONE_RUN_TMP=$(mktemp -d /dev/shm/atius-srv1-backup.XXXXXX)
        chmod 700 "$RCLONE_RUN_TMP"
        mkdir -m 700 "$RCLONE_RUN_TMP/rclone"
        if ! "$RCLONE_HYDRATOR" --materialize --output-dir "$RCLONE_RUN_TMP/rclone" >"$RCLONE_RUN_TMP/hydrate.json" 2>/dev/null; then
            echo "FAIL: Vault rclone hydration blocked" >&2
            exit 1
        fi
        RCLONE_CONFIG="$RCLONE_RUN_TMP/rclone/rclone.conf"
        ;;
    persistent) RCLONE_CONFIG="$PERSISTENT_RCLONE_CONFIG" ;;
    *) echo "FAIL: invalid RCLONE_CONFIG_MODE" >&2; exit 1 ;;
esac

if ! python3 "$STATE_HELPER" --state "$STATE_FILE" validate-config \
    --config "$RCLONE_CONFIG" --remote giovanni-drive; then
    python3 "$STATE_HELPER" --state "$STATE_FILE" retry \
        --label github --error-class dedicated-oauth-client-missing --exit-code 75
    echo "RETRY dedicated OAuth client required; public rclone client is blocked" >&2
    exit 75
fi

if [ "${RCLONE_FLEET_LOCK_HELD:-0}" != "1" ]; then
    exec 8>"$FLEET_LOCK"
    if ! flock -w "$FLEET_LOCK_WAIT_SECONDS" 8; then
        echo "RETRY fleet lock timeout: $FLEET_LOCK" >&2
        exit 75
    fi
fi

# === THROTTLE I/O ===
# Regra: 85% teto GLOBAL da maquina, 50% teto por unico processo de transferencia.
# SRV-1 max write real ~108MB/s -> 50% por processo = 54MB/s.
# checkers=1 reduz queries API para evitar rate limit.
BWLIMIT_KBPS=54000
TRANSFERS=1
CHECKERS=1

EXIT_CODE=0

# === HELPERS ===
log() {
    local msg
    msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOCAL_LOG"
}

state() {
    python3 "$STATE_HELPER" --state "$STATE_FILE" "$@"
}

build_unreadable_filter() {
    local src="$1"
    local output="$2"
    : > "$output"
    while IFS= read -r path; do
        local rel="${path#"$src"/}"
        [ "$rel" = "$path" ] && continue
        if [ -d "$path" ]; then
            printf '/%s/**\n' "$rel" >> "$output"
        else
            printf '/%s\n' "$rel" >> "$output"
        fi
    done < <(
        find "$src" -xdev \
            \( -type d \( ! -readable -o ! -executable \) -print -prune \) -o \
            \( -type f ! -readable -print \) 2>/dev/null
    )
}

bkp() {
    local label="$1"
    local src="$2"
    local dest="$3"
    shift 3
    local extra_args=("$@")

    if state is-complete --label "$label"; then
        log "RESUME skip-complete $label snapshot=$BACKUP_SNAPSHOT_ID"
        return 0
    fi

    if [[ ! -e "$src" ]]; then
        log "SKIP  $label — $src não existe"
        state skip --label "$label"
        return 0
    fi

    state begin --label "$label"
    local remote_path="${DEST}/${dest}/"

    local unreadable_filter
    unreadable_filter=$(mktemp)
    build_unreadable_filter "$src" "$unreadable_filter"
    local unreadable_count
    unreadable_count=$(wc -l < "$unreadable_filter")
    if (( unreadable_count > 0 )); then
        log "EXCLUDE unreadable $label count=$unreadable_count"
    fi

    local attempt=1
    local rclone_err rc err_msg

    if ! state is-copied --label "$label"; then
        log "COPY  $label — $src -> $remote_path"
        while (( attempt <= RCLONE_ATTEMPTS_PER_RUN )); do
            rclone_err=$(mktemp)
            if timeout --signal=TERM --kill-after=30s "${RCLONE_COMMAND_TIMEOUT_SECONDS}s" \
                rclone sync "$src" "$remote_path" \
                    --links \
                    --config="$RCLONE_CONFIG" \
                    --transfers="$TRANSFERS" \
                    --checkers="$CHECKERS" \
                    --bwlimit="${BWLIMIT_KBPS}k" \
                    --fast-list \
                    --tpslimit="$RCLONE_TPSLIMIT" \
                    --tpslimit-burst=1 \
                    --drive-pacer-min-sleep="$RCLONE_PACER_MIN_SLEEP" \
                    --drive-pacer-burst=1 \
                    --retries=1 \
                    --low-level-retries=2 \
                    --log-level=ERROR \
                    --stats=5m \
                    --stats-one-line \
                    --exclude-from="$unreadable_filter" \
                    "${extra_args[@]}" \
                    2>"$rclone_err"; then
                log "COPIED $label attempt=$attempt"
                rm -f "$rclone_err"
                state copy-complete --label "$label"
                break
            else
                rc=$?
            fi

            err_msg=$(cat "$rclone_err")
            rm -f "$rclone_err"
            if grep -qiE "rateLimitExceeded|storageQuotaExceeded|Quota exceeded|Rate Limit" <<< "$err_msg"; then
                log "RETRY rate-limit $label attempt=$attempt"
                state retry --label "$label" --error-class rate-limit --exit-code 75
                rm -f "$unreadable_filter"
                return 75
            elif grep -qi "source file is being updated" <<< "$err_msg"; then
                log "RETRY source-updated $label attempt=$attempt"
                state retry --label "$label" --error-class source-updated --exit-code 75
                rm -f "$unreadable_filter"
                return 75
            elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ] || [ "$rc" -eq 143 ]; then
                log "RETRY command-timeout $label rc=$rc attempt=$attempt"
                state retry --label "$label" --error-class command-timeout --exit-code 75
                rm -f "$unreadable_filter"
                return 75
            else
                log "FAIL copy $label attempt=$attempt rc=$rc detail=$(head -3 <<< "$err_msg")"
                state fail --label "$label" --error-class copy-non-retryable --exit-code "$rc"
                rm -f "$unreadable_filter"
                EXIT_CODE=1
                return 1
            fi
        done

        if ! state is-copied --label "$label"; then
            state retry --label "$label" --error-class per-run-attempt-budget --exit-code 75
            rm -f "$unreadable_filter"
            return 75
        fi
    else
        log "RESUME copy-complete $label snapshot=$BACKUP_SNAPSHOT_ID"
    fi

    log "VERIFY $label — $src -> $remote_path"
    rclone_err=$(mktemp)
    if timeout --signal=TERM --kill-after=30s "${RCLONE_COMMAND_TIMEOUT_SECONDS}s" \
        rclone check "$src" "$remote_path" \
            --links \
            --checksum \
            --config="$RCLONE_CONFIG" \
            --checkers="$CHECKERS" \
            --fast-list \
            --tpslimit="$RCLONE_TPSLIMIT" \
            --tpslimit-burst=1 \
            --drive-pacer-min-sleep="$RCLONE_PACER_MIN_SLEEP" \
            --drive-pacer-burst=1 \
            --retries=1 \
            --low-level-retries=2 \
            --exclude-from="$unreadable_filter" \
            "${extra_args[@]}" \
            2>"$rclone_err"; then
        rm -f "$rclone_err" "$unreadable_filter"
        state complete --label "$label"
        log "VERIFIED $label"
        return 0
    else
        rc=$?
    fi

    err_msg=$(cat "$rclone_err")
    rm -f "$rclone_err" "$unreadable_filter"
    if grep -qiE "rateLimitExceeded|storageQuotaExceeded|Quota exceeded|Rate Limit" <<< "$err_msg"; then
        state retry --label "$label" --error-class verify-rate-limit --exit-code 75
        return 75
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ] || [ "$rc" -eq 143 ]; then
        state retry --label "$label" --error-class verify-timeout --exit-code 75
        return 75
    fi

    log "RETRY verify-mismatch $label rc=$rc detail=$(head -3 <<< "$err_msg")"
    state invalidate-copy --label "$label" --error-class verify-mismatch --exit-code 75
    return 75
}

run_bkp() {
    local rc=0
    bkp "$@" || rc=$?
    if [ "$rc" -eq 75 ]; then
        log "BACKUP_RETRY snapshot=$BACKUP_SNAPSHOT_ID state=$STATE_FILE"
        exit 75
    fi
    if [ "$rc" -ne 0 ]; then
        EXIT_CODE=1
    fi
}

# === INÍCIO ===
mkdir -p "$HOME/.logs"

log "=================================================="
log "BACKUP SRV-1 INÍCIO — snapshot=$BACKUP_SNAPSHOT_ID"
log "Throttle: bwlimit=${BWLIMIT_KBPS}KB/s transfers=$TRANSFERS"
log "Disco local antes: $(df -h /home | tail -1 | awk '{print $4}')"

if ! state is-complete --label pre-backup-cleanup; then
    state begin --label pre-backup-cleanup
    if [ -x "$PRE_BACKUP_CLEANUP" ]; then
        if ! "$PRE_BACKUP_CLEANUP" >> "$HOME/.logs/pre-backup-cleanup.log" 2>&1; then
            state retry --label pre-backup-cleanup --error-class pre-backup-cleanup-failed --exit-code 75
            exit 75
        fi
    fi
    state complete --label pre-backup-cleanup
fi

# === 1. GitHub repos (exclui artefatos de build/deps) ===
EXCLUDE_GIT=(
    --exclude="node_modules/**"
    --exclude=".venv/**"
    --exclude="__pycache__/**"
    --exclude="*.pyc"
    --exclude=".cache/**"
    --exclude="target/**"
    --exclude="dist/**"
    --exclude=".git/**"
    --exclude=".next/**"
    --exclude="build/**"
    --exclude=".terraform/**"
    --exclude="**/.planning/graphs/**"
    --exclude="**/graphify-out/**"
    --exclude="**/.obsidian/workspace*.json"
    --exclude="**/data/postgres_data/**"
    --exclude="**/pytest-of-*/**"
    --exclude="/Atius-Capital/ats/config/.env"
    --exclude="/Atius-Capital/horistic/config/.env"
)

run_bkp "github" "$HOME/GitHub" "home/ubuntu/GitHub" "${EXCLUDE_GIT[@]}"

# === 2. Docker stacks (exclui dados de postgres, jenkins_home) ===
EXCLUDE_DOCKER=(
    --exclude="*/data/postgres*"
    --exclude="*/postgres_data/**"
    --exclude="*/db-data/**"
    --exclude="*/jenkins_home/**"
    --exclude="*/node_modules/**"
)

run_bkp "docker" "$HOME/docker" "home/ubuntu/docker" "${EXCLUDE_DOCKER[@]}"

# === 3. Hermes Agent configs, skills, sessions ===
EXCLUDE_HERMES=(
    --exclude="cache/**"
    --exclude=".cache/**"
    --exclude="logs/**"
    --exclude="sessions/**"
    --exclude="state.db*"
    --exclude="*/__pycache__/**"
)

run_bkp "hermes" "$HOME/.hermes" "home/ubuntu/.hermes" "${EXCLUDE_HERMES[@]}"

# === 3b. gbrain (v0.42.36.0) — config + install scripts, NOT the DB (it's in Postgres) ===
EXCLUDE_GBRAIN=(
    --exclude="*.lock"           # gbrain transient lockfiles
    --exclude=".locks/**"        # lock directory
    --exclude="last-update-check" # transient update-check cache
    --exclude="embed-cache/**"   # if any local embed cache materializes
)
run_bkp "gbrain" "$HOME/.gbrain" "home/ubuntu/.gbrain" "${EXCLUDE_GBRAIN[@]}"

# === 4. Shared SMB snapshots (espelho) ===
run_bkp "shared-smb" "$HOME/Shared_smb" "home/ubuntu/Shared_smb"

# === 5. Scripts customizados ===
run_bkp "local-bin" "$HOME/.local/bin" "home/ubuntu/.local/bin"

# === 6. Configs do sistema (systemd, rclone, git, ssh) ===
EXCLUDE_CONFIG=(
    --exclude="*/cache/**"
    --exclude="*/gyp/**"
)

run_bkp "config" "$HOME/.config" "home/ubuntu/.config" "${EXCLUDE_CONFIG[@]}"

# === 7. Logs imutáveis/rotacionados ===
EXCLUDE_LOGS=(
    --exclude="*.log"
    --exclude="**/*.log"
    --exclude="*.jsonl"
    --exclude="**/*.jsonl"
    --exclude="*.tmp"
    --exclude="**/*.tmp"
)
run_bkp "logs" "$HOME/.logs" "home/ubuntu/.logs" "${EXCLUDE_LOGS[@]}"

# === 8. Rotação — somente depois de todas as sources completas ===
if [ "$EXIT_CODE" -eq 0 ]; then
    log "ROTATE — verificando snapshots em ${REMOTE}${BASE_PATH}/"
    state begin --label rotation
    rotation_file=$(mktemp)
    if ! timeout --signal=TERM --kill-after=10s 300s \
        rclone lsf "${REMOTE}${BASE_PATH}/" --dirs-only \
            --config="$RCLONE_CONFIG" > "$rotation_file" 2>/dev/null; then
        rm -f "$rotation_file"
        state retry --label rotation --error-class rotation-list --exit-code 75
        exit 75
    fi
    completed_rotation_file=$(mktemp)
    while IFS= read -r remote_name; do
        snapshot_name=${remote_name%/}
        snapshot_id=${snapshot_name#snapshot-}
        candidate_state="$STATE_DIR/$snapshot_id.json"
        if [ -f "$candidate_state" ] && python3 - "$candidate_state" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if data.get("status") == "complete" else 1)
PY
        then
            printf '%s\n' "$remote_name" >> "$completed_rotation_file"
        else
            log "ROTATE protect-unverified $snapshot_name"
        fi
    done < "$rotation_file"
    SNAPSHOT_COUNT=$(wc -l < "$completed_rotation_file")

    if (( SNAPSHOT_COUNT > KEEP_SNAPSHOTS )); then
        DELETE_COUNT=$((SNAPSHOT_COUNT - KEEP_SNAPSHOTS))
        log "ROTATE — removendo $DELETE_COUNT snapshot(s) verified antigo(s) (mantendo últimos $KEEP_SNAPSHOTS)"
        while IFS= read -r old; do
            if ! timeout --signal=TERM --kill-after=10s 300s \
                rclone purge "${REMOTE}${BASE_PATH}/${old}" \
                    --config="$RCLONE_CONFIG" 2>>"$LOCAL_LOG"; then
                rm -f "$rotation_file" "$completed_rotation_file"
                state retry --label rotation --error-class rotation-purge --exit-code 75
                exit 75
            fi
            log "PURGE ${old%/}"
        done < <(sort "$completed_rotation_file" | head -n "$DELETE_COUNT")
    fi
    rm -f "$rotation_file" "$completed_rotation_file"
    state complete --label rotation
    state finalize
else
    log "ROTATE — skipped because one or more source copies failed"
fi

# === FINAL ===
log "Disco local depois: $(df -h /home | tail -1 | awk '{print $4}')"
log "BACKUP SRV-1 FIM — exit=$EXIT_CODE"
log "=================================================="
[ "$EXIT_CODE" -eq 0 ] && log "BACKUP_COMPLETE snapshot=$BACKUP_SNAPSHOT_ID state=$STATE_FILE"
exit $EXIT_CODE
