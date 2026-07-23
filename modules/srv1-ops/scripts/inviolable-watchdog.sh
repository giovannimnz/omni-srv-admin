#!/usr/bin/env bash
# inviolable-watchdog.sh - ATIUS-SRV-1
# Canonical source: omni-srv-admin/modules/srv1-ops/scripts/inviolable-watchdog.sh
# Deployed copy: /home/ubuntu/scripts/inviolable-watchdog.sh
#
# 2026-06-11: service-aware checks, single-instance lock and relaunch
# hysteresis/cooldown. This avoids deterministic timer relaunch storms for
# oneshot services and processes whose runtime name differs from their unit name.

set -u

export PATH="/home/ubuntu/.nvm/versions/node/v24.13.1/bin:/home/ubuntu/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

LOG="/home/ubuntu/.logs/resource-governor/inviolable-watchdog.log"
STATE_DIR="/home/ubuntu/.local/state/omni/inviolable-watchdog"
LOCK_FILE="/home/ubuntu/.local/state/omni/inviolable-watchdog.lock"
PM2_BIN="/home/ubuntu/.nvm/versions/node/v24.13.1/bin/pm2"
ATS_ECOSYSTEM="/home/ubuntu/GitHub/Atius-Capital/ats/ecosystem.config.js"
HORISTIC_ECOSYSTEM="/home/ubuntu/GitHub/Atius-Capital/horistic/ecosystem.config.js"

DEFAULT_COOLDOWN_SEC="${INVIOLABLE_RESTART_COOLDOWN_SEC:-180}"
DEFAULT_FAILURE_THRESHOLD="${INVIOLABLE_RESTART_FAILURE_THRESHOLD:-2}"
CRITICAL_COOLDOWN_SEC="${INVIOLABLE_CRITICAL_RESTART_COOLDOWN_SEC:-60}"

mkdir -p "$(dirname "$LOG")" "$STATE_DIR" "$(dirname "$LOCK_FILE")"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*" >> "$LOG"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "WARN service=inviolable-watchdog reason=lock-held"
  exit 0
fi

state_file() {
  printf '%s/%s.state\n' "$STATE_DIR" "$1"
}

state_value() {
  local service="$1"
  local field="$2"
  local file
  file="$(state_file "$service")"
  if [[ -r "$file" ]]; then
    awk -v field="$field" 'NR == 1 {
      if (field == "fail") {
        print ($1 ~ /^[0-9]+$/ ? $1 : 0)
      } else {
        print ($2 ~ /^[0-9]+$/ ? $2 : 0)
      }
    }' "$file"
  else
    printf '0\n'
  fi
}

write_state() {
  local service="$1"
  local fail_count="$2"
  local last_relaunch="$3"
  printf '%s %s\n' "$fail_count" "$last_relaunch" > "$(state_file "$service")"
}

mark_ok() {
  local service="$1"
  local reason="${2:-check-passed}"
  local last_relaunch
  last_relaunch="$(state_value "$service" last)"
  write_state "$service" 0 "$last_relaunch"
  log "OK service=$service reason=$reason"
}

guarded_relaunch() {
  local service="$1"
  local threshold="$2"
  local cooldown="$3"
  shift 3

  local now fail_count last_relaunch elapsed remaining rc
  now="$(date +%s)"
  fail_count="$(state_value "$service" fail)"
  last_relaunch="$(state_value "$service" last)"
  fail_count=$((fail_count + 1))

  if (( fail_count < threshold )); then
    write_state "$service" "$fail_count" "$last_relaunch"
    log "WARN service=$service failure_count=$fail_count threshold=$threshold reason=check-failed"
    return 0
  fi

  remaining=0
  if (( last_relaunch > 0 )); then
    elapsed=$((now - last_relaunch))
    if (( elapsed < cooldown )); then
      remaining=$((cooldown - elapsed))
      write_state "$service" "$fail_count" "$last_relaunch"
      log "COOLDOWN service=$service failure_count=$fail_count cooldown_remaining=${remaining}s"
      return 0
    fi
  fi

  log "RELAUNCH service=$service failure_count=$fail_count cooldown_remaining=0 cmd=$*"
  write_state "$service" 0 "$now"
  "$@"
  rc=$?
  if (( rc == 0 )); then
    log "OK service=$service action=relaunch rc=0"
  else
    log "WARN service=$service action=relaunch rc=$rc"
  fi
  return 0
}

process_check() {
  local pattern="$1"
  local min="${2:-1}"
  local count
  count="$(pgrep -fc "$pattern" 2>/dev/null | head -1 | tr -dc '0-9')"
  count="${count:-0}"
  [[ "$count" -ge "$min" ]]
}

sshd_banner_ok() {
  timeout 3 bash -lc '
    exec 3<>/dev/tcp/127.0.0.1/22 || exit 1
    IFS= read -r -t 2 banner <&3 || exit 1
    [[ $banner == SSH-* ]]
  ' >/dev/null 2>&1
}

