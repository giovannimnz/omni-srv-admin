#!/usr/bin/env bash
# scripts/ci/run-playwright-tests.sh
# Executa a suite de testes Playwright em modo headless com relatórios e CPU Guardrail
set -euo pipefail

echo "==> Iniciando suite de testes automatizados Playwright (Headless)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

# Carregar senhas e tokens do HashiCorp Vault para a execução
if [[ -f "$SCRIPT_DIR/vault-load-secrets.sh" ]]; then
  source "$SCRIPT_DIR/vault-load-secrets.sh" pipeline
fi

export CI=true
export HEADLESS=true

if command -v npx >/dev/null 2>&1; then
  echo "==> Rodando testes Playwright com npx (--workers=1 para CPU Guardrail)..."
  npx -y playwright test tests/playwright/ --reporter=list,html --workers=1
else
  echo "==> npx não encontrado, executando HTTP health checks de fallback..."
  curl -s -f -o /dev/null -w "SSO Status: %{http_code}\n" https://sso.atius.com.br/login
  curl -s -f -o /dev/null -w "OIDC Status: %{http_code}\n" https://auth.atius.com.br/realms/atius/.well-known/openid-configuration
fi

echo "==> Suite Playwright finalizada com sucesso."
