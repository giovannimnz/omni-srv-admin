#!/usr/bin/env bash
set -euo pipefail

TLS_BASE="${OMNI_PKI_TLS_BASE:-/etc/omni-srv-admin/tls}"
BACKUP_ROOT="${OMNI_PKI_BACKUP_ROOT:-/root/.backups}"

usage() {
  cat >&2 <<'USAGE'
Usage:
  omni-fleet-pki-host.sh preflight
  omni-fleet-pki-host.sh ensure-key-csr --host-id HOST --san-json JSON
  omni-fleet-pki-host.sh install-ca --root-ca ROOT --issuing-ca ISSUING
  omni-fleet-pki-host.sh install-leaf --host-id HOST --cert CERT --chain CHAIN
  omni-fleet-pki-host.sh install-peer --peer-id HOST --cert CERT
  omni-fleet-pki-host.sh verify --host-id HOST
USAGE
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'
}

backup_path() {
  local target="$1"
  if [ ! -e "$target" ]; then
    return 0
  fi
  local stamp backup_dir rel
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="$BACKUP_ROOT/omni-fleet-pki-$stamp"
  rel="${target#/}"
  mkdir -p "$backup_dir/$(dirname "$rel")"
  cp -a "$target" "$backup_dir/$rel"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "must run as root" >&2
    exit 1
  fi
}

safe_host_id() {
  case "$1" in
    ""|*[!A-Za-z0-9._-]*)
      echo "invalid host id: $1" >&2
      exit 1
      ;;
  esac
}

host_dir() {
  printf '%s/%s' "$TLS_BASE" "$1"
}

render_csr_config() {
  local host_id="$1" san_json="$2"
  HOST_ID="$host_id" SAN_JSON="$san_json" python3 <<'PY'
import ipaddress
import json
import os

host_id = os.environ["HOST_ID"]
sans = json.loads(os.environ["SAN_JSON"])
dns = [str(item).strip() for item in sans.get("dns", []) if str(item).strip()]
ips = []
for item in sans.get("ip", []):
    value = str(item).strip()
    if not value:
        continue
    ipaddress.ip_address(value)
    ips.append(value)

print("[req]")
print("default_bits = 3072")
print("prompt = no")
print("default_md = sha256")
print("distinguished_name = dn")
print("req_extensions = req_ext")
print()
print("[dn]")
print(f"CN = {host_id}")
print()
print("[req_ext]")
print("subjectAltName = @alt_names")
print()
print("[alt_names]")
for idx, value in enumerate(dns, 1):
    print(f"DNS.{idx} = {value}")
for idx, value in enumerate(ips, 1):
    print(f"IP.{idx} = {value}")
PY
}

preflight() {
  command -v openssl >/dev/null 2>&1
  if command -v update-ca-certificates >/dev/null 2>&1; then
    update_ca=true
  else
    update_ca=false
  fi
  printf '{"status":"ok","action":"preflight","openssl":true,"update_ca_certificates":%s}\n' "$update_ca"
}

ensure_key_csr() {
  require_root
  command -v openssl >/dev/null 2>&1
  local host_id="" san_json=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --host-id)
        host_id="${2:-}"
        shift 2
        ;;
      --san-json)
        san_json="${2:-}"
        shift 2
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
  safe_host_id "$host_id"
  if [ -z "$san_json" ]; then
    echo "--san-json is required" >&2
    exit 1
  fi
  local dir key csr cfg
  dir="$(host_dir "$host_id")"
  key="$dir/server.key.pem"
  csr="$dir/server.csr.pem"
  install -d -m 0750 "$dir"
  if [ ! -s "$key" ]; then
    openssl genrsa -out "$key" 3072 >/dev/null 2>&1
    chmod 0600 "$key"
  fi
  cfg="$(mktemp)"
  render_csr_config "$host_id" "$san_json" > "$cfg"
  backup_path "$csr"
  openssl req -new -key "$key" -out "$csr" -config "$cfg" >/dev/null 2>&1
  rm -f "$cfg"
  chmod 0644 "$csr"
  printf '{"status":"ok","action":"ensure-key-csr","host":%s,"csr":%s}\n' \
    "$(printf '%s' "$host_id" | json_escape)" \
    "$(printf '%s' "$csr" | json_escape)"
}

