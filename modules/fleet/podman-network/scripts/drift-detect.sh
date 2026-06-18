#!/usr/bin/env bash
# drift-detect.sh — runs the 7-point drift check on all 3 ATIUS servers
# in parallel, output as a comparison table.
#
# Usage: ./drift-detect.sh
# Output: text table with one row per check, one column per server
#
# Lives in omni-srv-admin/modules/fleet/podman-network/scripts/
# Vendored in ~/.hermes/skills/devops/podman-fleet-standardize/scripts/

set -u

SRV1=10.1.1.1
SRV2=10.1.1.2
SRV3=10.1.1.7
USER=ubuntu

# Path to the remote collector script (vendored alongside this file)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COLLECT_REMOTE="$SCRIPT_DIR/drift-collect.py"

RED='\033[0;31m'
GRN='\033[0;32m'
RST='\033[0m'

run_remote() {
  local N=$1
  local HOST=$2
  scp -o ConnectTimeout=5 -q "$COLLECT_REMOTE" "$USER@$HOST:/tmp/drift-collect-$N.py" 2>/dev/null
  ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$USER@$HOST" "bash -lc 'source /home/ubuntu/.profile >/dev/null 2>&1; python3 /tmp/drift-collect-$N.py $N'"
}

exec 3>&1
SRV1_OUT=$(run_remote 1 $SRV1)
SRV2_OUT=$(run_remote 2 $SRV2)
SRV3_OUT=$(run_remote 3 $SRV3)
exec 3>&-

parse() {
  local OUT=$1
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    key=$(echo "$line" | cut -d= -f1)
    val=$(echo "$line" | cut -d= -f2-)
    eval "PARSE_${key}='${val}'"
  done <<< "$OUT"
}

parse "$SRV1_OUT"
S1_default_network=$PARSE_default_network
S1_default_subnet=$PARSE_default_subnet
S1_netavark_backend=$PARSE_netavark_backend
S1_podman_backend=$PARSE_podman_backend
S1_srv_podman=$PARSE_srv1_podman
S1_resolved_dir_files=$PARSE_resolved_dir_files
S1_resolved_active=$PARSE_resolved_active
S1_podman_compose=$PARSE_podman_compose
S1_aardvark_pid=$PARSE_aardvark_pid

parse "$SRV2_OUT"
S2_default_network=$PARSE_default_network
S2_default_subnet=$PARSE_default_subnet
S2_netavark_backend=$PARSE_netavark_backend
S2_podman_backend=$PARSE_podman_backend
S2_srv_podman=$PARSE_srv2_podman
S2_resolved_dir_files=$PARSE_resolved_dir_files
S2_resolved_active=$PARSE_resolved_active
S2_podman_compose=$PARSE_podman_compose
S2_aardvark_pid=$PARSE_aardvark_pid

parse "$SRV3_OUT"
S3_default_network=$PARSE_default_network
S3_default_subnet=$PARSE_default_subnet
S3_netavark_backend=$PARSE_netavark_backend
S3_podman_backend=$PARSE_podman_backend
S3_srv_podman=$PARSE_srv3_podman
S3_resolved_dir_files=$PARSE_resolved_dir_files
S3_resolved_active=$PARSE_resolved_active
S3_podman_compose=$PARSE_podman_compose
S3_aardvark_pid=$PARSE_aardvark_pid

check() {
  local name=$1 e1=$2 a1=$3 e2=$4 a2=$5 e3=$6 a3=$7
  if [ "$a1" = "$e1" ] && [ "$a2" = "$e2" ] && [ "$a3" = "$e3" ]; then
    echo -e "  $name: ${GRN}PASS${RST}"
  else
    echo -e "  $name: ${RED}FAIL${RST}"
    echo "    SRV-1: expected '$e1', got '$a1'"
    echo "    SRV-2: expected '$e2', got '$a2'"
    echo "    SRV-3: expected '$e3', got '$a3'"
  fi
}

