#!/usr/bin/env bash
set -Eeuo pipefail
GATEWAY="${ATIUS_ADMIN_EDGE_GATEWAY:-/opt/atius/atius-admin-edge-gateway.js}"
CONFIG="${ATIUS_ADMIN_EDGE_GATEWAY_CONFIG:-/etc/atius/atius-admin-edge-gateway.json}"
: "${ATIUS_ADMIN_EDGE_GRAFANA_USER:=admin}"
: "${ATIUS_ADMIN_EDGE_PORTAINER_USER:=admin}"
ATIUS_ADMIN_EDGE_GRAFANA_PASS="$(tr -d '\r\n' </home/ubuntu/.secrets/grafana-admin-password)"
ATIUS_ADMIN_EDGE_PORTAINER_PASS="$(tr -d '\r\n' </home/ubuntu/.secrets/portainer-admin-password)"
export ATIUS_ADMIN_EDGE_GRAFANA_USER ATIUS_ADMIN_EDGE_GRAFANA_PASS ATIUS_ADMIN_EDGE_PORTAINER_USER ATIUS_ADMIN_EDGE_PORTAINER_PASS
exec /usr/bin/node "$GATEWAY" "$CONFIG"
