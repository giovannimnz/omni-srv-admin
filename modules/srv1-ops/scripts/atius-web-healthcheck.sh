#!/bin/bash
# Substitui atius-web-health.sh (cron) — agora roda via systemd user timer
# Health check do atius-web (Next.js) na porta ativa 3015. Restart via PM2 se cair.
# 2026-06-11: contrato vivo reconciliado para porta 3015 / PM2 app atius-web.

HOST="127.0.0.1"
PORT="3015"
PM2_APP="atius-web"
LOG="$HOME/.logs/atius-web-health.log"

mkdir -p "$(dirname "$LOG")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [health] $*" >> "$LOG"
}

if nc -z "$HOST" "$PORT" 2>/dev/null; then
    log "OK — $PM2_APP respondendo na porta $PORT"
    exit 0
fi

log "WARN — porta $PORT nao responde — restarting $PM2_APP"

if command -v pm2 >/dev/null 2>&1; then
    pm2 restart "$PM2_APP" >> "$LOG" 2>&1
elif [[ -x /home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2 ]]; then
    /home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2 restart "$PM2_APP" >> "$LOG" 2>&1
else
    log "FAIL — pm2 nao encontrado"
    exit 1
fi

sleep 10
if nc -z "$HOST" "$PORT" 2>/dev/null; then
    log "OK — $PM2_APP restartado com sucesso"
else
    log "FAIL — $PM2_APP nao respondeu apos restart"
    exit 1
fi
