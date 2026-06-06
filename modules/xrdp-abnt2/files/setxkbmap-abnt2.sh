#!/bin/sh

apply_abnt2() {
    command -v setxkbmap >/dev/null 2>&1 || return 0
    setxkbmap -model pc105 -layout br -variant abnt2 -option -option lv3:ralt_switch >/dev/null 2>&1 || true
}

case "${1:-}" in
    --watch)
        lock_file="/tmp/setxkbmap-abnt2-${USER:-ubuntu}.lock"
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
