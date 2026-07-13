#!/usr/bin/env bash
set -uo pipefail

PORT="${OMNI_PKI_MATRIX_PORT:-39447}"
CAFILE="${OMNI_PKI_TLS_BASE:-/etc/omni-srv-admin/tls}/ca-chain.crt.pem"
TLS_BASE="${OMNI_PKI_TLS_BASE:-/etc/omni-srv-admin/tls}"
JSON=0

HOST_IDS=(atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv)
HOST_IPS=(10.11.1.11 10.12.1.12 10.13.1.13 10.21.1.21)
HOST_DNS=(atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv)
HOST_REMOTES=(ubuntu@10.11.1.11 ubuntu@10.12.1.12 ubuntu@10.13.1.13 horistic@10.21.1.21)
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
if [ -n "${OMNI_SSH_BIN:-}" ]; then
  SSH_BIN="$OMNI_SSH_BIN"
elif [ -x /c/Windows/System32/OpenSSH/ssh.exe ]; then
  SSH_BIN=/c/Windows/System32/OpenSSH/ssh.exe
elif [ -x /mnt/c/Windows/System32/OpenSSH/ssh.exe ]; then
  SSH_BIN=/mnt/c/Windows/System32/OpenSSH/ssh.exe
else
  SSH_BIN=ssh
fi

usage() {
  cat >&2 <<'USAGE'
Usage: verify-fleet-pki-matrix.sh [--json]

Starts a temporary OpenSSL HTTPS endpoint on each target host and verifies every
source host against every target using both VPN IP SAN and DNS SAN checks.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --json)
      JSON=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

tmp_results="$(mktemp)"
cleanup_files=("$tmp_results")

cleanup_target() {
  local remote="$1"
  "$SSH_BIN" "${SSH_OPTS[@]}" "$remote" \
    "if [ -s /tmp/omni-pki-sserver-$PORT.pid ]; then sudo kill \$(cat /tmp/omni-pki-sserver-$PORT.pid) 2>/dev/null || true; rm -f /tmp/omni-pki-sserver-$PORT.pid; fi" \
    >/dev/null 2>&1 || true
}

cleanup_all() {
  local remote
  for remote in "${HOST_REMOTES[@]}"; do
    cleanup_target "$remote"
  done
  rm -f "${cleanup_files[@]}" 2>/dev/null || true
}
trap cleanup_all EXIT

start_target() {
  local host_id="$1" remote="$2"
  "$SSH_BIN" "${SSH_OPTS[@]}" "$remote" "set -eu; \
    sudo sh -c 'nohup openssl s_server -quiet -accept $PORT \
      -cert $TLS_BASE/$host_id/chain.crt.pem \
      -key $TLS_BASE/$host_id/server.key.pem \
      -www >/tmp/omni-pki-sserver-$PORT.log 2>&1 & echo \$! > /tmp/omni-pki-sserver-$PORT.pid'; \
    sleep 1; sudo ss -lntp | grep ':$PORT ' >/dev/null"
}

run_remote_check() {
  local source_remote="$1" target_ip="$2" verify_arg="$3" server_name="$4"
  "$SSH_BIN" "${SSH_OPTS[@]}" "$source_remote" "set -o pipefail; \
    echo Q | timeout 8 openssl s_client \
      -connect $target_ip:$PORT \
      -servername $server_name \
      -verify_return_error \
      -CAfile $CAFILE \
      $verify_arg \
      2>&1 | grep 'Verify return code: 0 (ok)' >/dev/null"
}

record_result() {
  local source="$1" target="$2" target_ip="$3" mode="$4" ok="$5"
  printf '%s\t%s\t%s\t%s\t%s\n' "$source" "$target" "$target_ip" "$mode" "$ok" >> "$tmp_results"
  if [ "$JSON" -eq 0 ]; then
    printf '%s %s -> %s %s (%s)\n' "$ok" "$source" "$target" "$mode" "$target_ip"
  fi
}

failures=0

for target_idx in "${!HOST_IDS[@]}"; do
  target_id="${HOST_IDS[$target_idx]}"
  target_ip="${HOST_IPS[$target_idx]}"
  target_dns="${HOST_DNS[$target_idx]}"
  target_remote="${HOST_REMOTES[$target_idx]}"

  cleanup_target "$target_remote"
  if ! start_target "$target_id" "$target_remote"; then
    for source_id in "${HOST_IDS[@]}"; do
      record_result "$source_id" "$target_id" "$target_ip" start failed
      failures=$((failures + 1))
    done
    continue
  fi

  for source_idx in "${!HOST_IDS[@]}"; do
    source_id="${HOST_IDS[$source_idx]}"
    source_remote="${HOST_REMOTES[$source_idx]}"
    if run_remote_check "$source_remote" "$target_ip" "-verify_ip $target_ip" "$target_dns"; then
      record_result "$source_id" "$target_id" "$target_ip" ip ok
    else
      record_result "$source_id" "$target_id" "$target_ip" ip failed
      failures=$((failures + 1))
    fi
    if run_remote_check "$source_remote" "$target_ip" "-verify_hostname $target_dns" "$target_dns"; then
      record_result "$source_id" "$target_id" "$target_ip" dns ok
    else
      record_result "$source_id" "$target_id" "$target_ip" dns failed
      failures=$((failures + 1))
    fi
  done

  cleanup_target "$target_remote"
done

if [ "$JSON" -eq 1 ]; then
  printf '{"status":"%s","port":%s,"results":[' "$(if [ "$failures" -eq 0 ]; then printf ok; else printf failed; fi)" "$PORT"
  first=1
  while IFS="$(printf '\t')" read -r source target target_ip mode ok; do
    if [ "$first" -eq 0 ]; then
      printf ','
    fi
    first=0
    printf '{"source":"%s","target":"%s","ip":"%s","mode":"%s","ok":%s}' \
      "$source" "$target" "$target_ip" "$mode" "$(if [ "$ok" = ok ]; then printf true; else printf false; fi)"
  done < "$tmp_results"
  printf ']}\n'
fi

if [ "$failures" -ne 0 ]; then
  exit 1
fi
