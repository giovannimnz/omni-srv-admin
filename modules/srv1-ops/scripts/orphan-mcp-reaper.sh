#!/usr/bin/env bash
# orphan-mcp-reaper.sh - Mata MCP servers orfaos do Codex
set -euo pipefail
DRY_RUN=0
MAX_AGE_MIN=30
LOG_DIR="${HOME}/.logs"
LOG="${LOG_DIR}/orphan-mcp-reaper.log"
mkdir -p "${LOG_DIR}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --max-age) MAX_AGE_MIN="$2"; shift 2 ;;
    *) echo "uso: $0 [--dry-run] [--max-age MIN]" >&2; exit 1 ;;
  esac
done
log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[${ts}] $*" | tee -a "${LOG}"
}
CODEX_APP_PIDS=$(pgrep -f 'codex.*app-server' 2>/dev/null || true)
if [[ -z "${CODEX_APP_PIDS}" ]]; then
  log "AVISO: nenhum Codex app-server ativo"
fi
MCP_PATTERNS=(
  'npx.*-y.*@modelcontextprotocol'
  'npx.*-y.*chrome-devtools-mcp'
  'npm exec.*@modelcontextprotocol'
  'npm exec.*chrome-devtools-mcp'
  'npm exec.*react-router-serve'
)
declare -a MCP_PIDS=()
for pattern in "${MCP_PATTERNS[@]}"; do
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] && MCP_PIDS+=("${pid}")
  done < <(pgrep -f "${pattern}" 2>/dev/null || true)
done
mapfile -t MCP_PIDS < <(printf '%s\n' "${MCP_PIDS[@]}" | sort -u)
if [[ ${#MCP_PIDS[@]} -eq 0 ]]; then
  log "OK: nenhum MCP server encontrado"
  exit 0
fi
ORPHAN_PIDS=()
for pid in "${MCP_PIDS[@]}"; do
  state=$(ps -p "${pid}" -o stat --no-headers 2>/dev/null || echo "")
  if [[ "${state}" == "Z" ]] || [[ "${state}" == "Z+" ]]; then
    continue
  fi
  current="${pid}"
  found_codex=0
  max_depth=20
  while [[ ${max_depth} -gt 0 ]]; do
    ppid=$(ps -p "${current}" -o ppid --no-headers 2>/dev/null || echo "")
    comm=$(ps -p "${current}" -o comm --no-headers 2>/dev/null || echo "")
    if [[ "${ppid}" == "0" ]] || [[ "${ppid}" == "1" ]] || [[ -z "${ppid}" ]]; then
      break
    fi
    if echo "${comm}" | grep -qi 'codex'; then
      for cp in ${CODEX_APP_PIDS}; do
        if [[ "${ppid}" == "${cp}" ]]; then
          found_codex=1
          break
        fi
      done
      if [[ ${found_codex} -eq 1 ]]; then
        break
      fi
    fi
    current="${ppid}"
    max_depth=$((max_depth - 1))
  done
  if [[ ${found_codex} -eq 0 ]]; then
    ORPHAN_PIDS+=("${pid}")
  fi
done
NOW_EPOCH=$(date +%s)
FINAL_PIDS=()
for pid in "${ORPHAN_PIDS[@]}"; do
  start_epoch=$(ps -p "${pid}" -o lstart= --no-headers 2>/dev/null | date +%s -f - 2>/dev/null || echo "")
  if [[ -z "${start_epoch}" ]]; then
    if [[ -f "/proc/${pid}/stat" ]]; then
      start_jiffies=$(awk '{print $22}' "/proc/${pid}/stat")
      start_epoch=$((NOW_EPOCH - start_jiffies / 100))
    else
      continue
    fi
  fi
  age_min=$(( (NOW_EPOCH - start_epoch) / 60 ))
  if [[ ${age_min} -ge ${MAX_AGE_MIN} ]]; then
    FINAL_PIDS+=("${pid}")
  fi
done
if [[ ${#FINAL_PIDS[@]} -eq 0 ]]; then
  log "OK: ${#MCP_PIDS[@]} MCP servers, nenhum orfao elegivel (max-age=${MAX_AGE_MIN}min)"
  exit 0
fi
log "ALERTA: ${#FINAL_PIDS[@]} MCP servers orfaos (max-age=${MAX_AGE_MIN}min)"
for pid in "${FINAL_PIDS[@]}"; do
  cmd=$(ps -p "${pid}" -o args= --no-headers 2>/dev/null | head -c 120 || echo "?")
  log "  PID ${pid}: ${cmd}"
done
if [[ ${DRY_RUN} -eq 1 ]]; then
  log "DRY-RUN: pulando kill"
  exit 0
fi
for pid in "${FINAL_PIDS[@]}"; do
  kill -TERM "${pid}" 2>/dev/null || true
done
sleep 5
SURVIVORS=()
for pid in "${FINAL_PIDS[@]}"; do
  if kill -0 "${pid}" 2>/dev/null; then
    SURVIVORS+=("${pid}")
    kill -KILL "${pid}" 2>/dev/null || true
  fi
done
if [[ ${#SURVIVORS[@]} -gt 0 ]]; then
  log "FORCADO: ${#SURVIVORS[@]} sobreviventes receberam SIGKILL"
fi
log "OK: ${#FINAL_PIDS[@]} MCP servers exterminados"
exit 0
