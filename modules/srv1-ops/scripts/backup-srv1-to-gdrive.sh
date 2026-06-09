#!/bin/bash
# Pre-backup: rodar cleanup local para liberar espaco antes do upload
/home/ubuntu/.local/bin/cleanup-local.sh >> /home/ubuntu/.logs/pre-backup-cleanup.log 2>&1
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

set -uo pipefail

# === CONFIG ===
REMOTE="giovanni-drive:"
BASE_PATH="ATIUS-SRV/SRV-1/Backup/snapshots"
LOCAL_LOG="$HOME/.logs/backup-srv1.log"
KEEP_SNAPSHOTS=14
DATE=$(date +%Y-%m-%d_%H%M%S)
DEST="${REMOTE}${BASE_PATH}/snapshot-$DATE"
RCLONE_CONFIG="$HOME/.config/rclone/rclone.conf"

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
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOCAL_LOG"
}

bkp() {
    local label="$1"
    local src="$2"
    local dest="$3"
    shift 3
    local extra_args=("$@")

    [[ ! -e "$src" ]] && { log "SKIP  $label — $src não existe"; return 0; }

    log "COPY  $label — $src -> $DEST/$dest/"

    local max_attempts=8
    local attempt=1
    local rclone_err

    while (( attempt <= max_attempts )); do
        rclone_err=$(mktemp)
        if rclone copy "$src" "${DEST}/${dest}/" \
                --config="$RCLONE_CONFIG" \
                --transfers="$TRANSFERS" \
                --checkers="$CHECKERS" \
                --bwlimit="${BWLIMIT_KBPS}k" \
                --retries=3 \
                --low-level-retries=5 \
                --log-level=ERROR \
                --stats=5m \
                --stats-one-line \
                "${extra_args[@]}" \
                2>"$rclone_err"; then
            log "OK    $label (attempt $attempt)"
            rm -f "$rclone_err"
            return 0
        fi

        local rc=$?
        local err_msg=$(cat "$rclone_err")
        rm -f "$rclone_err"

        # Verifica se é rate limit pela mensagem de erro
        if echo "$err_msg" | grep -q "rateLimitExceeded\|storageQuotaExceeded\|Quota exceeded\|Rate Limit"; then
            # Backoff: 60s, 90s, 120s, 150s, 180s, 210s, 240s
            local wait_time=$((60 + (attempt - 1) * 30))
            log "RATE  $label (attempt $attempt/$max_attempts) — esperando ${wait_time}s..."
            sleep "$wait_time"
            ((attempt++))
        else
            log "FAIL  $label (attempt $attempt/$max_attempts) — erro não recuperável (rc=$rc)"
            log "DETAIL: $(echo "$err_msg" | head -3)"
            EXIT_CODE=1
            return 1
        fi
    done

    log "FAIL  $label — esgotadas $max_attempts tentativas"
    EXIT_CODE=1
    return 1
}

# === INÍCIO ===
mkdir -p "$HOME/.logs"

log "=================================================="
log "BACKUP SRV-1 INÍCIO — snapshot=$DATE"
log "Throttle: bwlimit=${BWLIMIT_KBPS}KB/s transfers=$TRANSFERS"
log "Disco local antes: $(df -h /home | tail -1 | awk '{print $4}')"

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
)

bkp "github" "$HOME/GitHub" "home/ubuntu/GitHub" "${EXCLUDE_GIT[@]}"

# === 2. Docker stacks (exclui dados de postgres, jenkins_home) ===
EXCLUDE_DOCKER=(
    --exclude="*/data/postgres*"
    --exclude="*/postgres_data/**"
    --exclude="*/db-data/**"
    --exclude="*/jenkins_home/**"
    --exclude="*/node_modules/**"
)

bkp "docker" "$HOME/docker" "home/ubuntu/docker" "${EXCLUDE_DOCKER[@]}"

# === 3. Hermes Agent configs, skills, sessions ===
EXCLUDE_HERMES=(
    --exclude="cache/**"
    --exclude=".cache/**"
    --exclude="*/__pycache__/**"
)

bkp "hermes" "$HOME/.hermes" "home/ubuntu/.hermes" "${EXCLUDE_HERMES[@]}"

# === 3b. gbrain (v0.42.36.0) — config + install scripts, NOT the DB (it's in Postgres) ===
EXCLUDE_GBRAIN=(
    --exclude="*.lock"           # gbrain transient lockfiles
    --exclude=".locks/**"        # lock directory
    --exclude="last-update-check" # transient update-check cache
    --exclude="embed-cache/**"   # if any local embed cache materializes
)
bkp "gbrain" "$HOME/.gbrain" "home/ubuntu/.gbrain" "${EXCLUDE_GBRAIN[@]}"

# === 4. Shared SMB snapshots (espelho) ===
bkp "shared-smb" "$HOME/Shared_smb" "home/ubuntu/Shared_smb"

# === 5. Scripts customizados ===
bkp "local-bin" "$HOME/.local/bin" "home/ubuntu/.local/bin"

# === 6. Configs do sistema (systemd, rclone, git, ssh) ===
EXCLUDE_CONFIG=(
    --exclude="*/cache/**"
    --exclude="*/gyp/**"
)

bkp "config" "$HOME/.config" "home/ubuntu/.config" "${EXCLUDE_CONFIG[@]}"

# === 7. Logs do sistema ===
bkp "logs" "$HOME/.logs" "home/ubuntu/.logs"

# === 8. Rotação — manter só os 14 snapshots mais recentes ===
log "ROTATE — verificando snapshots em ${REMOTE}${BASE_PATH}/"
SNAPSHOT_COUNT=$(rclone lsf "${REMOTE}${BASE_PATH}/" --dirs-only --config="$RCLONE_CONFIG" 2>/dev/null | wc -l)

if (( SNAPSHOT_COUNT > KEEP_SNAPSHOTS )); then
    DELETE_COUNT=$((SNAPSHOT_COUNT - KEEP_SNAPSHOTS))
    log "ROTATE — removendo $DELETE_COUNT snapshot(s) antigo(s) (mantendo últimos $KEEP_SNAPSHOTS)"
    rclone lsf "${REMOTE}${BASE_PATH}/" --dirs-only --config="$RCLONE_CONFIG" 2>/dev/null \
        | sort \
        | head -n "$DELETE_COUNT" \
        | while read -r old; do
            rclone purge "${REMOTE}${BASE_PATH}/${old}" --config="$RCLONE_CONFIG" 2>>"$LOCAL_LOG" && \
                log "PURGE ${old%/}"
        done
fi

# === FINAL ===
log "Disco local depois: $(df -h /home | tail -1 | awk '{print $4}')"
log "BACKUP SRV-1 FIM — exit=$EXIT_CODE"
log "=================================================="
exit $EXIT_CODE
