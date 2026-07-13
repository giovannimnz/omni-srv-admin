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
    if [[ -f "${candidate}/modules/srv1-ops/configs/resource-governor.env" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! OMNI_SRV_ADMIN_DEFAULT="$(resolve_repo)"; then
  OMNI_SRV_ADMIN_DEFAULT="${HOME}/GitHub/omni-srv-admin"
fi
repo="${OMNI_SRV_ADMIN_DEFAULT}"
cmd_name="$(basename "$0")"
wrapper_path="$(readlink -f "$0" 2>/dev/null || printf '%s\n' "$0")"
CPU_PROFILE_KEY="RG_PROFILE_BUILDS_CPU_TOTAL_PCT"
CPU_TOTAL_PCT="20"
CPU_TOTAL_PCT_FALLBACK="20"
CPU_QUOTA="20%"

user_systemd_env() {
  local runtime_dir="/run/user/$(id -u)"
  env \
    XDG_RUNTIME_DIR="$runtime_dir" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime_dir}/bus" \
    "$@"
}

load_build_cpu_quota() {
  local cfg="$1"
  local key="$2"
  local line value
  [[ -f "$cfg" ]] || return 1
  while IFS='=' read -r key_raw value_raw; do
    key_raw="${key_raw%%[[:space:]]#*}"
    key_raw="$(printf '%s' "$key_raw" | xargs)"
    value="$(printf '%s' "$value_raw" | xargs)"
    if [[ "$key_raw" == "$key" && -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
  done < "$cfg"
  return 1
}

load_host_cpu_quota() {
  local repo_cfg rt_cfg val cpus
  repo_cfg="${OMNI_SRV_ADMIN_DEFAULT}/modules/srv1-ops/configs/resource-governor.env"
  rt_cfg="${HOME}/.config/omni/resource-governor.runtime.env"

  if val="$(load_build_cpu_quota "$rt_cfg" "${CPU_PROFILE_KEY}")"; then
    CPU_TOTAL_PCT="$val"
  elif val="$(load_build_cpu_quota "$repo_cfg" "${CPU_PROFILE_KEY}")"; then
    CPU_TOTAL_PCT="$val"
  elif val="$(load_build_cpu_quota "$rt_cfg" "RG_PROFILE_BUILDS_CPU_QUOTA")"; then
    CPU_QUOTA="$val"
  elif val="$(load_build_cpu_quota "$repo_cfg" "RG_PROFILE_BUILDS_CPU_QUOTA")"; then
    CPU_QUOTA="$val"
  else
    CPU_QUOTA="$CPU_TOTAL_PCT_FALLBACK%"
  fi

  if [[ -z "${CPU_TOTAL_PCT// /}" ]]; then
    return
  fi

  CPU_TOTAL_PCT="${CPU_TOTAL_PCT%\%}"
  if [[ ! "$CPU_TOTAL_PCT" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
    CPU_TOTAL_PCT=""
    return
  fi

  CPU_QUOTA=""
  cpus="$(nproc --all 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"
  CPU_QUOTA="$(LC_ALL=C awk -v pct="${CPU_TOTAL_PCT}" -v cpus="$cpus" 'BEGIN {printf "%d", pct * cpus}')"
}

find_real_command() {
  local name="$1"
  local dir candidate resolved
  IFS=':' read -r -a dirs <<< "${PATH:-}"
  for dir in "${dirs[@]}"; do
    [[ -n "$dir" ]] || continue
    candidate="${dir}/${name}"
    [[ -x "$candidate" ]] || continue
    resolved="$(readlink -f "$candidate" 2>/dev/null || printf '%s\n' "$candidate")"
    [[ "$resolved" != "$wrapper_path" ]] || continue
    case "$resolved" in
      */modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh) continue ;;
    esac
    printf '%s\n' "$candidate"
    return 0
  done

  # Non-interactive desktop/AppImage sessions do not always inherit
  # ~/.cargo/bin even though rustup installed its cargo/rustc shims there.
  # Resolve that canonical user toolchain location explicitly so the guard
  # does not turn a valid Rust installation into a command-not-found error.
  case "$name" in
    cargo|rustc)
      candidate="${HOME}/.cargo/bin/${name}"
      if [[ -x "$candidate" ]]; then
        resolved="$(readlink -f "$candidate" 2>/dev/null || printf '%s\n' "$candidate")"
        if [[ "$resolved" != "$wrapper_path" ]]; then
          printf '%s\n' "$candidate"
          return 0
        fi
      fi
      ;;
  esac
  return 1
}

is_build_command() {
  local name="$1"
  shift || true
  case "$name" in
    make|ninja)
      return 0
      ;;
    npm|pnpm|yarn|bun)
      case "${1:-}" in
        run)
          case "${2:-}" in
            build|compile|bundle|dist|package|release|export|generate) return 0 ;;
          esac
          ;;
        build|install|ci|rebuild|i)
          return 0
          ;;
      esac
      ;;
    npx)
      case "${1:-}" in
        next|vite|webpack|turbo|nx|tsc|tsup|rollup|esbuild) return 0 ;;
      esac
      ;;
    cargo)
      case "${1:-}" in
        build|install|test|bench|run) return 0 ;;
      esac
      ;;
    rustc|gcc|g++|clang|cc|c++|ld|node-gyp)
      return 0
      ;;
    go)
      case "${1:-}" in
        build|install|test|run|generate) return 0 ;;
      esac
      ;;
    podman|docker)
      case "${1:-}" in
        build)
          return 0
          ;;
        buildx)
          [[ "${2:-}" == "build" ]] && return 0
          ;;
      esac
      ;;
    cmake)
      [[ "${1:-}" == "--build" ]] && return 0
      ;;
    next|vite|webpack|turbo|nx|tsc|tsup|rollup|esbuild)
      return 0
      ;;
  esac
  return 1
}

