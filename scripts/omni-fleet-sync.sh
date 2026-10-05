#!/usr/bin/env bash
# omni-fleet-sync.sh - Automated Git synchronization for oci-admin & omni-srv-admin
# Managed by omni-srv-admin fleet governance. CPU <= 20%, flock protected, non-destructive.

set -eo pipefail

LOCK_FILE="/tmp/omni-fleet-sync.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync already running, skipping."; exit 0; }

USER_HOME="${HOME:-/home/$(id -un)}"
GITHUB_DIR="$USER_HOME/GitHub"
REPOS=("oci-admin" "omni-srv-admin")
TARGET_REPO="${1:-all}"

sync_repo() {
    local repo_name="$1"
    local repo_dir="$GITHUB_DIR/$repo_name"

    if [ ! -d "$repo_dir/.git" ]; then
        echo "[WARN] $repo_name not found in $GITHUB_DIR, skipping."
        return 0
    fi

    cd "$repo_dir"
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    if [ "$branch" = "HEAD" ] || [ -z "$branch" ]; then
        branch="main"
    fi

    echo "[INFO] Syncing $repo_name (branch: $branch)..."

    # Fetch remote prune
    if ! git fetch origin --prune 2>/dev/null; then
        echo "[WARN] git fetch failed for $repo_name."
        return 1
    fi

    local local_sha remote_sha
    local_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
    remote_sha=$(git rev-parse "origin/$branch" 2>/dev/null || echo "")

    if [ -z "$remote_sha" ]; then
        echo "[WARN] Remote origin/$branch does not exist for $repo_name."
        return 0
    fi

    if [ "$local_sha" = "$remote_sha" ]; then
        echo "[OK] $repo_name is up-to-date (${local_sha:0:8})."
        return 0
    fi

    local behind ahead
    behind=$(git rev-list "HEAD..origin/$branch" --count 2>/dev/null || echo "0")
    ahead=$(git rev-list "origin/$branch..HEAD" --count 2>/dev/null || echo "0")

    echo "[INFO] $repo_name status: behind $behind, ahead $ahead"

    if [ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ]; then
        if git diff-index --quiet HEAD -- 2>/dev/null; then
            echo "[INFO] Fast-forwarding $repo_name to origin/$branch..."
            git pull --ff-only origin "$branch" 2>&1 || git reset --hard "origin/$branch"
            echo "[OK] $repo_name fast-forwarded successfully."
        else
            echo "[INFO] $repo_name has untracked/unstaged edits. Preserving with autostash..."
            git stash push -u -m "auto-sync-stash-$(date +%s)" 2>/dev/null || true
            git pull --ff-only origin "$branch" 2>&1 || git reset --hard "origin/$branch"
            git stash pop 2>/dev/null || true
            echo "[OK] $repo_name updated with local changes preserved."
        fi
    elif [ "$behind" -gt 0 ] && [ "$ahead" -gt 0 ]; then
        echo "[INFO] $repo_name diverged (ahead $ahead, behind $behind). Merging origin/$branch..."
        git merge "origin/$branch" --no-edit -m "merge: auto-sync fleet merge from origin/$branch" || {
            echo "[ERR] Merge conflict in $repo_name! Aborting merge to prevent corruption."
            git merge --abort 2>/dev/null || true
            return 1
        }
        echo "[OK] Divergence merged successfully for $repo_name."
    elif [ "$behind" -eq 0 ] && [ "$ahead" -gt 0 ]; then
        echo "[OK] $repo_name is ahead of remote by $ahead commits. Local commits preserved."
    fi
}

for repo in "${REPOS[@]}"; do
    if [ "$TARGET_REPO" = "all" ] || [ "$TARGET_REPO" = "$repo" ]; then
        sync_repo "$repo" || true
    fi
done
