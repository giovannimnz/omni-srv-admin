#!/bin/bash
#
# Hermes Desktop - Stop Script
#

PID_FILE="/tmp/hermes-desktop.pid"
XVFB_PID_FILE="/tmp/xvfb.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Parando Hermes Desktop (PID: $PID)..."
        kill "$PID" 2>/dev/null
        sleep 1
        kill -9 "$PID" 2>/dev/null
        echo "Hermes Desktop parado."
    else
        echo "Hermes Desktop não está rodando (PID $PID não existe)."
    fi
    rm -f "$PID_FILE"
else
    echo "Nenhum PID_FILE encontrado. Matando processos..."
    pkill -f "hermes-desktop.*linux-arm64" 2>/dev/null
fi

# Opcional: parar Xvfb
# pkill -f "Xvfb :99" 2>/dev/null

echo "Done."
