#!/usr/bin/env bash
set -euo pipefail

ETC_DIR="/etc/omni-srv-admin"
PEERS_JSON="$ETC_DIR/fleet-peers.json"
SSH_DIR="$HOME/.ssh"
SSH_CONFIG="$SSH_DIR/config"
STAMP="$(date +%Y%m%d-%H%M%S)"
MARK_BEGIN="# BEGIN OMNI FLEET PEERS"
MARK_END="# END OMNI FLEET PEERS"

sudo install -d -m 0755 "$ETC_DIR"
tmp_json="$(mktemp)"
cat >"$tmp_json" <<'JSON'
{
  "strategy": "vpn-first-public-ssh-fallback",
  "database": {
    "primary": "10.11.1.11:6432",
    "public_fallback_enabled": false,
    "reason": "Do not expose PgBouncer/PostgreSQL on public IP; direct fallback is SSH/probe only."
  },
  "hosts": {
    "atius-srv-1": {
      "ssh_user": "ubuntu",
      "ssh_port": 22,
      "vpn_ip": "10.100.100.1",
      "oci_private_ip": "10.11.1.11",
      "public_ip": "137.131.190.161"
    },
    "atius-srv-2": {
      "ssh_user": "ubuntu",
      "ssh_port": 22,
      "vpn_ip": "10.100.100.2",
      "oci_private_ip": "10.12.1.12",
      "public_ip": "129.148.47.32"
    },
    "atius-srv-3": {
      "ssh_user": "ubuntu",
      "ssh_port": 22,
      "vpn_ip": "10.100.100.3",
      "oci_private_ip": "10.13.1.13",
      "public_ip": "136.248.126.12"
    }
  }
}
JSON
sudo install -m 0644 "$tmp_json" "$PEERS_JSON"
rm -f "$tmp_json"

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
touch "$SSH_CONFIG"
chmod 600 "$SSH_CONFIG"

if grep -q "$MARK_BEGIN" "$SSH_CONFIG"; then
  cp "$SSH_CONFIG" "$SSH_CONFIG.omni-peers-$STAMP.bak"
  python3 - "$SSH_CONFIG" "$MARK_BEGIN" "$MARK_END" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
begin = sys.argv[2]
end = sys.argv[3]
lines = path.read_text().splitlines()
out = []
skip = False
for line in lines:
    if line.strip() == begin:
        skip = True
        continue
    if line.strip() == end:
        skip = False
        continue
    if not skip:
        out.append(line)
path.write_text("\n".join(out).rstrip() + "\n")
PY
else
  cp "$SSH_CONFIG" "$SSH_CONFIG.omni-peers-$STAMP.bak"
fi

cat >>"$SSH_CONFIG" <<'EOF'

# BEGIN OMNI FLEET PEERS
Host atius-srv-1-vpn
  HostName 10.11.1.11
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2

Host atius-srv-1-direct
  HostName 137.131.190.161
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2

Host atius-srv-2-vpn
  HostName 10.12.1.12
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2

Host atius-srv-2-direct
  HostName 129.148.47.32
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2

Host atius-srv-3-vpn
  HostName 10.13.1.13
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2

Host atius-srv-3-direct
  HostName 136.248.126.12
  User ubuntu
  Port 22
  StrictHostKeyChecking accept-new
  ConnectTimeout 5
  ServerAliveInterval 15
  ServerAliveCountMax 2
# END OMNI FLEET PEERS
EOF

echo "peers_json=$PEERS_JSON"
echo "ssh_config=$SSH_CONFIG"
