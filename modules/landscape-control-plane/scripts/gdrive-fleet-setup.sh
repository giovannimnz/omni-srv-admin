#!/usr/bin/env bash
# omni::gdrive-fleet-setup v1.0.0 (alias / sync: setup-fleet-gdrive.sh)
# Instala, configura e reconcilia o mount governado do Google Drive (/mnt/gdrive) na frota ATIUS.
# Suporta execucao direta ou via Landscape Control-Plane.
set -euo pipefail

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

# 0. Verificacao de privilegios root
if [ "$(id -u)" -ne 0 ]; then
    err "Este script deve ser executado como root."
    printf '{"status": "FAIL", "reason": "must_run_as_root"}\n'
    exit 1
fi

# 1. Concurrency lock (/var/lock/setup-fleet-gdrive.lock)
LOCKFILE="/var/lock/setup-fleet-gdrive.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    err "Outro processo ja esta executando setup-fleet-gdrive (lock em ${LOCKFILE})."
    printf '{"status": "FAIL", "reason": "lock_acquired_by_another_process"}\n'
    exit 1
fi

log "Iniciando instalacao e reconciliacao do Fleet Google Drive Storage via Landscape..."

# 2. Verificacao e instalacao nao-interativa de fuse3 e rclone
export DEBIAN_FRONTEND=noninteractive
if (! command -v fusermount >/dev/null 2>&1 && ! command -v fusermount3 >/dev/null 2>&1) || ! command -v rclone >/dev/null 2>&1; then
    log "Instalando fuse3 e rclone de forma nao-interativa..."
    apt-get update -qq
    apt-get -y -qq install fuse3 rclone
fi

# 3. Idempotencia em /etc/fuse.conf: garantir user_allow_other ativo
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

# 4. Higienizacao de legados: parar e mascarar rclone-gdrive-mount.service e desmontar /home/ubuntu/GDrive
if id ubuntu >/dev/null 2>&1; then
    log "Verificando e higienizando servicos legados de usuario..."
    su - ubuntu -c "systemctl --user stop rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user disable rclone-gdrive-mount.service 2>/dev/null || true"
    su - ubuntu -c "systemctl --user mask rclone-gdrive-mount.service 2>/dev/null || true"

    if mountpoint -q /home/ubuntu/GDrive 2>/dev/null; then
        log "Desmontando /home/ubuntu/GDrive legado..."
        fusermount -u -z /home/ubuntu/GDrive 2>/dev/null || true
    fi
fi

# Desativa servico de sistema legado se existir
if systemctl is-active --quiet rclone-gdrive.service 2>/dev/null; then
    log "Desativando servico de sistema legado rclone-gdrive.service..."
    systemctl stop rclone-gdrive.service 2>/dev/null || true
    systemctl disable rclone-gdrive.service 2>/dev/null || true
fi

# 5. Criacao de diretorios operacionais
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

# 6. Instalacao de /usr/local/bin/gdrive-vault-hydrate com modo 0755
log "Instalando /usr/local/bin/gdrive-vault-hydrate..."
cat <<'EOF_HYDRATE' > /usr/local/bin/gdrive-vault-hydrate
#!/usr/bin/env bash
# /usr/local/bin/gdrive-vault-hydrate
# Hidratação em tempo de execução das credenciais Google Drive a partir do HashiCorp Vault.
# O arquivo gerado fica ESTRITAMENTE em tmpfs (/run/rclone/rclone.conf), mode 0600.
# NUNCA grava tokens em disco persistente.
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

if command -v rclone >/dev/null 2>&1; then
    rclone config show gdrive-main --config "${CONF_FILE}" >/dev/null 2>&1 || fail "sintaxe rclone.conf invalida"
fi

echo "SUCCESS: [gdrive-vault-hydrate] rclone.conf materializado com sucesso em ${CONF_FILE} (tmpfs, mode 0600)"
exit 0
EOF_HYDRATE
chmod 755 /usr/local/bin/gdrive-vault-hydrate