echo "=== Podman Fleet Standard Drift Check ($(date -Iseconds)) ==="
echo ""
echo "Server hosts: SRV-1=10.1.1.1, SRV-2=10.1.1.2, SRV-3=10.1.1.7"
echo ""
echo "--- per-server state ---"
printf "%-30s | %-40s | %-40s | %-40s\n" "Check" "SRV-1" "SRV-2" "SRV-3"
printf -- "-%.0s" {1..160}; echo
printf "%-30s | %-40s | %-40s | %-40s\n" "default_network" "${S1_default_network:-MISSING}" "${S2_default_network:-MISSING}" "${S3_default_network:-MISSING}"
printf "%-30s | %-40s | %-40s | %-40s\n" "default_subnet" "${S1_default_subnet:-MISSING}" "${S2_default_subnet:-MISSING}" "${S3_default_subnet:-MISSING}"
printf "%-30s | %-40s | %-40s | %-40s\n" "99-netavark.conf" "${S1_netavark_backend:-MISSING}" "${S2_netavark_backend:-MISSING}" "${S3_netavark_backend:-MISSING}"
printf "%-30s | %-40s | %-40s | %-40s\n" "podman info backend" "${S1_podman_backend:-?}" "${S2_podman_backend:-?}" "${S3_podman_backend:-?}"
printf "%-30s | %-40s | %-40s | %-40s\n" "srv<N>-podman" "${S1_srv_podman:-MISSING}" "${S2_srv_podman:-MISSING}" "${S3_srv_podman:-MISSING}"
printf "%-30s | %-40s | %-40s | %-40s\n" "systemd-resolve files" "${S1_resolved_dir_files:-0}" "${S2_resolved_dir_files:-0}" "${S3_resolved_dir_files:-0}"
printf "%-30s | %-40s | %-40s | %-40s\n" "systemd-resolved status" "${S1_resolved_active:-?}" "${S2_resolved_active:-?}" "${S3_resolved_active:-?}"
printf "%-30s | %-40s | %-40s | %-40s\n" "podman-compose" "${S1_podman_compose:-missing}" "${S2_podman_compose:-missing}" "${S3_podman_compose:-missing}"
printf "%-30s | %-40s | %-40s | %-40s\n" "aardvark-dns PID" "${S1_aardvark_pid:-NOT_RUNNING}" "${S2_aardvark_pid:-NOT_RUNNING}" "${S3_aardvark_pid:-NOT_RUNNING}"
echo ""
echo "--- fleet-conformance check ---"
check "default_network = srv<N>-podman" "srv1-podman" "${S1_default_network:-}" "srv2-podman" "${S2_default_network:-}" "srv3-podman" "${S3_default_network:-}"
check "default_subnet = 10.10.<N>.0/24" "10.10.1.0/24" "${S1_default_subnet:-}" "10.10.2.0/24" "${S2_default_subnet:-}" "10.10.3.0/24" "${S3_default_subnet:-}"
check "99-netavark.conf = netavark" "netavark" "${S1_netavark_backend:-}" "netavark" "${S2_netavark_backend:-}" "netavark" "${S3_netavark_backend:-}"
S1_srv_check="no"; echo "${S1_srv_podman:-}" | grep -q "dns: True subnet: 10.10.1" && S1_srv_check="yes"
S2_srv_check="no"; echo "${S2_srv_podman:-}" | grep -q "dns: True subnet: 10.10.2" && S2_srv_check="yes"
S3_srv_check="no"; echo "${S3_srv_podman:-}" | grep -q "dns: True subnet: 10.10.3" && S3_srv_check="yes"
check "srv<N>-podman has dns=true (accepts -v2)" "yes" "$S1_srv_check" "yes" "$S2_srv_check" "yes" "$S3_srv_check"
check "systemd-resolve dir non-empty (>=3)" "yes" "$( [ "${S1_resolved_dir_files:-0}" -ge 3 ] && echo yes || echo no )" "yes" "$( [ "${S2_resolved_dir_files:-0}" -ge 3 ] && echo yes || echo no )" "yes" "$( [ "${S3_resolved_dir_files:-0}" -ge 3 ] && echo yes || echo no )"
check "systemd-resolved active" "active" "${S1_resolved_active:-}" "active" "${S2_resolved_active:-}" "active" "${S3_resolved_active:-}"
echo ""
echo "=== end of report ==="
