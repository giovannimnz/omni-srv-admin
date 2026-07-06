#!/usr/bin/env bash
set -euo pipefail

TCP_PORTS="6443,2379,2380,10250,10257,10259"
UDP_PORTS="8472"

insert_rule() {
  local pos="$1"
  shift
  if ! iptables -C INPUT "$@" 2>/dev/null; then
    iptables -I INPUT "$pos" "$@"
  fi
}

append_rule() {
  if ! iptables -C INPUT "$@" 2>/dev/null; then
    iptables -A INPUT "$@"
  fi
}

insert_rule 1 -i lo -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
insert_rule 1 -i wg100 -s 10.100.100.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
insert_rule 1 -i wg0 -s 10.1.1.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
insert_rule 1 -s 10.42.0.0/16 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
insert_rule 1 -i wg100 -s 10.100.100.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT
insert_rule 1 -i wg0 -s 10.1.1.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT
insert_rule 1 -s 10.42.0.0/16 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT

append_rule -p tcp -m multiport --dports "$TCP_PORTS" -j DROP
append_rule -p udp -m multiport --dports "$UDP_PORTS" -j DROP

iptables -S INPUT | grep -E "(6443|2379|2380|10250|8472)" || true
