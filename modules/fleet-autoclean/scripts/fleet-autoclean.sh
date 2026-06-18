#!/usr/bin/env bash
set -euo pipefail

REPO="${OMNI_SRV_ADMIN:-/home/ubuntu/GitHub/omni-srv-admin}"
export PYTHONPATH="$REPO/cli${PYTHONPATH:+:$PYTHONPATH}"

MODE="${1:-dry-run}"
HOST="${2:-all}"

case "$MODE" in
  dry-run)
    exec python3 -m omni srv autoclean "$HOST"
    ;;
  apply)
    exec python3 -m omni srv autoclean "$HOST" --apply
    ;;
  audit)
    exec python3 -m omni srv storage-audit "$HOST"
    ;;
  *)
    echo "usage: $0 {dry-run|apply|audit} [host|all]" >&2
    exit 2
    ;;
esac
