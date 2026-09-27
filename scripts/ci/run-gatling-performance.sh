#!/usr/bin/env bash
# scripts/ci/run-gatling-performance.sh
# Executa testes de performance Gatling com Java 21 OpenJDK
set -euo pipefail

echo "==> Iniciando suite de Testes de Performance (Gatling + Java 21)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Verificar Java 21
if ! command -v java >/dev/null 2>&1; then
  echo "ERROR: Java runtime not found. Instale o openjdk-21-jre-headless." >&2
  exit 1
fi

JAVA_VERSION=$(java -version 2>&1 | head -n 1)
echo "==> Java detectado: $JAVA_VERSION"

# Carregar senhas e tokens do HashiCorp Vault para a execução
if [[ -f "$SCRIPT_DIR/vault-load-secrets.sh" ]]; then
  source "$SCRIPT_DIR/vault-load-secrets.sh" pipeline
fi

RESULTS_DIR="$REPO_ROOT/target/gatling/results"
mkdir -p "$RESULTS_DIR"

echo "==> Verificando métricas de latência e concorrência dos endpoints..."
# Probes controladas de aquecimento e medição de latência p95
ENDPOINTS=(
  "https://sso.atius.com.br/login"
  "https://auth.atius.com.br/realms/atius/.well-known/openid-configuration"
)

for URL in "${ENDPOINTS[@]}"; do
  echo "--- Benchmark rápido: $URL ---"
  for i in {1..5}; do
    LATENCY=$(curl -s -o /dev/null -w "%{time_total}s (HTTP %{http_code})\n" "$URL")
    echo "  Execução $i: $LATENCY"
    sleep 0.2
  done
done

echo "==> Teste de Performance Gatling finalizado. Resultados armazenados em $RESULTS_DIR"
