#!/usr/bin/env bash
set -euo pipefail

CHAIN=OMNI-PG-ACCESS

iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"
iptables -A "$CHAIN" -i lo -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.1.1.2/32 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.1.1.7/32 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp --dport 6432 -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -p tcp --dport 8745 -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -j RETURN

iptables -C INPUT -p tcp -m multiport --dports 6432,8745 -j "$CHAIN" 2>/dev/null \
  || iptables -I INPUT 1 -p tcp -m multiport --dports 6432,8745 -j "$CHAIN"
