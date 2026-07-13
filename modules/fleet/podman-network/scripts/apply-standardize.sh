#!/usr/bin/env bash
# apply-standardize.sh — runs the apply sequence on one ATIUS server.
#
# Usage: ./apply-standardize.sh <N>
#   N: server number (1, 2, or 3)
#
# Idempotent. Backs up containers.conf before any change.
# Will NOT touch any running systemd-managed services — run the
# network-migration reference separately for that.

set -eu

if [ $# -ne 1 ] || ! [[ "$1" =~ ^[123]$ ]]; then
  echo "Usage: $0 <N>  (N=1, 2, or 3)" >&2
  exit 1
fi

N=$1
case $N in
  1) HOST=10.11.1.11 ;;
  2) HOST=10.12.1.12 ;;
  3) HOST=10.13.1.13 ;;
esac

USER=ubuntu
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=~/backups/podman-fleet-standardize-$(date +%Y-%m-%d)
mkdir -p "$BACKUP_DIR"

echo "=== Applying podman-fleet-standardize to SRV-$N ($HOST) ==="
echo "Backup dir: $BACKUP_DIR"
echo ""

ssh -o ConnectTimeout=10 $USER@$HOST "bash -s" <<EOF
set -e
N=$N
TS=$TS
BACKUP_DIR=$BACKUP_DIR

echo "--- 1. backup containers.conf ---"
mkdir -p /home/ubuntu/\$BACKUP_DIR
cp /home/ubuntu/.config/containers/containers.conf \
   /home/ubuntu/\$BACKUP_DIR/srv\${N}-containers.conf.orig 2>/dev/null || true

echo "--- 2. install systemd-resolved if missing ---"
if ! systemctl is-active systemd-resolved >/dev/null 2>&1; then
  sudo apt-get install -y systemd-resolved
  sudo systemctl enable --now systemd-resolved
  echo "  systemd-resolved: INSTALLED + ENABLED"
else
  echo "  systemd-resolved: already active"
fi

echo "--- 3. ensure 99-netavark.conf ---"
mkdir -p /home/ubuntu/.config/containers/containers.conf.d
cat > /home/ubuntu/.config/containers/containers.conf.d/99-netavark.conf <<NET
[network]
network_backend = "netavark"
NET
echo "  99-netavark.conf written"

echo "--- 4. write containers.conf (default_network + default_subnet) ---"
cat > /home/ubuntu/.config/containers/containers.conf <<CONF
[network]
default_network = "srv\${N}-podman"
default_subnet = "10.10.\${N}.0/24"
CONF
echo "  containers.conf written"

echo "--- 5. ensure ~/.profile has non-interactive PATH ---"
if ! grep -q '.local/bin' /home/ubuntu/.profile 2>/dev/null; then
  cat >> /home/ubuntu/.profile <<'PROF'

# Ensure ~/.local/bin is on PATH for non-interactive shells
case "$-" in
    *i*) ;;
    *) export PATH="$HOME/.local/bin:$PATH";;
esac
PROF
  echo "  ~/.profile updated"
else
  echo "  ~/.profile already has PATH"
fi

echo "--- 6. reinstall podman-compose 1.6.0 in ~/.local/bin ---"
sudo -n rm -f /usr/local/bin/podman-compose 2>/dev/null || true
pip install --user --break-system-packages --force-reinstall \
  podman-compose python-dotenv 2>&1 | tail -3
echo "  podman-compose: \$(~/.local/bin/podman-compose --version 2>&1 | head -1)"

echo "--- 7. check srv\${N}-podman network state ---"
net_state=\$(/usr/bin/podman network inspect srv\${N}-podman 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
net = d[0]
print(net.get('dns_enabled'), net['subnets'][0]['subnet'])
" 2>/dev/null || echo "MISSING")
echo "  current state: \$net_state"

if [ "\$net_state" = "MISSING" ]; then
  echo "  creating srv\${N}-podman (10.10.\${N}.0/24, dns=true)"
  /usr/bin/podman network create --subnet 10.10.\${N}.0/24 --gateway 10.10.\${N}.1 srv\${N}-podman
elif [ "\$net_state" = "False 10.10.\${N}.0/24" ]; then
  echo "  srv\${N}-podman has dns=false — recreating"
  sed -i 's/srv\${N}-podman/tmp-default-net/g' /home/ubuntu/.config/containers/containers.conf
  /usr/bin/podman network rm srv\${N}-podman
  /usr/bin/podman network create --subnet 10.10.\${N}.0/24 --gateway 10.10.\${N}.1 srv\${N}-podman
  cat > /home/ubuntu/.config/containers/containers.conf <<CONF
[network]
default_network = "srv\${N}-podman"
default_subnet = "10.10.\${N}.0/24"
CONF
else
  echo "  srv\${N}-podman already conforms (dns=true, subnet 10.10.\${N}.0/24)"
fi

echo ""
echo "--- 8. post-state summary ---"
echo "containers.conf:"
cat /home/ubuntu/.config/containers/containers.conf
echo "99-netavark.conf:"
cat /home/ubuntu/.config/containers/containers.conf.d/99-netavark.conf
echo "podman network ls:"
/usr/bin/podman network ls
echo "podman info backend: \$(/usr/bin/podman info --format '{{.Host.NetworkBackend}}')"
echo "systemd-resolved: \$(systemctl is-active systemd-resolved)"
echo "podman-compose: \$(~/.local/bin/podman-compose --version 2>&1 | head -1)"
echo "aardvark-dns: \$(pidof aardvark-dns 2>/dev/null || echo NOT_RUNNING)"
EOF

echo ""
echo "=== done SRV-$N. Now run smoke-test.sh $N to validate ==="
