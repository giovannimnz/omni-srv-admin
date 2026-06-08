#!/usr/bin/env bash
set -euo pipefail
ROOT="${FORK_SYNC_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT="${1:?project required}"
CFG="$ROOT/projects/$PROJECT/sync.yaml"
[ -f "$CFG" ] || { echo "sync.yaml not found: $CFG"; exit 1; }
readarray -t CFGV < <(python3 - <<'PY' "$CFG"
import sys, yaml
cfg=yaml.safe_load(open(sys.argv[1]))
print(cfg.get('fork',''))
print(cfg.get('upstream',''))
print(cfg.get('upstream_branch','main'))
PY
)
REPO_PATH="${CFGV[0]}"
UPSTREAM_URL="${CFGV[1]}"
UPSTREAM_BRANCH="${CFGV[2]}"
[ -d "$REPO_PATH/.git" ] || { echo "repo is not a git repository: $REPO_PATH"; exit 1; }
cd "$REPO_PATH"
if git remote | grep -qx upstream; then git remote set-url upstream "$UPSTREAM_URL"; else git remote add upstream "$UPSTREAM_URL"; fi
git fetch upstream "$UPSTREAM_BRANCH" >/dev/null 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "upstream/$UPSTREAM_BRANCH")
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "NEW_RELEASE=false"
  echo "VERSION=$(git rev-parse --short "$REMOTE")"
else
  echo "NEW_RELEASE=true"
  echo "VERSION=$(git rev-parse --short "$REMOTE")"
fi
