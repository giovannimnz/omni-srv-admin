#!/usr/bin/env bash
set -euo pipefail

export PM2_HOME="/home/ubuntu/.pm2"
PM2_BIN="/usr/local/bin/pm2"
DUMP="$PM2_HOME/dump.pm2"

"$PM2_BIN" save --force
chmod 0600 "$DUMP"

if rg -q 'ATIUS_MCP_TOKEN|OCI_ADMIN_SECRET_KEY' "$DUMP"; then
  echo "ERRO: dump PM2 contém nomes de variáveis sensíveis; snapshot rejeitado" >&2
  exit 1
fi

jq -e '
  [ .[] | select((.namespace // .pm2_env.namespace) == "oci-admin") | .name ] | sort
  == ["oci-admin-mcp-http", "oci-admin-web"]
' "$DUMP" >/dev/null

echo "PM2 dump salvo sem env sensível e com namespace oci-admin completo"
