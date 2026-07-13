#!/usr/bin/env bash
# install-orphan-mcp-reaper.sh — Instala o orphan MCP reaper + systemd timer
# Uso: ./install-orphan-mcp-reaper.sh [--dry-run]
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" = "--dry-run" ]] && DRY_RUN=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REAPER="${SCRIPT_DIR}/orphan-mcp-reaper.sh"
TARGET="${HOME}/.local/bin/orphan-mcp-reaper.sh"

if [[ ! -f "${REAPER}" ]]; then
  echo "FATAL: ${REAPER} not found" >&2
  exit 1
fi

install_script() {
  cp "${REAPER}" "${TARGET}" && chmod +x "${TARGET}"
  echo "OK: script installed at ${TARGET}"
}

install_systemd() {
  sudo tee /etc/systemd/system/orphan-mcp-reaper.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Orphan MCP Server Reaper
Documentation=https://github.com/Atius-Capital/omni-srv-admin

[Service]
Type=oneshot
ExecStart=/c/Users/muniz/.local/bin/orphan-mcp-reaper.sh --max-age 30
Environment=HOME=/c/Users/muniz
User=ubuntu
Nice=19
IOSchedulingClass=idle
SERVICEEOF

  sudo tee /etc/systemd/system/orphan-mcp-reaper.timer > /dev/null << 'TIMEREOF'
[Unit]
Description=Orphan MCP Reaper (every 10 min)
Requires=orphan-mcp-reaper.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
TIMEREOF

  sudo systemctl daemon-reload
  sudo systemctl enable --now orphan-mcp-reaper.timer
  echo "OK: systemd timer installed and active"
}

if [[ "${DRY_RUN}" = "1" ]]; then
  echo "DRY-RUN: script -> ${TARGET}"
  echo "DRY-RUN: systemd unit + timer -> /etc/systemd/system/"
  exit 0
fi

install_script
install_systemd
