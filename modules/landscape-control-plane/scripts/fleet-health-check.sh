#!/usr/bin/env bash
# omni::fleet-health-check v1.0.0
# Read-only Landscape Control-Plane health check and reconciliation audit.
# Checks: Uptime, OS, CPU, RAM, D-State, Disks/NFS, Stale IPs, Landscape, APT Proxy.
set -u

section() {
  printf '\n== %s ==\n' "$1"
}

verdict="HEALTHY"

section identity
HOST=$(hostname 2>/dev/null || cat /etc/hostname)
FQDN=$(hostname -f 2>/dev/null || echo "$HOST")
printf 'host=%s\n' "$HOST"
printf 'fqdn=%s\n' "$FQDN"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

section uptime_and_load
uptime || true

section os_and_kernel
if [ -r /etc/os-release ]; then
  sed -n 's/^\(PRETTY_NAME\|VERSION_ID\|VERSION_CODENAME\)=/\1=/p' /etc/os-release || true
fi
uname -r -m || true

section memory_and_swap
free -h || true

section d_state_audit
d_procs=$(ps -eo stat,pid,comm 2>/dev/null | grep -w D || true)
if [ -n "$d_procs" ]; then
  printf 'd_state_detected=true\n'
  printf '%s\n' "$d_procs"
  verdict="DEGRADED"
else
  printf 'd_state_detected=false\n'
fi

section disk_and_storage
df -hT / /var /home 2>/dev/null || df -hT /
if mountpoint -q /mnt/gdrive 2>/dev/null; then
  printf 'mount_gdrive=active\n'
  timeout 3 df -hT /mnt/gdrive 2>/dev/null || printf 'mount_gdrive=timeout_or_stale\n'
else
  printf 'mount_gdrive=not_mounted\n'
fi

section stale_ip_audit
if grep -q "10.11.1.11" /etc/hosts 2>/dev/null; then
  printf 'stale_ip_10.11.1.11=detected_in_etc_hosts\n'
  verdict="DEGRADED"
else
  printf 'stale_ip_10.11.1.11=clean\n'
fi

section landscape_client
if command -v landscape-config >/dev/null 2>&1; then
  if landscape-config --is-registered >/dev/null 2>&1; then
    printf 'landscape_registered=true\n'
  else
    printf 'landscape_registered=false\n'
    verdict="DEGRADED"
  fi
else
  printf 'landscape_registered=unknown_missing_cli\n'
fi
if systemctl is-active --quiet landscape-client 2>/dev/null; then
  printf 'landscape_service=active\n'
else
  printf 'landscape_service=inactive\n'
  verdict="DEGRADED"
fi

section apt_cache_proxy
if [ -f /etc/apt/apt.conf.d/01proxy ]; then
  printf 'apt_proxy_conf=%s\n' "$(cat /etc/apt/apt.conf.d/01proxy)"
  # Test TCP connectivity to 10.13.1.13:3142
  if timeout 2 bash -c "cat < /dev/null > /dev/tcp/10.13.1.13/3142" 2>/dev/null; then
    printf 'apt_proxy_connectivity=reachable\n'
  else
    printf 'apt_proxy_connectivity=unreachable\n'
    # Only degrade if not srv3 itself (srv3 listens locally)
    if [ "$HOST" != "atius-srv-3" ]; then
      verdict="DEGRADED"
    fi
  fi
else
  printf 'apt_proxy_conf=none\n'
fi

section critical_services
for svc in pm2-ubuntu tailscaled xrdp k3s k3s-agent podman; do
  if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    printf '%s active=%s enabled=%s\n' "$svc" "$(systemctl is-active "$svc" 2>/dev/null || echo inactive)" "$(systemctl is-enabled "$svc" 2>/dev/null || echo disabled)"
  fi
done

section verdict
printf 'overall_health=%s\n' "$verdict"