real_cmd="$(find_real_command "$cmd_name" || true)"
if [[ -z "$real_cmd" ]]; then
  printf 'build-cpu-guard: real command not found for %s\n' "$cmd_name" >&2
  exit 127
fi

inside_build_cgroup() {
  local cgroup_file="/proc/$$/cgroup"
  [[ -r "$cgroup_file" ]] && grep -q 'omni-builds' "$cgroup_file"
}

if ! is_build_command "$cmd_name" "$@"; then
  exec "$real_cmd" "$@"
fi

# The marker is inherited by nested wrappers, but it is not authority by
# itself.  Only bypass routing when this process is demonstrably contained.
if [[ "${OMNI_BUILD_CPU_GUARD_ACTIVE:-0}" == "1" ]] && inside_build_cgroup; then
  exec "$real_cmd" "$@"
fi

export OMNI_BUILD_CPU_GUARD_ACTIVE=1
if command -v python3 >/dev/null 2>&1 && [[ -d "${repo}/cli" ]]; then
  user_systemd_env env PYTHONPATH="${repo}/cli${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m omni srv1-ops resources run builds -- "$real_cmd" "$@"
  exit $?
fi

# Fallback: preserve global build cap even sem omni CLI instalado.
load_host_cpu_quota
if [[ -z "$CPU_QUOTA" ]]; then
  CPU_QUOTA="$CPU_TOTAL_PCT_FALLBACK"
fi
CPU_QUOTA="${CPU_QUOTA%\%}"
if [[ ! "$CPU_QUOTA" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  CPU_QUOTA="$CPU_TOTAL_PCT_FALLBACK"
fi
if user_systemd_env systemctl --user start omni-builds.slice >/dev/null 2>&1; then
  exec env \
    XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
    systemd-run --user --scope \
    --same-dir \
    --slice=omni-builds.slice \
    -p CPUWeight=100 \
    -p CPUQuota="${CPU_QUOTA}%" \
    -p MemoryMax=12G \
    "$real_cmd" "$@"
fi

exec env \
  XDG_RUNTIME_DIR="/run/user/$(id -u)" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" \
  systemd-run --user --scope \
  --same-dir \
  -p CPUQuota="${CPU_QUOTA}%" \
  -p CPUWeight=100 \
  -p MemoryMax=12G \
  "$real_cmd" "$@"
