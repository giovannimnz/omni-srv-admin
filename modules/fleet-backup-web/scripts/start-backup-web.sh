#!/usr/bin/env bash
# start-backup-web.sh — Inicializador do daemon de Web Storage & Agendamentos
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/../../cli:${PYTHONPATH:-}"
export OMNI_GDRIVE_BACKUP_ROOT="${OMNI_GDRIVE_BACKUP_ROOT:-/mnt/gdrive/ATIUS-SRV}"

PORT="${PORT:-8085}"
HOST="${HOST:-127.0.0.1}"

echo "[START] Iniciando Atius Fleet Backup & Schedule Web Dashboard em http://${HOST}:${PORT}..."
exec python3 -m uvicorn backend.app:app --host "${HOST}" --port "${PORT}" --workers 2
