#!/usr/bin/env bash
set -euo pipefail

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--apply]" >&2
  exit 2
fi

uid="$(id -u)"
legacy_cgroup="/sys/fs/cgroup/atius-build-throttle"
builds_cgroup="/sys/fs/cgroup/user.slice/user-${uid}.slice/user@${uid}.service/omni.slice/omni-builds.slice"
user_cgroup="/sys/fs/cgroup/user.slice/user-${uid}.slice"
systemd_omni_cgroup="${user_cgroup}/user@${uid}.service/omni.slice"
backup_root="${HOME}/.backups/resource-governor-legacy-$(date +%Y%m%d-%H%M%S)"
legacy_files=(
  /usr/local/sbin/atius-build-throttle
  /etc/systemd/system/atius-build-throttle.service
  /etc/systemd/system/atius-build-throttle.timer
)

echo "mode=$([[ $APPLY -eq 1 ]] && echo apply || echo dry-run)"
echo "legacy_timer_enabled=$(systemctl is-enabled atius-build-throttle.timer 2>/dev/null || true)"
echo "legacy_timer_active=$(systemctl is-active atius-build-throttle.timer 2>/dev/null || true)"
echo "legacy_cgroup=$([[ -d $legacy_cgroup ]] && echo present || echo absent)"

if [[ $APPLY -eq 0 ]]; then
  echo "would backup legacy files, disable/remove the scanner, migrate surviving PIDs to omni-builds.slice, and purge timestamped post-build units"
  exit 0
fi

mkdir -p "$backup_root"
for src in "${legacy_files[@]}"; do
  [[ ! -e "$src" ]] || sudo cp -a "$src" "$backup_root/"
done
systemctl --user list-units 'omni-post-build-*' --all --no-pager >"$backup_root/legacy-post-build-units.txt" || true
systemctl --user list-timers 'omni-post-build-*' --all --no-pager >"$backup_root/legacy-post-build-timers.txt" || true

sudo systemctl disable --now atius-build-throttle.timer 2>/dev/null || true
sudo systemctl stop atius-build-throttle.service 2>/dev/null || true

if [[ -d "$legacy_cgroup" && -d "$builds_cgroup" ]]; then
  while IFS= read -r procs; do
    while IFS= read -r pid; do
      [[ -z "$pid" || ! -d "/proc/$pid" ]] || printf '%s\n' "$pid" | sudo tee "$builds_cgroup/cgroup.procs" >/dev/null
    done <"$procs"
  done < <(find "$legacy_cgroup" -type f -name cgroup.procs -print 2>/dev/null)
  for leaf in "$legacy_cgroup"/pid-*; do
    [[ ! -d "$leaf" ]] || sudo rmdir "$leaf" 2>/dev/null || true
  done
  sudo rmdir "$legacy_cgroup" 2>/dev/null || true
fi

# Older patcher versions created parallel plain cgroups.  Consolidate their
# processes into the same systemd slices used by wrappers and services.
for profile in builds interactive transfers; do
  old="${user_cgroup}/omni-${profile}"
  target="${systemd_omni_cgroup}/omni-${profile}.slice/omni-patcher"
  if [[ -d "$old" && -d "$(dirname "$target")" ]]; then
    sudo mkdir -p "$target"
    sudo chown "${uid}:$(id -g)" "$target"
    # Moving a parent does not atomically move descendants.  Iterate until
    # inherited children stop appearing, without killing any process.
    for _attempt in $(seq 1 20); do
      pids="$(<"$old/cgroup.procs")"
      [[ -n "$pids" ]] || break
      while IFS= read -r pid; do
        [[ -z "$pid" || ! -d "/proc/$pid" ]] || printf '%s\n' "$pid" | sudo tee "$target/cgroup.procs" >/dev/null
      done <<<"$pids"
    done
    sudo rmdir "$old" 2>/dev/null || true
    [[ ! -d "$old" ]] || echo "WARN obsolete cgroup still populated: $old" >&2
  fi
done

sudo rm -f "${legacy_files[@]}"
sudo systemctl daemon-reload
sudo systemctl reset-failed atius-build-throttle.service 2>/dev/null || true

systemctl --user list-units 'omni-post-build-*.timer' --all --no-legend --plain \
  | awk '{print $1}' | xargs -r -n 40 systemctl --user stop
systemctl --user list-units 'omni-post-build-*.service' --all --no-legend --plain \
  | awk '$3 != "active" && $3 != "activating" {print $1}' \
  | xargs -r -n 40 systemctl --user stop
systemctl --user reset-failed 'omni-post-build-*.service' 2>/dev/null || true

echo "backup=$backup_root"
echo "legacy_timer=$(systemctl is-enabled atius-build-throttle.timer 2>/dev/null || true)/$(systemctl is-active atius-build-throttle.timer 2>/dev/null || true)"
echo "legacy_cgroup=$([[ -d $legacy_cgroup ]] && echo present || echo absent)"
