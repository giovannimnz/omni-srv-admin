#!/bin/bash
# cleanup-local.sh — Rotina semanal de limpeza do host SRV-1
# ----------------------------------------------------------------------------
# Roda via systemd user timer (cleanup-local-weekly.timer)
# Frequência: semanal, domingo 03:00 BRT (com random 0-30min)
#
# CATEGORIAS:
#   1. /tmp antigos (extraídos root-like, binários soltos)
#   2. Caches npm/bun/pnpm/pip
#   3. Podman dangling (com segurança — só se nada crítico)
#   4. Logs locais ~/.logs (retenção 15d + trim)
# Managed by: ~/GitHub/omni-srv-admin/modules/srv1-ops/
#
# SEGURANÇA:
#   - Whitelist explícita de paths a NUNCA remover
#   - Cada fase tem --dry-run option
#   - Log sempre com timestamp + before/after sizes
#   - Falha em qualquer fase NÃO aborta as outras (continua)
# ----------------------------------------------------------------------------
set -uo pipefail

# Carregar PATH completo (nvm, .local) — systemd user não tem o mesmo PATH
export PATH="$HOME/.nvm/versions/node/v24.13.1/bin:$HOME/.local/bin:$HOME/.local/share/pnpm:$PATH"

LOG="$HOME/.logs/cleanup-local.log"
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')
DRY_RUN="${DRY_RUN:-0}"  # 1 = dry run, 0 = real

mkdir -p "$(dirname "$LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

# Banner
log "=========================================="
log "CLEANUP SRV-1 INÍCIO — modo=$([ "$DRY_RUN" = "1" ] && echo "DRY-RUN" || echo "REAL")"
log "Disco ANTES: $(df -h / | tail -1 | awk '{print $4}') livre"
log "=========================================="

