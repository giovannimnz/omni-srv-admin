#!/usr/bin/env bash
set -euo pipefail

WAYLAND_REPO="${WAYLAND_REPO:-/home/ubuntu/GitHub/wayland}"

cd "$WAYLAND_REPO"
sudo bash scripts/atius-postinstall-hook.sh
