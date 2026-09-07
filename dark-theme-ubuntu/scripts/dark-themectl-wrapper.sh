#!/usr/bin/env bash
set -Eeuo pipefail

export OMNI_DARK_MODULE_DIR="${OMNI_DARK_MODULE_DIR:-$HOME/GitHub/omni-srv-admin/dark-theme-ubuntu}"
exec "$HOME/.local/lib/omni-dark-theme/dark-themectl.sh" "$@"
