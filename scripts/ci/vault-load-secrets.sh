#!/usr/bin/env bash
# scripts/ci/vault-load-secrets.sh
# Carrega segredos governados do HashiCorp Vault em atius-srv-3 (https://10.1.1.3:8202 / 10.13.1.13:8202)
set -euo pipefail

PROFILE="${1:-pipeline}"
VAULT_HELPER="$HOME/.local/bin/atius-vault-env"

if [[ ! -x "$VAULT_HELPER" ]]; then
  echo "ERROR: Vault helper $VAULT_HELPER not found or not executable" >&2
  return 1 2>/dev/null || exit 1
fi

echo "==> Conectando ao HashiCorp Vault para profile: $PROFILE"
EXPORT_OUTPUT="$("$VAULT_HELPER" "$PROFILE")"
VAR_COUNT=$(echo "$EXPORT_OUTPUT" | grep -c "^export " || true)

echo "==> Sucesso: $VAR_COUNT variáveis exportadas do cofre HashiCorp Vault para a pipeline."

# Aplicar na sessão atual
eval "$EXPORT_OUTPUT"

# Se rodando dentro do GitHub Actions, registrar máscara e persistir em GITHUB_ENV
if [[ -n "${GITHUB_ENV:-}" && -f "${GITHUB_ENV:-}" ]]; then
  while IFS='=' read -r key val; do
    # Remover 'export ' prefix
    key="${key#export }"
    # Remover aspas envolventes se houver
    val="${val#\'}"
    val="${val%\'}"
    val="${val#\"}"
    val="${val%\"}"
    if [[ -n "$key" && -n "$val" ]]; then
      echo "::add-mask::$val"
      echo "$key=$val" >> "$GITHUB_ENV"
    fi
  done < <(echo "$EXPORT_OUTPUT")
fi
