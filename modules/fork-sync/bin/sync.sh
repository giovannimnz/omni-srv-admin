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
PYTHONPATH="$ROOT/cli${PYTHONPATH:+:$PYTHONPATH}" python3 - "$PROJECT" "$REPO_PATH" "$DRY" "$DEPLOY" <<'PY'
import json
import sys

from fork_sync.core.sync_runner import run_sync

project = sys.argv[1]
repo_path = sys.argv[2] or None
dry_run = sys.argv[3].lower() == "true"
deploy = sys.argv[4].lower() == "true"
result = run_sync(project, repo_path=repo_path, dry_run=dry_run, deploy=deploy)

for key in ("message", "error", "repo", "branch", "upstream_ref"):
    value = result.get(key)
    if value:
        print(f"{key}: {value}")

if result.get("dirty_files"):
    print("dirty_files:")
    for item in result["dirty_files"]:
        print(f"  - {item}")

if result.get("conflict_files"):
    print("conflict_files:")
    for item in result["conflict_files"]:
        print(f"  - {item}")

if result.get("stale_protected_paths"):
    print("stale_protected_paths:")
    for item in result["stale_protected_paths"]:
        print(f"  - {item}")

if result.get("status") != "success":
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(1)
PY
