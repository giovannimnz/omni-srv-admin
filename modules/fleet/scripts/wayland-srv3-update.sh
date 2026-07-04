#!/usr/bin/env bash
set -euo pipefail

WAYLAND_REPO="${WAYLAND_REPO:-/home/ubuntu/GitHub/wayland}"

cd "$WAYLAND_REPO"

if [[ "${1:-}" == "--pull" ]]; then
  git pull --ff-only
fi

bash scripts/atius-apply-source-patch.sh
sudo bash scripts/atius-postinstall-hook.sh
