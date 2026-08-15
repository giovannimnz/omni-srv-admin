#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/cli${PYTHONPATH:+:$PYTHONPATH}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OMNI=("$PYTHON_BIN" -m omni)

PACKS=(hermes-skills codex-skills shared-agent-content)
for pack in "${PACKS[@]}"; do
  echo "=== validate $pack ==="
  "${OMNI[@]}" agent-content validate-pack --pack "$pack"
done
