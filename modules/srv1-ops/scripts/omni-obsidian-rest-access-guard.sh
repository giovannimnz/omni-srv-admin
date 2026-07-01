#!/usr/bin/env bash
set -euo pipefail

CHAIN=OMNI-OBSIDIAN-REST
PORT=27124
SERVER_IP=10.1.1.1

iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"
iptables -A "$CHAIN" -i lo -j RETURN
iptables -A "$CHAIN" -i wg0 -s 10.1.1.2/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg0 -s 10.1.1.3/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp --dport "$PORT" -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -j RETURN

iptables -C INPUT -p tcp --dport "$PORT" -j "$CHAIN" 2>/dev/null \
  || iptables -I INPUT 1 -p tcp --dport "$PORT" -j "$CHAIN"
