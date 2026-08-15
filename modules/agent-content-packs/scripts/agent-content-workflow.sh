#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/cli${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="${PYTHON_BIN:-python}"
OMNI=("$PYTHON_BIN" -m omni)

PACKS=(hermes-skills codex-skills shared-agent-content)
HERMES_TARGETS=(windows-hermes-default wsl-hermes-default srv1-hermes-default srv2-hermes-default srv3-hermes-default)
CODEX_TARGETS=(windows-codex-default wsl-codex-default srv1-codex-default srv2-codex-default srv3-codex-default)
SHARED_TARGETS=(windows-hermes-default wsl-hermes-default windows-codex-default wsl-codex-default srv1-hermes-default srv1-codex-default srv2-hermes-default srv2-codex-default srv3-hermes-default srv3-codex-default)

usage() {
  cat <<'EOF'
Usage:
  agent-content-workflow.sh validate
  agent-content-workflow.sh dry-run-local
  agent-content-workflow.sh dry-run-fleet
  agent-content-workflow.sh dry-run-all
  agent-content-workflow.sh apply-local [--yes-sync]
  agent-content-workflow.sh apply-fleet [--yes-sync]
  agent-content-workflow.sh apply-all [--yes-sync]

Notes:
- validate: validates all pack manifests
- dry-run-*: never mutates targets
- apply-*: requires --yes-sync
- apply remains manual by design; use dry-run before apply
EOF
}

require_yes_sync() {
  local confirm="${1:-}"
  if [[ "$confirm" != "--yes-sync" ]]; then
    echo "Refusing apply without --yes-sync" >&2
    exit 2
  fi
}

run_validate() {
  local pack
  for pack in "${PACKS[@]}"; do
    echo "=== validate $pack ==="
    "${OMNI[@]}" agent-content validate-pack --pack "$pack"
  done
}

run_matrix() {
  local mode="$1"
  shift
  local targets=("$@")
  local t
  local pack
  for t in "${targets[@]}"; do
    echo "=== target $t ==="
    for pack in hermes-skills codex-skills shared-agent-content; do
      case "$pack" in
        hermes-skills)
          [[ " ${HERMES_TARGETS[*]} " == *" $t "* ]] || continue
          ;;
        codex-skills)
          [[ " ${CODEX_TARGETS[*]} " == *" $t "* ]] || continue
          ;;
        shared-agent-content)
          [[ " ${SHARED_TARGETS[*]} " == *" $t "* ]] || continue
          ;;
      esac
      echo "--- $mode $pack on $t ---"
      if [[ "$mode" == "dry-run" ]]; then
        "${OMNI[@]}" agent-content sync --pack "$pack" --target "$t" --dry-run --json-output
      else
        "${OMNI[@]}" agent-content sync --pack "$pack" --target "$t" --apply --json-output
      fi
    done
  done
}

LOCAL_TARGETS=(windows-hermes-default wsl-hermes-default windows-codex-default wsl-codex-default)
FLEET_TARGETS=(srv1-hermes-default srv1-codex-default srv2-hermes-default srv2-codex-default srv3-hermes-default srv3-codex-default)
ALL_TARGETS=("${LOCAL_TARGETS[@]}" "${FLEET_TARGETS[@]}")

main() {
  local cmd="${1:-}"
  case "$cmd" in
    validate)
      run_validate
      ;;
    dry-run-local)
      run_validate
      run_matrix dry-run "${LOCAL_TARGETS[@]}"
      ;;
    dry-run-fleet)
      run_validate
      run_matrix dry-run "${FLEET_TARGETS[@]}"
      ;;
    dry-run-all)
      run_validate
      run_matrix dry-run "${ALL_TARGETS[@]}"
      ;;
    apply-local)
      require_yes_sync "${2:-}"
      run_validate
      run_matrix dry-run "${LOCAL_TARGETS[@]}"
      run_matrix apply "${LOCAL_TARGETS[@]}"
      ;;
    apply-fleet)
      require_yes_sync "${2:-}"
      run_validate
      run_matrix dry-run "${FLEET_TARGETS[@]}"
      run_matrix apply "${FLEET_TARGETS[@]}"
      ;;
    apply-all)
      require_yes_sync "${2:-}"
      run_validate
      run_matrix dry-run "${ALL_TARGETS[@]}"
      run_matrix apply "${ALL_TARGETS[@]}"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
