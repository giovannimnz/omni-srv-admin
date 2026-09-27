#!/usr/bin/env bash
# scripts/ci/vault-load-secrets.sh
# Carrega segredos governados do HashiCorp Vault em atius-srv-3 (https://10.13.1.13:8202)
set -euo pipefail

PROFILE="${1:-pipeline}"
VAULT_HELPER="$HOME/.local/bin/atius-vault-env"

if [[ ! -x "$VAULT_HELPER" ]]; then
  echo "ERROR: Vault helper $VAULT_HELPER not found or not executable" >&2
  exit 1
fi

echo "==> Conectando ao HashiCorp Vault para profile: $PROFILE"
# Valida conectividade e sintaxe sem vazar valores
EXPORT_OUTPUT="$("$VAULT_HELPER" "$PROFILE")"
VAR_COUNT=$(echo "$EXPORT_OUTPUT" | grep -c "^export " || true)

echo "==> Sucesso: $VAR_COUNT variáveis exportadas do cofre HashiCorp Vault para a pipeline."
eval "$EXPORT_OUTPUT"