# 7. Instalacao de /usr/local/bin/gdrive-doctor com modo 0755
log "Instalando /usr/local/bin/gdrive-doctor..."
cat <<'EOF_DOCTOR' > /usr/local/bin/gdrive-doctor
#!/usr/bin/env bash
# /usr/local/bin/gdrive-doctor
# Diagnostico de 8 pontos de conformidade operacional do Google Drive Fleet Mount (/mnt/gdrive).
# Suporta saida legivel em texto tabular e JSON estruturado (--json).
# Exit codes: 0 = OK (Todos PASS), 1 = Falha Critica (Ao menos 1 FAIL), 2 = Aviso / Degradado (Ao menos 1 WARN).

set -euo pipefail

JSON_MODE=false
for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=true ;;
    esac
done

HOSTNAME=$(hostname -s 2>/dev/null || cat /etc/hostname 2>/dev/null || echo "unknown-host")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

PASSED_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
TOTAL_CHECKS=8

declare -A CHECK_STATUS
declare -A CHECK_MSG
declare -A CHECK_DETAILS

record_check() {
    local check_id="$1"
    local status="$2"
    local msg="$3"
    local details="${4:-}"

    CHECK_STATUS["$check_id"]="$status"
    CHECK_MSG["$check_id"]="$msg"
    CHECK_DETAILS["$check_id"]="$details"

    case "$status" in
        PASS) PASSED_COUNT=$((PASSED_COUNT + 1)) ;;
        WARN) WARN_COUNT=$((WARN_COUNT + 1)) ;;
        FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    esac
}

# 1. Checagem de /dev/fuse
if [ -c "/dev/fuse" ]; then
    if [ -w "/dev/fuse" ] || [ "$(id -u)" -eq 0 ]; then
        record_check "fuse_kernel" "PASS" "Dispositivo /dev/fuse presente com permissoes adequadas."
    else
        record_check "fuse_kernel" "WARN" "/dev/fuse presente mas sem permissao de escrita direta para usuario nao-root."
    fi
else
    record_check "fuse_kernel" "FAIL" "Dispositivo /dev/fuse inexistente no host (modulo fuse nao carregado)."
fi

# 2. Checagem de /etc/fuse.conf e user_allow_other
if [ -f "/etc/fuse.conf" ]; then
    if grep -q '^[[:space:]]*user_allow_other' /etc/fuse.conf; then
        record_check "fuse_conf" "PASS" "Diretiva user_allow_other ativa em /etc/fuse.conf."
    else
        record_check "fuse_conf" "FAIL" "Diretiva user_allow_other ausente ou comentada em /etc/fuse.conf."
    fi
else
    record_check "fuse_conf" "FAIL" "Arquivo /etc/fuse.conf inexistente."
fi

# 3. Checagem do binario rclone
if command -v rclone >/dev/null 2>&1; then
    RCLONE_VER=$(rclone --version 2>/dev/null | head -n 1 || echo "rclone unknown")
    record_check "rclone_binary" "PASS" "Binario rclone instalado e acessivel." "$RCLONE_VER"
else
    record_check "rclone_binary" "FAIL" "Binario rclone nao encontrado no PATH."
fi

# 4. Checagem de conectividade com HashiCorp Vault
VAULT_OK=false
VAULT_ENDPOINT=""
for ep in "https://10.13.1.13:8202" "https://10.100.100.3:8202"; do
    if command -v curl >/dev/null 2>&1; then
        if curl -k -s --connect-timeout 2 "${ep}/v1/sys/health" >/dev/null 2>&1; then
            VAULT_OK=true
            VAULT_ENDPOINT="$ep"
            break
        fi
    elif command -v nc >/dev/null 2>&1; then
        HOST_IP=$(echo "$ep" | sed -e 's|https://||' -e 's|:.*||')
        if nc -z -w 2 "$HOST_IP" 8202 2>/dev/null; then
            VAULT_OK=true
            VAULT_ENDPOINT="$ep"
            break
        fi
    fi
