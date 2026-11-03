#!/usr/bin/env bash
# /usr/local/bin/gdrive-doctor ou modules/fleet-gdrive/scripts/gdrive-doctor.sh
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

# Contadores
PASSED_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
TOTAL_CHECKS=8

# Arrays associativos simulados para compatibilidade Bash 3/4
declare -A CHECK_STATUS
declare -A CHECK_MSG
declare -A CHECK_DETAILS

# Helper para registrar resultado
record_check() {
    local check_id="$1"
    local status="$2" # PASS, WARN, FAIL
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
    # Teste de extracao sem vazar credenciais
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

# Host-specific quota requirements (GB)
case "$HOSTNAME" in
    atius-srv-1*) REQ_GB=5 ;;
    atius-srv-2*) REQ_GB=10 ;;
    atius-srv-3*) REQ_GB=5 ;;
    atius-srv-4*) REQ_GB=30 ;;
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

# Determinacao do status global e exit code
OVERALL_STATUS="PASS"
EXIT_CODE=0
if [ "$FAIL_COUNT" -gt 0 ]; then
    OVERALL_STATUS="FAIL"
    EXIT_CODE=1
elif [ "$WARN_COUNT" -gt 0 ]; then
    OVERALL_STATUS="WARN"
    EXIT_CODE=2
fi

# Emissao da Saida
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