install_ca() {
  require_root
  local root_ca="" issuing_ca=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --root-ca)
        root_ca="${2:-}"
        shift 2
        ;;
      --issuing-ca)
        issuing_ca="${2:-}"
        shift 2
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
  [ -s "$root_ca" ] || { echo "root CA not found: $root_ca" >&2; exit 1; }
  [ -s "$issuing_ca" ] || { echo "issuing CA not found: $issuing_ca" >&2; exit 1; }
  install -d -m 0755 "$TLS_BASE"
  install -d -m 0755 /usr/local/share/ca-certificates
  backup_path /usr/local/share/ca-certificates/atius-vpn-service-root-ca.crt
  backup_path /usr/local/share/ca-certificates/atius-vpn-service-issuing-ca.crt
  install -m 0644 "$root_ca" /usr/local/share/ca-certificates/atius-vpn-service-root-ca.crt
  install -m 0644 "$issuing_ca" /usr/local/share/ca-certificates/atius-vpn-service-issuing-ca.crt
  cat "$issuing_ca" "$root_ca" > "$TLS_BASE/ca-chain.crt.pem.tmp"
  backup_path "$TLS_BASE/ca-chain.crt.pem"
  mv "$TLS_BASE/ca-chain.crt.pem.tmp" "$TLS_BASE/ca-chain.crt.pem"
  chmod 0644 "$TLS_BASE/ca-chain.crt.pem"
  if command -v update-ca-certificates >/dev/null 2>&1; then
    update-ca-certificates >/dev/null
  fi
  printf '{"status":"ok","action":"install-ca","ca_chain":%s}\n' \
    "$(printf '%s' "$TLS_BASE/ca-chain.crt.pem" | json_escape)"
}

install_leaf() {
  require_root
  local host_id="" cert="" chain=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --host-id)
        host_id="${2:-}"
        shift 2
        ;;
      --cert)
        cert="${2:-}"
        shift 2
        ;;
      --chain)
        chain="${2:-}"
        shift 2
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
  safe_host_id "$host_id"
  [ -s "$cert" ] || { echo "cert not found: $cert" >&2; exit 1; }
  [ -s "$chain" ] || { echo "chain not found: $chain" >&2; exit 1; }
  local dir
  dir="$(host_dir "$host_id")"
  install -d -m 0750 "$dir"
  backup_path "$dir/server.crt.pem"
  backup_path "$dir/chain.crt.pem"
  install -m 0644 "$cert" "$dir/server.crt.pem"
  install -m 0644 "$chain" "$dir/chain.crt.pem"
  printf '{"status":"ok","action":"install-leaf","host":%s,"cert":%s,"chain":%s}\n' \
    "$(printf '%s' "$host_id" | json_escape)" \
    "$(printf '%s' "$dir/server.crt.pem" | json_escape)" \
    "$(printf '%s' "$dir/chain.crt.pem" | json_escape)"
}

install_peer() {
  require_root
  local peer_id="" cert=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --peer-id)
        peer_id="${2:-}"
        shift 2
        ;;
      --cert)
        cert="${2:-}"
        shift 2
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
  safe_host_id "$peer_id"
  [ -s "$cert" ] || { echo "peer cert not found: $cert" >&2; exit 1; }
  install -d -m 0755 "$TLS_BASE/peers"
  backup_path "$TLS_BASE/peers/$peer_id.crt.pem"
  install -m 0644 "$cert" "$TLS_BASE/peers/$peer_id.crt.pem"
  printf '{"status":"ok","action":"install-peer","peer":%s}\n' \
    "$(printf '%s' "$peer_id" | json_escape)"
}

verify_host() {
  local host_id=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --host-id)
        host_id="${2:-}"
        shift 2
        ;;
      *)
        usage
        exit 2
        ;;
    esac
  done
  safe_host_id "$host_id"
  local dir cert chain ca_chain
  dir="$(host_dir "$host_id")"
  cert="$dir/server.crt.pem"
  chain="$dir/chain.crt.pem"
  ca_chain="$TLS_BASE/ca-chain.crt.pem"
  [ -s "$cert" ] || { echo "cert missing: $cert" >&2; exit 1; }
  [ -s "$chain" ] || { echo "chain missing: $chain" >&2; exit 1; }
  [ -s "$ca_chain" ] || { echo "ca chain missing: $ca_chain" >&2; exit 1; }
  openssl verify -CAfile "$ca_chain" "$cert" >/dev/null
  printf '{"status":"ok","action":"verify","host":%s}\n' \
    "$(printf '%s' "$host_id" | json_escape)"
}

case "${1:-}" in
  preflight)
    shift
    preflight "$@"
    ;;
  ensure-key-csr)
    shift
    ensure_key_csr "$@"
    ;;
  install-ca)
    shift
    install_ca "$@"
    ;;
  install-leaf)
    shift
    install_leaf "$@"
    ;;
  install-peer)
    shift
    install_peer "$@"
    ;;
  verify)
    shift
    verify_host "$@"
    ;;
  *)
    usage
    exit 2
    ;;
esac