done

if [ "$VAULT_OK" = true ]; then
    record_check "vault_connectivity" "PASS" "Conectividade confirmada com HashiCorp Vault." "$VAULT_ENDPOINT"
else
    record_check "vault_connectivity" "FAIL" "Inacessivel: Falha de conexao com HashiCorp Vault (10.13.1.13/10.100.100.3:8202)."
fi

# 5. Checagem de credenciais omni-storage no Vault
VAULT_ENV_BIN=""
if command -v atius-vault-env >/dev/null 2>&1; then
    VAULT_ENV_BIN="atius-vault-env"
elif [ -x "/home/ubuntu/.local/bin/atius-vault-env" ]; then
    VAULT_ENV_BIN="/home/ubuntu/.local/bin/atius-vault-env"
elif [ -x "/usr/local/sbin/atius-vault-export-env" ]; then
    VAULT_ENV_BIN="sudo /usr/local/sbin/atius-vault-export-env"
fi

if [ -n "$VAULT_ENV_BIN" ]; then
    TEST_ENV=""
    if [ "$(id -u)" -eq 0 ] && id ubuntu >/dev/null 2>&1; then
        TEST_ENV=$(su - ubuntu -c "$VAULT_ENV_BIN omni-storage" 2>/dev/null || true)
    else
        TEST_ENV=$($VAULT_ENV_BIN omni-storage 2>/dev/null || true)
    fi

    HAS_ID=$(echo "$TEST_ENV" | grep -q "GDRIVE_CLIENT_ID=" && echo "yes" || echo "no")
    HAS_SECRET=$(echo "$TEST_ENV" | grep -q "GDRIVE_CLIENT_SECRET=" && echo "yes" || echo "no")
    HAS_TOKEN=$(echo "$TEST_ENV" | grep -q "GDRIVE_REFRESH_TOKEN=" && echo "yes" || echo "no")

    if [ "$HAS_ID" = "yes" ] && [ "$HAS_SECRET" = "yes" ] && [ "$HAS_TOKEN" = "yes" ]; then
        record_check "vault_secrets" "PASS" "Credenciais omni-storage presentes e validas no Vault."
    else
        record_check "vault_secrets" "FAIL" "Credenciais ausentes ou incompletas no profile omni-storage."
    fi
else
    record_check "vault_secrets" "WARN" "Helper atius-vault-env nao instalado no PATH local."
fi

# 6. Conectividade com Google Drive API (DNS e TLS 443)
GOOGLE_OK=false
if command -v curl >/dev/null 2>&1; then
    if curl -s --connect-timeout 3 -I "https://www.googleapis.com" >/dev/null 2>&1; then
        GOOGLE_OK=true
    fi
elif command -v nc >/dev/null 2>&1; then
    if nc -z -w 3 www.googleapis.com 443 2>/dev/null; then
        GOOGLE_OK=true
    fi
fi

if [ "$GOOGLE_OK" = true ]; then
    record_check "google_api_connectivity" "PASS" "Resolucao DNS e handshake TLS com www.googleapis.com:443 confirmados."
else
    record_check "google_api_connectivity" "FAIL" "Falha ao alcancar www.googleapis.com:443 (bloqueio DNS/Firewall)."
fi

# 7. Espaco em disco e headroom para VFS cache
TARGET_CACHE_DIR="/var/cache/rclone-gdrive"
mkdir -p "$TARGET_CACHE_DIR" 2>/dev/null || true
AVAIL_KB=$(df -k "$TARGET_CACHE_DIR" 2>/dev/null | tail -1 | awk '{print $4}' || echo "0")
AVAIL_GB=$((AVAIL_KB / 1024 / 1024))

