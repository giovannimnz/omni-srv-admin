#!/usr/bin/env bash
set -euo pipefail
D=:97
R=/tmp/omni-watchdog-lifecycle-$$
mkdir -p "$R"
cleanup(){ kill "${kp:-}" "${pp:-}" "${xp:-}" 2>/dev/null || true; wait "${kp:-}" "${pp:-}" "${xp:-}" 2>/dev/null || true; rm -rf "$R"; }
trap cleanup EXIT
Xvfb "$D" -screen 0 800x600x24 -nolisten tcp >"$R/xvfb.log" 2>&1 & xp=$!
for i in $(seq 1 20); do DISPLAY="$D" xdpyinfo >/dev/null 2>&1 && break; sleep .25; done
DISPLAY="$D" XAUTHORITY="$HOME/.Xauthority" "$HOME/.local/bin/setxkbmap-abnt2.sh" --watch >"$R/key.log" 2>&1 & kp=$!
DISPLAY="$D" XAUTHORITY="$HOME/.Xauthority" "$HOME/.local/bin/omni-lxde-panel-guard.sh" --watch >"$R/panel.log" 2>&1 & pp=$!
sleep 2
kill -0 "$kp"; kill -0 "$pp"
kill "$xp"; wait "$xp" 2>/dev/null || true
ka=1; pa=1
for i in $(seq 1 20); do
  ka=0; pa=0
  kill -0 "$kp" 2>/dev/null && ka=1 || true
  kill -0 "$pp" 2>/dev/null && pa=1 || true
  [ "$ka" -eq 0 ] && [ "$pa" -eq 0 ] && break
  sleep .5
done
printf "keyboard_alive=%s panel_alive=%s elapsed_max_sec=10\n" "$ka" "$pa"
[ "$ka" -eq 0 ] && [ "$pa" -eq 0 ]
echo watchdog_display_lifecycle=PASS
