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

# Helper para falhas limpas (fail-closed)
fail() {
    rm -f "${CONF_FILE}"
    echo "ERROR: [gdrive-vault-hydrate] $1" >&2
    exit 1
}

# Localiza atius-vault-env
VAULT_ENV_BIN=""
if command -v atius-vault-env >/dev/null 2>&1; then
    VAULT_ENV_BIN="atius-vault-env"
elif [ -x "/home/ubuntu/.local/bin/atius-vault-env" ]; then
    VAULT_ENV_BIN="/home/ubuntu/.local/bin/atius-vault-env"
elif [ -x "/usr/local/sbin/atius-vault-export-env" ]; then
    # Estamos no proprio host do Vault (atius-srv-3)
    VAULT_ENV_BIN="sudo /usr/local/sbin/atius-vault-export-env"
fi

[ -n "${VAULT_ENV_BIN}" ] || fail "atius-vault-env nao encontrado no host"

# Executa e extrai variáveis do profile omni-storage
# Executamos como usuario ubuntu se fomos chamados como root
if [ "$(id -u)" -eq 0 ] && id ubuntu >/dev/null 2>&1; then
    ENV_OUTPUT=$(su - ubuntu -c "${VAULT_ENV_BIN} omni-storage" 2>/dev/null || true)
else
    ENV_OUTPUT=$(${VAULT_ENV_BIN} omni-storage 2>/dev/null || true)
fi

[ -n "${ENV_OUTPUT}" ] || fail "falha ao consultar Vault profile omni-storage"

# Avalia variáveis em subshell seguro
CLIENT_ID=""
CLIENT_SECRET=""
REFRESH_TOKEN=""

while IFS='=' read -r key val; do
    key=$(echo "${key}" | sed -e 's/^export //' | xargs)
    # Remove aspas ao redor do valor
    val=$(echo "${val}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    case "${key}" in
        GDRIVE_CLIENT_ID) CLIENT_ID="${val}" ;;
        GDRIVE_CLIENT_SECRET) CLIENT_SECRET="${val}" ;;
        GDRIVE_REFRESH_TOKEN) REFRESH_TOKEN="${val}" ;;
    esac
done <<< "${ENV_OUTPUT}"

[ -n "${CLIENT_ID}" ] || fail "GDRIVE_CLIENT_ID vazio no retorno do Vault"
[ -n "${CLIENT_SECRET}" ] || fail "GDRIVE_CLIENT_SECRET vazio no retorno do Vault"
[ -n "${REFRESH_TOKEN}" ] || fail "GDRIVE_REFRESH_TOKEN vazio no retorno do Vault"

# Gera token JSON compatível com rclone
TOKEN_JSON=$(printf '{"access_token":"","token_type":"Bearer","refresh_token":"%s"}' "${REFRESH_TOKEN}")

# Escreve rclone.conf no tmpfs
cat <<EOF > "${CONF_FILE}"
[gdrive-main]
type = drive
client_id = ${CLIENT_ID}
client_secret = ${CLIENT_SECRET}
scope = drive
token = ${TOKEN_JSON}
EOF

chmod 600 "${CONF_FILE}"

# Auto-teste sintático sem rede
if command -v rclone >/dev/null 2>&1; then
    rclone config show gdrive-main --config "${CONF_FILE}" >/dev/null 2>&1 || fail "sintaxe rclone.conf invalida"
fi

echo "SUCCESS: [gdrive-vault-hydrate] rclone.conf materializado com sucesso em ${CONF_FILE} (tmpfs, mode 0600)"
exit 0
