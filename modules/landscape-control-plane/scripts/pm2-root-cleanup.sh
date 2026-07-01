#!/usr/bin/env bash
# omni::pm2-root-cleanup v1.0.0
# Targeted cleanup for accidental root PM2 daemon only.
set -u

printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

found=0
terminated=0

for pid in $(pgrep -u root -f 'PM2|pm2' 2>/dev/null || true); do
  [ -r "/proc/$pid/environ" ] || continue
  if tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -qx 'PM2_HOME=/root/.pm2'; then
    found=1
    printf 'root_pm2_pid=%s action=terminate\n' "$pid"
    kill "$pid" 2>/dev/null || true
    terminated=$((terminated + 1))
  fi
done

sleep 2

for pid in $(pgrep -u root -f 'PM2|pm2' 2>/dev/null || true); do
  [ -r "/proc/$pid/environ" ] || continue
  if tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -qx 'PM2_HOME=/root/.pm2'; then
    printf 'root_pm2_pid=%s action=kill\n' "$pid"
    kill -KILL "$pid" 2>/dev/null || true
  fi
done

if [ -d /root/.pm2 ]; then
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="/root/.pm2.omni-accidental-${ts}"
  mv /root/.pm2 "$backup"
  chmod 700 "$backup" 2>/dev/null || true
  printf 'root_pm2_home=moved backup=%s\n' "$backup"
else
  printf 'root_pm2_home=absent\n'
fi

printf 'root_pm2_found=%s terminated=%s\n' "$found" "$terminated"
