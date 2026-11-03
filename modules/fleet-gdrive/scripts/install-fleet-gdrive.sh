#!/usr/bin/env bash
# modules/fleet-gdrive/scripts/install-fleet-gdrive.sh
# Instalador local idempotente do Google Drive Fleet Mount (/mnt/gdrive) na frota ATIUS.
# Suporta execucao direta no host e integracao automatizada.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    err "Este script de instalacao deve ser executado como root (sudo)."
    exit 1
fi

HOSTNAME=$(hostname -s 2>/dev/null || cat /etc/hostname 2>/dev/null || echo "unknown-host")
log "Iniciando instalacao idempotente do Fleet Google Drive Storage no host '${HOSTNAME}'..."

# 1. Dependencias do sistema
if ! command -v fusermount >/dev/null 2>&1 && ! command -v fusermount3 >/dev/null 2>&1; then
    log "Instalando pacote fuse3..."
    apt-get update -qq && apt-get install -y -qq fuse3
fi

if ! command -v rclone >/dev/null 2>&1; then
    log "Instalando pacote rclone..."
    apt-get update -qq && apt-get install -y -qq rclone
fi

# 2. Habilita user_allow_other no /etc/fuse.conf
if [ -f /etc/fuse.conf ]; then
    if ! grep -q '^[[:space:]]*user_allow_other' /etc/fuse.conf; then
        log "Habilitando user_allow_other em /etc/fuse.conf..."
        sed -i 's/^[[:space:]]*#[[:space:]]*user_allow_other/user_allow_other/' /etc/fuse.conf
        if ! grep -q '^[[:space:]]*user_allow_other' /etc/fuse.conf; then
            echo "user_allow_other" >> /etc/fuse.conf
        fi
    fi
else
    echo "user_allow_other" > /etc/fuse.conf
    chmod 644 /etc/fuse.conf
fi

# 3. Limpeza de montagens e servicos legados de usuario (Prevenindo loops de restart)
if id ubuntu >/dev/null 2>&1; then
    log "Verificando e desativando servicos legados de usuario..."
    su - ubuntu -c "systemctl --user stop rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user disable rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user mask rclone-gdrive-mount.service 2>/dev/null || true"

    if mountpoint -q /home/ubuntu/GDrive 2>/dev/null; then
        log "Desmontando /home/ubuntu/GDrive legado..."
        fusermount -u -z /home/ubuntu/GDrive 2>/dev/null || true
    fi
fi

# 4. Criacao de diretorios operacionais
MOUNTPOINT="/mnt/gdrive"
CACHE_DIR="/var/cache/rclone-gdrive"
RUN_DIR="/run/rclone"

mkdir -p "${MOUNTPOINT}"
mkdir -p "${CACHE_DIR}"
mkdir -p "${RUN_DIR}"

chmod 755 "${MOUNTPOINT}"
chmod 700 "${CACHE_DIR}"
chmod 700 "${RUN_DIR}"

if id ubuntu >/dev/null 2>&1; then
    chown ubuntu:ubuntu "${MOUNTPOINT}"
    chown ubuntu:ubuntu "${CACHE_DIR}"
fi

# 5. Instalacao dos helpers operacionais (/usr/local/bin)
HYDRATE_SRC="${MODULE_DIR}/scripts/gdrive-vault-hydrate.sh"
DOCTOR_SRC="${MODULE_DIR}/scripts/gdrive-doctor.sh"

if [ -f "${HYDRATE_SRC}" ]; then
    cp -f "${HYDRATE_SRC}" /usr/local/bin/gdrive-vault-hydrate
    chmod 755 /usr/local/bin/gdrive-vault-hydrate
    log "Instalado /usr/local/bin/gdrive-vault-hydrate"
fi

if [ -f "${DOCTOR_SRC}" ]; then
    cp -f "${DOCTOR_SRC}" /usr/local/bin/gdrive-doctor
    chmod 755 /usr/local/bin/gdrive-doctor
    log "Instalado /usr/local/bin/gdrive-doctor"
fi

# 6. Definicao de quotas VFS proporcionais por host
CACHE_MAX_SIZE="4G"
CACHE_MAX_AGE="12h"

case "${HOSTNAME}" in
    atius-srv-1*)
        CACHE_MAX_SIZE="5G"
        CACHE_MAX_AGE="12h"
        ;;
    atius-srv-2*)
        CACHE_MAX_SIZE="10G"
        CACHE_MAX_AGE="24h"
        ;;
    atius-srv-3*)
        CACHE_MAX_SIZE="5G"
        CACHE_MAX_AGE="12h"
        ;;
    atius-srv-4*)
        CACHE_MAX_SIZE="30G"
        CACHE_MAX_AGE="48h"
        ;;
