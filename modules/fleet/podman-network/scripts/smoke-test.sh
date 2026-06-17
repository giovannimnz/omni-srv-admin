#!/usr/bin/env bash
# smoke-test.sh — runs the validation sequence on one ATIUS server.
#
# Usage: ./smoke-test.sh <N>
#   N: server number (1, 2, or 3)
#
# Verifies:
#   - aardvark-dns comes up
#   - container /etc/resolv.conf has correct nameserver
#   - self-lookup resolves
#   - external lookup resolves (via systemd-resolved forwarding)
#
# Uses a short-lived alpine container; no persistent state.

set -eu

if [ $# -ne 1 ] || ! [[ "$1" =~ ^[123]$ ]]; then
  echo "Usage: $0 <N>  (N=1, 2, or 3)" >&2
  exit 1
fi

N=$1
case $N in
  1) HOST=10.1.1.1 ;;
  2) HOST=10.1.1.2 ;;
  3) HOST=10.1.1.7 ;;
esac

USER=ubuntu
SUBNET="10.10.$N.0/24"
GATEWAY="10.10.$N.1"

ssh -o ConnectTimeout=10 $USER@$HOST "bash -s" <<EOF
set -e
N=$N
GATEWAY=$GATEWAY

echo "=== Smoke test SRV-\$N: podman netavark + aardvark-dns ==="

echo "--- pre: systemd-resolved active? ---"
systemctl is-active systemd-resolved || { echo "FAIL: systemd-resolved not active"; exit 1; }

echo "--- pre: srv\${N}-podman dns=true? ---"
dns_state=\$(/usr/bin/podman network inspect srv\${N}-podman 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('dns_enabled'))" 2>/dev/null)
if [ "\$dns_state" != "True" ]; then
  echo "FAIL: srv\${N}-podman dns_enabled=\$dns_state (expected True)"
  exit 1
fi
echo "  dns=true OK"

echo "--- 1. create test container ---"
CID=\$(/usr/bin/podman run --rm -d --name smoke-test-\$\$ --network srv\${N}-podman \
  docker.io/library/alpine:latest sleep 60)
echo "  container: \$CID"
sleep 3

echo "--- 2. aardvark-dns PID ---"
AARDVARK_PID=\$(pidof aardvark-dns)
if [ -z "\$AARDVARK_PID" ]; then
  echo "FAIL: aardvark-dns not running"
  /usr/bin/podman rm -f smoke-test-\$\$ 2>/dev/null
  exit 1
fi
echo "  aardvark-dns PID: \$AARDVARK_PID"

echo "--- 3. resolv.conf in container ---"
RESOLV=\$(/usr/bin/podman exec smoke-test-\$\$ cat /etc/resolv.conf)
echo "\$RESOLV"
if ! echo "\$RESOLV" | grep -q "nameserver \$GATEWAY"; then
  echo "FAIL: nameserver \$GATEWAY not in resolv.conf"
  /usr/bin/podman rm -f smoke-test-\$\$ 2>/dev/null
  exit 1
fi
echo "  nameserver OK"

echo "--- 4. self-lookup (test-dns should resolve to 10.10.\${N}.X) ---"
SELF_RESULT=\$(/usr/bin/podman exec smoke-test-\$\$ nslookup smoke-test-\$\$ 2>&1)
echo "\$SELF_RESULT" | head -8
if echo "\$SELF_RESULT" | grep -q "NXDOMAIN\|can't find"; then
  echo "FAIL: self-lookup returned NXDOMAIN (aardvark rootless bug — see references/aardvark-rootless-bug.md)"
  /usr/bin/podman rm -f smoke-test-\$\$ 2>/dev/null
  exit 1
fi
echo "  self-lookup OK"

echo "--- 5. external lookup (google.com should resolve) ---"
EXT_RESULT=\$(/usr/bin/podman exec smoke-test-\$\$ nslookup google.com \$GATEWAY 2>&1)
echo "\$EXT_RESULT" | head -8
if echo "\$EXT_RESULT" | grep -q "NXDOMAIN\|can't find\|timed out"; then
  echo "FAIL: external lookup failed (likely no systemd-resolved forwarding)"
  /usr/bin/podman rm -f smoke-test-\$\$ 2>/dev/null
  exit 1
fi
echo "  external lookup OK"

echo "--- 6. ICMP + TCP port 53 to gateway ---"
/usr/bin/podman exec smoke-test-\$\$ ping -c 2 -W 2 \$GATEWAY 2>&1 | head -4
echo "  TCP 53:"
/usr/bin/podman exec smoke-test-\$\$ sh -c "echo > /dev/tcp/\$GATEWAY/53 && echo TCP_OPEN || echo TCP_FAIL" 2>&1 | head -1

echo "--- 7. cleanup ---"
/usr/bin/podman rm -f smoke-test-\$\$ 2>/dev/null
echo "  container removed"

echo ""
echo "=== ALL SMOKE TESTS PASSED for SRV-\$N ==="
EOF
