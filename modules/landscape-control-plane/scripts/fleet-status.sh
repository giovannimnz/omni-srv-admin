#!/usr/bin/env bash
# omni::fleet-status v1.0.0
# Read-only Landscape script. Do not mutate services, packages or files.
set -u

section() {
  printf '\n== %s ==\n' "$1"
}

section identity
hostnamectl 2>/dev/null || hostname
printf 'fqdn=%s\n' "$(hostname -f 2>/dev/null || hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

section uptime
uptime || true

section os
cat /etc/os-release 2>/dev/null | sed -n 's/^\(PRETTY_NAME\|VERSION_ID\|VERSION_CODENAME\)=/\1=/p' || true
uname -a || true

section disk
df -hT / /var /home 2>/dev/null || df -hT /

section memory
free -h || true

section services
for svc in landscape-client xrdp xrdp-sesman pm2-ubuntu k3s k3s-agent container-vaultwarden-atius container-hashicorp-vault-atius; do
  if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    printf '%s active=%s enabled=%s\n' "$svc" "$(systemctl is-active "$svc" 2>/dev/null || true)" "$(systemctl is-enabled "$svc" 2>/dev/null || true)"
  else
    printf '%s missing\n' "$svc"
  fi
done

section ubuntu_pro
if command -v pro >/dev/null 2>&1; then
  pro status --format json 2>/dev/null || pro status 2>/dev/null || true
else
  echo "pro=missing"
fi

section landscape_client
if command -v landscape-config >/dev/null 2>&1; then
  if [ -r /etc/landscape/client.conf ]; then
    landscape-config --is-registered >/dev/null 2>&1 && echo "registered=true" || echo "registered=false"
  elif [ -e /etc/landscape/client.conf ]; then
    echo "client_conf=unreadable"
  else
    echo "client_conf=missing"
  fi
else
  echo "landscape-config=missing"
fi
