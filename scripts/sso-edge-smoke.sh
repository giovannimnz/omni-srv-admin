#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DRY_RUN=false
LOCAL_MODE=false
ASSERT_STATUS=false
ASSERT_HEADERS=false
APP_HOSTS=(
  "trade.atius.com.br"
  "painel.atius.com.br"
  "dashboard.atius.com.br"
  "backtest.atius.com.br"
  "strategy.atius.com.br"
  "admin.atius.com.br"
)

usage() {
  cat <<'EOF'
Usage: bash scripts/sso-edge-smoke.sh [--dry-run] [--local] [--assert-app-hosts host1,host2,...]

Modes:
  --dry-run            Print planned checks and rollback prerequisites only.
  --local              Run local Apache/curl/json/header assertions.
  --assert-status      Assert HTTP status and redirect targets.
  --assert-headers     Assert explicit Apache forwarded-header contracts.
  --assert-app-hosts   Override the default six ATS app hosts.
EOF
}

log() {
  printf '[sso-edge-smoke] %s\n' "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        ;;
      --local)
        LOCAL_MODE=true
        ;;
      --assert-status)
        ASSERT_STATUS=true
        ;;
      --assert-headers)
        ASSERT_HEADERS=true
        ;;
      --assert-app-hosts)
        [[ $# -ge 2 ]] || {
          echo "--assert-app-hosts requires a comma-separated value" >&2
          exit 1
        }
        IFS=',' read -r -a APP_HOSTS <<<"$2"
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
    shift
  done
}

assert_vhost_forwarded_contract() {
  local host="$1"
  local vhost_file="/etc/apache2/sites-available/${host}.conf"
  [[ -f "${vhost_file}" ]] || {
    echo "Missing Apache vhost: ${vhost_file}" >&2
    return 1
  }

  rg -n "RequestHeader set X-Forwarded-Host \"${host}\"" "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Host contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-Proto "https"' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Proto contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-Port "443"' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Port contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-For %\{REMOTE_ADDR\}s' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-For contract in ${vhost_file}" >&2; return 1; }
}

assert_sso_vhost_contract() {
  local vhost_file="/etc/apache2/sites-available/sso.atius.com.br.conf"

  [[ -f "${vhost_file}" ]] || {
    echo "Missing Apache vhost: ${vhost_file}" >&2
    return 1
  }

  rg -n 'ProxyPreserveHost On' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing ProxyPreserveHost in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-Host "sso\.atius\.com\.br"' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Host contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-Proto "https"' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Proto contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-Port "443"' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-Port contract in ${vhost_file}" >&2; return 1; }
  rg -n 'RequestHeader set X-Forwarded-For %\{REMOTE_ADDR\}s' "${vhost_file}" >/dev/null 2>&1 ||
    { echo "Missing explicit X-Forwarded-For contract in ${vhost_file}" >&2; return 1; }
}

assert_sso_vhost_enabled() {
  local vhost_real
  vhost_real="$(readlink -f /etc/apache2/sites-available/sso.atius.com.br.conf)"
  if ! find /etc/apache2/sites-enabled -maxdepth 1 -type l -print0 2>/dev/null | xargs -0 -r readlink -f | grep -Fx "${vhost_real}" >/dev/null 2>&1; then
    echo "sso.atius.com.br vhost exists but is not enabled in /etc/apache2/sites-enabled; local HTTP smoke would still hit the current live config until an explicit enable+reload gate is approved." >&2
    return 1
  fi
}

assert_redirect_target() {
  local host="$1"
  local headers_file="$2"

  python3 - "$host" "$headers_file" <<'PY'
from __future__ import annotations

import pathlib
import sys
from urllib.parse import parse_qs, urlparse

host = sys.argv[1]
headers_path = pathlib.Path(sys.argv[2])
headers = headers_path.read_text(encoding="utf-8", errors="ignore").splitlines()

status_line = next((line for line in headers if line.startswith("HTTP/")), "")
if not status_line:
    raise SystemExit("Missing HTTP status line")

parts = status_line.split()
status_code = int(parts[1])
if status_code not in (301, 302, 303, 307, 308):
    raise SystemExit(f"Unexpected redirect status {status_code}")

location_line = next((line for line in headers if line.lower().startswith("location:")), None)
if location_line is None:
    raise SystemExit("Missing Location header")

location = location_line.split(":", 1)[1].strip()
parsed_location = urlparse(location)
if parsed_location.scheme != "https" or parsed_location.netloc != "sso.atius.com.br" or parsed_location.path != "/login":
    raise SystemExit(f"Unexpected redirect target {location}")

return_to = parse_qs(parsed_location.query).get("return_to", [None])[0]
if not return_to:
    raise SystemExit("Missing return_to query param")

parsed_return = urlparse(return_to)
if parsed_return.scheme != "https":
    raise SystemExit("return_to must be https")
if parsed_return.netloc != host:
    raise SystemExit(f"return_to host mismatch: expected {host}, got {parsed_return.netloc}")
if not parsed_return.path:
    raise SystemExit("return_to path must not be empty")
PY
}

