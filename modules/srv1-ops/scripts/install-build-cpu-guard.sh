#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEFAULT_REPO="$(readlink -f "${SCRIPT_DIR}/../../..")"

resolve_repo() {
  local candidates=(
    "${OMNI_SRV_ADMIN:-}"
    "${DEFAULT_REPO}"
    "${HOME}/GitHub/omni-srv-admin"
  )
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if [[ -f "${candidate}/modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! REPO="$(resolve_repo)"; then
  printf 'build-cpu-guard: repo not found, expected modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh\n' >&2
  exit 1
fi
WRAPPER="${REPO}/modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh"
TARGET_DIR="${OMNI_BUILD_GUARD_BIN_DIR:-$HOME/.local/bin}"

commands=(
  npm pnpm yarn bun npx
  cargo rustc gcc g++ clang cc c++ ld
  make ninja cmake go node-gyp
  podman docker
  next vite webpack turbo nx tsc tsup rollup esbuild
)

if [[ ! -x "$WRAPPER" ]]; then
  chmod +x "$WRAPPER"
fi

mkdir -p "$TARGET_DIR"

for cmd in "${commands[@]}"; do
  ln -sfn "$WRAPPER" "${TARGET_DIR}/${cmd}"
done

cat <<EOF
build-cpu-guard installed
target_dir=${TARGET_DIR}
commands=${commands[*]}
rule=build commands run under omni-builds.slice, capped at 20% total host CPU
EOF
