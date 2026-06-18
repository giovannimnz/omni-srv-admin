#!/usr/bin/env bash
# uninstall-monitoring.sh — remove the entire observability stack from ATIUS-SRV-1.
#
# Part of Phase 17 (M005 Observability + RWX). Removes:
#   - kube-prometheus-stack release (omni-monitoring)
#   - loki-stack release (omni-loki)
#   - omni-monitoring-rules PrometheusRule
#   - Grafana dashboard ConfigMaps labeled grafana_dashboard=1
#   - The `monitoring` namespace (if empty)
#
# It does NOT remove the local-path StorageClass or its PVs that may
# have been created earlier (the helm uninstall handles those).
#
# Usage:
#   uninstall-monitoring.sh
#   uninstall-monitoring.sh --keep-namespace   # leave the namespace behind
#   uninstall-monitoring.sh --yes              # skip confirmation
set -euo pipefail

KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
KPS_NAMESPACE="${KPS_NAMESPACE:-monitoring}"
LOKI_RELEASE="${LOKI_RELEASE:-omni-loki}"
KPS_RELEASE="${KPS_RELEASE:-omni-monitoring}"
KEEP_NAMESPACE=0
YES=0
for arg in "$@"; do
  case "$arg" in
    --keep-namespace) KEEP_NAMESPACE=1 ;;
    --yes) YES=1 ;;
    --help|-h) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

if [[ "$YES" -ne 1 ]]; then
  echo "This will remove the observability stack from namespace ${KPS_NAMESPACE}."
  echo "Press Enter to continue or Ctrl-C to abort."
  read -r _
fi

command -v helm >/dev/null || { echo "[fatal] helm not found" >&2; exit 1; }
command -v sudo >/dev/null || { echo "[fatal] sudo not found" >&2; exit 1; }
sudo -n true 2>/dev/null || { echo "[fatal] sudo -n failed" >&2; exit 1; }

KCTL=(sudo -n k3s kubectl --kubeconfig "${KUBECONFIG}")

echo "[info] uninstalling ${KPS_RELEASE}"
helm uninstall "${KPS_RELEASE}" --namespace "${KPS_NAMESPACE}" --ignore-not-found || true

echo "[info] uninstalling ${LOKI_RELEASE}"
helm uninstall "${LOKI_RELEASE}" --namespace "${KPS_NAMESPACE}" --ignore-not-found || true

echo "[info] removing prometheus rules"
"${KCTL[@]}" -n "${KPS_NAMESPACE}" delete prometheusrule -l app.kubernetes.io/part-of=omni-srv-admin --ignore-not-found || true

echo "[info] removing grafana dashboard ConfigMaps"
"${KCTL[@]}" -n "${KPS_NAMESPACE}" delete cm -l grafana_dashboard=1 --ignore-not-found || true

if [[ "${KEEP_NAMESPACE}" -eq 0 ]]; then
  echo "[info] removing namespace ${KPS_NAMESPACE} (if empty)"
  "${KCTL[@]}" delete namespace "${KPS_NAMESPACE}" --ignore-not-found 2>/dev/null || true
fi

echo "[ok] uninstall complete"
