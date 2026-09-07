#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONDONTWRITEBYTECODE=1

ROOT="${OMNI_SRV_ADMIN:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd -P)}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/omni/oci-arm64-host-setup"
LOCK_FILE="$STATE_DIR/setup.lock"
RUN_ID="${OMNI_SETUP_RUN_ID:-$(date +%Y%m%dT%H%M%S%z)-$$}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._+-]+$ ]] || { printf 'invalid OMNI_SETUP_RUN_ID\n' >&2; exit 2; }
RUN_DIR="$STATE_DIR/runs/$RUN_ID"
LOG_FILE="$RUN_DIR/setup.log"
MODE="verify-only"
RESUME=0
FROM_STEP=""
SOURCE_MANIFEST_ORIGINAL="$ROOT/SOURCE-MANIFEST.json"
SOURCE_MANIFEST="$RUN_DIR/source-manifest.sealed.json"
EXPECTED_SOURCE_SHA256="${OMNI_SETUP_EXPECTED_SOURCE_SHA256:-}"
SOURCE_SHA256=""
TARGET_SHORT="${OMNI_SETUP_HOST_ID:-atius-srv-4}"
TARGET_FQDN="${OMNI_SETUP_FQDN:-atius-srv-4.atius.internal}"
TARGET_PRIVATE_IP="${OMNI_SETUP_PRIVATE_IP:-10.14.1.14}"
TARGET_PUBLIC_IP="${OMNI_SETUP_PUBLIC_IP:-164.152.48.22}"
TARGET_WG_IP="${OMNI_SETUP_WG_IP:-10.100.100.18}"
DNS_PRIMARY="${OMNI_SETUP_DNS:-10.11.1.11}"
NODE_VERSION="${OMNI_SETUP_NODE_VERSION:-v24.20.0}"
NPM_VERSION="${OMNI_SETUP_NPM_VERSION:-11.19.0}"
BUN_VERSION="${OMNI_SETUP_BUN_VERSION:-1.4.2}"
CODEX_VERSION="${OMNI_SETUP_CODEX_VERSION:-0.153.4}"
UV_VERSION="${OMNI_SETUP_UV_VERSION:-0.11.24}"
RUSTUP_VERSION="${OMNI_SETUP_RUSTUP_VERSION:-1.29.1}"
RUST_TOOLCHAIN_VERSION="${OMNI_SETUP_RUST_TOOLCHAIN_VERSION:-1.98.1}"
CARGO_BINSTALL_VERSION="${OMNI_SETUP_CARGO_BINSTALL_VERSION:-1.20.0}"
ZELLIJ_VERSION="${OMNI_SETUP_ZELLIJ_VERSION:-0.45.1}"
PODMAN_COMPOSE_VERSION="${OMNI_SETUP_PODMAN_COMPOSE_VERSION:-1.6.0}"
PYTHON_DOTENV_VERSION="${OMNI_SETUP_PYTHON_DOTENV_VERSION:-1.2.2}"
GRAPHIFY_VERSION="${OMNI_SETUP_GRAPHIFY_VERSION:-0.9.23}"
GRAPHIFY_OPENAI_VERSION="${OMNI_SETUP_GRAPHIFY_OPENAI_VERSION:-2.24.0}"
HERMES_PYTHON_VERSION="${OMNI_SETUP_HERMES_PYTHON_VERSION:-3.11.15}"
GSD_VERSION="${OMNI_SETUP_GSD_VERSION:-1.13.0}"
HERMES_COMMIT="${OMNI_SETUP_HERMES_COMMIT:-01ae7a5668ce0fa2efca524a4567cacdd0786c95}"
HERMES_REPO_URL="${OMNI_SETUP_HERMES_REPO_URL:-https://github.com/NousResearch/hermes-agent.git}"
OBSIDIAN_VERSION="${OMNI_SETUP_OBSIDIAN_VERSION:-1.12.7}"
CHATGPT_VERSION="${OMNI_SETUP_CHATGPT_VERSION:-26.901.51231}"
CHROME_VERSION="${OMNI_SETUP_CHROME_VERSION:-152.0.7977.82-1}"
UBUNTU_PRO_TOKEN_FILE="${OMNI_UBUNTU_PRO_TOKEN_FILE:-}"
DARK_THEME_CTL="${OMNI_DARK_THEME_CTL:-$HOME/.local/bin/dark-themectl}"
EXPECTED_ARCH="aarch64"
RUSTUP_INIT_SHA256="15f6e4ce9f583b929c996c91562bad6d4454f3281de858b02cdfdef615fac433"
CARGO_BINSTALL_ARCHIVE_SHA256="34daacc97111b8765b59128446ed4cd0bf6f8995a8c58199bd5597f1a42bf6b5"
CARGO_BINSTALL_BINARY_SHA256="140743c27577d74c5255e5fd9b559f1fcad1f3aa710603dd3160625f003fd86b"
ZELLIJ_ARCHIVE_SHA256="05f0802afadd53f8db9514e7cae53c9ae8432fed1b35b8294aa816ee3044a16b"
ZELLIJ_BINARY_SHA256="2a2c0621e6f3b11ecbb05d66939a48000a2508604620aa20727a5fd61c49f451"
BUN_ARCHIVE_SHA256="54328bbc2d9c8e0c9f892c544d66c57a83b84139e34909e5ee81758f1ac8fda7"
BUN_BINARY_SHA256="616f267a34278ff5ac282df37ffdfba1d7141f4f6926bca99af2cd6ef3ad32b1"
UV_ARCHIVE_SHA256="e22c66d36a0098b17cff80a8647e0b8c58202af899d4e9eb820fc7ad126435a1"
UV_BINARY_SHA256="6058ac5851b30edb57f2277d8b4328ab72effad02be8c88e4bfc33ed6140d094"
UVX_BINARY_SHA256="eace7b73a6181fd31d2a890370556928c01d03522465306bf5ae647c796e9122"
PODMAN_SMOKE_IMAGE="docker.io/library/alpine@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin"
SETUP_SIGNATURE="$(printf '%s\0' \
  "$TARGET_SHORT" "$TARGET_FQDN" "$TARGET_PRIVATE_IP" "$TARGET_PUBLIC_IP" "$TARGET_WG_IP" \
  "$DNS_PRIMARY" "$NODE_VERSION" "$NPM_VERSION" "$BUN_VERSION" "$CODEX_VERSION" \
  "$UV_VERSION" "$RUSTUP_VERSION" "$RUST_TOOLCHAIN_VERSION" "$CARGO_BINSTALL_VERSION" \
  "$ZELLIJ_VERSION" "$PODMAN_COMPOSE_VERSION" "$PYTHON_DOTENV_VERSION" \
  "$GRAPHIFY_VERSION" "$GRAPHIFY_OPENAI_VERSION" "$HERMES_PYTHON_VERSION" \
  "$GSD_VERSION" "$HERMES_COMMIT" "$HERMES_REPO_URL" "$OBSIDIAN_VERSION" \
  "$CHATGPT_VERSION" "$CHROME_VERSION" "$EXPECTED_ARCH" "$DARK_THEME_CTL" \
  | sha256sum | cut -d' ' -f1)"

STEPS=(
  "preflight"
  "packages"
  "ubuntu-pro"
  "identity-network"
  "podman"
  "desktop-xrdp"
  "landscape"
  "fleet-agent"
  "toolchains"
  "desktop-apps"
  "agents"
  "gsd-graphify"
  "agent-content"
  "obsidian"
  "resource-governor"
  "desktop-theme"
  "final-verify"
)

usage() {
  cat <<'EOF'
Usage: oci-arm64-host-setup.sh [--dry-run|--verify-only|--apply] [--resume] [--from-step STEP]

Default: --verify-only. --apply performs only idempotent remediations and writes
one receipt per completed step. --resume skips only PASS receipts produced by
the exact same source manifest and setup input signature. final-verify never skips.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry-run" ;;
    --verify-only) MODE="verify-only" ;;
    --apply) MODE="apply" ;;
    --resume) RESUME=1 ;;
    --from-step) shift; FROM_STEP="${1:?missing step after --from-step}" ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$RUN_DIR" "$STATE_DIR/completed/$MODE"
chmod 700 "$STATE_DIR" "$STATE_DIR/runs" "$RUN_DIR" "$STATE_DIR/completed" "$STATE_DIR/completed/$MODE" 2>/dev/null || true
exec 9>"$LOCK_FILE"
/usr/bin/flock -n 9 || { printf 'another OCI ARM64 setup is running\n' >&2; exit 75; }
if [ -f "$SOURCE_MANIFEST_ORIGINAL" ] && [ ! -L "$SOURCE_MANIFEST_ORIGINAL" ]; then
  python3 - "$SOURCE_MANIFEST_ORIGINAL" "$SOURCE_MANIFEST" <<'PY'
from pathlib import Path
import os,sys
source,target=map(Path,sys.argv[1:])
flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW
fd=os.open(source,flags)
try:
    chunks=[]
    while True:
        chunk=os.read(fd,1024*1024)
        if not chunk: break
        chunks.append(chunk)
finally:
    os.close(fd)
target.write_bytes(b''.join(chunks))
target.chmod(0o600)
PY
  SOURCE_SHA256="$(sha256sum "$SOURCE_MANIFEST" | cut -d' ' -f1)"
else
  SOURCE_SHA256="$(sha256sum "${BASH_SOURCE[0]}" | cut -d' ' -f1)"
fi
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

CURRENT_STEP="bootstrap"
step_started_at=""
cleanup_sensitive() {
  find "$RUN_DIR" -maxdepth 1 -type f \
    \( -name 'ubuntu-pro-attach.*.json' -o -name 'hermes-vault.env' -o -name 'hermes.env' \
       -o -name 'landscape-client.env' -o -name 'landscape-registration.ini' \
       -o -name 'omni-fleet.env' -o -name 'fleet-db.env' -o -name 'xrdp-srv4.env' \
       -o -name 'xrdp-cert.pem' -o -name 'xrdp-key.pem' -o -name 'xrdp.ini' \
       -o -name 'obsidian-readonly.env' -o -name 'obsidian-deploy-key' \
       -o -name 'obsidian-deploy-key.pub' -o -name 'obsidian-deploy-key.url' \) \
    -delete 2>/dev/null || true
}
trap cleanup_sensitive EXIT
trap 'rc=$?; printf "status=FAILED step=%s rc=%s at=%s\n" "$CURRENT_STEP" "$rc" "$(date -Is)" | tee "$RUN_DIR/FAILED" >&2; chmod 600 "$RUN_DIR/FAILED"; exit "$rc"' ERR

log() { printf '[oci-arm64-setup] %s\n' "$*"; }
fail() { log "FAIL $*" >&2; return 1; }
pass() { log "PASS $*"; }
run() {
  if [ "$MODE" = "dry-run" ]; then
    printf 'DRY'; printf ' %q' "$@"; printf '\n'
    return 0
  fi
  "$@"
}
run_shell() {
  local command="$1"
  if [ "$MODE" = "dry-run" ]; then
    printf 'DRY bash -lc %q\n' "$command"
    return 0
  fi
  /usr/bin/bash -lc "$command"
}

download_checked() {
  local url="$1" destination="$2" expected="$3" actual
  curl -fsSLo "$destination" "$url"
  actual="$(sha256sum "$destination" | cut -d' ' -f1)"
  require_eq "$actual" "$expected" "download checksum for $(basename "$destination")"
}

