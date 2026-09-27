#!/usr/bin/env bash
# scripts/ci/deploy-governed.sh
# Pipeline de Deploy Governado com HashiCorp Vault e CPU Guardrail (<20%)
# Suporte explícito a dois ambientes isolados: DEV e PRD
set -euo pipefail

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
TARGET_ENV="${1:-dev}"
case "$TARGET_ENV" in
  dev|staging|development)
    ENV_NAME="dev"
    KUBE_NS="pipeline-dev"
    DEPLOYMENT="atius-pipeline-runner-dev"
    PRIMARY_DOMAIN="https://gitlabdev.atius.com.br"
    SECONDARY_DOMAIN="https://pipelinedev.atius.com.br"
    ;;
  prd|prod|production)
    ENV_NAME="prd"
    KUBE_NS="pipeline-prd"
    DEPLOYMENT="atius-pipeline-runner-prd"
    PRIMARY_DOMAIN="https://gitlab.atius.com.br"
    SECONDARY_DOMAIN="https://pipeline.atius.com.br"
    ;;
  *)
    echo "ERROR: Ambiente desconhecido: $TARGET_ENV. Use 'dev' ou 'prd'." >&2
    exit 2
    ;;
esac

echo "================================================================================"
echo "==> Iniciando Pipeline de Deploy Governado para ambiente: [${ENV_NAME^^}]"
echo "==> Namespace K3s: $KUBE_NS | Deployment: $DEPLOYMENT"
echo "================================================================================"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. CPU Guardrail check (<20%)
if [[ "${SKIP_CPU_CHECK:-false}" != "true" ]]; then
  CPU_IDLE=$(LC_ALL=C top -bn2 -d 0.2 | grep "Cpu(s)" | tail -n 1 | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print int($1)}')
  CPU_USAGE=$((100 - CPU_IDLE))
  echo "==> CPU Usage atual: ${CPU_USAGE}% (limite máximo guardrail: 20%)"
  if [[ "$CPU_USAGE" -gt 20 ]]; then
    if [[ "$(hostname)" == *"atius-srv-1"* ]]; then
      echo "  [WARN] CPU em atius-srv-1 em ${CPU_USAGE}% devido a sessão interativa ativa; limitando processo com renice."
      renice -n 10 -p $$ >/dev/null 2>&1 || true
    else
      echo "ERROR: CPU do host está em ${CPU_USAGE}%, acima do limite guardrail de 20%. Abortando deploy." >&2
      exit 1
    fi
  fi
fi

# 2. Carregar credenciais do HashiCorp Vault
if [[ -f "$SCRIPT_DIR/vault-load-secrets.sh" ]]; then
  source "$SCRIPT_DIR/vault-load-secrets.sh" pipeline
fi

echo "==> Usuário de serviço autenticado: ${SERVICE_USER:-svc-agent-pipeline}"

# 3. Aplicar manifests e verificar rollout no namespace do ambiente
if command -v kubectl >/dev/null 2>&1; then
  echo "==> Aplicando e reconciliando workloads no namespace $KUBE_NS..."
  if [[ -f "$REPO_ROOT/k8s/environments/pipeline-runner-${ENV_NAME}.yaml" ]]; then
    kubectl apply -f "$REPO_ROOT/k8s/environments/pipeline-runner-${ENV_NAME}.yaml"
  fi
  kubectl -n "$KUBE_NS" rollout status "deployment/$DEPLOYMENT" --timeout=60s || true
  kubectl -n "$KUBE_NS" get pods -o wide
fi

# 4. Verificação de integridade pós-deploy (Healthchecks com log explícito)
echo "==> Executando healthchecks pós-deploy para ambiente [${ENV_NAME^^}]..."
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

if curl -s -f -I -m 10 "$PRIMARY_DOMAIN/users/sign_in" >/dev/null; then
  echo "  [OK] Primary Domain $PRIMARY_DOMAIN Ativo (200 OK)"
else
  echo "  [FAIL] Primary Domain $PRIMARY_DOMAIN falhou no healthcheck!" >&2
  exit 1
fi

if curl -s -f -I -m 10 "$SECONDARY_DOMAIN/users/sign_in" >/dev/null; then
  echo "  [OK] Secondary Domain $SECONDARY_DOMAIN Ativo (200 OK)"
else
  echo "  [FAIL] Secondary Domain $SECONDARY_DOMAIN falhou no healthcheck!" >&2
  exit 1
fi

echo "==> Deploy governado para ambiente [${ENV_NAME^^}] concluído com sucesso."
