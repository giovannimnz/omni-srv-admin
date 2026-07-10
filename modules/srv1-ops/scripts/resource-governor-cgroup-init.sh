#!/usr/bin/env bash
# resource-governor-cgroup-init.sh
# Workaround: systemd 249 user instance may ignore some cgroup props on files.
# To stay consistent, we also write limits directly into discovered cgroup paths.
#
# Roda no boot (via systemd user service) e no start/restart de cada slice.
#
# Source: https://github.com/giovannimnz/omni-srv-admin
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

if ! OMNI_SRV_ADMIN="$(resolve_repo)"; then
  OMNI_SRV_ADMIN="${HOME}/GitHub/omni-srv-admin"
fi

CONFIG="${OMNI_SRV_ADMIN}/modules/srv1-ops/configs/resource-governor.env"
RUNTIME_OVERRIDE="${HOME}/.config/omni/resource-governor.runtime.env"

# --- resolve config: base + runtime override ---
declare -A CFG
load_env() {
    local path="$1"
    [[ -f "$path" ]] || return 0
    while IFS='=' read -r key value; do
        key="${key%%[[:space:]]#*}"
        key="$(echo "$key" | xargs)"
        value="$(echo "$value" | xargs)"
        [[ -z "$key" || "$key" == \#* ]] && continue
        CFG["$key"]="$value"
    done < "$path"
}
load_env "$CONFIG"
load_env "$RUNTIME_OVERRIDE"

quote() { echo "$@" | sed "s/^['\"]//;s/['\"]$//"; }

write_cg() {
    local path="$1"
    shift
    if [[ $EUID -eq 0 ]]; then
        printf '%s\n' "$*" > "$path"
    else
        printf '%s\n' "$*" | sudo -n tee "$path" >/dev/null
    fi
}

get() {
    local key="$1" default="$2"
    local val="${CFG[$key]:-$default}"
    quote "$val"
}

cpu_quota_to_cg() {
    local pct="$1"
    pct="${pct%\%}"
    local period=100000
    local quota
    quota=$(LC_ALL=C awk "BEGIN{printf \"%d\", $pct * $period / 100}")
    echo "${quota} ${period}"
}

profile_cpu_quota_to_cg() {
    local key="$1"
    local cpu_total_pct
    cpu_total_pct="$(get "RG_PROFILE_${key}_CPU_TOTAL_PCT" "")"
    if [[ -n "$cpu_total_pct" ]]; then
        local cpus
        cpus="$(nproc --all 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"
        local period=100000
        local quota
        quota=$(LC_ALL=C awk "BEGIN{printf \"%d\", $cpu_total_pct * $cpus * $period / 100}")
        echo "${quota} ${period}"
        return
    fi
    cpu_quota_to_cg "$(get "RG_PROFILE_${key}_CPU_QUOTA" "100%")"
}

io_bw_to_cg() {
    local bw="$1"
    bw="${bw%M}"
    bw="${bw%m}"
    echo "${bw}000000"
}

mem_to_cg() {
    local mem="$1"
    [[ -z "$mem" || "$mem" == "max" ]] && { echo "max"; return; }
    local unit="${mem: -1}"
    local value="$mem"
    case "$unit" in
        K|k|M|m|G|g|T|t)
            value="${mem%?}"
            ;;
        *)
            unit=""
            ;;
    esac
    case "$unit" in
        K|k) LC_ALL=C awk "BEGIN{printf \"%d\", $value * 1024}" ;;
        M|m) LC_ALL=C awk "BEGIN{printf \"%d\", $value * 1024 * 1024}" ;;
        G|g) LC_ALL=C awk "BEGIN{printf \"%d\", $value * 1024 * 1024 * 1024}" ;;
        T|t) LC_ALL=C awk "BEGIN{printf \"%d\", $value * 1024 * 1024 * 1024 * 1024}" ;;
        *) echo "$value" ;;
    esac
}

ensure_cg_path() {
    local path="$1"
    local owner group
    owner="$(id -un)"
    group="$(id -gn)"
    if [[ -d "$path" ]]; then
        return
    fi
    mkdir -p "$path" >/dev/null 2>&1 || sudo -n mkdir -p "$path"
    chown "$owner:$group" "$path" >/dev/null 2>&1 || sudo -n chown "$owner:$group" "$path"
}