service_or_binary_exists() {
  local service="$1"
  local binary="$2"
  command -v "$binary" >/dev/null 2>&1 ||
    systemctl list-unit-files "$service" >/dev/null 2>&1
}

systemctl_user_is_active() {
  timeout 5s systemctl --user is-active --quiet "$1" >/dev/null 2>&1
}

systemctl_user_start() {
  timeout 15s systemctl --user start --no-block "$1"
}

systemctl_system_start() {
  timeout 15s sudo systemctl start --no-block "$1"
}

start_bg() {
  local name="$1"
  shift
  nohup "$@" > "/tmp/inviolable-${name}.log" 2>&1 &
  disown
}

start_system_transient() {
  local name="$1"
  shift
  sudo systemd-run \
    --unit="inviolable-${name}" \
    --collect \
    --property=Restart=on-failure \
    --property=RestartSec=5 \
    "$@" > "/tmp/inviolable-${name}.log" 2>&1
}

pm2_app_online() {
  local app="$1"
  timeout 8s "$PM2_BIN" jlist 2>/dev/null | jq -e --arg name "$app" \
    '.[] | select(.name == $name and .pm2_env.status == "online")' >/dev/null 2>&1
}

pm2_app_online_or_waiting() {
  local app="$1"
  timeout 8s "$PM2_BIN" jlist 2>/dev/null | jq -e --arg name "$app" \
    '.[] | select(.name == $name and (.pm2_env.status == "online" or .pm2_env.status == "waiting restart"))' >/dev/null 2>&1
}

pm2_start_ecosystem() {
  local ecosystem="$1"
  timeout 60s "$PM2_BIN" start "$ecosystem" --update-env
}

pm2_start_ecosystem_only() {
  local ecosystem="$1"
  local app="$2"
  timeout 60s "$PM2_BIN" start "$ecosystem" --only "$app" --update-env
}

atius_web_ok() {
  pm2_app_online "atius-web" && nc -z 127.0.0.1 3015 >/dev/null 2>&1
}

atius_web_healthcheck_ok() {
  timeout 20s /home/ubuntu/.local/bin/atius-web-healthcheck.sh >/tmp/inviolable-atius-web-healthcheck.probe 2>&1
}

atius_router_docs_ok() {
  systemctl_user_is_active "atius-router-docs.service" || nc -z 127.0.0.1 3003 >/dev/null 2>&1
}

atius_router_containers_ok() {
  local names
  names="$(podman ps --format '{{.Names}}' 2>/dev/null || true)"
  grep -Fxq "router-ai-atius" <<<"$names" &&
    grep -Fxq "postgres" <<<"$names" &&
    grep -Fxq "redis" <<<"$names" &&
    grep -Eqx "(model-detailed|model-detailed-hotfix)" <<<"$names"
}

atius_pm2_stack_ok() {
  pm2_app_online "atius-api" &&
    pm2_app_online "atius-webhook-signals" &&
    pm2_app_online "atius-divap-indicator" &&
    pm2_app_online_or_waiting "atius-strategy-builder" &&
    pm2_app_online_or_waiting "atius-unified-bot-launcher" &&
    nc -z 127.0.0.1 8015 >/dev/null 2>&1 &&
    nc -z 127.0.0.1 8199 >/dev/null 2>&1
}

horistic_pm2_stack_ok() {
  pm2_app_online "horistic-api" &&
    pm2_app_online "horistic-web" &&
    pm2_app_online "horistic-webhook-signals" &&
    pm2_app_online "horistic-divap-indicator" &&
    pm2_app_online_or_waiting "horistic-unified-bot-launcher" &&
    nc -z 127.0.0.1 8050 >/dev/null 2>&1 &&
    nc -z 127.0.0.1 3050 >/dev/null 2>&1 &&
    nc -z 127.0.0.1 8099 >/dev/null 2>&1
}

hermes_telegram_ok() {
  systemctl_user_is_active "hermes-telegram.service" ||
    pgrep -f "python -m hermes_cli.main gateway run --replace" >/dev/null 2>&1
}

hermes_ws_gateway_ok() {
  pm2_app_online "hermes-ws-gateway-pg" ||
    systemctl_user_is_active "hermes-ws-gateway.service" ||
    pgrep -f "hermes.*ws.*gateway" >/dev/null 2>&1
}

start_sshd() {
  systemctl_system_start "ssh" || start_system_transient "sshd" /usr/sbin/sshd -D
}

start_xrdp() {
  start_system_transient "xrdp" /usr/sbin/xrdp --nodaemon
}

start_xrdp_sesman() {
  start_system_transient "xrdp-sesman" /usr/sbin/xrdp-sesman --nodaemon
}

start_wg0() {
  systemctl_system_start "wg-quick@wg0"
}

start_horistic_stack() {
  pm2_start_ecosystem "$HORISTIC_ECOSYSTEM"
}

start_atius_web() {
  pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-web"
}

