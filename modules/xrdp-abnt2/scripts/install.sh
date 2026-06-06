#!/bin/sh
set -eu

# Standalone installer for Omni XRDP ABNT2 module.
# Prefer: sudo omni xrdp-abnt2 install --yes

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../../" && pwd)

if command -v omni >/dev/null 2>&1; then
    exec omni xrdp-abnt2 install --yes "$@"
fi

PYTHON_BIN=${PYTHON_BIN:-python3}
exec "$PYTHON_BIN" "$REPO_DIR/cli/omni/xrdp_abnt2.py" install --yes "$@"