install_vault_helper() {
  install -d -m 0700 "$HOME/.config/omni"
  install -m 0600 "$ROOT/modules/fleet/configs/ssh/atius-srv3-vault-known-hosts" \
    "$HOME/.config/omni/atius-srv3-vault-known-hosts"
  install -m 0755 "$ROOT/modules/fleet/scripts/atius-vault-env" \
    "$HOME/.local/bin/atius-vault-env"
}

install_desktop_app_repositories() {
  [ "$MODE" = "apply" ] || return 0
  sudo -n install -D -m 0644 -o root -g root \
    "$ROOT/modules/fleet/configs/apt/keyrings/chatgpt-archive-keyring.gpg" \
    /usr/share/keyrings/chatgpt-archive-keyring.gpg
  sudo -n install -D -m 0644 -o root -g root \
    "$ROOT/modules/fleet/configs/apt/keyrings/google-chrome.gpg" \
    /usr/share/keyrings/google-chrome.gpg
  sudo -n install -D -m 0644 -o root -g root \
    "$ROOT/modules/fleet/configs/apt/sources.list.d/chatgpt.sources" \
    /etc/apt/sources.list.d/chatgpt.sources
  sudo -n install -D -m 0644 -o root -g root \
    "$ROOT/modules/fleet/configs/apt/sources.list.d/google-chrome.sources" \
    /etc/apt/sources.list.d/google-chrome.sources
}

verify_desktop_app_repositories() {
  require_file "$ROOT/modules/fleet/configs/apt/keyrings/chatgpt-archive-keyring.gpg"
  require_file "$ROOT/modules/fleet/configs/apt/keyrings/google-chrome.gpg"
  require_file "$ROOT/modules/fleet/configs/apt/sources.list.d/chatgpt.sources"
  require_file "$ROOT/modules/fleet/configs/apt/sources.list.d/google-chrome.sources"
  sudo -n cmp -s "$ROOT/modules/fleet/configs/apt/keyrings/chatgpt-archive-keyring.gpg" \
    /usr/share/keyrings/chatgpt-archive-keyring.gpg || fail "ChatGPT keyring drift"
  sudo -n cmp -s "$ROOT/modules/fleet/configs/apt/keyrings/google-chrome.gpg" \
    /usr/share/keyrings/google-chrome.gpg || fail "Google Chrome keyring drift"
  sudo -n cmp -s "$ROOT/modules/fleet/configs/apt/sources.list.d/chatgpt.sources" \
    /etc/apt/sources.list.d/chatgpt.sources || fail "ChatGPT apt source drift"
  sudo -n cmp -s "$ROOT/modules/fleet/configs/apt/sources.list.d/google-chrome.sources" \
    /etc/apt/sources.list.d/google-chrome.sources || fail "Google Chrome apt source drift"
  gpg --show-keys --with-fingerprint /usr/share/keyrings/chatgpt-archive-keyring.gpg \
    | grep -Fq '3BFA 0E4A E8B8 CC16 A2D9  BA68 4A3B 4A56 6C46 60E4' \
    || fail "ChatGPT keyring fingerprint drift"
  gpg --show-keys --with-fingerprint /usr/share/keyrings/google-chrome.gpg \
    | grep -Fq 'EB4C 1BFD 4F04 2F6D DDCC  EC91 7721 F63B D38B 4796' \
    || fail "Google Chrome keyring fingerprint drift"
  apt-cache policy chatgpt | grep -Fq 'persistent.oaistatic.com/codex-app-prod/linux/deb' \
    || fail "ChatGPT apt policy missing official repo"
  apt-cache policy google-chrome-stable | grep -Fq 'dl.google.com/linux/chrome-stable/deb' \
    || fail "Google Chrome apt policy missing official repo"
  pass "desktop app apt repositories"
}
verify_source_manifest() {
  [ -f "$SOURCE_MANIFEST" ] && [ ! -L "$SOURCE_MANIFEST" ] || {
    [ "$MODE" = "dry-run" ] && return 0
    fail "SOURCE-MANIFEST.json absent"
    return
  }
  if [ "$MODE" != "dry-run" ]; then
    [ -n "$EXPECTED_SOURCE_SHA256" ] || fail "OMNI_SETUP_EXPECTED_SOURCE_SHA256 is required"
    require_eq "$SOURCE_SHA256" "$EXPECTED_SOURCE_SHA256" "source manifest out-of-band seal"
  fi
  python3 - "$ROOT" "$SOURCE_MANIFEST" <<'PY'
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]).resolve()
manifest=json.load(open(sys.argv[2]))
rows=manifest.get("files") or []
if not rows:
    raise SystemExit("empty source manifest")
declared={row["path"] for row in rows}
actual={
    str(path.relative_to(root))
    for path in root.rglob("*")
    if path.is_file() and path.name != "SOURCE-MANIFEST.json"
}
if actual != declared:
    raise SystemExit({"missing": sorted(declared-actual), "undeclared": sorted(actual-declared)})
for row in rows:
    raw=root/row["path"]
    path=raw.resolve()
    if not path.is_relative_to(root): raise SystemExit(f"outside root: {row['path']}")
    cursor=raw
    while cursor != root:
        if cursor.is_symlink(): raise SystemExit(f"symlink component: {row['path']}")
        cursor=cursor.parent
    if not raw.is_file() or raw.is_symlink(): raise SystemExit(f"invalid file: {row['path']}")
    if raw.stat().st_size != int(row["bytes"]): raise SystemExit(f"size drift: {row['path']}")
    if (raw.stat().st_mode & 0o777) != int(str(row["mode"]), 8): raise SystemExit(f"mode drift: {row['path']}")
    if hashlib.sha256(raw.read_bytes()).hexdigest() != row["sha256"]: raise SystemExit(f"sha drift: {row['path']}")
print(f"source_manifest_entries={len(rows)}")
PY
  pass "source manifest"
}
require_file() { [ -f "$1" ] || fail "required file missing: $1"; }
require_command() { command -v "$1" >/dev/null 2>&1 || fail "required command missing: $1"; }
require_eq() { [ "$1" = "$2" ] || fail "$3 expected=$2 actual=$1"; }
must_not_exist() { [ ! -e "$1" ] || fail "forbidden local auth/state exists: $1"; }
must_not_load() {
  local unit="$1" load
  if ! load="$(systemctl --user show "$unit" -p LoadState --value 2>&1)"; then
    fail "systemctl state query failed for $unit: $load"
  fi
  [ "$load" = "not-found" ] || fail "SRV-1-only unit loaded: $unit state=$load"
}

receipt_path() { printf '%s/%s/%s.json' "$STATE_DIR/completed" "$MODE" "$1"; }
mark_step_complete() {
  local step="$1" receipt tmp
  receipt="$(receipt_path "$step")"
  tmp="$receipt.tmp.$$"
  python3 - "$step" "$MODE" "$RUN_ID" "$step_started_at" "$SOURCE_SHA256" "$SETUP_SIGNATURE" >"$tmp" <<'PY'
import json,sys,datetime
step,mode,run_id,started,source_sha256,setup_signature=sys.argv[1:]
print(json.dumps({
  "step": step,
  "status": "PASS",
  "mode": mode,
  "run_id": run_id,
  "started_at": started,
  "completed_at": datetime.datetime.now().astimezone().isoformat(),
  "source_sha256": source_sha256,
  "setup_signature": setup_signature,
}, sort_keys=True))
PY
  chmod 600 "$tmp"
  mv -f "$tmp" "$receipt"
}

receipt_is_current() {
  local receipt="$1"
  [ -f "$receipt" ] || return 1
  python3 - "$receipt" "$SOURCE_SHA256" "$SETUP_SIGNATURE" <<'PY'
import json,sys
receipt,expected,setup_signature=sys.argv[1:]
try:
    value=json.load(open(receipt))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if value.get("status") == "PASS" and value.get("source_sha256") == expected and value.get("setup_signature") == setup_signature else 1)
PY
}

apply_packages() {
  local packages=(
    ca-certificates curl git gnupg jq unzip xz-utils tar rsync openssh-client
    build-essential python3 python3-dev python3-pip python3-venv libffi-dev pipx
    dnsutils postgresql-client file openssl ripgrep systemd-resolved
    wireguard-tools xdg-user-dirs podman-compose cockpit cockpit-podman
    lightdm lightdm-gtk-greeter lxde lxde-core lxhotkey-plugin-openbox
    xrdp xorgxrdp tigervnc-common tigervnc-standalone-server tigervnc-tools
    dbus-x11 freerdp2-x11 desktop-file-utils wmctrl xdotool kdocker
    podman prometheus-node-exporter landscape-client zsh ffmpeg
    "chatgpt=$CHATGPT_VERSION" "google-chrome-stable=$CHROME_VERSION"
  )
  if [ "$MODE" = "apply" ]; then
    install_desktop_app_repositories
    run sudo -n apt-get update -qq
    run sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install --allow-downgrades -y "${packages[@]}"
  elif [ "$MODE" = "dry-run" ]; then
    run sudo -n apt-get update -qq
    run sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install --allow-downgrades -y "${packages[@]}"
  fi
  local package
  for package in ca-certificates curl git gnupg jq unzip xz-utils tar rsync openssh-client \
    build-essential python3 python3-dev python3-pip python3-venv libffi-dev pipx \
    dnsutils postgresql-client file openssl ripgrep systemd-resolved \
    wireguard-tools xdg-user-dirs podman-compose cockpit cockpit-podman \
    lightdm lightdm-gtk-greeter lxde lxde-core lxhotkey-plugin-openbox \
    xrdp xorgxrdp tigervnc-common tigervnc-standalone-server tigervnc-tools \
    dbus-x11 freerdp2-x11 desktop-file-utils wmctrl xdotool kdocker \
    podman prometheus-node-exporter landscape-client zsh ffmpeg \
    chatgpt google-chrome-stable; do
    dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed' \
      || fail "package missing: $package"
  done
  verify_desktop_app_repositories
  pass "packages"
}

verify_ubuntu_pro() {
  sudo -n pro status --format json | python3 -c '
import json,sys
x=json.load(sys.stdin)
services={item.get("name"): item for item in x.get("services", [])}
if x.get("attached") is not True: raise SystemExit("Ubuntu Pro detached")
if services.get("esm-apps", {}).get("status") != "enabled": raise SystemExit("esm-apps disabled")
if services.get("esm-infra", {}).get("status") != "enabled": raise SystemExit("esm-infra disabled")
'
  pass "pro status --format json attached with esm-apps/esm-infra"
}

apply_ubuntu_pro() {
  if [ "$MODE" = "dry-run" ]; then
    log "DRY verify or attach Ubuntu Pro, enable esm-apps/esm-infra, apt upgrade"
    return 0
  fi
  if ! sudo -n pro status --format json | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("attached") else 1)'; then
    [ "$MODE" = "apply" ] || fail "Ubuntu Pro not attached"
    [ -n "$UBUNTU_PRO_TOKEN_FILE" ] && [ -f "$UBUNTU_PRO_TOKEN_FILE" ] \
      || fail "Ubuntu Pro token file unavailable; set OMNI_UBUNTU_PRO_TOKEN_FILE"
    [ "$(stat -c %a "$UBUNTU_PRO_TOKEN_FILE")" = "600" ] \
      || fail "Ubuntu Pro token file must be mode 0600"
    attach_config="$(mktemp "$RUN_DIR/ubuntu-pro-attach.XXXXXX.json")"
    chmod 600 "$attach_config"
    python3 - "$UBUNTU_PRO_TOKEN_FILE" "$attach_config" <<'PY'
