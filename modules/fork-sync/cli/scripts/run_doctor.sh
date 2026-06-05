#!/usr/bin/env bash
# run_doctor.sh — wrapper PM2-friendly que roda `fork-sync doctor` e loga.
# Usado por ecosystem.doctor.cron.json com cron_restart "0 7 * * *"

set -euo pipefail
LOG_DIR="/home/ubuntu/fork-sync/logs"
mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOG_DIR/doctor-$TS.log"

echo "[doctor $TS] start" | tee -a "$LOG"
fork-sync doctor 2>&1 | tee -a "$LOG"
EXIT=${PIPESTATUS[0]}
echo "[doctor $TS] exit=$EXIT" | tee -a "$LOG"
exit $EXIT