case "$HOSTNAME" in
    atius-srv-1*) REQ_GB=3 ;;
    atius-srv-2*) REQ_GB=10 ;;
    atius-srv-3*) REQ_GB=5 ;;
    atius-srv-4*) REQ_GB=30 ;;
    horistic-srv*) REQ_GB=10 ;;
    *) REQ_GB=4 ;;
esac

if [ "$AVAIL_GB" -ge "$((REQ_GB * 2))" ]; then
    record_check "vfs_disk_headroom" "PASS" "Espaco em disco saudavel (${AVAIL_GB}GB livres, cota VFS=${REQ_GB}GB)."
elif [ "$AVAIL_GB" -ge "$REQ_GB" ]; then
    record_check "vfs_disk_headroom" "WARN" "Espaco livre suficiente mas proximo da cota (${AVAIL_GB}GB livres, cota VFS=${REQ_GB}GB)."
else
    record_check "vfs_disk_headroom" "FAIL" "Espaco em disco insuficiente (${AVAIL_GB}GB livres < cota VFS ${REQ_GB}GB)."
fi

# 8. Ausencia de montagens ou units legadas conflitantes
CONFLICT_FOUND=false
CONFLICT_MSG=""
if [ "$(id -u)" -eq 0 ] && id ubuntu >/dev/null 2>&1; then
    LEGACY_SVC=$(su - ubuntu -c "systemctl --user is-active rclone-gdrive-mount.service 2>/dev/null || true")
elif [ "$(id -un)" = "ubuntu" ]; then
    LEGACY_SVC=$(systemctl --user is-active rclone-gdrive-mount.service 2>/dev/null || true)
else
    LEGACY_SVC="unknown"
fi
if [ "$LEGACY_SVC" = "active" ]; then
    CONFLICT_FOUND=true
    CONFLICT_MSG="rclone-gdrive-mount.service ativo no escopo user de ubuntu."
fi
if mountpoint -q /home/ubuntu/GDrive 2>/dev/null; then
    CONFLICT_FOUND=true
    CONFLICT_MSG="${CONFLICT_MSG} Mount legado ativo em /home/ubuntu/GDrive."
fi

if [ "$CONFLICT_FOUND" = true ]; then
    record_check "no_legacy_mounts" "FAIL" "Conflito legado detectado: ${CONFLICT_MSG}"
else
    record_check "no_legacy_mounts" "PASS" "Nenhum servico ou mount legado concorrente em execucao."
fi

OVERALL_STATUS="PASS"
EXIT_CODE=0
if [ "$FAIL_COUNT" -gt 0 ]; then
    OVERALL_STATUS="FAIL"
    EXIT_CODE=1
elif [ "$WARN_COUNT" -gt 0 ]; then
    OVERALL_STATUS="WARN"
    EXIT_CODE=2
fi

