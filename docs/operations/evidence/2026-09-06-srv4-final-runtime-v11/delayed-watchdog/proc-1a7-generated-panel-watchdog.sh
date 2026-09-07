#!/usr/bin/env bash
set -u

panel_height="${OMNI_LXPANEL_HEIGHT:-38}"

screen_size() {
  if command -v xrandr >/dev/null 2>&1; then
    xrandr --current 2>/dev/null | awk '
      / connected/ {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, p, /[x+]/)
            print p[1], p[2]
            exit
          }
        }
      }'
    return
  fi
  if command -v xdpyinfo >/dev/null 2>&1; then
    xdpyinfo 2>/dev/null | awk '/dimensions:/ { split($2, p, "x"); print p[1], p[2]; exit }'
  fi
}

fix_once() {
  command -v wmctrl >/dev/null 2>&1 || return 0
  if ! wmctrl -lG 2>/dev/null | awk '$0 ~ / panel$/ { found = 1 } END { exit !found }'; then
    setsid -f lxpanel --profile LXDE >/tmp/omni-dark-theme-lxpanel.log 2>&1 || true
    sleep 1
  fi
  set -- $(screen_size)
  [ "$#" -ge 2 ] || return 0
  width="$1"
  max_width="$(wmctrl -lG 2>/dev/null | awk '$0 ~ / panel$/ && $5 > max { max = $5 } END { print max + 0 }')"
  [ "${max_width:-0}" -ge $((width - 8)) ] || return 0
  command -v xdotool >/dev/null 2>&1 || return 0
  wmctrl -lG 2>/dev/null \
    | awk -v width="$width" '$0 ~ / panel$/ && $5 < width - 8 { print $1 }' \
    | while read -r id; do
        xdotool windowraise "$id" >/dev/null 2>&1 || true
      done
}

case "${1:-}" in
  --watch)
    display_id="$(printf '%s' "${DISPLAY:-unknown}" | tr -c '[:alnum:]_.-' '_')"
    lock_file="/tmp/omni-lxde-panel-guard-${USER:-ubuntu}-${display_id}.lock"
    exec 9>"$lock_file" || exit 0
    flock -n 9 || exit 0
    while :; do
      command -v xdpyinfo >/dev/null 2>&1 && xdpyinfo >/dev/null 2>&1 || exit 0
      fix_once
      sleep 5
    done
    ;;
  *)
    fix_once
    ;;
esac