write_limits() {
    local cg_path="$1"
    local key="$2"

    [[ -d "$cg_path" ]] || return

    local root_dev dev_major_minor dev_major dev_minor
    local rbps wbps cg_cpu

    for ctl in cpu io memory pids; do
        cur=$(cat "$cg_path/cgroup.subtree_control" 2>/dev/null || echo "")
        if ! echo "$cur" | grep -q "$ctl"; then
            write_cg "$cg_path/cgroup.subtree_control" "+$ctl" 2>/dev/null || true
        fi
    done

    cg_cpu=$(profile_cpu_quota_to_cg "$key")
    write_cg "$cg_path/cpu.max" "$cg_cpu" 2>/dev/null || true

    cpu_weight=$(get "RG_PROFILE_${key}_CPU_WEIGHT" "")
    [[ -n "$cpu_weight" ]] && write_cg "$cg_path/cpu.weight" "$cpu_weight" 2>/dev/null || true

    root_dev=$(get "RG_ROOT_DEVICE" "/dev/sda")
    io_read=$(get "RG_PROFILE_${key}_IO_READ_BW" "")
    io_write=$(get "RG_PROFILE_${key}_IO_WRITE_BW" "")
    if [[ -n "$io_read" || -n "$io_write" ]]; then
        dev_major_minor=$(stat -c '%t %T' "$root_dev" 2>/dev/null || echo "8 0")
        dev_major=$((0x${dev_major_minor% *}))
        dev_minor=$((0x${dev_major_minor#* }))
        rbps=$(io_bw_to_cg "${io_read:-0}")
        wbps=$(io_bw_to_cg "${io_write:-0}")
        write_cg "$cg_path/io.max" "${dev_major}:${dev_minor} rbps=${rbps} wbps=${wbps}" 2>/dev/null || true
    fi

    io_weight=$(get "RG_PROFILE_${key}_IO_WEIGHT" "")
    [[ -n "$io_weight" ]] && write_cg "$cg_path/io.weight" "$io_weight" 2>/dev/null || true

    memory_high=$(get "RG_PROFILE_${key}_MEMORY_HIGH" "")
    [[ -n "$memory_high" ]] && write_cg "$cg_path/memory.high" "$(mem_to_cg "$memory_high")" 2>/dev/null || true

    memory_max=$(get "RG_PROFILE_${key}_MEMORY_MAX" "")
    [[ -n "$memory_max" ]] && write_cg "$cg_path/memory.max" "$(mem_to_cg "$memory_max")" 2>/dev/null || true

    memory_swap_max=$(get "RG_PROFILE_${key}_MEMORY_SWAP_MAX" "")
    if [[ -n "$memory_swap_max" && -f "$cg_path/memory.swap.max" ]]; then
        write_cg "$cg_path/memory.swap.max" "$(mem_to_cg "$memory_swap_max")" 2>/dev/null || true
    fi
}

USER_ID=$(id -u)
USER_CGROUP_BASE="/sys/fs/cgroup/user.slice/user-${USER_ID}.slice"
SERVICE_CGROUP_BASE="/sys/fs/cgroup/user.slice/user-${USER_ID}.slice/user@${USER_ID}.service/omni.slice"

# --- 1. Ensure known omni ancestors have subtree controllers enabled.
for base in "$USER_CGROUP_BASE" "$SERVICE_CGROUP_BASE"; do
    [[ -d "$base" ]] || continue
    cur=$(cat "$base/cgroup.subtree_control" 2>/dev/null || echo "")
    for ctl in cpu io memory pids; do
        if ! echo "$cur" | grep -q "$ctl"; then
            write_cg "$base/cgroup.subtree_control" "+$ctl" 2>/dev/null || true
        fi
    done
done

# --- 2. Per-profile: write limits to discovered paths.
declare -A PROFILES
PROFILES["builds"]="BUILDS"
PROFILES["interactive"]="INTERACTIVE"
PROFILES["transfers"]="TRANSFERS"

for profile in builds interactive transfers; do
    key="${PROFILES[$profile]}"
    slice="omni-${profile}.slice"

    # systemd-managed path
    if systemctl --user start "$slice" 2>/dev/null; then
        :
    fi

    service_path="${SERVICE_CGROUP_BASE}/${slice}"
    plain_path="${USER_CGROUP_BASE}/omni-${profile}"
    ensure_cg_path "$plain_path"
    for path in "$plain_path" "$service_path"; do
        write_limits "$path" "$key"
    done
done

echo "cgroup-init: $(date -Isec) completou"
