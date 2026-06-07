#!/usr/bin/env bash
# fork-sync-docs.sh — Wrapper principal do projeto atius-router-docs.
#
# Chamado pelo cron diário (0 8 * * *). Pode também ser rodado
# manualmente:
#   $0 [--rebuild] [--deploy]
#
# O que faz:
#   1. Detecta novo release do upstream QuantumNous/new-api-docs-v1
#   2. Entra no submodule docs/atius-router-docs/ dentro de router-ai-atius
#   3. Puxa upstream e aplica merge (com protected_paths preservados)
#   4. Roda post-merge.sh (rebrand Atius + logo swap)
#   5. Copia docs PT-BR (content/docs/pt/) para o submodule
#   6. Build (bun run build)
#   7. Restart do systemd user service atius-router-docs.service
#   8. Verifica /pt/ retorna 200
#
# Outputs:
#   - Log: /home/ubuntu/fork-sync/logs/sync-atius-router-docs-YYYYMMDD.log
#
# NOTA (Phase 09): O target operacional agora é o submodule dentro
# de router-ai-atius/docs/atius-router-docs/. O checkout standalone
# legado /home/ubuntu/docker/Atius/atius-router-docs permanece
# apenas como rollback source até cutover final validado.

set -euo pipefail

# === Args ===
REBUILD=false
DEPLOY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=true ;;
    --deploy) DEPLOY=true ;;
    *)
      echo "Usage: $0 [--rebuild] [--deploy]"
      exit 1
      ;;
  esac
  shift
done

ROUTER_REPO="/home/ubuntu/docker/Atius/router-ai-atius"
REPO_PATH="$ROUTER_REPO/docs/atius-router-docs"
SOURCE_DIR="/home/ubuntu/fork-sync"
PROJECT="atius-router-docs"
SYNC_YAML="$SOURCE_DIR/projects/$PROJECT/sync.yaml"
LOG_DIR="$SOURCE_DIR/logs"
DATE=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/sync-${PROJECT}-${DATE}.log"

mkdir -p "$LOG_DIR"

log() {
  local level="${1:-INFO}"
  shift
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
  echo "$msg" | tee -a "$LOG_FILE"
}

# === 1. Load config ===
log "INFO" "Starting $PROJECT sync (rebuild=$REBUILD deploy=$DEPLOY)"
log "INFO" "Submodule path: $REPO_PATH"
log "INFO" "Log: $LOG_FILE"

UPSTREAM=$(grep '^upstream:' "$SYNC_YAML" | sed 's/upstream: *//')
UPSTREAM_BRANCH=$(grep '^upstream_branch:' "$SYNC_YAML" | sed 's/upstream_branch: *//')

log "INFO" "Upstream: $UPSTREAM (branch: $UPSTREAM_BRANCH)"

# === 2. Ensure submodule is initialized ===
if [ ! -f "$REPO_PATH/package.json" ]; then
  log "INFO" "Initializing submodule at $REPO_PATH..."
  cd "$ROUTER_REPO"
  git submodule update --init --recursive
fi

cd "$REPO_PATH"

# === 3. Detect new release ===
log "INFO" "Checking for new upstream release..."
NEW_VERSION=$("$SOURCE_DIR/bin/detect-release.sh" "$PROJECT" 2>/dev/null | grep '^VERSION=' | cut -d= -f2 || true)
if [ -z "$NEW_VERSION" ]; then
  log "ERROR" "Could not detect latest upstream release (gh CLI or network issue?)"
  exit 1
fi

LAST_SYNC=$("$SOURCE_DIR/lib/github.sh" get_last_sync "$PROJECT" 2>/dev/null || true)
log "INFO" "Last synced: ${LAST_SYNC:-none}, Latest upstream: $NEW_VERSION"

# If no new release AND no --rebuild, skip
if [ "$NEW_VERSION" = "$LAST_SYNC" ] && [ "$REBUILD" = false ]; then
  log "INFO" "No new release. Skipping (use --rebuild to force)."
  exit 0
fi