from pathlib import Path
import json,sys
source,target=map(Path,sys.argv[1:])
token=source.read_text().strip()
if not token:
    raise SystemExit("Ubuntu Pro token file is empty")
target.write_text(json.dumps({"token": token}) + "\n")
PY
    sudo -n pro attach --no-auto-enable --attach-config "$attach_config"
    rm -f "$attach_config"
  fi
  sudo -n pro enable esm-apps --assume-yes >/dev/null 2>&1 || true
  sudo -n pro enable esm-infra --assume-yes >/dev/null 2>&1 || true
  if [ "$MODE" = "apply" ]; then
    sudo -n apt-get update -qq
    sudo -n env DEBIAN_FRONTEND=noninteractive apt-get \
      -o Dpkg::Options::=--force-confold upgrade -y
  fi
  verify_ubuntu_pro
}

verify_network() {
  require_eq "$(hostname -s)" "$TARGET_SHORT" "short hostname"
  require_eq "$(hostname -f)" "$TARGET_FQDN" "FQDN"
  require_eq "$(getent ahostsv4 "$TARGET_FQDN" | awk 'NR == 1 { print $1 }')" "$TARGET_PRIVATE_IP" "self FQDN address"
  ip -4 -o addr show | grep -Fq "$TARGET_PRIVATE_IP/" || fail "private IP missing"
  ip -4 -o addr show wg100 | grep -Fq "$TARGET_WG_IP/32" || fail "WireGuard IP missing"
  resolvectl dns | grep -Fq "$DNS_PRIMARY" || fail "internal resolver missing"
  require_eq "$(dig +short @"$DNS_PRIMARY" "$TARGET_FQDN" A | tail -n1)" "$TARGET_PRIVATE_IP" "internal A"
  require_eq "$(dig +short "$TARGET_SHORT.atius.com.br" A | tail -n1)" "$TARGET_PUBLIC_IP" "public A"
  require_eq "$(dig +short @"$DNS_PRIMARY" -x "$TARGET_PRIVATE_IP" | tail -n1)" "$TARGET_FQDN." "internal PTR"
  sudo -n wg show wg100 >/dev/null
  ping -c1 -W2 "$DNS_PRIMARY" >/dev/null
  pass "hostname -f / resolvectl / wg show / A/PTR"
}

apply_host_identity() {
  [ "$MODE" = "apply" ] || return 0
  local rendered
  rendered="$(mktemp "$RUN_DIR/hosts.XXXXXX")"
  python3 - /etc/hosts "$rendered" "$TARGET_PRIVATE_IP" "$TARGET_FQDN" "$TARGET_SHORT" <<'PY'
from pathlib import Path
import sys

source, target = map(Path, sys.argv[1:3])
private_ip, fqdn, short = sys.argv[3:]
output = []
for raw in source.read_text().splitlines():
    body = raw.split("#", 1)[0]
    fields = body.split()
    names = set(fields[1:]) if len(fields) > 1 else set()
    if fqdn in names or short in names:
        continue
    output.append(raw)
output.append(f"{private_ip}\t{fqdn}\t{short}")
target.write_text("\n".join(output).rstrip() + "\n")
PY
  chmod 600 "$rendered"
  sudo -n install -m 644 -o root -g root "$rendered" /etc/hosts
  rm -f "$rendered"
}

verify_podman() {
  require_command podman
  require_command podman-compose
  require_eq "$(podman-compose --version | tail -n1 | awk '{print $NF}')" "1.6.0" "podman-compose"
  systemctl --user is-active --quiet podman.socket || fail "podman.socket inactive"
  systemctl --user is-enabled --quiet podman.socket || fail "podman.socket disabled"
  podman network inspect srv4-podman >/dev/null
  podman info --format '{{.Host.NetworkBackend}}' | grep -qx netavark || fail "Podman backend not netavark"
  if [ "$MODE" != "dry-run" ]; then
    /usr/bin/podman image exists "$PODMAN_SMOKE_IMAGE" || fail "pinned Podman smoke image absent"
    local marker="omni-setup-podman-$RUN_ID"
    podman run --rm --pull=never --network srv4-podman "$PODMAN_SMOKE_IMAGE" \
      sh -c "getent hosts example.com >/dev/null && printf '%s\\n' '$marker'" | grep -qx "$marker"
  fi
  pass "podman-compose 1.6.0 / srv4-podman / netavark"
}

apply_podman() {
  local podman_subnet="10.10.4.0/24" podman_gateway="10.10.4.1" network_state attached
  if [ "$MODE" = "apply" ]; then
    local podman_backup="$HOME/.backups/oci-arm64-host-setup-podman-$RUN_ID" source
    install -d -m 0700 "$podman_backup"
    for source in "$HOME/.config/containers/containers.conf" "$HOME/.config/containers/containers.conf.d/99-netavark.conf"; do
      if [ -f "$source" ] && [ ! -L "$source" ]; then cp -a "$source" "$podman_backup/$(basename "$source")"; fi
    done
    install -d -m 0755 "$HOME/.config/containers/containers.conf.d"
    printf '[network]\ndefault_network = "srv4-podman"\ndefault_subnet = "%s"\n' "$podman_subnet" \
      > "$HOME/.config/containers/containers.conf"
    printf '[network]\nnetwork_backend = "netavark"\n' \
      > "$HOME/.config/containers/containers.conf.d/99-netavark.conf"
    python3 -m pip install --user --break-system-packages --disable-pip-version-check \
      "podman-compose==$PODMAN_COMPOSE_VERSION" "python-dotenv==$PYTHON_DOTENV_VERSION"
    sudo -n systemctl enable --now systemd-resolved
    sudo -n loginctl enable-linger "$USER"
    systemctl --user enable --now podman.socket
    /usr/bin/podman pull "$PODMAN_SMOKE_IMAGE"
    network_state="$( { /usr/bin/podman network inspect srv4-podman 2>/dev/null || true; } | python3 -c '
import json,sys
try:
    item=json.load(sys.stdin)[0]
    network=(item.get("subnets") or [{}])[0]
    subnet=network.get("subnet")
    gateway=network.get("gateway")
    print("ok" if item.get("dns_enabled") is True and subnet == "10.10.4.0/24" and gateway == "10.10.4.1" else "drift")
except Exception:
    print("missing")
')"
    if [ "$network_state" = "drift" ]; then
      attached="$(/usr/bin/podman ps --filter network=srv4-podman --format '{{.ID}}' | wc -l)"
      [ "$attached" = "0" ] || fail "srv4-podman drift with attached containers; migrate before recreate"
      printf '[network]\ndefault_network = "podman"\ndefault_subnet = "10.88.0.0/16"\n' \
        > "$HOME/.config/containers/containers.conf"
      /usr/bin/podman network rm srv4-podman
      printf '[network]\ndefault_network = "srv4-podman"\ndefault_subnet = "%s"\n' "$podman_subnet" \
        > "$HOME/.config/containers/containers.conf"
      network_state="missing"
    fi
    if [ "$network_state" = "missing" ]; then
      /usr/bin/podman network create --subnet "$podman_subnet" \
        --gateway "$podman_gateway" srv4-podman
    fi
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY configure rootless Podman, podman-compose $PODMAN_COMPOSE_VERSION and srv4-podman"
    return 0
  fi
  verify_podman
}

verify_xrdp() {
  systemctl is-active --quiet lightdm xrdp xrdp-sesman || fail "desktop services inactive"
  systemctl is-enabled --quiet xrdp xrdp-sesman || fail "XRDP services disabled"
  sudo -n env PYTHONPATH="$ROOT/cli" python3 "$ROOT/cli/omni/xrdp_abnt2.py" validate --user "$USER"
  pass "xrdp_abnt2.py validate"
}

verify_xrdp_tls() {
  local cert="/etc/xrdp/atius-rdp/server.crt.pem"
  local key="/etc/xrdp/atius-rdp/server.key.pem"
  local ca cert_pub key_pub san
  sudo -n test -f "$cert" || fail "XRDP ATIUS certificate missing: $cert"
  sudo -n test -f "$key" || fail "XRDP ATIUS private key missing: $key"
  require_eq "$(sudo -n stat -c '%U:%G:%a' "$cert")" "root:root:644" "XRDP certificate ownership/mode"
  require_eq "$(sudo -n stat -c '%U:%G:%a' "$key")" "root:xrdp:640" "XRDP private-key ownership/mode"
  sudo -n -u xrdp test -r "$cert" || fail "XRDP user cannot read certificate"
  sudo -n -u xrdp test -r "$key" || fail "XRDP user cannot read private key"
  sudo -n grep -Fqx "certificate=$cert" /etc/xrdp/xrdp.ini
  sudo -n grep -Fqx "key_file=$key" /etc/xrdp/xrdp.ini
  ca="$(mktemp "$RUN_DIR/atius-rdp-root.XXXXXX.pem")"
  chmod 600 "$ca"
  curl -fsS --max-time 20 \
    https://landscape.atius.com.br/rdp-pki/atius-rdp-fleet-root-ca.crt.pem -o "$ca"
  sudo -n openssl verify -CAfile "$ca" "$cert" >/dev/null
  sudo -n openssl x509 -checkend 2592000 -noout -in "$cert" >/dev/null
  sudo -n openssl x509 -in "$cert" -noout -purpose | grep -Fq 'SSL server : Yes'
  san="$(sudo -n openssl x509 -in "$cert" -noout -ext subjectAltName)"
  for expected in \
    'DNS:atius-srv-4.atius.internal' 'DNS:atius-srv-4' 'DNS:srv4' \
    'IP Address:164.152.48.22' 'IP Address:10.14.1.14' 'IP Address:10.100.100.18'; do
    grep -Fq "$expected" <<<"$san" || fail "XRDP certificate SAN missing: $expected"
  done
  cert_pub="$(sudo -n openssl x509 -in "$cert" -pubkey -noout \
    | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)"
  key_pub="$(sudo -n openssl pkey -in "$key" -pubout 2>/dev/null \
    | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)"
  require_eq "$cert_pub" "$key_pub" "XRDP certificate/private-key public key"
  rm -f "$ca"
  pass "XRDP ATIUS TLS leaf / SAN / key / trust"
}

verify_landscape() {
  sudo -n landscape-config --is-registered >/dev/null
  systemctl is-active --quiet landscape-client.service
  systemctl is-enabled --quiet landscape-client.service
  sudo -n grep -Fqx 'account_name = standalone' /etc/landscape/client.conf
  sudo -n grep -Fqx 'url = https://landscape.atius.com.br/message-system' /etc/landscape/client.conf
  sudo -n grep -Fqx 'ping_url = http://landscape.atius.com.br/ping' /etc/landscape/client.conf
  sudo -n grep -Eq '^registration_key = .+' /etc/landscape/client.conf
  pass "landscape-config --is-registered"
}

