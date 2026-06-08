#!/usr/bin/env bash
# run_sync_all.sh — wrapper PM2-friendly que roda sync de TODOS os projetos.
# Cron recomendado: "0 8 * * *" (8h UTC = 5h BRT — antes do expediente)

set -euo pipefail
LOG_DIR="/home/ubuntu/GitHub/omni-srv-admin/modules/fork-sync/logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d)
LOG="$LOG_DIR/sync-all-$TS.log"

echo "[sync-all $TS] start" | tee -a "$LOG"

# Lista todos os projetos
PROJECTS=$(fork-sync --json projects list 2>/dev/null | python3 -c "import json,sys; [print(p['name']) for p in json.load(sys.stdin)]" 2>/dev/null || true)

if [ -z "$PROJECTS" ]; then
  echo "[sync-all] Nenhum projeto configurado" | tee -a "$LOG"
  exit 0
fi

for project in $PROJECTS; do
  echo "[sync-all $TS] → $project" | tee -a "$LOG"
  # dry-run primeiro; se --apply for passado, sync real
  if [ "${1:-}" = "--apply" ]; then
    fork-sync sync "$project" 2>&1 | tee -a "$LOG" || true
  else
    fork-sync sync "$project" --dry-run 2>&1 | tee -a "$LOG" || true
  fi
done

echo "[sync-all $TS] done" | tee -a "$LOG"
