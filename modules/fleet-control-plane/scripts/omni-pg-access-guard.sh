#!/usr/bin/env bash
set -euo pipefail

CHAIN=OMNI-PG-ACCESS
RULE_SPEC=(-p tcp -m multiport --dports 6432,8745 -j "$CHAIN")

iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"
iptables -A "$CHAIN" -i lo -j RETURN
iptables -A "$CHAIN" -i wg100 -p tcp -s 10.100.100.0/24 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.12.0.0/16 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.13.0.0/16 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.14.0.0/16 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp -s 10.21.0.0/16 --dport 6432 -j RETURN
iptables -A "$CHAIN" -p tcp --dport 6432 -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -p tcp --dport 8745 -j REJECT --reject-with tcp-reset
iptables -A "$CHAIN" -j RETURN

while iptables -C INPUT "${RULE_SPEC[@]}" 2>/dev/null; do
  iptables -D INPUT "${RULE_SPEC[@]}"
done

WG_OPEN_LINE="$(
  iptables -L INPUT --line-numbers -n \
    | awk '
        $4 == "ACCEPT" && $7 == "wg100" && $9 == "10.100.100.0/24" { print $1; exit }
      '
)"

if [ -n "$WG_OPEN_LINE" ]; then
  iptables -I INPUT "$WG_OPEN_LINE" "${RULE_SPEC[@]}"
else
  iptables -I INPUT 1 "${RULE_SPEC[@]}"
fi
