#!/usr/bin/env bash
# install-loki.sh — install Loki + Promtail via Helm on ATIUS-SRV-1.
#
# Part of Phase 17 (M005 Observability + RWX). Requires the
# `monitoring` namespace to exist (created by install-prometheus-stack.sh
# or by `--create-namespace` here).
#
# Usage:
#   install-loki.sh                 # install (idempotent: skip if already installed)
#   install-loki.sh --upgrade       # helm upgrade if installed
#   install-loki.sh --dry-run       # render manifests, do not apply
#   install-loki.sh --uninstall     # helm uninstall
#
# The values file is `monitoring/loki/values.yaml` and is the
# single source of truth for the Loki configuration. Edit there,
# then re-run with `--upgrade` to apply changes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
LOKI_NAMESPACE="${LOKI_NAMESPACE:-monitoring}"
LOKI_RELEASE="${LOKI_RELEASE:-omni-loki}"
LOKI_VALUES="${LOKI_VALUES:-${MODULE_DIR}/loki/values.yaml}"
LOKI_CHART_REPO="${LOKI_CHART_REPO:-grafana}"
LOKI_CHART_NAME="${LOKI_CHART_NAME:-loki-stack}"
LOKI_CHART_VERSION="${LOKI_CHART_VERSION:-}"  # empty = latest

DRY_RUN=0
UPGRADE=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --upgrade) UPGRADE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --help|-h)
      sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# ── Pre-flight ──────────────────────────────────────────────────────
command -v helm >/dev/null || { echo "[fatal] helm not found" >&2; exit 1; }
command -v sudo >/dev/null || { echo "[fatal] sudo not found" >&2; exit 1; }
sudo -n true 2>/dev/null || { echo "[fatal] sudo -n failed" >&2; exit 1; }

KCTL=(sudo -n k3s kubectl --kubeconfig "${KUBECONFIG}")

# ── Uninstall path ──────────────────────────────────────────────────
if [[ "${UNINSTALL}" -eq 1 ]]; then
  echo "[info] uninstalling helm release ${LOKI_RELEASE}"
  helm uninstall "${LOKI_RELEASE}" --namespace "${LOKI_NAMESPACE}" || true
  echo "[ok] uninstall complete"
  exit 0
fi

# ── Repo and namespace ─────────────────────────────────────────────
helm repo add "${LOKI_CHART_REPO}" "https://${LOKI_CHART_REPO}.github.io/helm-charts" 2>/dev/null || true
helm repo update >/dev/null

if ! "${KCTL[@]}" get namespace "${LOKI_NAMESPACE}" >/dev/null 2>&1; then
  echo "[info] creating namespace ${LOKI_NAMESPACE}"
  "${KCTL[@]}" create namespace "${LOKI_NAMESPACE}"
fi

# ── Idempotency check ──────────────────────────────────────────────
if [[ "${UPGRADE}" -eq 0 ]] && "${KCTL[@]}" get -n "${LOKI_NAMESPACE}" all,cm,secret -l app.kubernetes.io/instance="${LOKI_RELEASE}" >/dev/null 2>&1; then
  if "${KCTL[@]}" get -n "${LOKI_NAMESPACE}" statefulset "${LOKI_RELEASE}-loki" >/dev/null 2>&1; then
    echo "[info] release ${LOKI_RELEASE} already present; pass --upgrade to update"
    exit 0
  fi
fi

# ── Install/upgrade ────────────────────────────────────────────────
HELM_ARGS=(
  install
  --namespace "${LOKI_NAMESPACE}"
  --create-namespace
  --values "${LOKI_VALUES}"
)
if [[ "${LOKI_CHART_VERSION}" != "" ]]; then
  HELM_ARGS+=(--version "${LOKI_CHART_VERSION}")
fi
if [[ "${DRY_RUN}" -eq 1 ]]; then
  HELM_ARGS+=(--dry-run --debug)
fi
if [[ "${UPGRADE}" -eq 1 ]]; then
  HELM_ARGS=(upgrade --install "${LOKI_RELEASE}" "${LOKI_CHART_REPO}/${LOKI_CHART_NAME}" "${HELM_ARGS[@]/#install/}")
else
  HELM_ARGS+=("${LOKI_RELEASE}" "${LOKI_CHART_REPO}/${LOKI_CHART_NAME}")
fi

echo "[info] running: helm ${HELM_ARGS[*]}"
helm "${HELM_ARGS[@]}"

echo "[ok] done"