apply_landscape() {
  local dump="$RUN_DIR/landscape-client.env" registration="$RUN_DIR/landscape-registration.ini"
  local needs_apply=0 backup
  if ! sudo -n landscape-config --is-registered >/dev/null 2>&1 \
    || ! sudo -n grep -Fqx 'account_name = standalone' /etc/landscape/client.conf \
    || ! sudo -n grep -Fqx 'url = https://landscape.atius.com.br/message-system' /etc/landscape/client.conf \
    || ! sudo -n grep -Fqx 'ping_url = http://landscape.atius.com.br/ping' /etc/landscape/client.conf; then
    needs_apply=1
  fi
  if [ "$MODE" = "apply" ] && [ "$needs_apply" -eq 1 ]; then
    backup="/root/.backups/landscape-client-$TARGET_SHORT-$RUN_ID"
    sudo -n install -d -m 0700 "$backup"
    sudo -n test -f /etc/landscape/client.conf \
      && sudo -n cp -a /etc/landscape/client.conf "$backup/client.conf"
    sudo -n sh -c "cd '$backup' && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null"
    install_vault_helper
    "$HOME/.local/bin/atius-vault-env" landscape-client > "$dump"
    chmod 0600 "$dump"
    python3 - "$dump" "$registration" <<'PY'
from pathlib import Path
import shlex,sys
source,target=map(Path,sys.argv[1:]); values={}
for raw in source.read_text().splitlines():
    parts=shlex.split(raw)
    if len(parts)==2 and parts[0]=='export' and '=' in parts[1]:
        key,value=parts[1].split('=',1); values[key]=value
value=values.get('LANDSCAPE_REGISTRATION_KEY','')
if not value: raise SystemExit('LANDSCAPE_REGISTRATION_KEY missing')
target.write_text('[client]\naccount_name = standalone\nregistration_key = '+value+'\ncomputer_title = atius-srv-4\nurl = https://landscape.atius.com.br/message-system\nping_url = http://landscape.atius.com.br/ping\n')
PY
    chmod 0600 "$registration"
    sudo -n landscape-config --silent --import "$registration"
    rm -f "$dump" "$registration"
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY register Landscape with Vault-backed client registration key"
    return 0
  fi
  verify_landscape
}

hydrate_fleet_db_env() {
  local dump="$RUN_DIR/omni-fleet.env" rendered="$RUN_DIR/fleet-db.env"
  install_vault_helper
  "$HOME/.local/bin/atius-vault-env" omni-fleet > "$dump"
  chmod 0600 "$dump"
  python3 - "$dump" "$rendered" <<'PY'
from pathlib import Path
import json,shlex,sys
source,target=map(Path,sys.argv[1:]); values={}
for raw in source.read_text().splitlines():
    parts=shlex.split(raw)
    if len(parts)==2 and parts[0]=='export' and '=' in parts[1]:
        key,value=parts[1].split('=',1); values[key]=value
required=('PGDATABASE','PGHOST','PGPASSWORD','PGPORT','PGSSLMODE','PGUSER')
if any(not values.get(key) for key in required): raise SystemExit('incomplete omni-fleet profile')
target.write_text(''.join(f'{key}={json.dumps(values[key])}\n' for key in required))
PY
  chmod 0600 "$rendered"
  sudo -n install -d -m 0755 /etc/omni-srv-admin
  sudo -n install -m 0600 -o root -g root "$rendered" /etc/omni-srv-admin/fleet-db.env
  install -d -m 0700 "$HOME/.config/omni-srv-admin"
  install -m 0600 "$rendered" "$HOME/.config/omni-srv-admin/fleet-db.env"
  require_eq "$(sudo -n sha256sum /etc/omni-srv-admin/fleet-db.env | cut -d' ' -f1)" \
    "$(sha256sum "$HOME/.config/omni-srv-admin/fleet-db.env" | cut -d' ' -f1)" \
    "Fleet DB root/user cache hash"
  rm -f "$dump" "$rendered"
}

apply_xrdp_tls() {
  local dump="$RUN_DIR/xrdp-srv4.env" cert_tmp="$RUN_DIR/xrdp-cert.pem" key_tmp="$RUN_DIR/xrdp-key.pem" ini_tmp="$RUN_DIR/xrdp.ini"
  local backup="/root/.backups/xrdp-cert-$TARGET_SHORT-$RUN_ID" source cert_pub key_pub
  if [ "$MODE" != "apply" ]; then return 0; fi
  install_vault_helper
  "$HOME/.local/bin/atius-vault-env" xrdp-srv4 > "$dump"
  chmod 0600 "$dump"
  python3 - "$dump" "$cert_tmp" "$key_tmp" <<'PY'
from pathlib import Path
import base64,shlex,sys
source,cert,key=map(Path,sys.argv[1:]); values={}
for raw in source.read_text().splitlines():
    parts=shlex.split(raw)
    if len(parts)==2 and parts[0]=='export' and '=' in parts[1]:
        name,value=parts[1].split('=',1); values[name]=value
cert.write_bytes(base64.b64decode(values['XRDP_CERT_PEM_B64'],validate=True))
key.write_bytes(base64.b64decode(values['XRDP_KEY_PEM_B64'],validate=True))
PY
  chmod 0600 "$cert_tmp" "$key_tmp"
  sudo -n cat /etc/xrdp/xrdp.ini > "$ini_tmp"
  chmod 0600 "$ini_tmp"
  python3 - "$ini_tmp" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); lines=p.read_text().splitlines(); out=[]
seen_cert=seen_key=False
for line in lines:
    if line.startswith('certificate='):
        out.append('certificate=/etc/xrdp/atius-rdp/server.crt.pem'); seen_cert=True
    elif line.startswith('key_file='):
        out.append('key_file=/etc/xrdp/atius-rdp/server.key.pem'); seen_key=True
    else:
        out.append(line)
if not seen_cert or not seen_key: raise SystemExit('xrdp.ini lacks certificate/key_file directives')
p.write_text('\n'.join(out)+'\n')
PY
  cert_pub="$(openssl x509 -in "$cert_tmp" -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)"
  key_pub="$(openssl pkey -in "$key_tmp" -pubout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)"
  require_eq "$cert_pub" "$key_pub" "XRDP Vault certificate/private-key public key"
  if sudo -n cmp -s "$cert_tmp" /etc/xrdp/atius-rdp/server.crt.pem \
    && sudo -n cmp -s "$key_tmp" /etc/xrdp/atius-rdp/server.key.pem \
    && sudo -n cmp -s "$ini_tmp" /etc/xrdp/xrdp.ini \
    && [ "$(sudo -n stat -c '%U:%G:%a' /etc/xrdp/atius-rdp/server.crt.pem)" = "root:root:644" ] \
    && [ "$(sudo -n stat -c '%U:%G:%a' /etc/xrdp/atius-rdp/server.key.pem)" = "root:xrdp:640" ]; then
    rm -f "$dump" "$cert_tmp" "$key_tmp" "$ini_tmp"
    return 0
  fi
  sudo -n install -d -m 0700 "$backup"
  for source in /etc/xrdp/atius-rdp/server.crt.pem /etc/xrdp/atius-rdp/server.key.pem /etc/xrdp/xrdp.ini; do
    sudo -n test -e "$source" && sudo -n cp -a "$source" "$backup/$(basename "$source")"
  done
  sudo -n sh -c "cd '$backup' && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null"
  sudo -n install -d -m 0750 -o root -g xrdp /etc/xrdp/atius-rdp
  sudo -n install -m 0644 -o root -g root "$cert_tmp" /etc/xrdp/atius-rdp/server.crt.pem
  sudo -n install -m 0640 -o root -g xrdp "$key_tmp" /etc/xrdp/atius-rdp/server.key.pem
  sudo -n install -m 0644 -o root -g root "$ini_tmp" /etc/xrdp/xrdp.ini
  rm -f "$dump" "$cert_tmp" "$key_tmp" "$ini_tmp"
  sudo -n systemctl restart xrdp.service
}

verify_fleet_agent() {
  systemctl --user is-active --quiet omni-fleet-agent.service
  systemctl --user is-enabled --quiet omni-fleet-agent.service
  systemctl --user show omni-fleet-agent.service -p Result --value | grep -qx success
  local heartbeat version db_env expected_commit
  heartbeat="$HOME/.logs/fleet/heartbeats/$TARGET_SHORT.json"
  version="$HOME/.logs/fleet/versions/$TARGET_SHORT.json"
  require_file "$heartbeat"
  require_file "$version"
  python3 -B - "$heartbeat" "$version" "$TARGET_SHORT" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json, sys

heartbeat_path, version_path, host = sys.argv[1:]
heartbeat = json.loads(Path(heartbeat_path).read_text())
version = json.loads(Path(version_path).read_text())
now = datetime.now(timezone.utc)

def age(raw):
    return (now - datetime.fromisoformat(str(raw).replace("Z", "+00:00"))).total_seconds()

checks=[heartbeat.get("host")==host,heartbeat.get("health")=="healthy",heartbeat.get("agent_version")=="0.2.3",0<=age(heartbeat.get("last_contact"))<=180,version.get("host")==host,version.get("component")=="omni-srv-admin",version.get("installed_version")=="0.2.5",0<=age(version.get("observed_at"))<=180]
if not all(checks): raise SystemExit("fleet cache validation failed")
PY
  db_env="$HOME/.config/omni-srv-admin/fleet-db.env"
  require_file "$db_env"
  require_eq "$(sudo -n sha256sum /etc/omni-srv-admin/fleet-db.env | cut -d' ' -f1)" \
    "$(sha256sum "$db_env" | cut -d' ' -f1)" "Fleet DB root/user cache hash"
  expected_commit="$(git -C "$HOME/GitHub/omni-srv-admin" rev-parse HEAD)"
  env PYTHONPATH="$ROOT/cli" python3 -B - "$db_env" "$TARGET_SHORT" "$expected_commit" <<'PY'
from pathlib import Path
import os, subprocess, sys
from omni.db_runtime import load_env_file

path, host, expected_commit = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
env = os.environ.copy()
env.update(load_env_file(path))
env["PGCONNECT_TIMEOUT"] = "5"

def query(sql: str) -> list[str]:
    proc = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-v", f"host_id={host}"],
        input=sql,
        text=True,
        capture_output=True,
        timeout=20,
        env=env,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or "fleet DB query failed")
    return proc.stdout.strip().split("|")

node = query('''SELECT concat_ws('|', host_id, agent_version, health_status,
extract(epoch from (now()-last_heartbeat_at))::int::text)
FROM "TbNodes" WHERE host_id = :'host_id';\n''')
version = query('''SELECT concat_ws('|', host_id, component, installed_version, git_commit,
extract(epoch from (now()-observed_at))::int::text)
FROM "TbVersion" WHERE host_id = :'host_id' AND component = 'omni-srv-admin';\n''')
if len(node) != 4 or node[:3] != [host, "0.2.3", "healthy"] or int(node[3]) > 180:
    raise SystemExit(f"invalid fleet node row: {node}")
if len(version) != 5 or version[:4] != [host, "omni-srv-admin", "0.2.5", expected_commit] or int(version[4]) > 180:
    raise SystemExit(f"invalid fleet version row: {version}")
PY
  pass "omni-fleet-agent.service / cache / DbOmniFleet readback"
}