esac

log "Configurando quotas para host '${HOSTNAME}': CACHE_MAX_SIZE=${CACHE_MAX_SIZE}, CACHE_MAX_AGE=${CACHE_MAX_AGE}"

# Escreve arquivo de ambiente de configuracao de quotas
cat <<EOF > /etc/default/gdrive-mount
# Configuracoes de cota VFS geradas para ${HOSTNAME}
CACHE_MAX_SIZE=${CACHE_MAX_SIZE}
CACHE_MAX_AGE=${CACHE_MAX_AGE}
EOF
chmod 644 /etc/default/gdrive-mount

# 7. Instalacao da unit systemd canônica
SERVICE_SRC="${MODULE_DIR}/systemd/gdrive-mount.service"
SERVICE_DST="/etc/systemd/system/gdrive-mount.service"

if [ -f "${SERVICE_SRC}" ]; then
    cp -f "${SERVICE_SRC}" "${SERVICE_DST}"
else
    # Fallback caso executado standalone
    cat <<EOF > "${SERVICE_DST}"
[Unit]
Description=Atius Fleet Google Drive FUSE Mount
Documentation=man:rclone(1) https://atius.com.br
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory=${MOUNTPOINT}

[Service]
Type=notify
NotifyAccess=all
Restart=on-failure
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s
LimitNOFILE=65536

CPUQuota=20%
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

EnvironmentFile=-/etc/default/gdrive-mount
Environment="CACHE_MAX_SIZE=${CACHE_MAX_SIZE}"
Environment="CACHE_MAX_AGE=${CACHE_MAX_AGE}"

ExecStartPre=-/bin/mkdir -p ${RUN_DIR} ${CACHE_DIR} ${MOUNTPOINT}
ExecStartPre=-/bin/chmod 700 ${RUN_DIR} ${CACHE_DIR}
ExecStartPre=/usr/local/bin/gdrive-vault-hydrate

ExecStart=/usr/bin/rclone mount gdrive-main: ${MOUNTPOINT} \\
    --config /run/rclone/rclone.conf \\
    --allow-other \\
    --umask 022 \\
    --dir-cache-time 72h \\
    --poll-interval 1m \\
    --vfs-cache-mode full \\
    --vfs-cache-max-size \${CACHE_MAX_SIZE} \\
    --vfs-cache-max-age \${CACHE_MAX_AGE} \\
    --vfs-read-chunk-size 32M \\
    --vfs-read-chunk-size-limit 256M \\
    --cache-dir ${CACHE_DIR} \\
    --buffer-size 16M \\
    --tpslimit 4 \\
    --tpslimit-burst 1 \\
    --drive-pacer-min-sleep 100ms \\
    --drive-pacer-burst 1 \\
    --transfers 2 \\
    --checkers 4 \\
    --attr-timeout 1s \\
    --log-level INFO \\
    --syslog-facility DAEMON

ExecStop=/bin/fusermount -u -z ${MOUNTPOINT}
ExecStopPost=-/bin/rm -f /run/rclone/rclone.conf

[Install]
WantedBy=multi-user.target
EOF
fi

chmod 644 "${SERVICE_DST}"
systemctl daemon-reload
systemctl enable gdrive-mount.service

# 8. Teste de hidratacao do Vault antes de inicializar o servico
if [ -x /usr/local/bin/gdrive-vault-hydrate ]; then
    log "Testando hidratacao efemera de credenciais do HashiCorp Vault..."
    if /usr/local/bin/gdrive-vault-hydrate; then
        log "Hidratacao efemera confirmada com sucesso."
    else
        err "Falha na hidratacao do Vault. Verifique perfil omni-storage."
        exit 1
    fi
fi

# 9. Inicializacao e validacao do servico
log "Reiniciando gdrive-mount.service..."
systemctl restart gdrive-mount.service

# Aguarda ate 10 segundos para montagem
MOUNTED=false
for i in {1..10}; do
    if mountpoint -q "${MOUNTPOINT}" && systemctl is-active --quiet gdrive-mount.service; then
        MOUNTED=true
        break
    fi
    sleep 1
done

if [ "${MOUNTED}" = true ]; then
    log "SUCCESS: Google Drive montado com sucesso em ${MOUNTPOINT} (gdrive-mount.service active)."
    exit 0
else
    err "FALHA: O servico gdrive-mount nao estabilizou ou ${MOUNTPOINT} nao foi montado."
    systemctl status gdrive-mount.service --no-pager || true
    exit 1
fi
