#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/cli${PYTHONPATH:+:$PYTHONPATH}"
if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi
OMNI=("$PYTHON_BIN" -m omni)

PACKS=(hermes-skills codex-skills shared-agent-content)
for pack in "${PACKS[@]}"; do
  echo "=== validate $pack ==="
  "${OMNI[@]}" agent-content validate-pack --pack "$pack"
done