# === FASE 1: /tmp antigos ===
cleanup_tmp() {
    log "FASE 1 — /tmp antigos (>3d, com whitelist)"

    # Whitelist: nunca remover
    local KEEP_PATTERNS=(
        '/tmp/.X*'              # X11 sockets/locks
        '/tmp/.ICE-*'           # ICE (X11)
        '/tmp/.font-unix'       # font sockets
        '/tmp/.Test-unix'       # Test sockets
        '/tmp/systemd-*'        # systemd private
        '/tmp/snap*'            # snap
        '/tmp/lu*'              # lu (?)
        '/tmp/hermes_*'         # sessões Hermes ativas (atual)
    )

    # Top-level dirs com mtime >3d, exceto whitelist
    while IFS= read -r -d '' d; do
        local name=$(basename "$d")
        local skip=0
        for pat in "${KEEP_PATTERNS[@]}"; do
            if [[ "$d" == $pat ]]; then
                skip=1
                break
            fi
        done
        if (( skip )); then
            log "  KEEP  $d (whitelist)"
            continue
        fi
        local size=$(du -sh "$d" 2>/dev/null | cut -f1)
        local age=$(( ($(date +%s) - $(stat -c %Y "$d")) / 86400 ))
        if (( age > 3 )); then
            if [[ "$DRY_RUN" = "1" ]]; then
                log "  DRY   $size age=${age}d  $d"
            else
                rm -rf "$d" 2>/dev/null && log "  ✅ $size age=${age}d  $d"
            fi
        else
            log "  KEEP  $size age=${age}d  $d (recente)"
        fi
    done < <(find /tmp -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

    # Arquivos soltos em /tmp >50MB mtime >3d
    while IFS= read -r -d '' f; do
        local size=$(du -h "$f" 2>/dev/null | cut -f1)
        if [[ "$DRY_RUN" = "1" ]]; then
            log "  DRY  FILE $size  $f"
        else
            rm -f "$f" && log "  ✅ FILE $size  $f"
        fi
    done < <(find /tmp -maxdepth 1 -type f -size +50M -mtime +3 -print0 2>/dev/null)
}

# === FASE 2: Caches npm/bun/pnpm/pip ===
cleanup_caches() {
    log "FASE 2 — Caches"

    # npm _npx orphans (manter últimos 5)
    if [[ -d "$HOME/.npm/_npx" ]]; then
        local count=$(ls -1 "$HOME/.npm/_npx" 2>/dev/null | wc -l)
        if (( count > 5 )); then
            local removed=$((count - 5))
            log "  npm _npx: $count entries, removendo $removed mais antigos"
            if [[ "$DRY_RUN" = "0" ]]; then
                ls -t "$HOME/.npm/_npx/" 2>/dev/null | tail -n +6 | while read d; do
                    rm -rf "$HOME/.npm/_npx/$d" 2>/dev/null
                done
            fi
        fi
    fi

    # bun install cache (regenera on demand)
    if [[ -d "$HOME/.bun/install/cache" ]]; then
        local size=$(du -sh "$HOME/.bun/install/cache" 2>/dev/null | cut -f1)
        log "  bun install cache: $size"
        if [[ "$DRY_RUN" = "0" ]]; then
            rm -rf "$HOME/.bun/install/cache/"* 2>/dev/null
        fi
    fi

    # pnpm store prune (inteligente, mantém packages ativos)
    log "  pnpm store prune"
    if [[ "$DRY_RUN" = "0" ]]; then
        pnpm store prune 2>&1 | tail -3 | tee -a "$LOG"
    fi

    # pip cache purge
    if [[ -d "$HOME/.cache/pip" ]]; then
        local size=$(du -sh "$HOME/.cache/pip" 2>/dev/null | cut -f1)
        log "  pip cache: $size"
        if [[ "$DRY_RUN" = "0" ]]; then
            pip cache purge 2>&1 | tail -2 | tee -a "$LOG"
        fi
    fi
}

# === FASE 3: Podman dangling (idempotente, seguro) ===
cleanup_podman() {
    log "FASE 3 — Podman dangling (somente unused)"

    # NÃO usar -a flag: prune -a remove imagens com nome. Só dangling
    if [[ "$DRY_RUN" = "1" ]]; then
        local count=$(podman images -f dangling=true -q 2>/dev/null | wc -l)
        log "  DRY podman image prune: $count dangling images"
    else
        podman image prune -f 2>&1 | tail -3 | tee -a "$LOG"
        podman volume prune -f 2>&1 | tail -3 | tee -a "$LOG"
    fi
}

# === FASE 4: Logs locais ~/.logs (trim + retenção 15d) ===
cleanup_logs() {
    log "FASE 4 — ~/.logs trim + retenção 15d"

    # Trim arquivos .log > 1MB com 3 rotações
    for f in "$HOME"/.logs/*.log; do
        [[ ! -f "$f" ]] && continue
        local size=$(stat -c %s "$f" 2>/dev/null)
        # 1MB = 1048576 bytes
        if (( size > 1048576 )); then
            log "  TRIM $(du -h "$f" | cut -f1)  $f"
            if [[ "$DRY_RUN" = "0" ]]; then
                mv "$f" "$f.1" 2>/dev/null
                # Append latest 100KB to keep tail
                tail -c 102400 "$f.1" > "$f" 2>/dev/null || true
            fi
        fi
    done

    # Retenção local: arquivos de log antigos (>15d) saem do host.
    # O backup diário já copia ~/.logs para GDrive. Aqui só remove local antigo.
    if [[ -d "$HOME/.logs" ]]; then
        while IFS= read -r -d '' old; do
            if [[ "$DRY_RUN" = "1" ]]; then
                log "  DRY  old-log>15d $old"
            else
                rm -f "$old" && log "  DELETE old-log>15d $old"
            fi
        done < <(find "$HOME/.logs" -type f -mtime +15 \( -name '*.log' -o -name '*.log.*' -o -name '*.bak' \) -print0 2>/dev/null)
    fi
}

# === FASE 5: Journal vacuum (defesa em profundidade) ===
cleanup_journal() {
    log "FASE 5 — Journal systemd"
    local usage=$(journalctl --disk-usage 2>/dev/null | grep -oE "[0-9.]+[MGK]" | head -1)
    log "  Journal: $usage"
    # Journal já tem SystemMaxUse=500M, mas se crescer entre configs
    if [[ "$DRY_RUN" = "0" ]]; then
        sudo journalctl --vacuum-size=400M 2>&1 | tail -3 | tee -a "$LOG" || \
            log "  (sudo falhou, journal não vacumado)"
    fi
}

# === EXECUTAR TODAS ===
cleanup_tmp
cleanup_caches
cleanup_podman
cleanup_logs
cleanup_journal

# === FINAL ===
log "Disco DEPOIS: $(df -h / | tail -1 | awk '{print $4}') livre"
log "=========================================="
log "CLEANUP SRV-1 FIM"
log "=========================================="
