#!/usr/bin/env bash
# omni::gdrive-fleet-setup v1.0.0
# Instalador, configurador e reconciliador seguro do mount Google Drive (/mnt/gdrive) na frota ATIUS.
# Suporta execucao direta ou via Landscape Control-Plane.
set -euo pipefail

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    err "Este script deve ser executado como root."
    exit 1
fi

log "Iniciando instalacao/reconciliacao do Google Drive Fleet Mount..."

# 1. Dependencias do sistema
if ! command -v fusermount >/dev/null 2>&1 && ! command -v fusermount3 >/dev/null 2>&1; then
    log "Instalando fuse3..."
    apt-get update -qq && apt-get install -y -qq fuse3
fi

if ! command -v rclone >/dev/null 2>&1; then
    log "Instalando rclone..."
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

# 3. Limpeza de montagens e servicos legados de usuario
if id ubuntu >/dev/null 2>&1; then
    log "Verificando e desativando servicos legados de usuario..."
    su - ubuntu -c "systemctl --user stop rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user disable rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user mask rclone-gdrive-mount.service 2>/dev/null || true"
    
    # Desmonta mount legado se ainda estiver pendurado
    if mountpoint -q /home/ubuntu/GDrive 2>/dev/null; then
        log "Desmontando /home/ubuntu/GDrive legado..."
        fusermount -u -z /home/ubuntu/GDrive 2>/dev/null || true
    fi
fi

# 4. Criacao de diretorios e permissoes
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

# 5. Instalacao do helper de hidratacao do Vault
HYDRATE_SCRIPT="/usr/local/bin/gdrive-vault-hydrate"
cat <<'EOF_HYDRATE' > "${HYDRATE_SCRIPT}"
#!/usr/bin/env bash
# /usr/local/bin/gdrive-vault-hydrate
# Hidratacao em tempo de execucao das credenciais Google Drive a partir do HashiCorp Vault.
set -euo pipefail
umask 077

RUN_DIR="/run/rclone"
CONF_FILE="${RUN_DIR}/rclone.conf"

mkdir -p "${RUN_DIR}"
chmod 700 "${RUN_DIR}"

fail() {
    rm -f "${CONF_FILE}"
    echo "ERROR: [gdrive-vault-hydrate] $1" >&2
    exit 1
}

VAULT_ENV_BIN=""
if command -v atius-vault-env >/dev/null 2>&1; then
    VAULT_ENV_BIN="atius-vault-env"
elif [ -x "/home/ubuntu/.local/bin/atius-vault-env" ]; then
    VAULT_ENV_BIN="/home/ubuntu/.local/bin/atius-vault-env"
elif [ -x "/usr/local/sbin/atius-vault-export-env" ]; then
    VAULT_ENV_BIN="sudo /usr/local/sbin/atius-vault-export-env"
fi

[ -n "${VAULT_ENV_BIN}" ] || fail "atius-vault-env nao encontrado no host"

if [ "$(id -u)" -eq 0 ] && id ubuntu >/dev/null 2>&1; then
    ENV_OUTPUT=$(su - ubuntu -c "${VAULT_ENV_BIN} omni-storage" 2>/dev/null || true)
else
    ENV_OUTPUT=$(${VAULT_ENV_BIN} omni-storage 2>/dev/null || true)
fi

[ -n "${ENV_OUTPUT}" ] || fail "falha ao consultar Vault profile omni-storage"

CLIENT_ID=""
CLIENT_SECRET=""
REFRESH_TOKEN=""
TOKEN_JSON_RAW=""

while IFS='=' read -r key val; do
    key=$(echo "${key}" | sed -e 's/^export //' | xargs)
    val=$(echo "${val}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    case "${key}" in
        GDRIVE_CLIENT_ID|client_id) CLIENT_ID="${val}" ;;
        GDRIVE_CLIENT_SECRET|client_secret) CLIENT_SECRET="${val}" ;;
        GDRIVE_REFRESH_TOKEN|refresh_token) REFRESH_TOKEN="${val}" ;;
        GDRIVE_TOKEN_JSON|token_json) TOKEN_JSON_RAW="${val}" ;;
    esac
done <<< "${ENV_OUTPUT}"

[ -n "${CLIENT_ID}" ] || fail "GDRIVE_CLIENT_ID vazio no retorno do Vault"
[ -n "${CLIENT_SECRET}" ] || fail "GDRIVE_CLIENT_SECRET vazio no retorno do Vault"

if [ -n "${TOKEN_JSON_RAW}" ] && echo "${TOKEN_JSON_RAW}" | grep -q 'refresh_token'; then
    TOKEN_JSON="${TOKEN_JSON_RAW}"
elif [ -n "${REFRESH_TOKEN}" ]; then
    TOKEN_JSON=$(printf '{"access_token":"","token_type":"Bearer","refresh_token":"%s","expiry":"2000-01-01T00:00:00Z"}' "${REFRESH_TOKEN}")
else
    fail "Nem GDRIVE_TOKEN_JSON nem GDRIVE_REFRESH_TOKEN encontrados no Vault"
fi

cat <<EOF > "${CONF_FILE}"
[gdrive-main]
type = drive
client_id = ${CLIENT_ID}
client_secret = ${CLIENT_SECRET}
scope = drive
token = ${TOKEN_JSON}
EOF

