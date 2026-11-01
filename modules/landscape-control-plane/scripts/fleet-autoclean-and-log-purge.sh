#!/usr/bin/env bash
# omni::fleet-autoclean-and-log-purge v1.0.0
# Limpeza segura, rotatividade de logs e recuperacao de espaco em disco em toda a frota ATIUS.
# Executa simultaneamente via Landscape Control-Plane ou localmente via systemd timer.
set -euo pipefail

HOSTNAME_RAW=$(hostname -s | tr '[:upper:]' '[:lower:]')
LOG="/var/log/omni-fleet-autoclean.log"
touch "${LOG}" 2>/dev/null || LOG="/tmp/omni-fleet-autoclean.log"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "${LOG}"; }

# CPU e IO Guardrail: max 20% CPU total do host
renice -n 15 $$ >/dev/null 2>&1 || true
ionice -c 2 -n 7 -p $$ >/dev/null 2>&1 || true

log "========================================================"
log "INICIO AUTOCLEAN & LOG PURGE - Host: ${HOSTNAME_RAW}"
DISK_BEFORE=$(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " usado, " $4 " livre)"}')
log "Espaco em disco ANTES: ${DISK_BEFORE}"
log "========================================================"

# 1. Ajuste e limpeza de logs do SSSD (previne spam de ~1GB/dia)
if [ -d /var/log/sssd ]; then
    log "[SSSD] Purgando logs rotacionados do SSSD..."
    find /var/log/sssd -type f -name '*.log.*' -delete 2>/dev/null || true
    # Trunca logs ativos se > 20MB
    for f in /var/log/sssd/*.log; do
        if [ -f "$f" ]; then
            sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
            if [ "$sz" -gt 20971520 ]; then
                log "[SSSD] Truncando log gigante $f ($sz bytes)..."
                tail -c 5242880 "$f" > "$f.tmp" 2>/dev/null && mv "$f.tmp" "$f" 2>/dev/null || true
            fi
        fi
    done
    # Assegura debug_level baixo em /etc/sssd/sssd.conf
    if [ -f /etc/sssd/sssd.conf ] && ! grep -q "debug_level = 0x0010" /etc/sssd/sssd.conf; then
        log "[SSSD] Ajustando debug_level para 0x0010 em /etc/sssd/sssd.conf..."
        if grep -q "debug_level" /etc/sssd/sssd.conf; then
            sed -i 's/^debug_level.*/debug_level = 0x0010/' /etc/sssd/sssd.conf
        else
            sed -i '/\[sssd\]/a debug_level = 0x0010' /etc/sssd/sssd.conf 2>/dev/null || true
        fi
        systemctl reload sssd 2>/dev/null || true
    fi
fi

# 2. Limpeza de logs do PostgreSQL
if [ -d /var/log/postgresql ]; then
    log "[PostgreSQL] Compactando e purgando logs antigos do PostgreSQL..."
    find /var/log/postgresql -type f -name '*.log.*' -mtime +14 -delete 2>/dev/null || true
    find /var/log/postgresql -type f -name '*.log.[1-9]' -exec gzip -9 {} + 2>/dev/null || true
fi

# 3. Systemd Journal Vacuum
log "[Journal] Aplicando vacuum no systemd journal..."
journalctl --vacuum-size=300M 2>&1 | tail -5 | tee -a "${LOG}" || true
journalctl --vacuum-time=14d 2>&1 | tail -5 | tee -a "${LOG}" || true

# 4. APT Cache Clean
if command -v apt-get >/dev/null 2>&1; then
    log "[APT] Limpando cache de pacotes baixados (.deb)..."
    apt-get clean 2>/dev/null || true
    apt-get autoclean -y 2>/dev/null || true
fi

# 5. Logs rotacionados antigos em /var/log
log "[varlog] Removendo logs comprimidos com mais de 21 dias em /var/log..."
find /var/log -type f \( -name '*.gz' -o -name '*.old' -o -name '*.xz' \) -mtime +21 -delete 2>/dev/null || true

# Trunca logs de display / XRDP se > 30MB
for xf in /var/log/xrdp.log /var/log/xrdp-sesman.log; do
    if [ -f "$xf" ]; then
        xsz=$(stat -c %s "$xf" 2>/dev/null || echo 0)
        if [ "$xsz" -gt 31457280 ]; then
            log "[XRDP] Truncando $xf ($xsz bytes)..."
            : > "$xf" 2>/dev/null || true
        fi
    fi
done

# 6. /tmp antigos (>3 dias, preservando whitelist)
log "[tmp] Limpando arquivos temporarios em /tmp (>3 dias)..."
find /tmp -maxdepth 1 -mindepth 1 -mtime +3 \
  ! -name '.X*' ! -name '.ICE*' ! -name '.font*' ! -name '.Test*' \
  ! -name 'systemd-*' ! -name 'snap*' ! -name 'hermes_*' \
  -exec rm -rf {} + 2>/dev/null || true

# 7. Caches de desenvolvimento e runtimes (usuario ubuntu)
USER_HOME="/home/ubuntu"
if [ -d "${USER_HOME}" ]; then
    log "[Caches] Limpando caches de build e runtimes em ${USER_HOME}..."
    for p in \
      "${USER_HOME}/.cache/go-build" \
      "${USER_HOME}/.cache/codex-update-manager" \
      "${USER_HOME}/.cache/ms-playwright" \
      "${USER_HOME}/.cache/copilot" \
      "${USER_HOME}/.cache/node-gyp" \
      "${USER_HOME}/.cache/pip" \
      "${USER_HOME}/.cache/yarn" \
      "${USER_HOME}/.bun/install/cache" \
      "${USER_HOME}/.npm/_cacache"; do
        if [ -d "$p" ]; then
            rm -rf "$p"/* 2>/dev/null || true
        fi
    done

    # Trim de logs locais ~/.logs e ~/.pm2/logs
    for ldir in "${USER_HOME}/.logs" "${USER_HOME}/.pm2/logs"; do
        if [ -d "$ldir" ]; then
            find "$ldir" -type f \( -name '*.log' -o -name '*.log.*' \) -mtime +14 -delete 2>/dev/null || true
            find "$ldir" -type f \( -name '*.log' -o -name '*.log.*' \) -size +50M -print0 2>/dev/null | while IFS= read -r -d '' f; do
                tail -c 5242880 "$f" > "$f.tmp" 2>/dev/null && mv "$f.tmp" "$f" 2>/dev/null || true
            done
        fi
    done
fi

# 8. Podman Containers and Images Prune
if command -v podman >/dev/null 2>&1; then
    log "[Podman] Podman image prune (root)..."
    podman image prune -f 2>&1 | tail -5 | tee -a "${LOG}" || true
    # Se rodando sob usuario ubuntu tambem
    if id ubuntu >/dev/null 2>&1; then
        log "[Podman] Podman image prune (user ubuntu)..."
        su - ubuntu -c "podman image prune -f" 2>&1 | tail -5 | tee -a "${LOG}" || true
    fi
fi

# 9. Docker Prune se instalado
if command -v docker >/dev/null 2>&1; then
    log "[Docker] Docker image prune..."
    docker image prune -f 2>&1 | tail -5 | tee -a "${LOG}" || true
fi

log "========================================================"
DISK_AFTER=$(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " usado, " $4 " livre)"}')
log "Espaco em disco DEPOIS: ${DISK_AFTER}"
log "CONCLUIDO AUTOCLEAN & LOG PURGE - Host: ${HOSTNAME_RAW}"
log "========================================================"
exit 0
