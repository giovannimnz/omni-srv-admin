#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
MANIFEST_DIR="${REPO_ROOT}/k8s/embeddings-bench"
NAMESPACE=embeddings-bench
SSH_TARGET=atius-srv-1

DEPLOYMENTS=(
  tei-qwen-fp16
  tei-qwen-fp32
  llama-qwen-q8
  llama-qwen-q8-kv-q8
  ollama-qwen-q8
  tei-qwen-onnx-int8
  ort-qwen-q8
  transformersjs-qwen-q8
)

MANIFESTS=(
  base.yaml
  tei-qwen-fp16.yaml
  tei-qwen-fp32.yaml
  llama-qwen-q8.yaml
  llama-qwen-q8-kv-q8.yaml
  ollama-qwen-q8.yaml
  tei-qwen-onnx-int8.yaml
  ort-qwen-q8.yaml
  transformersjs-qwen-q8.yaml
)

kctl() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "${SSH_TARGET}" \
    sudo -n k3s kubectl "$@"
}

usage() {
  echo "usage: $0 {validate|apply|start DEPLOYMENT|stop|status|logs DEPLOYMENT}" >&2
  echo "deployments: ${DEPLOYMENTS[*]}" >&2
}

is_known_deployment() {
  local candidate=$1
  local deployment
  for deployment in "${DEPLOYMENTS[@]}"; do
    if [[ "${candidate}" == "${deployment}" ]]; then
      return 0
    fi
  done
  return 1
}

scale_all_to_zero() {
  local deployment
  for deployment in "${DEPLOYMENTS[@]}"; do
    kctl -n "${NAMESPACE}" scale "deployment/${deployment}" --replicas=0 >/dev/null
  done
  kctl -n "${NAMESPACE}" wait --for=delete pod \
    -l app.kubernetes.io/component=embeddings-canary \
    --timeout=180s >/dev/null 2>&1 || true
}

command=${1:-}
case "${command}" in
  validate)
    for manifest in "${MANIFESTS[@]}"; do
      kctl apply --dry-run=client -f - < "${MANIFEST_DIR}/${manifest}" >/dev/null
      echo "valid: ${manifest}"
    done
    ;;
  apply)
    for manifest in "${MANIFESTS[@]}"; do
      kctl apply -f - < "${MANIFEST_DIR}/${manifest}"
    done
    scale_all_to_zero
    ;;
  start)
    deployment=${2:-}
    if ! is_known_deployment "${deployment}"; then
      usage
      exit 2
    fi
    scale_all_to_zero
    kctl -n "${NAMESPACE}" scale "deployment/${deployment}" --replicas=1
    kctl -n "${NAMESPACE}" rollout status "deployment/${deployment}" --timeout=30m
    ;;
  stop)
    scale_all_to_zero
    ;;
  status)
    kctl -n "${NAMESPACE}" get deployment,pod,service,pvc,resourcequota,limitrange -o wide
    ;;
  logs)
    deployment=${2:-}
    if ! is_known_deployment "${deployment}"; then
      usage
      exit 2
    fi
    kctl -n "${NAMESPACE}" logs "deployment/${deployment}" --all-containers --tail=200
    ;;
  *)
    usage
    exit 2
    ;;
esac
