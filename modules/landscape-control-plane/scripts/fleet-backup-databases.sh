#!/usr/bin/env bash
# omni::fleet-backup-databases v1.0.0
# Dispara o backup governado de bancos de dados para /mnt/gdrive em toda a frota ATIUS via Landscape.
set -euo pipefail

REPO="/home/ubuntu/GitHub/omni-srv-admin"
SCRIPT="${REPO}/modules/fleet-backup/scripts/backup-databases.sh"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [ ! -f "${SCRIPT}" ]; then
    log "Atualizando repositorio omni-srv-admin..."
    if [ -d "${REPO}" ]; then
        git -C "${REPO}" fetch origin main >/dev/null 2>&1 || true
        git -C "${REPO}" checkout main >/dev/null 2>&1 || true
        git -C "${REPO}" pull --ff-only origin main >/dev/null 2>&1 || true
    fi
fi

if [ -f "${SCRIPT}" ]; then
    chmod +x "${SCRIPT}"
    exec /bin/bash "${SCRIPT}"
else
    log "ERRO: Script de backup nao encontrado em ${SCRIPT}"
    exit 1
fi
