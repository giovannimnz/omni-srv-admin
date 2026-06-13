#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export OMNI_SRV_ADMIN="$ROOT"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$ROOT/cli"

echo "== M004 compile =="
python3 -m compileall -q cli/omni modules/fleet-control-plane/tools/validate_m004.py

echo "== M004 pytest =="
pytest -q modules/fleet-control-plane/tests/test_m004_contract.py

echo "== M004 offline contract validation =="
python3 modules/fleet-control-plane/tools/validate_m004.py --json

if [[ "${OMNI_M004_LIVE:-0}" == "1" ]]; then
  echo "== M004 live read-only validation =="
  python3 modules/fleet-control-plane/tools/validate_m004.py --live --json
else
  echo "== M004 live read-only validation skipped =="
  echo "Set OMNI_M004_LIVE=1 to probe SRV1/SRV2/SRV3 over SSH without applying changes."
fi