run_login_smoke() {
  require_cmd curl
  local headers_file
  local body_file
  headers_file="$(mktemp)"
  body_file="$(mktemp)"

  local status
  status="$(curl --silent --show-error --fail-with-body \
    --resolve sso.atius.com.br:443:127.0.0.1 \
    --dump-header "${headers_file}" \
    --output "${body_file}" \
    --write-out '%{http_code}' \
    https://sso.atius.com.br/login)"

  [[ "${status}" =~ ^2 ]] || {
    echo "Unexpected login status: ${status}" >&2
    return 1
  }
}

run_keycloak_discovery_smoke() {
  require_cmd curl
  local body_file
  body_file="$(mktemp)"

  curl --silent --show-error --fail-with-body \
    --resolve auth.atius.com.br:443:127.0.0.1 \
    --output "${body_file}" \
    https://auth.atius.com.br/realms/atius/.well-known/openid-configuration >/dev/null

  python3 - "${body_file}" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys

body = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
issuer = body.get("issuer")
auth = body.get("authorization_endpoint")
logout = body.get("end_session_endpoint")
if issuer != "https://auth.atius.com.br/realms/atius":
    raise SystemExit(f"Unexpected issuer {issuer!r}")
if not auth or not logout:
    raise SystemExit("Discovery document missing authorization/logout endpoint")
PY
}

run_app_host_smoke() {
  require_cmd curl
  for host in "${APP_HOSTS[@]}"; do
    local headers_file
    local body_file
    headers_file="$(mktemp)"
    body_file="$(mktemp)"

    local status
    status="$(curl --silent --show-error \
      --resolve "${host}:443:127.0.0.1" \
      --dump-header "${headers_file}" \
      --output "${body_file}" \
      --write-out '%{http_code}' \
      "https://${host}/")"

    if [[ ! "${status}" =~ ^30[12378]?$ && ! "${status}" =~ ^30[1278]$ && ! "${status}" =~ ^30[2-8]$ ]]; then
      echo "Unexpected status ${status} for ${host}" >&2
      return 1
    fi

    assert_redirect_target "${host}" "${headers_file}"
    if [[ "${ASSERT_HEADERS}" == "true" || "${ASSERT_STATUS}" == "false" ]]; then
      assert_vhost_forwarded_contract "${host}"
    fi
  done
}

print_dry_run() {
  log "Dry run only. No Apache, DNS, Cloudflare, Keycloak, PM2, or ATS mutation will occur."
  log "Rollback prerequisites:"
  log "  - capture current /etc/apache2/sites-available/*.conf backups before edits"
  log "  - record current DNS/proxy/TLS state for sso.atius.com.br before publication"
  log "Planned local assertions:"
  log "  - apache2ctl configtest"
  log "  - curl --resolve sso.atius.com.br:443:127.0.0.1 https://sso.atius.com.br/login with explicit 2xx assertion"
  log "  - Keycloak discovery JSON issuer/auth/logout assertions via auth.atius.com.br"
  for host in "${APP_HOSTS[@]}"; do
    log "  - ${host}: unauthenticated redirect must target https://sso.atius.com.br/login with normalized return_to"
    log "  - ${host}: /etc/apache2/sites-available/${host}.conf must set explicit X-Forwarded-Host"
  done
}

main() {
  parse_args "$@"

  if [[ "${DRY_RUN}" == "true" ]]; then
    print_dry_run
    exit 0
  fi

  [[ "${LOCAL_MODE}" == "true" ]] || {
    echo "Non-dry execution requires --local" >&2
    exit 1
  }

  if [[ "${ASSERT_STATUS}" == "false" && "${ASSERT_HEADERS}" == "false" ]]; then
    ASSERT_STATUS=true
    ASSERT_HEADERS=true
  fi

  require_cmd apache2ctl
  require_cmd find
  require_cmd rg
  require_cmd python3

  log "Running apache2ctl configtest"
  apache2ctl configtest >/dev/null

  if [[ "${ASSERT_HEADERS}" == "true" ]]; then
    log "Checking static Apache forwarded-header contracts"
    assert_sso_vhost_contract
    for host in "${APP_HOSTS[@]}"; do
      assert_vhost_forwarded_contract "${host}"
    done
  fi

  if [[ "${ASSERT_STATUS}" == "true" ]]; then
    log "Checking whether sso.atius.com.br is enabled before live HTTP smoke"
    assert_sso_vhost_enabled

    log "Running local sso.atius.com.br login smoke"
    run_login_smoke

    log "Running Keycloak discovery smoke"
    run_keycloak_discovery_smoke

    log "Running ATS app-host redirect/header assertions"
    run_app_host_smoke
  fi

  log "Edge smoke passed."
}

main "$@"