install_node() {
  local node_base="node-${NODE_VERSION}-linux-arm64" node_dir="$HOME/.local/opt/node-${NODE_VERSION}-linux-arm64"
  if [ "$MODE" = "apply" ] && { [ ! -x "$node_dir/bin/node" ] || [ "$($node_dir/bin/node --version)" != "$NODE_VERSION" ]; }; then
    local tmp; tmp="$(mktemp -d)"
    curl -fsSLo "$tmp/$node_base.tar.xz" "https://nodejs.org/dist/$NODE_VERSION/$node_base.tar.xz"
    curl -fsSLo "$tmp/SHASUMS256.txt" "https://nodejs.org/dist/$NODE_VERSION/SHASUMS256.txt"
    (cd "$tmp" && grep " $node_base.tar.xz$" SHASUMS256.txt | sha256sum -c -)
    mkdir -p "$HOME/.local/opt"
    tar -xJf "$tmp/$node_base.tar.xz" -C "$HOME/.local/opt"
    rm -rf "$tmp"
  fi
  if [ "$MODE" = "dry-run" ]; then log "DRY install verified Node $NODE_VERSION"; fi
  mkdir -p "$HOME/.local/bin"
  local cmd
  for cmd in node npm npx corepack; do
    if [ "$MODE" = "apply" ]; then ln -sfn "$node_dir/bin/$cmd" "$HOME/.local/bin/$cmd"; fi
  done
  if [ "$MODE" = "apply" ] && [ "$($node_dir/bin/npm --version)" != "$NPM_VERSION" ]; then
    "$node_dir/bin/npm" install -g "npm@$NPM_VERSION"
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"
  require_eq "$(node --version)" "$NODE_VERSION" "Node"
}

install_uv() {
  local install_root="$HOME/.local/opt/uv-$UV_VERSION" tmp archive
  if [ "$MODE" = "apply" ] && { [ ! -x "$install_root/uv" ] || [ ! -x "$install_root/uvx" ] || [ "$($install_root/uv --version | awk '{print $2}')" != "$UV_VERSION" ] || [ "$($install_root/uvx --version | awk '{print $2}')" != "$UV_VERSION" ]; }; then
    tmp="$(mktemp -d)"; archive="$tmp/uv.tar.gz"
    download_checked "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-unknown-linux-gnu.tar.gz" \
      "$archive" "$UV_ARCHIVE_SHA256"
    tar -xzf "$archive" -C "$tmp"
    require_eq "$(sha256sum "$tmp/uv-aarch64-unknown-linux-gnu/uv" | cut -d' ' -f1)" "$UV_BINARY_SHA256" "uv binary checksum"
    require_eq "$(sha256sum "$tmp/uv-aarch64-unknown-linux-gnu/uvx" | cut -d' ' -f1)" "$UVX_BINARY_SHA256" "uvx binary checksum"
    install -d -m 0755 "$install_root" "$HOME/.local/bin"
    install -m 0755 "$tmp/uv-aarch64-unknown-linux-gnu/uv" "$install_root/uv"
    install -m 0755 "$tmp/uv-aarch64-unknown-linux-gnu/uvx" "$install_root/uvx"
    rm -rf "$tmp"
  fi
  if [ "$MODE" = "apply" ]; then
    ln -sfn "$install_root/uv" "$HOME/.local/bin/uv"
    ln -sfn "$install_root/uvx" "$HOME/.local/bin/uvx"
  fi
}

install_bun() {
  local tmp archive binary
  if [ "$MODE" != "apply" ]; then return 0; fi
  if [ -x "$HOME/.bun/bin/bun" ] && [ "$($HOME/.bun/bin/bun --version)" = "$BUN_VERSION" ]; then return 0; fi
  tmp="$(mktemp -d)"; archive="$tmp/bun.zip"
  download_checked "https://github.com/oven-sh/bun/releases/download/bun-v$BUN_VERSION/bun-linux-aarch64.zip" \
    "$archive" "$BUN_ARCHIVE_SHA256"
  unzip -q "$archive" -d "$tmp"
  binary="$tmp/bun-linux-aarch64/bun"
  require_eq "$(sha256sum "$binary" | cut -d' ' -f1)" "$BUN_BINARY_SHA256" "Bun binary checksum"
  install -d -m 0755 "$HOME/.bun/bin"
  install -m 0755 "$binary" "$HOME/.bun/bin/bun"
  ln -sfn "$HOME/.bun/bin/bun" "$HOME/.bun/bin/bunx"
  rm -rf "$tmp"
}

install_rust_toolchain() {
  local tmp installer
  if [ "$MODE" != "apply" ]; then return 0; fi
  if [ ! -x "$HOME/.cargo/bin/rustup" ] || [ "$($HOME/.cargo/bin/rustup --version 2>/dev/null | awk 'NR == 1 { print $2 }')" != "$RUSTUP_VERSION" ]; then
    tmp="$(mktemp -d)"; installer="$tmp/rustup-init"
    download_checked "https://static.rust-lang.org/rustup/archive/$RUSTUP_VERSION/aarch64-unknown-linux-gnu/rustup-init" \
      "$installer" "$RUSTUP_INIT_SHA256"
    chmod 0700 "$installer"
    "$installer" -y --no-modify-path --profile minimal --default-toolchain "$RUST_TOOLCHAIN_VERSION"
    rm -rf "$tmp"
  else
    "$HOME/.cargo/bin/rustup" toolchain install "$RUST_TOOLCHAIN_VERSION" --profile minimal --allow-downgrade
    "$HOME/.cargo/bin/rustup" default "$RUST_TOOLCHAIN_VERSION"
  fi
}

install_cargo_tools() {
  local tmp archive
  if [ "$MODE" != "apply" ]; then return 0; fi
  if [ ! -x "$HOME/.cargo/bin/cargo-binstall" ] || [ "$($HOME/.cargo/bin/cargo-binstall -V)" != "$CARGO_BINSTALL_VERSION" ]; then
    tmp="$(mktemp -d)"; archive="$tmp/cargo-binstall.tgz"
    download_checked "https://github.com/cargo-bins/cargo-binstall/releases/download/v$CARGO_BINSTALL_VERSION/cargo-binstall-aarch64-unknown-linux-gnu.tgz" \
      "$archive" "$CARGO_BINSTALL_ARCHIVE_SHA256"
    tar -xzf "$archive" -C "$tmp"
    require_eq "$(sha256sum "$tmp/cargo-binstall" | cut -d' ' -f1)" "$CARGO_BINSTALL_BINARY_SHA256" "cargo-binstall binary checksum"
    install -d -m 0755 "$HOME/.cargo/bin"
    install -m 0755 "$tmp/cargo-binstall" "$HOME/.cargo/bin/cargo-binstall"
    rm -rf "$tmp"
  fi
  if [ ! -x "$HOME/.cargo/bin/zellij" ] || [ "$($HOME/.cargo/bin/zellij --version | awk '{print $2}')" != "$ZELLIJ_VERSION" ]; then
    tmp="$(mktemp -d)"; archive="$tmp/zellij.tar.gz"
    download_checked "https://github.com/zellij-org/zellij/releases/download/v$ZELLIJ_VERSION/zellij-aarch64-unknown-linux-musl.tar.gz" \
      "$archive" "$ZELLIJ_ARCHIVE_SHA256"
    tar -xzf "$archive" -C "$tmp"
    require_eq "$(sha256sum "$tmp/zellij" | cut -d' ' -f1)" "$ZELLIJ_BINARY_SHA256" "Zellij binary checksum"
    install -m 0755 "$tmp/zellij" "$HOME/.cargo/bin/zellij"
    rm -rf "$tmp"
  fi
}

persist_devtools_path() {
  mkdir -p "$HOME/.config/environment.d"
  printf 'PATH=%s/.local/bin:%s/.cargo/bin:%s/.bun/bin:/usr/local/bin:/usr/bin:/bin\n' \
    "$HOME" "$HOME" "$HOME" > "$HOME/.config/environment.d/90-atius-developer-tools.conf"
  chmod 644 "$HOME/.config/environment.d/90-atius-developer-tools.conf"
  local file
  for file in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshenv"; do
    touch "$file"
    if ! grep -qF '# atius developer tools begin' "$file"; then
      cat >>"$file" <<'EOF'

# atius developer tools begin
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"
# atius developer tools end
EOF
    fi
  done
}

verify_toolchains() {
  require_eq "$(node --version)" "$NODE_VERSION" "Node"
  require_eq "$(npm --version)" "$NPM_VERSION" "npm"
  require_eq "$(bun --version)" "$BUN_VERSION" "Bun"
  require_eq "$(codex --version | awk '{print $2}')" "$CODEX_VERSION" "Codex"
  require_eq "$(uv --version | awk '{print $2}')" "$UV_VERSION" "uv"
  require_eq "$(uvx --version | awk '{print $2}')" "$UV_VERSION" "uvx"
  require_eq "$("$HOME/.cargo/bin/rustup" --version 2>/dev/null | awk 'NR == 1 { print $2 }')" "$RUSTUP_VERSION" "rustup"
  require_eq "$("$HOME/.rustup/toolchains/$RUST_TOOLCHAIN_VERSION-aarch64-unknown-linux-gnu/bin/rustc" --version | awk '{print $2}')" "$RUST_TOOLCHAIN_VERSION" "Rust"
  require_eq "$("$HOME/.cargo/bin/cargo-binstall" -V)" "$CARGO_BINSTALL_VERSION" "cargo-binstall"
  require_eq "$("$HOME/.cargo/bin/zellij" --version | awk '{print $2}')" "$ZELLIJ_VERSION" "Zellij"
  pass "node --version / npm --version / bun --version / codex --version"
}

apply_toolchains() {
  install_uv
  install_node
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"
  if [ "$MODE" = "apply" ]; then
    persist_devtools_path
    if [ "$(codex --version 2>/dev/null | awk '{print $2}')" != "$CODEX_VERSION" ]; then
      "$HOME/.local/opt/node-$NODE_VERSION-linux-arm64/bin/npm" install -g --prefix "$HOME/.local" "@openai/codex@$CODEX_VERSION"
    else
      log "NOOP Codex already at $CODEX_VERSION"
    fi
    install_bun
    install_rust_toolchain
    install_cargo_tools
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY install pinned uv/Node/npm/Bun/Codex/Rust/cargo-binstall/Zellij from checksummed artifacts"
    return 0
  fi
  verify_toolchains
}

verify_desktop_apps() {
  verify_desktop_app_repositories
  require_eq "$(dpkg-query -W -f='${Version}' chatgpt)" "$CHATGPT_VERSION" "ChatGPT package"
  require_eq "$(dpkg-query -W -f='${Version}' google-chrome-stable)" "$CHROME_VERSION" "Google Chrome package"
  dpkg -V chatgpt >/dev/null
  dpkg -V google-chrome-stable >/dev/null
  file /usr/lib/chatgpt/ChatGPT | grep -q 'ARM aarch64' || fail "ChatGPT is not AArch64"
  file /opt/google/chrome/chrome | grep -q 'ARM aarch64' || fail "Chrome is not AArch64"
  [ "$(stat -c '%U:%G:%a' /opt/google/chrome/chrome-sandbox)" = "root:root:4755" ] \
    || fail "Chrome sandbox owner/mode drift"
  pass "chatgpt / google-chrome-stable"
}

