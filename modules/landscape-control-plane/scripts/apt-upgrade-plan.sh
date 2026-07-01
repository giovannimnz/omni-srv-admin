#!/usr/bin/env bash
# omni::apt-upgrade-plan v1.0.0
# APT simulation only. Does not install, upgrade, remove, restart or reboot.
set -u

export DEBIAN_FRONTEND=noninteractive
printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get=missing"
  exit 0
fi

echo "== apt simulation =="
apt-get -s -o Debug::NoLocking=1 dist-upgrade 2>&1 || true

echo "== autoremove simulation =="
apt-get -s -o Debug::NoLocking=1 autoremove 2>&1 || true

echo "== reboot marker =="
if [ -f /var/run/reboot-required ]; then
  echo "reboot_required=true"
  cat /var/run/reboot-required.pkgs 2>/dev/null || true
else
  echo "reboot_required=false"
fi
