#!/usr/bin/env bash
set -u
exec 9>/tmp/atius-k3s-watchdog.lock
flock -n 9 || exit 0
LOG=/home/ubuntu/.logs/atius-k3s-watchdog.log
mkdir -p "$(dirname "$LOG")"
log(){ echo "[$(date -Iseconds)] $*" >> "$LOG"; }

KUBECTL="sudo -n /usr/local/bin/k3s kubectl"

ensure_local_service(){
  local unit=$1
  if ! systemctl is-active --quiet "$unit"; then
    log "DOWN local system service $unit — restarting"
    sudo -n systemctl restart "$unit" >>"$LOG" 2>&1 || log "FAIL restart $unit"
  fi
}

ensure_remote_k3s(){
  local host=$1
  local name=$2
  if ! ssh -o ConnectTimeout=5 -o BatchMode=yes ubuntu@"$host" 'systemctl is-active --quiet k3s' >/dev/null 2>&1; then
    log "DOWN remote k3s $name/$host — restarting"
    ssh -o ConnectTimeout=8 -o BatchMode=yes ubuntu@"$host" 'sudo -n systemctl restart k3s' >>"$LOG" 2>&1 || log "FAIL restart remote k3s $name/$host"
  fi
}

check_http(){
  local name=$1
  local url=$2
  local pattern=$3
  if ! curl -sk --max-time 8 "$url" | grep -qi "$pattern"; then
    log "BAD_HTTP $name $url"
    return 1
  fi
  return 0
}

check_http_basic(){
  local name=$1
  local url=$2
  local pattern=$3
  local pass_file=/home/ubuntu/.secrets/edge-admin-password
  if [ ! -s "$pass_file" ]; then
    log "BAD_HTTP_BASIC $name missing edge password file"
    return 1
  fi
  local pass
  pass=$(cat "$pass_file")
  if ! curl -skL --max-time 15 -u "giovanni:$pass" "$url" | grep -qi "$pattern"; then
    log "BAD_HTTP_BASIC $name $url"
    return 1
  fi
  return 0
}

ensure_local_service k3s
ensure_remote_k3s 10.1.1.2 SRV-2
ensure_remote_k3s 10.1.1.7 SRV-3
ensure_local_service atius-k3s-firewall.service
ensure_local_service k3s-portainer-portforward.service
ensure_local_service k3s-grafana-portforward.service

ready_nodes=$($KUBECTL get nodes --no-headers 2>/dev/null | awk '$2=="Ready"{c++} END{print c+0}')
total_nodes=$($KUBECTL get nodes --no-headers 2>/dev/null | wc -l | tr -dc '0-9')
if [ "${ready_nodes:-0}" -ne 3 ] || [ "${total_nodes:-0}" -ne 3 ]; then
  log "BAD_NODES ready=${ready_nodes:-0} total=${total_nodes:-0}"
fi

notready_pods=$($KUBECTL get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.status.containerStatuses[*].ready}{"\n"}{end}' 2>/dev/null | awk '$0 ~ /false/ {c++} END{print c+0}')
if [ "${notready_pods:-0}" -ne 0 ]; then
  log "BAD_PODS notready=${notready_pods:-0}"
fi

check_http portainer https://127.0.0.1:9443/api/system/status 'Version' || sudo -n systemctl restart k3s-portainer-portforward.service
check_http grafana http://127.0.0.1:3005/api/health 'database' || sudo -n systemctl restart k3s-grafana-portforward.service
check_http_basic public_portainer https://portainer.atius.com.br/api/system/status 'Version' || true
check_http_basic public_grafana https://grafana.atius.com.br/ 'Grafana' || true

log "OK ready_nodes=${ready_nodes:-0}/${total_nodes:-0} notready_pods=${notready_pods:-0}"
