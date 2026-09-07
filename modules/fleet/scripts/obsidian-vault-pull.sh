#!/usr/bin/env bash
set -euo pipefail

VAULT="${OBSIDIAN_VAULT_REPO:-$HOME/GitHub/obsidian-vault}"
LOCK="${XDG_STATE_HOME:-$HOME/.local/state}/omni/obsidian-vault-pull.lock"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/omni/obsidian-vault-pull.log"
BRANCH="${OBSIDIAN_VAULT_BRANCH:-master}"

mkdir -p "$(dirname "$LOCK")" "$(dirname "$LOG")"
exec 9>"$LOCK"
/usr/bin/flock -n 9 || exit 0

[ -d "$VAULT/.git" ] || {
  printf '%s FAIL vault repo missing: %s\n' "$(date -Is)" "$VAULT" >>"$LOG"
  exit 1
}
cd "$VAULT"

if [ -n "$(git status --porcelain)" ]; then
  printf '%s SKIP dirty vault replica: %s\n' "$(date -Is)" "$VAULT" >>"$LOG"
  exit 0
fi

git fetch --prune origin >>"$LOG" 2>&1
git merge --ff-only "origin/$BRANCH" >>"$LOG" 2>&1
printf '%s OK %s branch=%s\n' "$(date -Is)" "$(git rev-parse --short HEAD)" "$BRANCH" >>"$LOG"
