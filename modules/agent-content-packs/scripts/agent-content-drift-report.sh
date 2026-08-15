#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
REPORT_DIR="$REPO_ROOT/modules/agent-content-packs/reports"
mkdir -p "$REPORT_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$REPORT_DIR/drift-$TS.jsonl"

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/cli${PYTHONPATH:+:$PYTHONPATH}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OMNI=("$PYTHON_BIN" -m omni)

TARGETS=(
  windows-hermes-default
  wsl-hermes-default
  windows-codex-default
  wsl-codex-default
  srv1-hermes-default
  srv1-codex-default
  srv2-hermes-default
  srv2-codex-default
  srv3-hermes-default
  srv3-codex-default
)

packs_for_target() {
  local t="$1"
  case "$t" in
    *hermes*) echo hermes-skills shared-agent-content ;;
    *codex*) echo codex-skills shared-agent-content ;;
    *) echo ;;
  esac
}

for t in "${TARGETS[@]}"; do
  for pack in $(packs_for_target "$t"); do
    echo "running dry-run $pack -> $t" >&2
    "${OMNI[@]}" agent-content sync --pack "$pack" --target "$t" --dry-run --json-output >> "$OUT"
    printf '\n' >> "$OUT"
  done
done

echo "$OUT"
