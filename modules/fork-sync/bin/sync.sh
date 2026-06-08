#!/usr/bin/env bash
set -euo pipefail
ROOT="${FORK_SYNC_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT="${1:?project required}"
REPO_PATH="${2:-}"
DRY=false
DEPLOY=false
shift 2 || true
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=true ;;
    --deploy) DEPLOY=true ;;
  esac
done
CFG="$ROOT/projects/$PROJECT/sync.yaml"
[ -f "$CFG" ] || { echo "sync.yaml not found: $CFG"; exit 1; }
readarray -t CFGV < <(python3 - <<'PY' "$CFG"
import sys, yaml
cfg=yaml.safe_load(open(sys.argv[1]))
print(cfg.get('fork',''))
print(cfg.get('upstream',''))
print(cfg.get('upstream_branch','main'))
print(str(cfg.get('auto_push', False)).lower())
print('1' if (cfg.get('post_sync') or {}).get('enabled') else '0')
print((cfg.get('post_sync') or {}).get('script',''))
PY
)
FORK_PATH="${CFGV[0]}"
UPSTREAM_URL="${CFGV[1]}"
UPSTREAM_BRANCH="${CFGV[2]}"
AUTO_PUSH="${CFGV[3]}"
POST_SYNC_ENABLED="${CFGV[4]}"
POST_SYNC_SCRIPT="${CFGV[5]}"
[ -n "$REPO_PATH" ] || REPO_PATH="$FORK_PATH"
[ -d "$REPO_PATH/.git" ] || { echo "repo is not a git repository: $REPO_PATH"; exit 1; }
cd "$REPO_PATH"
if git remote | grep -qx upstream; then git remote set-url upstream "$UPSTREAM_URL"; else git remote add upstream "$UPSTREAM_URL"; fi

git fetch upstream "$UPSTREAM_BRANCH" >/dev/null 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "upstream/$UPSTREAM_BRANCH")
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "Already up to date"
  exit 0
fi
if [ "$DRY" = true ]; then
  echo "Would merge upstream/$UPSTREAM_BRANCH into $(git rev-parse --abbrev-ref HEAD)"
  exit 0
fi
git merge --no-edit --no-ff "upstream/$UPSTREAM_BRANCH"
if [ "$POST_SYNC_ENABLED" = "1" ] && [ -n "$POST_SYNC_SCRIPT" ] && [ -x "$POST_SYNC_SCRIPT" -o -f "$POST_SYNC_SCRIPT" ]; then
  bash "$POST_SYNC_SCRIPT"
fi
if [ "$AUTO_PUSH" = "true" ] && git remote | grep -qx origin; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  git push origin "$BRANCH" || true
fi
if [ "$DEPLOY" = true ]; then
  echo "Deploy flag ignored by minimal sync wrapper"
fi
