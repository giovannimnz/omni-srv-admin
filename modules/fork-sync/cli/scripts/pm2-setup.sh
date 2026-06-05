#!/usr/bin/env bash
# pm2-setup.sh — Instala/remove serviços fork-sync no PM2.
#
# Uso:
#   ./pm2-setup.sh install     # instala todos
#   ./pm2-setup.sh install daily  # só o sync diário
#   ./pm2-setup.sh remove all
#   ./pm2-setup.sh status
#   ./pm2-setup.sh logs

set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

ACTION="${1:-status}"
TARGET="${2:-all}"

case "$ACTION" in
  install)
    case "$TARGET" in
      all)
        pm2 start ecosystem.config.cjs
        pm2 start ecosystem.doctor.cron.json
        pm2 start ecosystem.logrotate.cron.json
        pm2 start ecosystem.daily-sync.cron.json
        pm2 save
        echo "✅ Todos serviços instalados e salvos no PM2"
        pm2 status
        ;;
      repl|scheduler)
        pm2 start ecosystem.config.cjs
        pm2 save
        ;;
      doctor)
        pm2 start ecosystem.doctor.cron.json
        pm2 save
        ;;
      logrotate)
        pm2 start ecosystem.logrotate.cron.json
        pm2 save
        ;;
      daily)
        pm2 start ecosystem.daily-sync.cron.json
        pm2 save
        ;;
      *)
        echo "TARGET desconhecido: $TARGET (use: all|repl|doctor|logrotate|daily)"
        exit 1
        ;;
    esac
    ;;
  remove)
    pm2 delete all 2>/dev/null || true
    pm2 save
    echo "✅ Todos serviços removidos"
    ;;
  status)
    pm2 status
    ;;
  logs)
    pm2 logs "${2:-fork-sync-scheduler}" --lines 50
    ;;
  *)
    echo "Uso: $0 {install|remove|status|logs} [target]"
    echo ""
    echo "Targets para install: all (default), repl, doctor, logrotate, daily"
    echo ""
    echo "Targets para logs: nome do processo (ex: fork-sync-doctor)"
    exit 1
    ;;
esac