if [ "$JSON_MODE" = true ]; then
    cat <<EOF
{
  "host": "${HOSTNAME}",
  "timestamp": "${TIMESTAMP}",
  "status": "${OVERALL_STATUS}",
  "passed": ${PASSED_COUNT},
  "warnings": ${WARN_COUNT},
  "failures": ${FAIL_COUNT},
  "total": ${TOTAL_CHECKS},
  "checks": {
    "fuse_kernel": {"status": "${CHECK_STATUS[fuse_kernel]}", "message": "${CHECK_MSG[fuse_kernel]}"},
    "fuse_conf": {"status": "${CHECK_STATUS[fuse_conf]}", "message": "${CHECK_MSG[fuse_conf]}"},
    "rclone_binary": {"status": "${CHECK_STATUS[rclone_binary]}", "message": "${CHECK_MSG[rclone_binary]}"},
    "vault_connectivity": {"status": "${CHECK_STATUS[vault_connectivity]}", "message": "${CHECK_MSG[vault_connectivity]}"},
    "vault_secrets": {"status": "${CHECK_STATUS[vault_secrets]}", "message": "${CHECK_MSG[vault_secrets]}"},
    "google_api_connectivity": {"status": "${CHECK_STATUS[google_api_connectivity]}", "message": "${CHECK_MSG[google_api_connectivity]}"},
    "vfs_disk_headroom": {"status": "${CHECK_STATUS[vfs_disk_headroom]}", "message": "${CHECK_MSG[vfs_disk_headroom]}"},
    "no_legacy_mounts": {"status": "${CHECK_STATUS[no_legacy_mounts]}", "message": "${CHECK_MSG[no_legacy_mounts]}"}
  }
}
EOF
else
    echo "================================================================================"
    echo " ATIUS FLEET GOOGLE DRIVE DOCTOR — AUDITORIA DE 8 PONTOS"
    echo " Host: ${HOSTNAME} | Timestamp: ${TIMESTAMP} | Status Global: [${OVERALL_STATUS}]"
    echo "================================================================================"
    printf "%-25s %-8s %s\n" "VERIFICACAO" "STATUS" "DETALHES"
    echo "--------------------------------------------------------------------------------"
    for check_id in "fuse_kernel" "fuse_conf" "rclone_binary" "vault_connectivity" "vault_secrets" "google_api_connectivity" "vfs_disk_headroom" "no_legacy_mounts"; do
        printf "%-25s [%-4s] %s\n" "$check_id" "${CHECK_STATUS[$check_id]}" "${CHECK_MSG[$check_id]}"
    done
    echo "================================================================================"
    echo "Resultado: ${PASSED_COUNT}/${TOTAL_CHECKS} Aprovados, ${WARN_COUNT} Avisos, ${FAIL_COUNT} Falhas."
fi

exit $EXIT_CODE
EOF_DOCTOR
chmod 755 /usr/local/bin/gdrive-doctor

# 8. Deteccao de hostname e gravacao de /etc/default/gdrive-mount com cotas VFS
HOSTNAME_RAW=$(hostname -s 2>/dev/null || cat /etc/hostname 2>/dev/null || echo "unknown-host")
HOSTNAME_LOWER=$(echo "${HOSTNAME_RAW}" | tr '[:upper:]' '[:lower:]')

case "${HOSTNAME_LOWER}" in
    atius-srv-1*)
        CACHE_MAX_SIZE="3G"
        CACHE_MAX_AGE="6h"
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
    horistic-srv*)
        CACHE_MAX_SIZE="10G"
        CACHE_MAX_AGE="24h"
        ;;
    *)
        CACHE_MAX_SIZE="4G"
        CACHE_MAX_AGE="12h"
        ;;
esac

log "Host identificado como '${HOSTNAME_LOWER}'. Gravando /etc/default/gdrive-mount (size=${CACHE_MAX_SIZE}, age=${CACHE_MAX_AGE})..."
cat <<EOF > /etc/default/gdrive-mount
# Configuracoes de cota VFS geradas pelo omni::gdrive-fleet-setup para ${HOSTNAME_LOWER}
CACHE_MAX_SIZE=${CACHE_MAX_SIZE}
CACHE_MAX_AGE=${CACHE_MAX_AGE}
EOF
chmod 644 /etc/default/gdrive-mount

# 9. Instalacao de /etc/systemd/system/gdrive-mount.service
UNIT_FILE="/etc/systemd/system/gdrive-mount.service"
log "Instalando unit systemd ${UNIT_FILE}..."

cat <<'EOF_UNIT' > "${UNIT_FILE}"
[Unit]
Description=Atius Fleet Google Drive FUSE Mount
Documentation=man:rclone(1) https://atius.com.br
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory=/mnt/gdrive

[Service]
Type=notify
NotifyAccess=all
Restart=on-failure
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s
LimitNOFILE=65536

# Governanca de Recursos do Host (Contencao CPU <= 20% do total)
CPUQuota=80%
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

