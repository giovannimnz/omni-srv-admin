#!/usr/bin/env bash
set -euo pipefail

BASE="${OMNI_PKI_CA_BASE:-/var/lib/omni-srv-admin/pki}"
TLS_BASE="${OMNI_PKI_TLS_BASE:-/etc/omni-srv-admin/tls}"
OPENSSL_CNF="${OMNI_PKI_OPENSSL_CNF:-/opt/omni-srv-admin/modules/fleet-pki/templates/openssl-ca.cnf}"
BACKUP_ROOT="${OMNI_PKI_BACKUP_ROOT:-/root/.backups}"
ROOT_CN="${OMNI_PKI_ROOT_CN:-ATIUS VPN Service Root CA}"
ISSUING_CN="${OMNI_PKI_ISSUING_CN:-ATIUS VPN Service Issuing CA}"

usage() {
  cat >&2 <<'USAGE'
Usage:
  omni-fleet-pki-bootstrap.sh init-ca
  omni-fleet-pki-bootstrap.sh sign-host --host-id HOST --csr CSR --san-json JSON
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

ensure_layout() {
  install -d -m 0700 "$BASE/private"
  install -d -m 0755 "$BASE/certs" "$BASE/certs/hosts" "$BASE/crl" "$BASE/db" "$BASE/intake" "$BASE/state"
  install -d -m 0755 "$TLS_BASE"
  touch "$BASE/db/index.txt"
  [ -s "$BASE/db/serial" ] || printf '1000\n' > "$BASE/db/serial"
  [ -s "$BASE/db/crlnumber" ] || printf '1000\n' > "$BASE/db/crlnumber"
}

install_ca_chain() {
  cat "$BASE/certs/issuing-ca.crt.pem" "$BASE/certs/root-ca.crt.pem" > "$BASE/certs/ca-chain.crt.pem.tmp"
  backup_path "$BASE/certs/ca-chain.crt.pem"
  mv "$BASE/certs/ca-chain.crt.pem.tmp" "$BASE/certs/ca-chain.crt.pem"
  chmod 0644 "$BASE/certs/ca-chain.crt.pem"

  backup_path "$TLS_BASE/ca-chain.crt.pem"
  install -m 0644 "$BASE/certs/ca-chain.crt.pem" "$TLS_BASE/ca-chain.crt.pem"
}

init_ca() {
  require_root
  command -v openssl >/dev/null 2>&1
  ensure_layout

  if [ ! -s "$BASE/private/root-ca.key.pem" ]; then
    openssl genrsa -out "$BASE/private/root-ca.key.pem" 4096 >/dev/null 2>&1
    chmod 0600 "$BASE/private/root-ca.key.pem"
  fi

  if [ ! -s "$BASE/certs/root-ca.crt.pem" ]; then
    openssl req -x509 -new -nodes \
      -key "$BASE/private/root-ca.key.pem" \
      -sha256 -days 3650 \
      -subj "/CN=$ROOT_CN" \
      -extensions root_ca_extensions \
      -config "$OPENSSL_CNF" \
      -out "$BASE/certs/root-ca.crt.pem" >/dev/null 2>&1
    chmod 0644 "$BASE/certs/root-ca.crt.pem"
  fi

  if [ ! -s "$BASE/private/issuing-ca.key.pem" ]; then
    openssl genrsa -out "$BASE/private/issuing-ca.key.pem" 4096 >/dev/null 2>&1
    chmod 0600 "$BASE/private/issuing-ca.key.pem"
  fi

  if [ ! -s "$BASE/certs/issuing-ca.crt.pem" ]; then
    openssl req -new \
      -key "$BASE/private/issuing-ca.key.pem" \
      -subj "/CN=$ISSUING_CN" \
      -out "$BASE/db/issuing-ca.csr.pem" >/dev/null 2>&1
    openssl x509 -req \
      -in "$BASE/db/issuing-ca.csr.pem" \
      -CA "$BASE/certs/root-ca.crt.pem" \
      -CAkey "$BASE/private/root-ca.key.pem" \
      -CAcreateserial \
      -out "$BASE/certs/issuing-ca.crt.pem" \
      -days 1825 -sha256 \
      -extfile "$OPENSSL_CNF" \
      -extensions issuing_ca_extensions >/dev/null 2>&1
    chmod 0644 "$BASE/certs/issuing-ca.crt.pem"
  fi

  install_ca_chain

  local root_fp issuing_fp
  root_fp="$(openssl x509 -in "$BASE/certs/root-ca.crt.pem" -noout -fingerprint -sha256 | cut -d= -f2)"
  issuing_fp="$(openssl x509 -in "$BASE/certs/issuing-ca.crt.pem" -noout -fingerprint -sha256 | cut -d= -f2)"
  printf '{"status":"ok","action":"init-ca","ca_base":%s,"root_fingerprint_sha256":%s,"issuing_fingerprint_sha256":%s}\n' \
    "$(printf '%s' "$BASE" | json_escape)" \
    "$(printf '%s' "$root_fp" | json_escape)" \
    "$(printf '%s' "$issuing_fp" | json_escape)"
}

render_leaf_ext() {
  local san_json="$1"
  SAN_JSON="$san_json" python3 <<'PY'
import ipaddress
import json
import os

sans = json.loads(os.environ["SAN_JSON"])
dns = [str(item).strip() for item in sans.get("dns", []) if str(item).strip()]
ips = []
for item in sans.get("ip", []):
    value = str(item).strip()
    if not value:
        continue
    ipaddress.ip_address(value)
    ips.append(value)

print("[server_cert]")
print("basicConstraints = critical, CA:FALSE")
print("keyUsage = critical, digitalSignature, keyEncipherment")
print("extendedKeyUsage = serverAuth, clientAuth")
print("subjectKeyIdentifier = hash")
print("authorityKeyIdentifier = keyid,issuer")
print("subjectAltName = @alt_names")
print()
print("[alt_names]")
for idx, value in enumerate(dns, 1):
    print(f"DNS.{idx} = {value}")
for idx, value in enumerate(ips, 1):
    print(f"IP.{idx} = {value}")
PY
}

sign_host() {
  require_root
  command -v openssl >/dev/null 2>&1
  local host_id="" csr="" san_json=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --host-id)
        host_id="${2:-}"
        shift 2
        ;;
      --csr)
        csr="${2:-}"
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
  if [ ! -s "$csr" ]; then
    echo "CSR not found: $csr" >&2
    exit 1
  fi
  if [ -z "$san_json" ]; then
    echo "--san-json is required" >&2
    exit 1
  fi
  ensure_layout
  if [ ! -s "$BASE/certs/issuing-ca.crt.pem" ] || [ ! -s "$BASE/private/issuing-ca.key.pem" ]; then
    echo "issuing CA is not initialized" >&2
    exit 1
  fi

  local ext cert chain
  ext="$(mktemp)"
  render_leaf_ext "$san_json" > "$ext"
  cert="$BASE/certs/hosts/$host_id.crt.pem"
  chain="$BASE/certs/hosts/$host_id.chain.crt.pem"
  backup_path "$cert"
  backup_path "$chain"
  openssl x509 -req \
    -in "$csr" \
    -CA "$BASE/certs/issuing-ca.crt.pem" \
    -CAkey "$BASE/private/issuing-ca.key.pem" \
    -CAserial "$BASE/db/serial" \
    -out "$cert" \
    -days 397 -sha256 \
    -extfile "$ext" \
    -extensions server_cert >/dev/null 2>&1
  rm -f "$ext"
  cat "$cert" "$BASE/certs/issuing-ca.crt.pem" "$BASE/certs/root-ca.crt.pem" > "$chain"
  chmod 0644 "$cert" "$chain"

  local serial fp
  serial="$(openssl x509 -in "$cert" -noout -serial | cut -d= -f2)"
  fp="$(openssl x509 -in "$cert" -noout -fingerprint -sha256 | cut -d= -f2)"
  printf '{"status":"ok","action":"sign-host","host":%s,"serial":%s,"fingerprint_sha256":%s,"cert":%s,"chain":%s}\n' \
    "$(printf '%s' "$host_id" | json_escape)" \
    "$(printf '%s' "$serial" | json_escape)" \
    "$(printf '%s' "$fp" | json_escape)" \
    "$(printf '%s' "$cert" | json_escape)" \
    "$(printf '%s' "$chain" | json_escape)"
}

case "${1:-}" in
  init-ca)
    shift
    init_ca "$@"
    ;;
  sign-host)
    shift
    sign_host "$@"
    ;;
  *)
    usage
    exit 2
    ;;
esac