verify_browser_default_reconciler() {
  require_file "$HOME/.local/libexec/browser-default-reconciler.py"
  require_file "$HOME/.config/omni/browser-default-reconciler.env"
  require_file "$HOME/.local/state/omni/browser-default-reconciler.json"
  cmp -s "$ROOT/modules/managed-apps/scripts/browser-default-reconciler.py" \
    "$HOME/.local/libexec/browser-default-reconciler.py" \
    || fail "browser-default-reconciler.py drift"
  for unit in browser-default-reconciler.service browser-default-reconciler.path browser-default-reconciler.timer; do
    cmp -s "$ROOT/modules/managed-apps/systemd/$unit" "$HOME/.config/systemd/user/$unit" \
      || fail "$unit drift"
  done
  grep -Fqx 'BROWSER_DESKTOP=google-chrome.desktop' "$HOME/.config/omni/browser-default-reconciler.env"
  grep -Fqx 'CODEX_DESKTOP=chatgpt.desktop' "$HOME/.config/omni/browser-default-reconciler.env"
  systemctl --user is-active --quiet browser-default-reconciler.path
  systemctl --user is-active --quiet browser-default-reconciler.timer
  systemctl --user is-enabled --quiet browser-default-reconciler.path
  systemctl --user is-enabled --quiet browser-default-reconciler.timer
  systemctl --user show browser-default-reconciler.service -p Result --value | grep -qx success
  python3 -B - "$HOME/.local/state/omni/browser-default-reconciler.json" <<'PY'
import json, sys
state=json.load(open(sys.argv[1]))
if state.get('status') != 'success': raise SystemExit(state)
if state.get('browser_desktop') != 'google-chrome.desktop': raise SystemExit(state)
handlers=state.get('handlers') or {}
expected={'text/html':'google-chrome.desktop','x-scheme-handler/http':'google-chrome.desktop','x-scheme-handler/https':'google-chrome.desktop','x-scheme-handler/codex':'chatgpt.desktop'}
if any(handlers.get(k)!=v for k,v in expected.items()): raise SystemExit(handlers)
PY
  pass "browser-default-reconciler google-chrome/chatgpt"
}

apply_desktop_apps() {
  if [ "$MODE" = "apply" ]; then
    BROWSER_DESKTOP=google-chrome.desktop CODEX_DESKTOP=chatgpt.desktop \
      "$ROOT/modules/managed-apps/scripts/install-browser-default-reconciler"
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY install browser-default-reconciler for google-chrome.desktop/chatgpt.desktop"
    return 0
  fi
  verify_desktop_apps
  verify_browser_default_reconciler
}

verify_agents() {
  require_command hermes
  [ -f "$HOME/.hermes/config.yaml" ] && [ ! -L "$HOME/.hermes/config.yaml" ] || fail "Hermes config is not regular"
  [ -f "$HOME/.hermes/.env" ] && [ ! -L "$HOME/.hermes/.env" ] || fail "Hermes env is not regular"
  [ -z "$(git -C "$HOME/.hermes/hermes-agent" status --porcelain)" ] || fail "Hermes checkout dirty"
  require_eq "$(hermes --version | sed -n '1s/.*v\([0-9][^ ]*\).*/\1/p')" "0.21.0" "Hermes semantic version"
  require_eq "$(git -C "$HOME/.hermes/hermes-agent" rev-parse HEAD)" "$HERMES_COMMIT" "Hermes pinned commit"
  hermes config check >/dev/null
  python3 - <<'PY'
from pathlib import Path
import yaml
p=Path.home()/'.hermes/config.yaml'
cfg=yaml.safe_load(p.read_text()) or {}
model=cfg.get('model') or {}
if model.get('provider') != 'custom:atius-router': raise SystemExit(model)
if model.get('default') != 'gpt-5.6-sol': raise SystemExit(model)
if int(model.get('context_length')) != 1050000: raise SystemExit(model)
if not {'gbrain_http','obsidian_http','oci_admin_http'} <= set((cfg.get('mcp_servers') or {}).keys()): raise SystemExit('missing MCP')
if cfg.get('timezone') != 'America/Sao_Paulo': raise SystemExit(cfg.get('timezone'))
providers={str(item.get('name','')).lower():item for item in (cfg.get('custom_providers') or [])}
if providers.get('atius router',{}).get('key_env') != 'ATIUS_ROUTER_API_KEY': raise SystemExit(providers)
PY
  verify_host_local_auth "$HOME/.codex/auth.json"
  verify_host_local_auth "$HOME/.hermes/auth.json"
  printf 'source_commit_observed_at=%s head=%s\n' "$(date -Is)" \
    "$(git -C "$HOME/.hermes/hermes-agent" rev-parse HEAD)" > "$RUN_DIR/hermes-source-observation.env"
  chmod 600 "$RUN_DIR/hermes-source-observation.env"
  pass "Hermes configured; auth.json remains host-local/pending"
}

verify_host_local_auth() {
  local path="$1"
  [ ! -e "$path" ] && return 0
  [ -f "$path" ] && [ ! -L "$path" ] || fail "host-local auth must be a regular non-symlink: $path"
  [ "$(stat -c %a "$path")" = "600" ] || fail "host-local auth must be mode 0600: $path"
}