start_atius_stack() {
  local rc=0

  # The web has its own port-aware recovery path above. Starting the complete
  # ecosystem here restarts a healthy atius-web whenever an unrelated worker
  # is degraded, briefly removing port 3015 from Apache. Recover only the
  # unhealthy member instead.
  if ! pm2_app_online "atius-api" || ! nc -z 127.0.0.1 8015 >/dev/null 2>&1; then
    pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-api" || rc=1
  fi
  if ! pm2_app_online "atius-webhook-signals" || ! nc -z 127.0.0.1 8199 >/dev/null 2>&1; then
    pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-webhook-signals" || rc=1
  fi
  if ! pm2_app_online "atius-divap-indicator"; then
    pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-divap-indicator" || rc=1
  fi
  if ! pm2_app_online_or_waiting "atius-strategy-builder"; then
    pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-strategy-builder" || rc=1
  fi
  if ! pm2_app_online_or_waiting "atius-unified-bot-launcher"; then
    pm2_start_ecosystem_only "$ATS_ECOSYSTEM" "atius-unified-bot-launcher" || rc=1
  fi

  return "$rc"
}

start_router_containers() {
  local name
  for name in router-ai-atius postgres redis model-detailed router-ai-atius-db router-ai-atius-redis router-ai-atius-model-detailed; do
    if podman container exists "$name" >/dev/null 2>&1; then
      podman start "$name"
    fi
  done
}

# Remote access and network services. These keep threshold=1 but still have a
# cooldown so a hard failure cannot trigger a timer-cycle storm.
if sshd_banner_ok; then
  mark_ok "sshd"
else
  guarded_relaunch "sshd" 1 "$CRITICAL_COOLDOWN_SEC" start_sshd
fi

if process_check "/usr/sbin/xrdp" 1; then
  mark_ok "xrdp"
else
  guarded_relaunch "xrdp" 1 "$CRITICAL_COOLDOWN_SEC" start_xrdp
fi

if process_check "/usr/sbin/xrdp-sesman" 1; then
  mark_ok "xrdp-sesman"
else
  guarded_relaunch "xrdp-sesman" 1 "$CRITICAL_COOLDOWN_SEC" start_xrdp_sesman
fi

if process_check "/usr/sbin/apache2 -k" 1; then
  mark_ok "apache2"
else
  guarded_relaunch "apache2" 1 "$CRITICAL_COOLDOWN_SEC" systemctl_system_start "apache2"
fi

if ! service_or_binary_exists "nginx.service" "nginx"; then
  mark_ok "nginx" "not-installed"
elif process_check "nginx: master" 1; then
  mark_ok "nginx"
else
  guarded_relaunch "nginx" 1 "$CRITICAL_COOLDOWN_SEC" systemctl_system_start "nginx"
fi

if ip link show wg0 2>/dev/null | grep -q "UP"; then
  mark_ok "wg0"
else
  guarded_relaunch "wg0" 1 "$CRITICAL_COOLDOWN_SEC" start_wg0
fi

# Atius stack: exact PM2/systemd/podman checks replace fragile process-name
# probes for services observed flapping on 2026-06-11.
if atius_web_ok; then
  mark_ok "atius-web" "pm2-online-port-3015"
else
  guarded_relaunch "atius-web" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" start_atius_web
fi

if atius_router_docs_ok; then
  mark_ok "atius-router-docs" "systemd-or-port-3003"
else
  guarded_relaunch "atius-router-docs" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" systemctl_user_start "atius-router-docs.service"
fi

if horistic_pm2_stack_ok; then
  mark_ok "horistic-pm2" "pm2-apps-online-ports-3050-8050-8099"
else
  guarded_relaunch "horistic-pm2" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" start_horistic_stack
fi

if atius_pm2_stack_ok; then
  mark_ok "ats-pm2" "pm2-apps-online-ports-8015-8199"
else
  guarded_relaunch "ats-pm2" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" start_atius_stack
fi

if atius_router_containers_ok; then
  mark_ok "atius-router-containers" "podman-online"
else
  guarded_relaunch "atius-router-containers" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" start_router_containers
fi

if atius_web_healthcheck_ok; then
  mark_ok "atius-web-healthcheck" "oneshot-exit-0"
else
  guarded_relaunch "atius-web-healthcheck" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" systemctl_user_start "atius-web-healthcheck.service"
fi

if hermes_telegram_ok; then
  mark_ok "hermes-telegram" "systemd-or-gateway-process"
else
  guarded_relaunch "hermes-telegram" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" systemctl_user_start "hermes-telegram.service"
fi

if hermes_ws_gateway_ok; then
  mark_ok "hermes-ws-gateway" "pm2-or-systemd"
else
  guarded_relaunch "hermes-ws-gateway" "$DEFAULT_FAILURE_THRESHOLD" "$DEFAULT_COOLDOWN_SEC" systemctl_user_start "hermes-ws-gateway.service"
fi

if mountpoint -q /home/ubuntu/GDrive 2>/dev/null; then
  mark_ok "gdrive-mount"
else
  guarded_relaunch "gdrive-mount" 1 "$CRITICAL_COOLDOWN_SEC" systemctl_user_start "gdrive-mount.service"
fi

log "OK cycle complete"