chmod 600 "${CONF_FILE}"
echo "SUCCESS: [gdrive-vault-hydrate] rclone.conf materializado com sucesso em ${CONF_FILE} (tmpfs, mode 0600)"
exit 0
EOF_HYDRATE

chmod 755 "${HYDRATE_SCRIPT}"

# 6. Definicao de quotas por hostname
HOSTNAME_RAW=$(hostname -s | tr '[:upper:]' '[:lower:]')
case "${HOSTNAME_RAW}" in
    atius-srv-1)
        CACHE_MAX_SIZE="5G"
        CACHE_MAX_AGE="12h"
        ;;
    atius-srv-2)
        CACHE_MAX_SIZE="10G"
        CACHE_MAX_AGE="24h"
        ;;
    atius-srv-3)
        CACHE_MAX_SIZE="5G"
        CACHE_MAX_AGE="12h"
        ;;
    atius-srv-4)
        CACHE_MAX_SIZE="30G"
        CACHE_MAX_AGE="48h"
        ;;
    *)
        CACHE_MAX_SIZE="4G"
        CACHE_MAX_AGE="12h"
        ;;
esac

log "Host identificado como '${HOSTNAME_RAW}'. Quota VFS: size=${CACHE_MAX_SIZE}, age=${CACHE_MAX_AGE}"

# 7. Criacao da unit systemd de sistema /etc/systemd/system/gdrive-mount.service
UNIT_FILE="/etc/systemd/system/gdrive-mount.service"

cat <<EOF_UNIT > "${UNIT_FILE}"
[Unit]
Description=Atius Fleet Google Drive FUSE Mount
Documentation=man:rclone(1) https://atius.com.br
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory=${MOUNTPOINT}

[Service]
Type=notify
Restart=always
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s
LimitNOFILE=65536

# Governanca de CPU e IO
CPUQuota=20%
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

# Preparacao de diretorios e hidratacao Vault
ExecStartPre=-/bin/mkdir -p /run/rclone ${CACHE_DIR} ${MOUNTPOINT}
ExecStartPre=-/bin/chmod 700 /run/rclone
ExecStartPre=/usr/local/bin/gdrive-vault-hydrate

# Rclone Mount Daemon
ExecStart=/usr/bin/rclone mount gdrive-main: ${MOUNTPOINT} \\
    --config /run/rclone/rclone.conf \\
    --allow-other \\
    --umask 022 \\
    --dir-cache-time 72h \\
    --poll-interval 1m \\
    --vfs-cache-mode full \\
    --vfs-cache-max-size ${CACHE_MAX_SIZE} \\
    --vfs-cache-max-age ${CACHE_MAX_AGE} \\
    --vfs-read-chunk-size 32M \\
    --vfs-read-chunk-size-limit 256M \\
    --cache-dir ${CACHE_DIR} \\
    --buffer-size 16M \\
    --transfers 2 \\
    --checkers 4 \\
    --attr-timeout 1s \\
    --log-level INFO \\
    --syslog-facility DAEMON

# Desmontagem limpa
ExecStop=/bin/fusermount -u -z ${MOUNTPOINT}
ExecStopPost=-/bin/rm -f /run/rclone/rclone.conf

[Install]
WantedBy=multi-user.target
EOF_UNIT

chmod 644 "${UNIT_FILE}"

# 8. Reload, enable e start do servico
log "Recarregando systemd e iniciando servico gdrive-mount..."
systemctl daemon-reload
systemctl enable gdrive-mount.service

# Desmonta caso esteja montado anteriormente
if mountpoint -q "${MOUNTPOINT}" 2>/dev/null; then
    fusermount -u -z "${MOUNTPOINT}" 2>/dev/null || true
fi

systemctl restart gdrive-mount.service

# 9. Aguarda e valida inicializacao
log "Aguardando mountpoint ficar disponivel..."
MOUNTED=false
for i in {1..15}; do
    if mountpoint -q "${MOUNTPOINT}" 2>/dev/null; then
        MOUNTED=true
        break
    fi
    sleep 1
done

if [ "${MOUNTED}" != "true" ]; then
    err "Mountpoint ${MOUNTPOINT} nao foi montado a tempo. Status da unit:"
    systemctl status gdrive-mount.service --no-pager || true
    journalctl -u gdrive-mount.service -n 20 --no-pager || true
    exit 1
fi

# 10. Smoke test de leitura
ITEMS_COUNT=$(ls -1 "${MOUNTPOINT}" 2>/dev/null | wc -l || echo "0")
log "SUCCESS: Google Drive montado em ${MOUNTPOINT} com sucesso! Pastas encontradas: ${ITEMS_COUNT}"

# Emite resultado JSON final
cat <<EOF_JSON
{
  "status": "PASS",
  "host": "${HOSTNAME_RAW}",
  "mountpoint": "${MOUNTPOINT}",
  "cache_max_size": "${CACHE_MAX_SIZE}",
  "cache_max_age": "${CACHE_MAX_AGE}",
  "service_active": true,
  "items_count": ${ITEMS_COUNT}
}
EOF_JSON
exit 0