hydrate_hermes_config() {
  local vault_dump="$RUN_DIR/hermes-vault.env" env_tmp="$RUN_DIR/hermes.env"
  local backup="$HOME/.backups/oci-arm64-host-setup-hermes-config-$RUN_ID" source
  install -d -m 0700 "$HOME/.hermes"
  [ ! -L "$HOME/.hermes/config.yaml" ] || fail "Hermes config symlink forbidden"
  [ ! -L "$HOME/.hermes/.env" ] || fail "Hermes env symlink forbidden"
  install -d -m 0700 "$backup"
  for source in "$HOME/.hermes/config.yaml" "$HOME/.hermes/.env"; do
    if [ -f "$source" ] && [ ! -L "$source" ]; then
      cp -a "$source" "$backup/$(basename "$source")"
    fi
  done
  find "$backup" -maxdepth 1 -type f ! -name SHA256SUMS -print0 \
    | sort -z | xargs -0 -r sha256sum > "$backup/SHA256SUMS"
  chmod 0600 "$backup"/*
  if [ -s "$backup/SHA256SUMS" ]; then
    (cd "$backup" && sha256sum -c SHA256SUMS >/dev/null)
  fi
  install -d -m 0700 "$HOME/.config/omni"
  install -m 0600 "$ROOT/modules/fleet/configs/ssh/atius-srv3-vault-known-hosts" \
    "$HOME/.config/omni/atius-srv3-vault-known-hosts"
  install -m 0755 "$ROOT/modules/fleet/scripts/atius-vault-env" "$HOME/.local/bin/atius-vault-env"
  "$HOME/.local/bin/atius-vault-env" router-ai-atius atius-mcp > "$vault_dump"
  chmod 0600 "$vault_dump"
  python3 - "$HOME/.hermes/.env" "$vault_dump" "$env_tmp" <<'PY'
from pathlib import Path
import json, shlex, sys
source,vault,target=map(Path,sys.argv[1:])
vault_values={}
for raw in vault.read_text().splitlines():
    parts=shlex.split(raw)
    if len(parts) != 2 or parts[0] != "export" or "=" not in parts[1]:
        raise SystemExit("invalid Vault export stream")
    key,value=parts[1].split("=",1)
    vault_values[key]=value
for required in ("ATIUS_ROUTER_API_KEY","ATIUS_MCP_TOKEN"):
    if not vault_values.get(required):
        raise SystemExit(f"Vault profile lacks {required}")
managed_keys={
    "ATIUS_MCP_TOKEN": vault_values["ATIUS_MCP_TOKEN"],
    "ATIUS_ROUTER_API_KEY": vault_values["ATIUS_ROUTER_API_KEY"],
    "ATIUS_ROUTER_BASE_URL": "https://router.atius.com.br/v1",
    "ATIUS_ROUTER_DEFAULT_MODEL": "gpt-5.6-sol",
}
preserved=[]
for raw in source.read_text().splitlines() if source.exists() else []:
    body=raw.strip()
    key=body.split("=",1)[0].removeprefix("export ").strip() if "=" in body else ""
    if key not in managed_keys:
        preserved.append(raw)
preserved.extend(f"{key}={json.dumps(value)}" for key,value in managed_keys.items())
target.write_text("\n".join(preserved).rstrip()+"\n")
PY
  chmod 0600 "$env_tmp"
  install -m 0600 "$env_tmp" "$HOME/.hermes/.env"
  python3 - "$ROOT/modules/fleet/configs/hermes/config.yaml" "$HOME/.hermes/config.yaml" <<'PY'
from pathlib import Path
import sys, yaml
source,target=map(Path,sys.argv[1:])
required=yaml.safe_load(source.read_text()) or {}
current=yaml.safe_load(target.read_text()) or {} if target.exists() else {}
def merge(base, forced):
    if not isinstance(base, dict) or not isinstance(forced, dict):
        return forced
    out=dict(base)
    for key,value in forced.items():
        out[key]=merge(out.get(key),value)
    return out
target.write_text(yaml.safe_dump(merge(current,required),sort_keys=False,allow_unicode=True))
PY
  chmod 0600 "$HOME/.hermes/config.yaml"
  rm -f "$vault_dump" "$env_tmp"
}

bootstrap_hermes() {
  local repo="$HOME/.hermes/hermes-agent"
  if [ "$MODE" != "apply" ]; then return 0; fi
  install -d -m 0700 "$HOME/.hermes"
  if [ ! -d "$repo/.git" ]; then
    [ ! -e "$repo" ] || fail "Hermes install path exists but is not a Git checkout: $repo"
    git clone --filter=blob:none --no-checkout "$HERMES_REPO_URL" "$repo"
    git -C "$repo" fetch origin "$HERMES_COMMIT"
    git -C "$repo" checkout -B main "$HERMES_COMMIT"
  fi
  git -C "$repo" cat-file -e "$HERMES_COMMIT^{commit}"
}

install_hermes_runtime() {
  local repo="$HOME/.hermes/hermes-agent"
  UV_PROJECT_ENVIRONMENT="$repo/venv" "$HOME/.local/bin/uv" sync \
    --project "$repo" --locked --extra all --python "$HERMES_PYTHON_VERSION"
  install -d -m 0755 "$HOME/.local/bin"
  rm -f "$HOME/.local/bin/hermes"
  cat > "$HOME/.local/bin/hermes" <<EOF
#!/usr/bin/env bash
unset PYTHONPATH
unset PYTHONHOME
exec "$repo/venv/bin/python" "$repo/hermes" "\$@"
EOF
  chmod 0755 "$HOME/.local/bin/hermes"
  hydrate_hermes_config
  PYTHONPATH="$repo" "$repo/venv/bin/python" - <<'PY'
from tools.skills_sync import sync_skills
result=sync_skills(quiet=True)
print({k:len(result.get(k, [])) for k in ("copied","updated","user_modified","cleaned")})
PY
}

apply_agents() {
  if [ "$MODE" = "apply" ]; then
    local repo current backup orphan_ref rc
    repo="$HOME/.hermes/hermes-agent"
    backup="$HOME/.backups/oci-arm64-host-setup-hermes-$RUN_ID"
    install -d -m 0700 "$backup"
    if [ -d "$repo/.git" ]; then
      [ -z "$(git -C "$repo" status --porcelain)" ] || fail "Hermes checkout dirty before execution"
      current="$(git -C "$repo" rev-parse HEAD)"
      printf '%s\n' "$current" > "$backup/old-head"
      git -C "$repo" bundle create "$backup/hermes-before.bundle" HEAD
      git -C "$repo" bundle verify "$backup/hermes-before.bundle" >"$backup/bundle-verify.txt" 2>&1
      if [ -d "$repo/venv" ]; then tar -C "$repo" -czf "$backup/venv-before.tgz" venv; else touch "$backup/venv-absent"; fi
    else
      touch "$backup/repo-absent" "$backup/venv-absent"
    fi
    managed_paths=(.hermes/config.yaml .hermes/.env .hermes/skills .local/bin/hermes)
    : > "$backup/managed-existing.list"; : > "$backup/managed-absent.list"
    for source in "${managed_paths[@]}"; do
      if [ -e "$HOME/$source" ] || [ -L "$HOME/$source" ]; then
        printf '%s\n' "$source" >> "$backup/managed-existing.list"
      else
        printf '%s\n' "$source" >> "$backup/managed-absent.list"
      fi
    done
    if [ -s "$backup/managed-existing.list" ]; then
      tar -C "$HOME" -czf "$backup/managed-before.tgz" -T "$backup/managed-existing.list"
    else
      tar -C "$HOME" -czf "$backup/managed-before.tgz" --files-from /dev/null
    fi
    if command -v hermes >/dev/null 2>&1; then
      hermes backup -o "$backup/hermes-state.zip"
      [ -s "$backup/hermes-state.zip" ] || fail "Hermes full backup was not created"
      unzip -t "$backup/hermes-state.zip" > "$backup/state-restore-test.txt"
    fi
    find "$backup" -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$backup/SHA256SUMS"
    (cd "$backup" && sha256sum -c SHA256SUMS >/dev/null)
    chmod 0600 "$backup"/*

    set +e
    (
      set -Eeuo pipefail
      bootstrap_hermes
      [ -z "$(git -C "$repo" status --porcelain)" ] || fail "Hermes checkout dirty before execution"
      git -C "$repo" fetch origin "$HERMES_COMMIT"
      current="$(git -C "$repo" rev-parse HEAD)"
      if [ "$current" != "$HERMES_COMMIT" ]; then
        if git -C "$repo" merge-base --is-ancestor "$current" "$HERMES_COMMIT"; then
          git -C "$repo" merge --ff-only "$HERMES_COMMIT"
        else
          orphan_ref="refs/hermes-update-backups/orphan-${RUN_ID}"
          git -C "$repo" update-ref "$orphan_ref" "$current"
          printf 'classification=grafted-orphan-reset\nold_head=%s\ntarget=%s\nrollback_ref=%s\n' \
            "$current" "$HERMES_COMMIT" "$orphan_ref" > "$backup/grafted-reset.env"
          chmod 0600 "$backup/grafted-reset.env"
          git -C "$repo" reset --hard "$HERMES_COMMIT"
        fi
      fi
      python3 -m compileall -q "$repo/hermes_cli" "$repo/agent" "$repo/tools"
      install_hermes_runtime
      if [ "$(hermes config get timezone 2>/dev/null || true)" != "America/Sao_Paulo" ]; then
        hermes config set timezone America/Sao_Paulo
      fi
      verify_agents
    )
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      while IFS= read -r source; do rm -rf -- "$HOME/$source"; done < "$backup/managed-existing.list"
      while IFS= read -r source; do rm -rf -- "$HOME/$source"; done < "$backup/managed-absent.list"
      tar -C "$HOME" -xzf "$backup/managed-before.tgz"
      if [ -f "$backup/repo-absent" ]; then
        rm -rf -- "$repo"
      else
        current="$(<"$backup/old-head")"
        git -C "$repo" reset --hard "$current"
        rm -rf -- "$repo/venv"
        [ -f "$backup/venv-absent" ] || tar -C "$repo" -xzf "$backup/venv-before.tgz"
      fi
      fail "Hermes transaction failed rc=$rc; source/config/env/skills/venv restored"
    fi
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY pin Hermes to $HERMES_COMMIT with full state backup and git bundle"
    return 0
  fi
  verify_agents
}

verify_gsd_graphify() {
  require_eq "$(cat "$HOME/.codex/gsd-core/VERSION")" "$GSD_VERSION" "Codex GSD"
  require_eq "$(cat "$HOME/.hermes/gsd-core/VERSION")" "$GSD_VERSION" "Hermes GSD"
  require_eq "$(cat "$HOME/.codex/.gsd-profile")" "full" "Codex GSD profile"
  require_eq "$(cat "$HOME/.hermes/.gsd-profile")" "full" "Hermes GSD profile"
  node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" check auto-mode >/dev/null
  node "$HOME/.hermes/gsd-core/bin/gsd-tools.cjs" check auto-mode >/dev/null
  graphify --version | grep -q '^graphify 0.9.23$' || fail "Graphify version drift"
  PYTHONPATH="$HOME/.local/share/graphify-patches" \
    "$HOME/.local/share/uv/tools/graphifyy/bin/python" - <<'PY'
import openai
from graphify import llm
if "atius-router-gpt" not in llm.BACKENDS: raise SystemExit("Graphify Atius backend missing")
if not getattr(llm._call_llm,"_graphify_atius_router_stream_patched",False): raise SystemExit("Graphify label patch missing")
if not getattr(llm._call_openai_compat,"_graphify_atius_router_stream_patched",False): raise SystemExit("Graphify extraction patch missing")
PY
  pass "GSD check auto-mode / Graphify"
}

install_graphify() {
  if [ "$MODE" != "apply" ]; then return 0; fi
  "$HOME/.local/bin/uv" tool install --force "graphifyy==$GRAPHIFY_VERSION" \
    --with "openai==$GRAPHIFY_OPENAI_VERSION"
  install -d -m 0700 "$HOME/.graphify"
  install -m 0600 "$ROOT/modules/fleet/configs/graphify/providers.json" "$HOME/.graphify/providers.json"
  install -m 0600 "$ROOT/modules/fleet/configs/graphify/embeddings.json" "$HOME/.graphify/embeddings.json"
  install -d -m 0700 "$HOME/.local/share/graphify-patches"
  install -m 0600 "$ROOT/modules/fleet/configs/graphify/graphify_atius_router_patch.py" \
    "$HOME/.local/share/graphify-patches/graphify_atius_router_patch.py"
  install -m 0600 "$ROOT/modules/fleet/configs/graphify/sitecustomize.py" \
    "$HOME/.local/share/graphify-patches/sitecustomize.py"
  rm -f "$HOME/.local/bin/graphify"
  install -m 0755 "$ROOT/modules/fleet/scripts/graphify-atius-runtime" "$HOME/.local/bin/graphify"
  PYTHONPATH="$HOME/.local/share/graphify-patches" \
    "$HOME/.local/share/uv/tools/graphifyy/bin/python" - <<'PY'
from graphify import llm
if not getattr(llm._call_llm, "_graphify_atius_router_stream_patched", False): raise SystemExit("Graphify patch inactive")
PY
}

apply_gsd_graphify() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.bun/bin:$PATH"
  if [ "$MODE" = "apply" ]; then
    GSD_INSTALLER_MIGRATION_RESOLVE=remove npx -y "@opengsd/gsd-core@$GSD_VERSION" --codex --global --profile=full
    GSD_INSTALLER_MIGRATION_RESOLVE=remove npx -y "@opengsd/gsd-core@$GSD_VERSION" --hermes --global --profile=full
    install_graphify
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY install @opengsd/gsd-core@$GSD_VERSION for Codex and Hermes"
    return 0
  fi
  verify_gsd_graphify
}

verify_agent_content() {
  local pack target result
  for pack in codex-skills hermes-skills shared-agent-content; do
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content validate-pack --pack "$pack" --json-output >/dev/null
  done
  if [ "$MODE" = "dry-run" ]; then
    log "DRY parent-side agent-content sync must converge to noop before apply"
    return 0
  fi
  for target in srv4-codex-local srv4-hermes-local; do
    for pack in codex-skills hermes-skills shared-agent-content; do
      case "$pack:$target" in
        codex-skills:srv4-hermes-local|hermes-skills:srv4-codex-local) continue ;;
      esac
      result="$(env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content sync --pack "$pack" --target "$target" --dry-run --json-output)"
      python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(0 if all(item["status"] == "noop" for item in x["results"]) else 1)' <<<"$result"
    done
  done
  pass "agent-content all managed files converge to noop"
}

verify_obsidian() {
  local vault="$HOME/GitHub/obsidian-vault"
  require_file "$HOME/GitHub/Programs/obsidian/Obsidian.AppImage"
  [ -d "$vault/.git" ] || fail "Obsidian vault repository missing"
  require_eq "$(git -C "$vault" remote get-url origin)" "git@github.com:giovannimnz/obsidian-vault.git" "Obsidian origin"
  require_eq "$(git -C "$vault" branch --show-current)" "master" "Obsidian branch"
  [ -z "$(git -C "$vault" status --porcelain)" ] || fail "dirty vault replica"
  require_file "$vault/AiSecondBrain/.obsidian/appearance.json"
  jq -e '.titlebarStyle == "native"' "$vault/AiSecondBrain/.obsidian/appearance.json" >/dev/null
  require_command obsidian
  require_command obsidian-tray
  require_command xrdp-launch
  desktop-file-validate "$HOME/Desktop/obsidian.desktop"
  systemctl --user is-active --quiet obsidian-vault-pull.timer
  systemctl --user is-enabled --quiet obsidian-vault-pull.timer
  systemctl --user show obsidian-vault-pull.service -p Result --value | grep -qx success
  pass "Obsidian $OBSIDIAN_VERSION / obsidian-vault-pull.timer"
}

install_obsidian_repo() {
  local dump="$RUN_DIR/obsidian-readonly.env" key_tmp="$RUN_DIR/obsidian-deploy-key"
  local vault="$HOME/GitHub/obsidian-vault" clone_tmp="$HOME/GitHub/.obsidian-vault-clone-$RUN_ID"
  local public_expected repo_url ssh_command
  install_vault_helper
  "$HOME/.local/bin/atius-vault-env" obsidian-readonly > "$dump"
  chmod 0600 "$dump"
  python3 - "$dump" "$key_tmp" <<'PY'
from pathlib import Path
import base64,shlex,sys
source,target=map(Path,sys.argv[1:]); values={}
for raw in source.read_text().splitlines():
    parts=shlex.split(raw)
    if len(parts)==2 and parts[0]=='export' and '=' in parts[1]:
        key,value=parts[1].split('=',1); values[key]=value
target.write_bytes(base64.b64decode(values['OBSIDIAN_DEPLOY_KEY_B64'],validate=True))
Path(str(target)+'.pub').write_text(values['OBSIDIAN_DEPLOY_PUBLIC_KEY'].strip()+'\n')
Path(str(target)+'.url').write_text(values['OBSIDIAN_REPO_URL'].strip()+'\n')
PY
  chmod 0600 "$key_tmp" "$key_tmp.pub" "$key_tmp.url"
  install -d -m 0700 "$HOME/.ssh"
  install -m 0600 "$key_tmp" "$HOME/.ssh/id_ed25519_obsidian"
  install -m 0644 "$key_tmp.pub" "$HOME/.ssh/id_ed25519_obsidian.pub"
  public_expected="$(cut -d' ' -f1-2 "$key_tmp.pub")"
  require_eq "$(ssh-keygen -y -f "$HOME/.ssh/id_ed25519_obsidian" | cut -d' ' -f1-2)" "$public_expected" "Obsidian deploy keypair"
  install -m 0600 "$ROOT/modules/fleet/configs/ssh/github-ed25519-known-hosts" "$HOME/.ssh/github-ed25519-known-hosts"
  require_eq "$(ssh-keygen -lf "$HOME/.ssh/github-ed25519-known-hosts" | awk '{print $2}')" \
    "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU" "GitHub ED25519 host key"
  repo_url="$(<"$key_tmp.url")"
  require_eq "$repo_url" "git@github.com:giovannimnz/obsidian-vault.git" "Obsidian Vault repo URL"
  ssh_command="ssh -F /dev/null -i $HOME/.ssh/id_ed25519_obsidian -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=$HOME/.ssh/github-ed25519-known-hosts -o HostKeyAlgorithms=ssh-ed25519"
  if [ ! -d "$vault/.git" ]; then
    [ ! -e "$vault" ] && [ ! -L "$vault" ] || fail "Obsidian vault path exists but is not a Git repo"
    [ ! -e "$clone_tmp" ] && [ ! -L "$clone_tmp" ] || fail "stale Obsidian clone staging exists: $clone_tmp"
    if ! GIT_SSH_COMMAND="$ssh_command" git clone --branch master --single-branch "$repo_url" "$clone_tmp"; then
      rm -rf -- "${clone_tmp:?}"
      fail "Obsidian vault clone failed"
    fi
    git -C "$clone_tmp" config core.sshCommand "$ssh_command"
    mv "$clone_tmp" "$vault"
  else
    git -C "$vault" config core.sshCommand "$ssh_command"
    git -C "$vault" remote set-url origin "$repo_url"
  fi
  rm -f "$dump" "$key_tmp" "$key_tmp.pub" "$key_tmp.url"
}

apply_obsidian() {
  if [ "$MODE" = "apply" ]; then
    install_obsidian_repo
    OBSIDIAN_VERSION="$OBSIDIAN_VERSION" "$ROOT/modules/managed-apps/scripts/install-obsidian-arm64-appimage" apply
    install -d -m 0755 "$HOME/.local/lib/omni-fleet" "$HOME/.config/systemd/user"
    install -m 0755 "$ROOT/modules/fleet/scripts/obsidian-vault-pull.sh" "$HOME/.local/lib/omni-fleet/obsidian-vault-pull.sh"
    install -m 0644 "$ROOT/modules/fleet/systemd/obsidian-vault-pull.service" "$HOME/.config/systemd/user/obsidian-vault-pull.service"
    install -m 0644 "$ROOT/modules/fleet/systemd/obsidian-vault-pull.timer" "$HOME/.config/systemd/user/obsidian-vault-pull.timer"
    systemctl --user daemon-reload
    systemctl --user enable --now obsidian-vault-pull.timer
    systemctl --user start obsidian-vault-pull.service
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY install/verify Obsidian $OBSIDIAN_VERSION and versioned pull-only units"
    return 0
  fi
  verify_obsidian
}

verify_resource_governor() {
  env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni srv1-ops resources doctor --json-output \
    | python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(0 if x["doctor_ok"] and x["structural_ok"] else 1)'
  local unit
  for unit in \
    offload-dotbackups-to-gdrive.service offload-dotbackups-to-gdrive.timer \
    pm2-dump-sanitizer.service pm2-dump-sanitizer.path pm2-dump-sanitizer.timer \
    inviolable-watchdog.service inviolable-watchdog.timer \
    server-analysis.service server-analysis.timer; do
    must_not_load "$unit"
  done
  [ "$(readlink -f "$HOME/.local/bin/make")" = "$ROOT/modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh" ] || fail "make build guard source drift"
  grep -q '^if inside_build_cgroup; then$' "$HOME/.local/bin/make" || fail "build guard lacks nested cgroup bypass"
  pass "resources doctor; SRV-1-only units must_not_load"
}

apply_resource_governor() {
  if [ "$MODE" = "apply" ]; then
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni srv1-ops resources install --generic-host --no-run-audit-now
    OMNI_SRV_ADMIN="$ROOT" "$ROOT/modules/srv1-ops/scripts/install-build-cpu-guard.sh"
  elif [ "$MODE" = "dry-run" ]; then
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni srv1-ops resources install --generic-host --dry-run --no-run-audit-now
    log "DRY install build-cpu-guard wrapper"
    return 0
  fi
  verify_resource_governor
}

verify_theme() {
  [ -x "$DARK_THEME_CTL" ] || DARK_THEME_CTL="$ROOT/dark-theme-ubuntu/scripts/dark-themectl.sh"
  "$DARK_THEME_CTL" validate
  pass "dark-themectl.sh validate"
}

apply_theme() {
  if [ "$MODE" = "apply" ]; then
    [ -x "$DARK_THEME_CTL" ] || DARK_THEME_CTL="$ROOT/dark-theme-ubuntu/scripts/dark-themectl.sh"
    "$DARK_THEME_CTL" apply --install-packages --with-sublime --with-zsh
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY dark theme apply without --restart-session"
  fi
  verify_theme
}

step_preflight() {
  verify_source_manifest
  if [ "$MODE" != "dry-run" ]; then
    require_eq "$(readlink -f "$ROOT")" \
      "$(readlink -f "${OMNI_SETUP_CANONICAL_ROOT:-$HOME/.local/share/omni-setup-source}")" \
      "canonical setup root"
  fi
  require_eq "$(uname -m)" "$EXPECTED_ARCH" "architecture"
  require_eq "$(hostname -s)" "$TARGET_SHORT" "host scope"
  sudo -n true
  cloud-init status --wait >/dev/null
  require_eq "$(cloud-init status --format json | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status"))')" "done" "cloud-init"
  [ "$(systemctl --failed --no-legend --plain | wc -l)" -eq 0 ] || fail "failed system units"
  [ "$(systemctl --user --failed --no-legend --plain | wc -l)" -eq 0 ] || fail "failed user units"
  [ "$(git -C "$HOME/GitHub/omni-srv-admin" status --porcelain | wc -l)" -eq 0 ] || fail "canonical omni clone dirty"
  if [ "$MODE" = "apply" ]; then
    grep -q 'omni-builds' /proc/self/cgroup || fail "apply must run inside omni-builds.slice"
  fi
  pass "preflight"
}
step_packages() { apply_packages; }
step_ubuntu_pro() { apply_ubuntu_pro; }
step_identity_network() {
  if [ "$MODE" = "apply" ]; then
    apply_host_identity
    sudo -n install -D -m 0644 -o root -g root \
      "$ROOT/modules/fleet/configs/systemd/resolved.conf.d/60-atius-internal.conf" \
      /etc/systemd/resolved.conf.d/60-atius-internal.conf
    sudo -n netplan generate
    sudo -n systemctl restart systemd-resolved
  fi
  verify_network
}
step_podman() { apply_podman; }
step_desktop_xrdp() {
  if [ "$MODE" = "apply" ]; then
    sudo -n env PYTHONPATH="$ROOT/cli" python3 "$ROOT/cli/omni/xrdp_abnt2.py" install --user "$USER" --yes
    apply_xrdp_tls
  fi
  verify_xrdp
  verify_xrdp_tls
}
step_landscape() { apply_landscape; }
step_fleet_agent() {
  if [ "$MODE" = "apply" ]; then
    hydrate_fleet_db_env
    OMNI_SRV_ADMIN="$ROOT" OMNI_FLEET_RUNTIME_REPO="$HOME/GitHub/omni-srv-admin" \
      "$ROOT/modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh" "$TARGET_SHORT" >/dev/null
  fi
  verify_fleet_agent
}
step_toolchains() { apply_toolchains; }
step_desktop_apps() {
  apply_desktop_apps
}
step_agents() { apply_agents; }
step_gsd_graphify() { apply_gsd_graphify; }
step_agent_content() {
  if [ "$MODE" = "apply" ]; then
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content sync --pack codex-skills --target srv4-codex-local --apply --json-output >/dev/null
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content sync --pack hermes-skills --target srv4-hermes-local --apply --json-output >/dev/null
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content sync --pack shared-agent-content --target srv4-codex-local --apply --json-output >/dev/null
    env OMNI_SRV_ADMIN="$ROOT" PYTHONPATH="$ROOT/cli" python3 -m omni agent-content sync --pack shared-agent-content --target srv4-hermes-local --apply --json-output >/dev/null
  elif [ "$MODE" = "dry-run" ]; then
    log "DRY apply Codex/Hermes content packs through linux-local targets"
    return 0
  fi
  verify_agent_content
}
step_obsidian() { apply_obsidian; }
step_resource_governor() { apply_resource_governor; }
step_desktop_theme() { apply_theme; }
step_final_verify() {
  if [ "$MODE" = "dry-run" ]; then
    log "DRY final-verify runs after apply against all postconditions"
    return 0
  fi
  step_preflight
  verify_ubuntu_pro
  verify_network
  verify_podman
  verify_xrdp
  verify_xrdp_tls
  verify_landscape
  verify_fleet_agent
  verify_toolchains
  verify_desktop_apps
  verify_agents
  verify_gsd_graphify
  verify_agent_content
  verify_obsidian
  verify_resource_governor
  verify_theme
  [ "$(apt list --upgradable 2>/dev/null | sed 1d | wc -l)" -eq 0 ] || fail "pending apt packages"
  [ ! -e /var/run/reboot-required ] || fail "reboot required"
  pass "final-verify"
}

from_seen=0
[ -z "$FROM_STEP" ] && from_seen=1
for step in "${STEPS[@]}"; do
  if [ "$step" = "preflight" ]; then
    [ "$FROM_STEP" = "preflight" ] && from_seen=1
    CURRENT_STEP="$step"
    step_started_at="$(date -Is)"
    log "START step=$step mode=$MODE"
    step_preflight
    mark_step_complete "$step"
    log "DONE step=$step"
    continue
  fi
  if [ "$from_seen" -eq 0 ]; then
    [ "$step" = "$FROM_STEP" ] && from_seen=1 || continue
  fi
  receipt="$(receipt_path "$step")"
  if [ "$RESUME" -eq 1 ] && [ "$step" != "final-verify" ] && receipt_is_current "$receipt"; then
    log "SKIP completed step=$step"
    continue
  fi
  CURRENT_STEP="$step"
  step_started_at="$(date -Is)"
  log "START step=$step mode=$MODE"
  "step_${step//-/_}"
  mark_step_complete "$step"
  log "DONE step=$step"
done

[ "$from_seen" -eq 1 ] || fail "unknown --from-step: $FROM_STEP"
CURRENT_STEP="complete"
printf 'status=PASS mode=%s run_id=%s completed_at=%s\n' "$MODE" "$RUN_ID" "$(date -Is)" | tee "$RUN_DIR/COMPLETE"
chmod 600 "$RUN_DIR/COMPLETE"
rm -f "$RUN_DIR/FAILED"