# Carga dinamica de quotas por host (com fallback seguro caso o arquivo nao exista)
EnvironmentFile=-/etc/default/gdrive-mount
Environment="CACHE_MAX_SIZE=4G"
Environment="CACHE_MAX_AGE=12h"

# Preparacao do tmpfs e injecao de credenciais Vault (Zero-Disk Footprint)
ExecStartPre=-/bin/mkdir -p /run/rclone /var/cache/rclone-gdrive /mnt/gdrive
ExecStartPre=-/bin/chmod 700 /run/rclone /var/cache/rclone-gdrive
ExecStartPre=/usr/local/bin/gdrive-vault-hydrate

# Rclone Mount com Full VFS Cache, Rate Pacing e Pacing de API
ExecStart=/usr/bin/rclone mount gdrive-main: /mnt/gdrive \
    --config /run/rclone/rclone.conf \
    --allow-other \
    --umask 022 \
    --dir-cache-time 72h \
    --poll-interval 1m \
    --vfs-cache-mode full \
    --vfs-cache-max-size ${CACHE_MAX_SIZE} \
    --vfs-cache-max-age ${CACHE_MAX_AGE} \
    --vfs-read-chunk-size 32M \
    --vfs-read-chunk-size-limit 256M \
    --cache-dir /var/cache/rclone-gdrive \
    --buffer-size 16M \
    --tpslimit 4 \
    --tpslimit-burst 1 \
    --drive-pacer-min-sleep 100ms \
    --drive-pacer-burst 1 \
    --transfers 2 \
    --checkers 4 \
    --attr-timeout 1s \
    --log-level INFO \
    --syslog-facility DAEMON

# Desmontagem limpa lazy e purga imediata de credenciais efemeras em tmpfs
ExecStop=/bin/fusermount -u -z /mnt/gdrive
ExecStopPost=-/bin/rm -f /run/rclone/rclone.conf

[Install]
WantedBy=multi-user.target
EOF_UNIT

chmod 644 "${UNIT_FILE}"

# 10. Recarregar systemd, habilitar e iniciar servico
log "Recarregando systemd daemon e habilitando gdrive-mount.service..."
systemctl daemon-reload
systemctl enable gdrive-mount.service

# Desmonta caso ja esteja montado antes do reinicio
if mountpoint -q "${MOUNTPOINT}" 2>/dev/null; then
    fusermount -u -z "${MOUNTPOINT}" 2>/dev/null || true
fi

log "Iniciando gdrive-mount.service..."
systemctl restart gdrive-mount.service

# 11. Validacao de mountpoint (/mnt/gdrive)
log "Aguardando mountpoint ${MOUNTPOINT} ficar disponivel..."
MOUNTED=false
for i in {1..15}; do
    if mountpoint -q "${MOUNTPOINT}" 2>/dev/null && systemctl is-active --quiet gdrive-mount.service 2>/dev/null; then
        MOUNTED=true
        break
    fi
    sleep 1
done

if [ "${MOUNTED}" != "true" ]; then
    err "Mountpoint ${MOUNTPOINT} nao foi montado a tempo ou gdrive-mount.service falhou."
    systemctl status gdrive-mount.service --no-pager 2>/dev/null || true
    journalctl -u gdrive-mount.service -n 25 --no-pager 2>/dev/null || true
    printf '{"status": "FAIL", "host": "%s", "mountpoint": "%s", "service_active": false}\n' "${HOSTNAME_LOWER}" "${MOUNTPOINT}"
    exit 1
fi

ITEMS_COUNT=$(ls -1 "${MOUNTPOINT}" 2>/dev/null | wc -l || echo "0")
log "SUCCESS: Google Drive montado com sucesso em ${MOUNTPOINT} (items: ${ITEMS_COUNT})."

# 12. Emissao de payload JSON na ultima linha de stdout
printf '{"status": "PASS", "host": "%s", "mountpoint": "%s", "service_active": true}\n' "${HOSTNAME_LOWER}" "${MOUNTPOINT}"
exit 0