# === 4. Fetch upstream and merge ===
log "INFO" "Adding upstream remote (if needed)..."
git remote get-url upstream 2>/dev/null || git remote add upstream "$UPSTREAM"
git fetch upstream "$UPSTREAM_BRANCH"

log "INFO" "Running merge-upstream.sh..."
"$SOURCE_DIR/bin/merge-upstream.sh" "$PROJECT" "$REPO_PATH" "$NEW_VERSION" 2>&1 | tee -a "$LOG_FILE"

# === 5. Copy Atius PT-BR docs into the submodule ===
log "INFO" "Copying PT-BR docs from $SOURCE_DIR/projects/$PROJECT/pt-content/..."
PT_SRC="$SOURCE_DIR/projects/$PROJECT/pt-content"
PT_DST="$REPO_PATH/content/docs/pt"
if [ -d "$PT_SRC/docs/pt" ]; then
  mkdir -p "$PT_DST"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$PT_SRC/docs/pt/" "$PT_DST/"
  else
    cp -r "$PT_SRC/docs/pt/." "$PT_DST/"
  fi
  log "INFO" "PT-BR docs synced ($(find "$PT_DST" -type f | wc -l) files)"
  cd "$REPO_PATH"
  git add -A
  git -c user.email="giovannimnz@users.noreply.github.com" \
      -c user.name="Atius Bot" \
      commit -m "feat(i18n): sync PT-BR docs from Atius fork-sync" 2>&1 | tee -a "$LOG_FILE" || true
fi

# === 6. Build ===
if [ "$REBUILD" = true ] || [ "$DEPLOY" = true ] || [ "$NEW_VERSION" != "$LAST_SYNC" ]; then
  log "INFO" "Installing dependencies (bun install)..."
  cd "$REPO_PATH"
  bun install 2>&1 | tee -a "$LOG_FILE" | tail -3

  log "INFO" "Building docs (bun run build)..."
  bun run build 2>&1 | tee -a "$LOG_FILE" | tail -5
  log "INFO" "Build complete"
fi

# === 7. Deploy (restart systemd user service) ===
if [ "$DEPLOY" = true ] || [ "$NEW_VERSION" != "$LAST_SYNC" ]; then
  log "INFO" "Restarting atius-router-docs.service..."
  systemctl --user daemon-reload
  systemctl --user restart atius-router-docs.service
  log "INFO" "Service restarted"

  # Wait for healthy
  for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:3003/pt/ >/dev/null 2>&1; then
      log "INFO" "Service is healthy (got 200 from /pt/)"
      break
    fi
    log "INFO" "Waiting for service... ($i/30)"
    sleep 2
  done
fi

# === 8. Commit submodule reference bump in router-ai-atius ===
if [ "$(cd "$REPO_PATH" && git rev-parse HEAD)" != "$(cd "$ROUTER_REPO" && git submodule status docs/atius-router-docs | awk '{print substr($1,1,length($1)-1)}' 2>/dev/null || true)" ]; then
  log "INFO" "Updating submodule reference in router-ai-atius..."
  cd "$ROUTER_REPO"
  git add docs/atius-router-docs
  git -c user.email="giovannimnz@users.noreply.github.com" \
      -c user.name="Atius Bot" \
      commit -m "chore(docs): bump submodule to $(cd "$REPO_PATH" && git rev-parse --short HEAD)" 2>&1 | tee -a "$LOG_FILE" || true
fi

# === 9. Save last_sync version ===
"$SOURCE_DIR/lib/github.sh" save_last_sync "$PROJECT" "$NEW_VERSION"
log "INFO" "Saved last_sync: $NEW_VERSION"

# === 10. Notify (optional, via Telegram) ===
if [ -f "$SOURCE_DIR/bin/notify-telegram.sh" ]; then
  "$SOURCE_DIR/bin/notify-telegram.sh" "$PROJECT" "$NEW_VERSION" "Docs site updated to upstream $NEW_VERSION + Atius rebrand + PT-BR sync" 2>&1 | tee -a "$LOG_FILE" || true
fi

log "INFO" "=== Sync complete ==="
