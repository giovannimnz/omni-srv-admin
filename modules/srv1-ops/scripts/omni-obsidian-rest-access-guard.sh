#!/usr/bin/env bash
set -euo pipefail

CHAIN=OMNI-OBSIDIAN-REST
PORT=27124
SERVER_IP=10.11.1.11

iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"
iptables -A "$CHAIN" -i lo -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.5/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.6/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.8/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.9/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.2/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -i wg100 -s 10.100.100.3/32 -d "$SERVER_IP/32" -p tcp --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.12.0.0/16 --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.13.0.0/16 --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.14.0.0/16 --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.21.0.0/16 --dport "$PORT" -j RETURN
iptables -A "$CHAIN" -p tcp --dport "$PORT" -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -j RETURN

iptables -C INPUT -p tcp --dport "$PORT" -j "$CHAIN" 2>/dev/null \
  || iptables -I INPUT 1 -p tcp --dport "$PORT" -j "$CHAIN"
