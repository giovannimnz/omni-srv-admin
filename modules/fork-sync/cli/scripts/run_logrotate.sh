#!/usr/bin/env bash
# run_logrotate.sh — wrapper PM2-friendly que roda rotação de logs.
# Cron recomendado: "0 3 * * *" (3h UTC = 0h BRT, evita pico de uso)

set -euo pipefail
LOG_DIR="/home/ubuntu/fork-sync/logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOG_DIR/logrotate-$TS.log"

echo "[logrotate $TS] start" | tee -a "$LOG"
fork-sync logs --rotate --apply 2>&1 | tee -a "$LOG"
EXIT=${PIPESTATUS[0]}
echo "[logrotate $TS] exit=$EXIT" | tee -a "$LOG"
exit $EXIT
