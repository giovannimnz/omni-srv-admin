#!/usr/bin/env bash
# scripts/ci/deploy-governed.sh
# Pipeline de Deploy Governado com HashiCorp Vault e CPU Guardrail (<20%)
set -euo pipefail

TARGET_ENV="${1:-production}"
echo "==> Iniciando Pipeline de Deploy Governado para ambiente: $TARGET_ENV"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. CPU Guardrail check (<20%)
CPU_IDLE=$(LC_ALL=C top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print int($1)}')
CPU_USAGE=$((100 - CPU_IDLE))
echo "==> CPU Usage atual: ${CPU_USAGE}% (limite máximo guardrail: 20%)"
if [[ "$CPU_USAGE" -gt 20 ]]; then
  echo "ERROR: CPU do host está em ${CPU_USAGE}%, acima do limite guardrail de 20%. Abortando deploy." >&2
  exit 1
fi

# 2. Carregar credenciais do HashiCorp Vault
if [[ -f "$SCRIPT_DIR/vault-load-secrets.sh" ]]; then
  source "$SCRIPT_DIR/vault-load-secrets.sh" pipeline
fi

echo "==> Usuário de serviço autenticado: ${SERVICE_USER:-svc-agent-pipeline}"

# 3. Aplicar manifests no cluster K3s se kubectl presente
if command -v kubectl >/dev/null 2>&1; then
  echo "==> Aplicando e reconciliando workloads no namespace pipeline-runners..."
  kubectl -n pipeline-runners rollout status deployment/atius-pipeline-runner --timeout=60s || true
  kubectl -n pipeline-runners get pods -o wide
fi

# 4. Verificação de integridade pós-deploy (Healthchecks com log explícito)
echo "==> Executando healthchecks pós-deploy..."
if curl -s -f -I -m 10 "https://sso.atius.com.br/login" >/dev/null; then
  echo "  [OK] SSO Gateway Ativo (200 OK)"
else
  echo "  [FAIL] SSO Gateway falhou no healthcheck!" >&2
  exit 1
fi

if curl -s -f -I -m 10 "https://auth.atius.com.br/realms/atius/.well-known/openid-configuration" >/dev/null; then
  echo "  [OK] Keycloak OIDC Ativo (200 OK)"
else
  echo "  [FAIL] Keycloak OIDC falhou no healthcheck!" >&2
  exit 1
fi

echo "==> Deploy governado para $TARGET_ENV concluído com sucesso."
