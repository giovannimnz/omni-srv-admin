#!/usr/bin/env bash
set -euo pipefail

TCP_PORTS="6443,2379,2380,10250,10257,10259"
UDP_PORTS="8472"
PRIVATE_CIDRS=(
  "10.11.0.0/16"
  "10.12.0.0/16"
  "10.13.0.0/16"
  "10.21.0.0/16"
)

delete_comment_rules() {
  local comment="$1"
  while iptables -S INPUT | grep -q -- "--comment $comment"; do
    local spec
    spec=$(iptables -S INPUT | grep -- "--comment $comment" | head -1 | sed 's/^-A INPUT //')
    # shellcheck disable=SC2086
    iptables -D INPUT $spec
  done
}

insert_before_k3s_drop() {
  local kind="$1"
  shift
  local drop_line drop_index
  if [ "$kind" = "tcp" ]; then
    drop_line=$(iptables -L INPUT --line-numbers -n | awk '/tcp/ && /dpts:(6443|2379|2380|10250|10257|10259)/ && /DROP/ {print $1; exit}')
  else
    drop_line=$(iptables -L INPUT --line-numbers -n | awk '/udp/ && /dpt:8472|dpts:8472/ && /DROP/ {print $1; exit}')
  fi
  drop_index=${drop_line:-1}
  # shellcheck disable=SC2086
  iptables -I INPUT "$drop_index" "$@"
}

delete_comment_rules ATIUS_K3S_PRIVATE_TCP
delete_comment_rules ATIUS_K3S_PRIVATE_UDP

for cidr in "${PRIVATE_CIDRS[@]}"; do
  insert_before_k3s_drop tcp -s "$cidr" -p tcp -m multiport --dports "$TCP_PORTS" -m comment --comment ATIUS_K3S_PRIVATE_TCP -j ACCEPT
  insert_before_k3s_drop udp -s "$cidr" -p udp -m multiport --dports "$UDP_PORTS" -m comment --comment ATIUS_K3S_PRIVATE_UDP -j ACCEPT
done

# Keep the older allow-list and final deny guard if they are absent on a restored host.
iptables -C INPUT -i lo -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i lo -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
iptables -C INPUT -s 10.42.0.0/16 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -s 10.42.0.0/16 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
iptables -C INPUT -s 10.42.0.0/16 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -s 10.42.0.0/16 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT
iptables -C INPUT -i wg0 -s 10.1.1.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i wg0 -s 10.1.1.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
iptables -C INPUT -i wg0 -s 10.1.1.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i wg0 -s 10.1.1.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT
iptables -C INPUT -i wg100 -s 10.100.100.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i wg100 -s 10.100.100.0/24 -p tcp -m multiport --dports "$TCP_PORTS" -j ACCEPT
iptables -C INPUT -i wg100 -s 10.100.100.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -i wg100 -s 10.100.100.0/24 -p udp -m multiport --dports "$UDP_PORTS" -j ACCEPT
iptables -C INPUT -p tcp -m multiport --dports "$TCP_PORTS" -j DROP 2>/dev/null || iptables -A INPUT -p tcp -m multiport --dports "$TCP_PORTS" -j DROP
iptables -C INPUT -p udp -m multiport --dports "$UDP_PORTS" -j DROP 2>/dev/null || iptables -A INPUT -p udp -m multiport --dports "$UDP_PORTS" -j DROP

iptables -S INPUT | grep -E 'ATIUS_K3S_PRIVATE|6443|2379|2380|10250|8472' || true
