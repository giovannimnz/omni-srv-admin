#!/bin/bash
#
# Hermes Desktop - Start Script
# Starts both the Dashboard (port 9119) and the Desktop (Electron)
# via Xvfb
#
set -e

HERMES_DESKTOP_DIR="/home/ubuntu/GitHub/hermes-desktop"
HERMES_DESKTOP_BIN="$HERMES_DESKTOP_DIR/dist/linux-arm64-unpacked/hermes-desktop"
LOG_FILE="/home/ubuntu/.hermes/logs/hermes-desktop.log"
PID_FILE="/tmp/hermes-desktop.pid"
XVFB_PID_FILE="/tmp/xvfb-hermes-desktop.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[HERMES-DESKTOP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Hermes Desktop already running (PID $PID)"
        exit 0
    else
        warn "Stale PID file found, removing..."
        rm -f "$PID_FILE"
    fi
fi

# Check if Hermes Agent is installed
if [ ! -f "/home/ubuntu/.hermes/hermes-agent/venv/bin/hermes" ]; then
    error "Hermes Agent not found at ~/.hermes/hermes-agent/"
    exit 1
fi

# Ensure HERMES_HOME is set
export HERMES_HOME="/home/ubuntu/.hermes"

# ── Ensure Dashboard server is running on port 9119 ──
log "Checking Dashboard server on port 9119..."
if ! curl -s --max-time 2 http://127.0.0.1:9119/ > /dev/null 2>&1; then
    log "Starting Hermes Dashboard server..."
    nohup ~/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main dashboard \
        --port 9119 --host 0.0.0.0 --insecure --skip-build \
        >> /home/ubuntu/.hermes/logs/hermes-dashboard.log 2>&1 &
    DASH_PID=$!
    log "Dashboard started (PID $DASH_PID)"
    sleep 5
else
    log "Dashboard already running"
fi

# ── Ensure Xvfb is running ──
log "Checking Xvfb..."
if pgrep -f "Xvfb :99" > /dev/null; then
    log "Xvfb already running on :99"
else
    log "Starting Xvfb on :99..."
    Xvfb :99 -screen 0 1920x1080x24 >> /home/ubuntu/.hermes/logs/xvfb.log 2>&1 &
    XVFB_PID=$!
    echo $XVFB_PID > "$XVFB_PID_FILE"
    log "Xvfb started (PID $XVFB_PID)"
    sleep 2
fi

# ── Start Hermes Desktop (Electron) ──
log "Starting Hermes Desktop..."
export DISPLAY=:99
nohup xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    "$HERMES_DESKTOP_BIN" \
    --no-sandbox \
    --disable-gpu \
    --disable-software-rasterizer \
    >> "$LOG_FILE" 2>&1 &
DESKTOP_PID=$!
echo $DESKTOP_PID > "$PID_FILE"

log "Hermes Desktop started (PID $DESKTOP_PID)"
log "Dashboard: https://hermes-desktop.atius.com.br"
log "API Server: https://hermes-desktop.atius.com.br/v1/"
