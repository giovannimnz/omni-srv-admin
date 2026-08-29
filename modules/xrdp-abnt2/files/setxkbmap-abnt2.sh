#!/bin/sh

apply_abnt2() {
    command -v setxkbmap >/dev/null 2>&1 || return 0
    if [ -z "${XAUTHORITY:-}" ] && [ -n "${HOME:-}" ]; then
        export XAUTHORITY="$HOME/.Xauthority"
    fi
    setxkbmap -model pc105 -layout br -variant abnt2 -option '' -option lv3:ralt_switch >/dev/null 2>&1 || true
}

case "${1:-}" in
    --watch)
        display_id=$(printf '%s' "${DISPLAY:-nodisplay}" | tr -c 'A-Za-z0-9_.-' '_')
        lock_file="/tmp/setxkbmap-abnt2-${USER:-ubuntu}-${display_id}.lock"
        exec 9>"$lock_file" || exit 0
        flock -n 9 || exit 0

        while :; do
            apply_abnt2
            sleep 5
        done
        ;;
    *)
        apply_abnt2
        ;;
esac
