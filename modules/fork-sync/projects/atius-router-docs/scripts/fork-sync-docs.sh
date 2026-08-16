#!/usr/bin/env bash
# fork-sync-docs.sh — Wrapper principal do projeto atius-router-docs.
#
# Chamado pelo cron diário (0 8 * * *). Pode também ser rodado
# manualmente:
#   $0 /home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs [--rebuild] [--deploy]
#
# O que faz:
#   1. Detecta novo release do upstream QuantumNous/new-api-docs-v1
#   2. Atualiza o worktree Git do fork
#   3. Aplica merge upstream (com protected_paths preservados)
#   4. Roda post-merge.sh (rebrand Atius + Dockerfile + logo swap)
#   5. Copia docs PT-BR (content/docs/pt/) para o repo
#   6. Build local do Next.js
#   7. Restart do atius-router-docs.service
#   8. Verifica /en/ local retorna 200
#
# Outputs:
#   - Log: /home/ubuntu/fork-sync/logs/sync-atius-router-docs-YYYYMMDD.log
#   - GitHub release: v{upstream_version}-rf{N}

set -euo pipefail

# === Args ===
REPO_PATH=""
REBUILD=false
DEPLOY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild) REBUILD=true ;;
    --deploy) DEPLOY=true ;;
    *)
      if [ -z "$REPO_PATH" ]; then
        REPO_PATH="$1"
      fi
      ;;
  esac
  shift
done

REPO_PATH="${REPO_PATH:-/home/ubuntu/GitHub/containers/router-ai-atius/docs/atius-router-docs}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PROJECT="atius-router-docs"
SYNC_YAML="$SOURCE_DIR/projects/$PROJECT/sync.yaml"
LOG_DIR="$SOURCE_DIR/logs"
DATE=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/sync-${PROJECT}-${DATE}.log"
RUNTIME_INSTALLER="$SOURCE_DIR/projects/$PROJECT/scripts/install-runtime.sh"

mkdir -p "$LOG_DIR" "$(dirname "$REPO_PATH")"

log() {
  local level="${1:-INFO}"
  shift
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
  echo "$msg" | tee -a "$LOG_FILE"
}

# === 1. Load config ===
log "INFO" "Starting $PROJECT sync (rebuild=$REBUILD deploy=$DEPLOY)"
log "INFO" "Repo: $REPO_PATH"
log "INFO" "Log: $LOG_FILE"

UPSTREAM=$(grep '^upstream:' "$SYNC_YAML" | sed 's/upstream: *//')
UPSTREAM_BRANCH=$(grep '^upstream_branch:' "$SYNC_YAML" | sed 's/upstream_branch: *//')
ORIGIN_BRANCH=$(grep '^origin_branch:' "$SYNC_YAML" | sed 's/origin_branch: *//')

log "INFO" "Upstream: $UPSTREAM (branch: $UPSTREAM_BRANCH)"
log "INFO" "Origin: $ORIGIN_BRANCH"

# === 2. Clone or update the repo ===
if [ ! -d "$REPO_PATH/.git" ]; then
  log "ERROR" "Canonical docs worktree missing: $REPO_PATH"
  log "ERROR" "Clone https://github.com/giovannimnz/new-api-docs-v1 there before syncing."
  exit 1
fi

# The docs unit used to be static, so it remained dead after a reboot or an
# operator stop. Reconcile and enable the canonical user unit on every sync,
# including no-release runs, before deciding whether the upstream needs work.
"$RUNTIME_INSTALLER" 2>&1 | tee -a "$LOG_FILE"

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

# === 4. Clone fresh from upstream (if repo doesn't exist) ===
if [ ! -d "$REPO_PATH/.git" ]; then
  log "INFO" "Cloning fresh from upstream $UPSTREAM..."
  git clone --depth=1 --branch="$UPSTREAM_BRANCH" "$UPSTREAM" "$REPO_PATH"
  cd "$REPO_PATH"
  # Add our fork as origin
  ORIGIN_URL=$(grep '^origin:' "$SYNC_YAML" 2>/dev/null | sed 's/origin: *//' || true)
  if [ -n "$ORIGIN_URL" ]; then
    git remote add origin "$ORIGIN_URL"
  fi
fi

# === 5. Merge upstream ===
log "INFO" "Running merge-upstream.sh..."
"$SOURCE_DIR/bin/merge-upstream.sh" "$PROJECT" "$REPO_PATH" "$NEW_VERSION" 2>&1 | tee -a "$LOG_FILE"

# === 6. Copy Atius PT-BR docs into the repo ===
log "INFO" "Copying PT-BR docs from $SOURCE_DIR/projects/$PROJECT/pt-content/..."
PT_SRC="$SOURCE_DIR/projects/$PROJECT/pt-content"
PT_DST="$REPO_PATH/content/docs/pt"
if [ -d "$PT_SRC" ]; then
  mkdir -p "$PT_DST"
  # Use rsync if available (preserves git), else cp -r
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

# === 7. Build the docs image ===
if [ "$REBUILD" = true ] || [ "$DEPLOY" = true ] || [ "$NEW_VERSION" != "$LAST_SYNC" ]; then
  log "INFO" "Building docs image (podman build)..."
  if [ -d "$REPO_PATH" ]; then
    # Build with a tag
    IMAGE_TAG="router-ai-atius-docs:rf$(date +%s)"
    cd "$REPO_PATH"
    podman build -t "$IMAGE_TAG" -t router-ai-atius-docs:local . 2>&1 | tee -a "$LOG_FILE" | tail -5
    log "INFO" "Image built: $IMAGE_TAG"
  fi
fi

# === 8. Deploy (restart container) ===
if [ "$DEPLOY" = true ] || [ "$NEW_VERSION" != "$LAST_SYNC" ]; then
  log "INFO" "Restarting atius-router-docs.service..."
  systemctl --user daemon-reload 2>&1 | tee -a "$LOG_FILE" || true
  systemctl --user restart atius-router-docs.service 2>&1 | tee -a "$LOG_FILE"
  # Wait for healthy
  for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:3003/en/ >/dev/null 2>&1; then
      log "INFO" "Docs service is healthy (got 200 from local /en/)"
      break
    fi
    log "INFO" "Waiting for docs service... ($i/30)"
    sleep 2
  done
fi

# === 9. Save last_sync version ===
"$SOURCE_DIR/lib/github.sh" save_last_sync "$PROJECT" "$NEW_VERSION"
log "INFO" "Saved last_sync: $NEW_VERSION"

# === 10. Notify (optional, via Telegram) ===
if [ -f "$SOURCE_DIR/bin/notify-telegram.sh" ]; then
  "$SOURCE_DIR/bin/notify-telegram.sh" "$PROJECT" "$NEW_VERSION" "Docs site updated to upstream $NEW_VERSION + Atius rebrand + PT-BR sync" 2>&1 | tee -a "$LOG_FILE" || true
fi

log "INFO" "=== Sync complete ==="
