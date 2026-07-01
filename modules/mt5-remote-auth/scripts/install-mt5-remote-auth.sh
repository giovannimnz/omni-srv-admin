#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

APPLY_APACHE=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: install-mt5-remote-auth.sh [--apply-apache] [--dry-run]

Installs the local MT5 SSO auth proxy service. Apache is not changed unless
--apply-apache is provided.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply-apache)
      APPLY_APACHE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

node --check "${MODULE_DIR}/scripts/mt5-remote-auth-proxy.js"

run sudo install -d -m 0755 /opt/atius /etc/atius
run sudo install -m 0755 "${MODULE_DIR}/scripts/mt5-remote-auth-proxy.js" /opt/atius/mt5-remote-auth-proxy.js
run sudo install -m 0644 "${MODULE_DIR}/configs/mt5-remote-auth-proxy.json" /etc/atius/mt5-remote-auth-proxy.json
run sudo install -m 0644 "${MODULE_DIR}/systemd/mt5-remote-auth-proxy.service" /etc/systemd/system/mt5-remote-auth-proxy.service
run sudo systemctl daemon-reload
run sudo systemctl enable mt5-remote-auth-proxy.service
run sudo systemctl restart mt5-remote-auth-proxy.service

if [[ "${DRY_RUN}" != "true" ]]; then
  for attempt in {1..20}; do
    if curl -fsS http://127.0.0.1:8095/healthz >/dev/null 2>&1; then
      break
    fi
    if [[ "${attempt}" == "20" ]]; then
      echo "mt5-remote-auth-proxy healthcheck failed after ${attempt} attempts" >&2
      exit 1
    fi
    sleep 0.5
  done
fi

if [[ "${APPLY_APACHE}" == "true" ]]; then
  backup_dir="${HOME}/.backups/mt5-remote-auth-apache-$(date -u +%Y%m%dT%H%M%SZ)"
  run mkdir -p "${backup_dir}"
  if [[ -f /etc/apache2/sites-available/remote.atius.com.br.conf ]]; then
    run sudo cp /etc/apache2/sites-available/remote.atius.com.br.conf "${backup_dir}/remote.atius.com.br.conf"
  fi

  run sudo install -m 0644 "${MODULE_DIR}/apache/remote.atius.com.br.sso.conf" /etc/apache2/sites-available/remote.atius.com.br.conf
  run sudo apache2ctl configtest
  run sudo systemctl reload apache2
  echo "Apache backup: ${backup_dir}"
fi

echo "MT5 remote SSO auth proxy installed."
