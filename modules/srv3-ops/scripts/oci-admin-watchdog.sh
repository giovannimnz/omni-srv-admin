#!/usr/bin/env bash
set -u

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PM2_HOME="/home/ubuntu/.pm2"

PM2_BIN="/usr/local/bin/pm2"
ECOSYSTEM="/home/ubuntu/GitHub/oci-admin/deploy/pm2/ecosystem.config.cjs"
STATE_DIR="/home/ubuntu/.local/state/omni/oci-admin-watchdog"
LOG_DIR="/home/ubuntu/.logs/omni"
LOG_FILE="$LOG_DIR/oci-admin-watchdog.log"
LOCK_FILE="/home/ubuntu/.local/state/omni/oci-admin-watchdog.lock"
FAILURE_THRESHOLD="${OCI_ADMIN_WATCHDOG_FAILURE_THRESHOLD:-2}"
RECOVERY_COOLDOWN_SEC="${OCI_ADMIN_WATCHDOG_RECOVERY_COOLDOWN_SEC:-120}"
RECOVER=true

if [[ "${1:-}" == "--no-recover" ]]; then
  RECOVER=false
elif [[ -n "${1:-}" ]]; then
  echo "uso: $0 [--no-recover]" >&2
  exit 64
fi

mkdir -p "$STATE_DIR" "$LOG_DIR" "$(dirname "$LOCK_FILE")"

log() {
  local line
  line="[$(date -Iseconds)] $*"
  printf '%s\n' "$line" | tee -a "$LOG_FILE"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "WARN service=oci-admin-watchdog reason=lock-held"
  exit 0
fi

state_file() {
  printf '%s/%s.state\n' "$STATE_DIR" "$1"
}

read_state() {
  local app="$1"
  local file
  file="$(state_file "$app")"
  if [[ -r "$file" ]]; then
    awk 'NR == 1 { print ($1 ~ /^[0-9]+$/ ? $1 : 0), ($2 ~ /^[0-9]+$/ ? $2 : 0) }' "$file"
  else
    printf '0 0\n'
  fi
}

write_state() {
  printf '%s %s\n' "$2" "$3" > "$(state_file "$1")"
}

pm2_app_exists() {
  local app="$1"
  timeout 10s "$PM2_BIN" jlist 2>/dev/null |
    jq -e --arg app "$app" '.[] | select(.name == $app and (.namespace // .pm2_env.namespace) == "oci-admin")' >/dev/null
}

pm2_app_online() {
  local app="$1"
  timeout 10s "$PM2_BIN" jlist 2>/dev/null |
    jq -e --arg app "$app" '.[] | select(.name == $app and (.namespace // .pm2_env.namespace) == "oci-admin" and .pm2_env.status == "online")' >/dev/null
}

health_ok() {
  local url="$1"
  [[ "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 "$url" 2>/dev/null || true)" == "200" ]]
}

recover_app() {
  local app="$1"
  if pm2_app_exists "$app"; then
    timeout 60s "$PM2_BIN" restart "$app"
  else
    timeout 60s "$PM2_BIN" start "$ECOSYSTEM" --only "$app"
    timeout 60s /usr/local/sbin/oci-admin-pm2-save
  fi
}

check_app() {
  local app="$1"
  local health_url="$2"
  local state fail_count last_recovery now elapsed

  if pm2_app_online "$app" && health_ok "$health_url"; then
    state="$(read_state "$app")"
    read -r _ last_recovery <<<"$state"
    write_state "$app" 0 "$last_recovery"
    log "OK namespace=oci-admin app=$app health=200"
    return 0
  fi

  state="$(read_state "$app")"
  read -r fail_count last_recovery <<<"$state"
  fail_count=$((fail_count + 1))
  now="$(date +%s)"
  write_state "$app" "$fail_count" "$last_recovery"

  if (( fail_count < FAILURE_THRESHOLD )); then
    log "WARN namespace=oci-admin app=$app failure_count=$fail_count threshold=$FAILURE_THRESHOLD action=observe"
    return 1
  fi

  elapsed=$((now - last_recovery))
  if (( last_recovery > 0 && elapsed < RECOVERY_COOLDOWN_SEC )); then
    log "COOLDOWN namespace=oci-admin app=$app failure_count=$fail_count remaining=$((RECOVERY_COOLDOWN_SEC - elapsed))s"
    return 1
  fi

  if [[ "$RECOVER" != true ]]; then
    log "WARN namespace=oci-admin app=$app failure_count=$fail_count action=would-recover"
    return 1
  fi

  log "RECOVER namespace=oci-admin app=$app failure_count=$fail_count action=targeted-restart"
  write_state "$app" 0 "$now"
  if ! recover_app "$app" >/dev/null 2>&1; then
    log "ERROR namespace=oci-admin app=$app action=targeted-restart result=failed"
    return 1
  fi

  sleep 5
  if pm2_app_online "$app" && health_ok "$health_url"; then
    log "OK namespace=oci-admin app=$app action=targeted-restart health=200"
    return 0
  fi

  log "ERROR namespace=oci-admin app=$app action=targeted-restart health=failed"
  return 1
}

rc=0
check_app "oci-admin-web" "http://10.13.1.13:8080/healthz" || rc=1
check_app "oci-admin-mcp-http" "http://10.13.1.13:8090/healthz" || rc=1

public_code="$(curl -L -sS -o /dev/null -w '%{http_code}' --max-time 12 https://oci.atius.com.br/ 2>/dev/null || true)"
if [[ "$public_code" == "200" ]]; then
  log "OK service=oci-admin-public health=200"
else
  log "WARN service=oci-admin-public health=${public_code:-unreachable} action=no-local-restart"
fi

exit "$rc"
