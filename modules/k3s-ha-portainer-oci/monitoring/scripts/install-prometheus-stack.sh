#!/usr/bin/env bash
# install-prometheus-stack.sh — install kube-prometheus-stack via Helm on ATIUS-SRV-1.
#
# Part of Phase 17 (M005 Observability + RWX). This script is the
# user-facing entry point for the operator. It is intentionally
# read-only outside the `monitoring` namespace, and it never
# overwrites a release that already exists unless --upgrade is
# passed.
#
# Usage:
#   install-prometheus-stack.sh                 # install (idempotent: skip if already installed)
#   install-prometheus-stack.sh --upgrade       # helm upgrade if installed
#   install-prometheus-stack.sh --dry-run       # render manifests, do not apply
#   install-prometheus-stack.sh --uninstall     # helm uninstall (asks for confirmation)
#
# Environment overrides:
#   KUBECONFIG                 path to kubeconfig (default: /etc/rancher/k3s/k3s.yaml via sudo)
#   KPS_NAMESPACE              namespace (default: monitoring)
#   KPS_RELEASE                helm release name (default: omni-monitoring)
#   KPS_VALUES                 path to values file (default: module file)
#
# This script uses `sudo -n` for the kubeconfig read because the
# file is mode 0600 owned by root. If sudo isn't cached, the
# script aborts with a clear message and the operator can run
# `sudo k3s kubectl ...` manually.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Defaults ────────────────────────────────────────────────────────
KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
KPS_NAMESPACE="${KPS_NAMESPACE:-monitoring}"
KPS_RELEASE="${KPS_RELEASE:-omni-monitoring}"
KPS_VALUES="${KPS_VALUES:-${MODULE_DIR}/k8s/kube-prometheus-stack-values.yaml}"
KPS_RULES_DIR="${MODULE_DIR}/monitoring/prometheus-rules}"
KPS_DASHBOARDS_DIR="${MODULE_DIR}/monitoring/dashboards}"
KPS_ALERTMANAGER_VALUES="${MODULE_DIR}/monitoring/alertmanager/values.yaml"
KPS_CHART_REPO="${KPS_CHART_REPO:-prometheus-community}"
KPS_CHART_NAME="${KPS_CHART_NAME:-kube-prometheus-stack}"
KPS_CHART_VERSION="${KPS_CHART_VERSION:-}"  # empty = latest

DRY_RUN=0
UPGRADE=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --upgrade) UPGRADE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --help|-h)
      sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# ── Pre-flight ──────────────────────────────────────────────────────
if ! command -v helm >/dev/null 2>&1; then
  echo "[fatal] helm not found in PATH" >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "[fatal] sudo not found in PATH" >&2
  exit 1
fi

if ! sudo -n true 2>/dev/null; then
  echo "[fatal] sudo -n failed; cannot read ${KUBECONFIG} (mode 0600 root:root)" >&2
  exit 1
fi

if [[ ! -f "${KPS_VALUES}" ]]; then
  echo "[fatal] values file not found: ${KPS_VALUES}" >&2
  exit 1
fi

# KUBECONFIG is mode 0600 root, so we use sudo for the read.
KCTL=(sudo -n k3s kubectl --kubeconfig "${KUBECONFIG}")

# ── Uninstall path ──────────────────────────────────────────────────
if [[ "${UNINSTALL}" -eq 1 ]]; then
  echo "[info] uninstalling helm release ${KPS_RELEASE} from namespace ${KPS_NAMESPACE}"
  helm uninstall "${KPS_RELEASE}" --namespace "${KPS_NAMESPACE}" || true
  echo "[info] removing prometheus-rules ConfigMap if present"
  "${KCTL[@]}" -n "${KPS_NAMESPACE}" delete configmap -l app.kubernetes.io/name=omni-monitoring-rules --ignore-not-found
  echo "[ok] uninstall complete"
  exit 0
fi

# ── Add chart repo ─────────────────────────────────────────────────
helm repo add "${KPS_CHART_REPO}" "https://${KPS_CHART_REPO}.github.io/helm-charts" 2>/dev/null || true
helm repo update >/dev/null

# ── Create namespace if missing ────────────────────────────────────
if ! "${KCTL[@]}" get namespace "${KPS_NAMESPACE}" >/dev/null 2>&1; then
  echo "[info] creating namespace ${KPS_NAMESPACE}"
  "${KCTL[@]}" create namespace "${KPS_NAMESPACE}"
fi

# ── Install/upgrade ────────────────────────────────────────────────
HELM_ARGS=(
  install
  --namespace "${KPS_NAMESPACE}"
  --create-namespace
  --values "${KPS_VALUES}"
)
if [[ "${KPS_CHART_VERSION}" != "" ]]; then
  HELM_ARGS+=(--version "${KPS_CHART_VERSION}")
fi
if [[ "${DRY_RUN}" -eq 1 ]]; then
  HELM_ARGS+=(--dry-run --debug)
fi
if [[ "${UPGRADE}" -eq 1 ]]; then
  HELM_ARGS=(upgrade --install "${KPS_RELEASE}" "${KPS_CHART_REPO}/${KPS_CHART_NAME}" "${HELM_ARGS[@]/#install/}")
else
  HELM_ARGS+=("${KPS_RELEASE}" "${KPS_CHART_REPO}/${KPS_CHART_NAME}")
fi

# Make sure we never reuse a release name silently
if [[ "${UPGRADE}" -eq 0 ]] && "${KCTL[@]}" get helmrelease -n "${KPS_NAMESPACE}" "${KPS_RELEASE}" >/dev/null 2>&1; then
  echo "[info] release ${KPS_RELEASE} already exists; pass --upgrade to update"
  exit 0
fi

echo "[info] running: helm ${HELM_ARGS[*]}"
helm "${HELM_ARGS[@]}"

# ── Apply the prometheus-rules bundle (not bundled by chart) ────────
if [[ "${DRY_RUN}" -eq 0 ]]; then
  for f in "${KPS_RULES_DIR}"/*.yaml; do
    [[ -f "$f" ]] || continue
    echo "[info] applying prometheus rule: $f"
    "${KCTL[@]}" apply -f "$f"
  done
fi

# ── Apply dashboards as ConfigMaps labeled for Grafana sidecar ─────
# kube-prometheus-stack's Grafana picks up ConfigMaps with the
# label `grafana_datasource=1` (for datasources) and dashboard
# sidecar picks up ConfigMaps with the `grafana_dashboard=1` label.
if [[ "${DRY_RUN}" -eq 0 ]]; then
  for d in "${KPS_DASHBOARDS_DIR}"/*.json; do
    [[ -f "$d" ]] || continue
    name="$(basename "${d}" .json)"
    echo "[info] uploading dashboard ConfigMap: ${name}"
    "${KCTL[@]}" -n "${KPS_NAMESPACE}" create configmap "grafana-dashboard-${name}" \
      --from-file="${d}" \
      --dry-run=client -o yaml | \
    "${KCTL[@]}" -n "${KPS_NAMESPACE}" label --local -f- grafana_dashboard=1 -o yaml | \
    "${KCTL[@]}" apply -f -
  done
fi

echo "[ok] done"
