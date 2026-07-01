#!/usr/bin/env bash
# omni::reboot-required v1.0.0
# Read-only reboot-required state report.
set -u

printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ -f /var/run/reboot-required ]; then
  echo "reboot_required=true"
else
  echo "reboot_required=false"
fi

if [ -f /var/run/reboot-required.pkgs ]; then
  echo "packages:"
  sed 's/^/- /' /var/run/reboot-required.pkgs
fi

if command -v needrestart >/dev/null 2>&1; then
  echo "needrestart:"
  needrestart -b 2>/dev/null || true
fi
