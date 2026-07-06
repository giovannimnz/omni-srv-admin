#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHONPATH="${repo_root}/modules/fork-sync/cli:${repo_root}/cli:${PYTHONPATH:-}" \
  python3 -m fork_sync.core.release_preflight "$@"
