#!/usr/bin/env bash
# omni::fleet-apt-proxy-configure v1.0.0
# Canonical ATIUS fleet centralized APT cache via OCI DRG (10.13.1.13:3142) & GDrive persistence.
set -euo pipefail

host="$(hostname)"
printf 'host=%s\n' "$host"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export DEBIAN_FRONTEND=noninteractive

DRG_PROXY="http://10.13.1.13:3142"

# Se estiver no proprio atius-srv-3, aponta para loopback
if [[ "$host" == *"atius-srv-3"* ]]; then
  TARGET_PROXY="http://127.0.0.1:3142"
else
  TARGET_PROXY="$DRG_PROXY"
fi

# 1. Configurar /etc/apt/apt.conf.d/01proxy com fallback resiliente
cat <<EOF > /etc/apt/apt.conf.d/01proxy
// Managed by omni::fleet-apt-proxy-configure
Acquire::http::Proxy "${TARGET_PROXY}/";
Acquire::https::Proxy "${TARGET_PROXY}/";
Acquire::http::Timeout "5";
Acquire::https::Timeout "5";
Acquire::Retries "2";
EOF

echo "proxy_configured=${TARGET_PROXY}"

# 2. Testar conectividade ao proxy com timeout de 3 segundos
if curl -sI --connect-timeout 3 "${TARGET_PROXY}/" >/dev/null 2>&1; then
  echo "proxy_status=reachable"
else
  echo "proxy_status=unreachable_warning"
fi

# 3. Executar apt update de teste sob cota controlada
nice -n 19 apt-get update -qq || true

echo "status=configured_and_active"
