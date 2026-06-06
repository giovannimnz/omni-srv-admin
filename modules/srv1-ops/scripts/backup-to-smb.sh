#!/bin/bash
# backup-to-smb.sh — backup de pastas criticas pro SMB share //10.1.1.2/Shared
# NAO monta, NAO pesa no / local. Roda via systemd user timer.
# Mantem ultimos 7 snapshots. Loga em ~/logs/backup-smb.log
#
# === LIMITES DE I/O (Oracle OCI SSD simples, 65-70MB/s de teto) ===
# Internet 300MB/s, mas disco local cap. Backup em paralelo mataria latencia
# de Hermes, builds, containers. Cap abaixo do disco pra nao saturar.
#   BWLIMIT_KBPS=50000  → 50MB/s hard cap no rsync (rede + disco)
#   IONICE=best-effort/prio 7  → menor prioridade de I/O no kernel
#   TRANSFERS=1 CHECKERS=2  → uma transferencia por vez, baixo paralelismo
# Ajustar BWLIMIT_KBPS aqui se mudar de maquina (SRV-2, SRV-3).

# set -u (variavel nao definida) ainda ativo.
# set -e DESLIGADO — rsync pode retornar 23 (partial transfer, symlinks em CIFS)
# e isso nao pode matar o script. Capturamos STATUS manualmente.
set -uo pipefail

# === THROTTLE CONFIG ===
BWLIMIT_KBPS=60000  # 60MB/s hard cap — abaixo do teto de 65-70MB/s do SSD simples OCI
TRANSFERS=1
CHECKERS=2
IONICE_CLASS=best-effort
IONICE_PRIO=7

# === TARGETS ===
SMB_BASE="$HOME/Shared_smb/backup/atius-srv-1"
GDRIVE_REMOTE="giovanni-drive:"
GDRIVE_BASE="hermes-backups"
LOCAL_LOG="$HOME/logs/backup-smb.log"
KEEP_SNAPSHOTS=7
DATE=$(date +%Y-%m-%d_%H%M%S)
SNAPSHOT_DIR="$SMB_BASE/snapshot-$DATE"
EXIT_CODE=0

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOCAL_LOG"
}

# Detectar ionice — se nao existir (ex: container sem capability), pula
IONICE_BIN=""
if command -v ionice >/dev/null 2>&1; then
    IONICE_BIN="ionice -c $IONICE_CLASS -n $IONICE_PRIO"
fi

mkdir -p "$HOME/logs" "$SMB_BASE"

log "===== BACKUP START snapshot=$DATE ====="
log "Throttle: bwlimit=${BWLIMIT_KBPS}KB/s transfers=$TRANSFERS ionice=$IONICE_CLASS/$IONICE_PRIO"
log "Disco livre /home: $(df -h /home | tail -1 | awk '{print $4}')"
log "Disco livre SMB: $(df -h $HOME/Shared_smb/ | tail -1 | awk '{print $4}')"

# Lista de pares (label:origem) — ajusta aqui
# NUNCA: /tmp, node_modules, dist, .git (rebuild from origin)
declare -A SOURCES=(
    ["vault"]="$HOME/GitHub/obsidian-vault/ideaverse"
    ["docker-configs"]="$HOME/docker/scripts"
    ["dotfiles-local-bin"]="$HOME/.local/bin"
    ["systemd-user"]="$HOME/.config/systemd/user"
    ["cron-current"]="$HOME/cron-current"
)

for label in "${!SOURCES[@]}"; do
    src="${SOURCES[$label]}"
    if [[ ! -e "$src" ]]; then
        log "SKIP  $label — $src nao existe"
        continue
    fi
    log "COPY  $label — $src -> $SNAPSHOT_DIR/$label/"

    # ionice wrapper (se disponivel)
    if [[ -n "$IONICE_BIN" ]]; then
        $IONICE_BIN rsync -aR \
            --bwlimit="$BWLIMIT_KBPS" \
            --exclude="node_modules/" \
            --exclude="node_modules/**" \
            --exclude="dist/" \
            --exclude="dist/**" \
            --exclude=".venv/" \
            --exclude="__pycache__/" \
            --exclude="*.pyc" \
            --exclude=".cache/" \
            --exclude="target/" \
            --exclude="**/node_modules/**" \
            "$src" "$SNAPSHOT_DIR/" 2>>"$LOCAL_LOG"; STATUS=$?
    else
        rsync -aR \
            --bwlimit="$BWLIMIT_KBPS" \
            --exclude="node_modules/" \
            --exclude="node_modules/**" \
            --exclude="dist/" \
            --exclude="dist/**" \
            --exclude=".venv/" \
            --exclude="__pycache__/" \
            --exclude="*.pyc" \
            --exclude=".cache/" \
            --exclude="target/" \
            --exclude="**/node_modules/**" \
            "$src" "$SNAPSHOT_DIR/" 2>>"$LOCAL_LOG"; STATUS=$?
    fi

    if [[ $STATUS -eq 0 ]]; then
        log "OK    $label"
    elif [[ $STATUS -eq 23 ]]; then
        # rsync code 23 = partial transfer (CIFS symlinks etc) — nao fatal
        log "WARN  $label — partial transfer (symlinks em CIFS, ignorado)"
    else
        log "FAIL  $label — rsync exit=$STATUS"
        EXIT_CODE=1
    fi
done

# Rotacao: manter so ultimos N snapshots
if [[ -d "$SMB_BASE" ]]; then
    SNAPSHOT_COUNT=$(ls -1d "$SMB_BASE"/snapshot-* 2>/dev/null | wc -l)
    if (( SNAPSHOT_COUNT > KEEP_SNAPSHOTS )); then
        DELETE_COUNT=$((SNAPSHOT_COUNT - KEEP_SNAPSHOTS))
        log "ROTATE — removendo $DELETE_COUNT snapshot(s) antigo(s) (mantendo ultimos $KEEP_SNAPSHOTS)"
        ls -1d "$SMB_BASE"/snapshot-* 2>/dev/null \
            | sort \
            | head -n "$DELETE_COUNT" \
            | while read -r old; do
                # Delete em background com ionice pra nao travar disco
                if [[ -n "$IONICE_BIN" ]]; then
                    $IONICE_BIN rm -rf "$old" && log "PURGE $old"
                else
                    rm -rf "$old" && log "PURGE $old"
                fi
            done
    fi
fi

# Upload paralelo pra GDrive (vai falhar de quota ate configurar OAuth)
# Quando configurar OAuth pessoal, remover o bloco 'if false' e ajustar BWLIMIT.
# rclone tem --bwlimit em kbytes/s (mesma unidade do rsync).
if false; then
    log "UPLOAD GDrive — tentativa de upload paralelo (OAuth ainda nao configurado)"
    rclone copy "$SNAPSHOT_DIR" "${GDRIVE_REMOTE}${GDRIVE_BASE}/snapshot-$DATE/" \
        --config="$HOME/.config/rclone/rclone.conf" \
        --transfers="$TRANSFERS" \
        --checkers="$CHECKERS" \
        --bwlimit="${BWLIMIT_KBPS}K" \
        --retries=3 \
        --low-level-retries=5 \
        --log-level=ERROR \
        --exclude="node_modules/**" --exclude="dist/**" \
        2>>"$LOCAL_LOG" || log "WARN  GDrive upload falhou (esperado ate configurar OAuth)"
fi

log "Disco livre /home pos: $(df -h /home | tail -1 | awk '{print $4}')"
log "===== BACKUP END exit=$EXIT_CODE ====="
exit $EXIT_CODE
