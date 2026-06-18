#!/usr/bin/env bash
# resource-governor-cgroup-init.sh
# Workaround: systemd 249 user instance não aplica CPUQuota / IO*BandwidthMax
# ao cgroup filesystem. Escrevemos diretamente nos arquivos cgroup.
#
# Roda no boot (via systemd user service e no start/restart de cada slice).
#
# Source: https://github.com/giovannimnz/omni-srv-admin
set -euo pipefail

OMNI_SRV_ADMIN="${OMNI_SRV_ADMIN:-/home/ubuntu/GitHub/omni-srv-admin}"
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

# --- helpers ---
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
    # pct pode ser tipo "125%" ou "125"
    local period=100000
    local quota=$(LC_ALL=C awk "BEGIN{printf \"%d\", $pct * $period / 100}")
    echo "${quota} ${period}"
}

io_bw_to_cg() {
    local bw="$1"
    # Remove sufixo M/k/etc
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

USER_ID=$(id -u)
CGROUP_BASE="/sys/fs/cgroup/user.slice/user-${USER_ID}.slice/user@${USER_ID}.service/omni.slice"

# --- 1. Ensure omni.slice has cpu+io in subtree_control ---
OMNI_SLICE="${CGROUP_BASE}"
if [[ -d "$OMNI_SLICE" ]]; then
    current_sub=$(cat "$OMNI_SLICE/cgroup.subtree_control" 2>/dev/null || echo "")
    for ctl in cpu io memory pids; do
        if ! echo "$current_sub" | grep -q "$ctl"; then
            write_cg "$OMNI_SLICE/cgroup.subtree_control" "+$ctl" 2>/dev/null || true
        fi
    done
fi

# --- 2. Per-profile: enable controllers + write limits ---
declare -A PROFILES
PROFILES["builds"]="BUILDS"
PROFILES["interactive"]="INTERACTIVE"
PROFILES["transfers"]="TRANSFERS"

for profile in builds interactive transfers; do
    key="${PROFILES[$profile]}"
    slice="omni-${profile}.slice"
    cg_path="${OMNI_SLICE}/${slice}"

    # Start slice even when its cgroup directory does not exist yet.
    XDG_RUNTIME_DIR=/run/user/${USER_ID} \
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/${USER_ID}/bus}" \
    systemctl --user start "${slice}" 2>/dev/null || true

    # Ensure cgroup dir exists
    [[ -d "$cg_path" ]] || continue

    # Enable controllers for children (so scopes get files)
    for ctl in cpu io memory pids; do
        cur=$(cat "$cg_path/cgroup.subtree_control" 2>/dev/null || echo "")
        if ! echo "$cur" | grep -q "$ctl"; then
            write_cg "$cg_path/cgroup.subtree_control" "+$ctl" 2>/dev/null || true
        fi
    done

    # --- cpu.max ---
    cpu_quota=$(get "RG_PROFILE_${key}_CPU_QUOTA" "100%")
    cg_cpu=$(cpu_quota_to_cg "$cpu_quota")
    write_cg "$cg_path/cpu.max" "$cg_cpu" 2>/dev/null || true

    cpu_weight=$(get "RG_PROFILE_${key}_CPU_WEIGHT" "")
    [[ -n "$cpu_weight" ]] && write_cg "$cg_path/cpu.weight" "$cpu_weight" 2>/dev/null || true

    # --- io.max ---
    root_dev=$(get "RG_ROOT_DEVICE" "/dev/sda")
    dev_major_minor=$(stat -c '%t %T' "$root_dev" 2>/dev/null || echo "8 0")
    dev_major=$((0x${dev_major_minor% *}))
    dev_minor=$((0x${dev_major_minor#* }))

    io_read=$(get "RG_PROFILE_${key}_IO_READ_BW" "")
    io_write=$(get "RG_PROFILE_${key}_IO_WRITE_BW" "")
    if [[ -n "$io_read" || -n "$io_write" ]]; then
        rbps=$(io_bw_to_cg "${io_read:-0}")
        wbps=$(io_bw_to_cg "${io_write:-0}")
        write_cg "$cg_path/io.max" "${dev_major}:${dev_minor} rbps=${rbps} wbps=${wbps}" 2>/dev/null || true
    fi

    io_weight=$(get "RG_PROFILE_${key}_IO_WEIGHT" "")
    [[ -n "$io_weight" ]] && write_cg "$cg_path/io.weight" "$io_weight" 2>/dev/null || true

    # --- memory ---
    memory_high=$(get "RG_PROFILE_${key}_MEMORY_HIGH" "")
    [[ -n "$memory_high" ]] && write_cg "$cg_path/memory.high" "$(mem_to_cg "$memory_high")" 2>/dev/null || true

    memory_max=$(get "RG_PROFILE_${key}_MEMORY_MAX" "")
    [[ -n "$memory_max" ]] && write_cg "$cg_path/memory.max" "$(mem_to_cg "$memory_max")" 2>/dev/null || true

    memory_swap_max=$(get "RG_PROFILE_${key}_MEMORY_SWAP_MAX" "")
    if [[ -n "$memory_swap_max" && -f "$cg_path/memory.swap.max" ]]; then
        write_cg "$cg_path/memory.swap.max" "$(mem_to_cg "$memory_swap_max")" 2>/dev/null || true
    fi
done

echo "cgroup-init: $(date -Isec) completou"
