#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/graphify-sync.sh {status|query <text>|build|update|init-plan-phase <workstream> <phase>}" >&2
  exit 64
}

action="${1:-}"
shift || true
case "$action" in
  status|build|update)
    [ "$#" -eq 0 ] || usage
    ;;
  query)
    [ "$#" -eq 1 ] && [ -n "$1" ] || usage
    ;;
  init-plan-phase)
    [ "$#" -eq 2 ] && [ -n "$1" ] && [[ "$2" =~ ^[0-9]+([.][0-9]+)?$ ]] || usage
    ;;
  *)
    usage
    ;;
esac

repo_root="$(git rev-parse --show-toplevel)"
gsd_tools_linux="${CODEX_HOME:-$HOME/.codex}/gsd-core/bin/gsd-tools.cjs"
if [ ! -f "$gsd_tools_linux" ]; then
  echo "graphify wrapper: gsd-tools.cjs not found" >&2
  exit 69
fi

runtime=()
if command -v node >/dev/null 2>&1; then
  runtime=(node "$gsd_tools_linux")
elif command -v node.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
  runtime=(node.exe "$(wslpath -w "$gsd_tools_linux")")
else
  echo "graphify wrapper: neither Linux node nor node.exe+wslpath is available" >&2
  exit 69
fi

case "$action" in
  status)
    command_args=("${runtime[@]}" graphify "$action")
    ;;
  query)
    command_args=("${runtime[@]}" graphify query "$1")
    ;;
  init-plan-phase)
    command_args=(
      "${runtime[@]}"
      --ws "$1"
      query init.plan-phase "$2"
      --pick phase_found
    )
    ;;
esac

cd "$repo_root"
case "${runtime[0]}" in
  *.exe)
    export GIT_DIR
    GIT_DIR="$(git rev-parse --git-dir)"
    export GIT_WORK_TREE="$repo_root"
    export WSLENV="${WSLENV:+$WSLENV:}GIT_DIR/p:GIT_WORK_TREE/p"
    ;;
esac

if [ "$action" != "update" ] && [ "$action" != "build" ]; then
  exec "${command_args[@]}"
fi

host_name="$(hostname -s)"
script_path="$repo_root/scripts/graphify-sync.sh"
case "$host_name" in
  atius-srv-1|atius-srv-2|atius-srv-3|horistic-srv)
    if [ "${GRAPHIFY_SYNC_GUARDED:-0}" != "1" ]; then
      if command -v omni >/dev/null 2>&1; then
        exec omni srv1-ops resources run builds -- \
          env GRAPHIFY_SYNC_GUARDED=1 "$script_path" "$action"
      fi
      if command -v systemd-run >/dev/null 2>&1; then
        exec systemd-run --user --scope --quiet \
          -p CPUQuota=20% \
          nice -n 10 ionice -c 2 -n 7 \
          env GRAPHIFY_SYNC_GUARDED=1 "$script_path" "$action"
      fi
      echo "graphify wrapper: no verified 20% CPU containment on managed server" >&2
      exit 70
    fi
    ;;
esac

graphify_cli=()
if command -v graphify >/dev/null 2>&1; then
  graphify_cli=("$(command -v graphify)")
elif command -v graphify.exe >/dev/null 2>&1; then
  graphify_cli=("$(command -v graphify.exe)")
else
  config_parent="$(dirname "${CODEX_HOME:-$HOME/.codex}")"
  if [ -x "$config_parent/.local/bin/graphify.exe" ]; then
    graphify_cli=("$config_parent/.local/bin/graphify.exe")
  elif [ -x "$HOME/.local/bin/graphify" ]; then
    graphify_cli=("$HOME/.local/bin/graphify")
  else
    echo "graphify wrapper: external graphify CLI not found" >&2
    exit 69
  fi
fi

graphify_args=(update .)
if [ "${GRAPHIFY_FORCE:-0}" = "1" ]; then
  graphify_args+=(--force)
fi
"${graphify_cli[@]}" "${graphify_args[@]}"
test -f graphify-out/graph.json
test -f graphify-out/GRAPH_REPORT.md
for generated_text in \
  graphify-out/.graphify_labels.json \
  graphify-out/.last-build-snapshot.json \
  graphify-out/graph.json \
  graphify-out/GRAPH_REPORT.md; do
  if [ -f "$generated_text" ]; then
    sed -i 's/\r$//' "$generated_text"
  fi
done
cp graphify-out/graph.json .planning/graphs/graph.json
cp graphify-out/GRAPH_REPORT.md .planning/graphs/GRAPH_REPORT.md
if [ -f graphify-out/graph.html ]; then
  cp graphify-out/graph.html .planning/graphs/graph.html
fi
"${runtime[@]}" graphify build snapshot
exec "${runtime[@]}" graphify status
