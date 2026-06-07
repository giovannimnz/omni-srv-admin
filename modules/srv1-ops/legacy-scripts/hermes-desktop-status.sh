#!/bin/bash
#
# Hermes Desktop - Status Check
#

PID_FILE="/tmp/hermes-desktop.pid"
LOG_FILE="/home/ubuntu/.hermes/logs/hermes-desktop.log"

echo "=== Hermes Desktop Status ==="
echo ""

# Check process
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Status: RODANDO (PID: $PID)"
    else
        echo "Status: PARADO (PID file existe mas processo não)"
    fi
else
    # Check if any hermes-desktop process is running
    ANY_PID=$(pgrep -f "hermes-desktop.*linux-arm64" | head -1)
    if [ -n "$ANY_PID" ]; then
        echo "Status: RODANDO (PID: $ANY_PID) - sem PID file"
        echo "$ANY_PID" > "$PID_FILE"
    else
        echo "Status: PARADO"
    fi
fi

echo ""

# Check Xvfb
if pgrep -f "Xvfb" > /dev/null 2>&1; then
    echo "Xvfb: RODANDO"
else
    echo "Xvfb: PARADO"
fi

echo ""

# Check API server
if curl -s --max-time 2 http://127.0.0.1:8642/health > /dev/null 2>&1; then
    echo "API Server :8642: RESPONDENDO"
else
    echo "API Server :8642: NÃO RESPONDE"
fi

echo ""
echo "Logs: $LOG_FILE"
echo "PID file: $PID_FILE"
