#!/usr/bin/env bash
# omni::version-report v1.0.1
# Read-only Landscape script. Reports versions for governance.
set -u

report() {
  name="$1"
  shift
  if command -v "$1" >/dev/null 2>&1; then
    printf '%s=' "$name"
    "$@" 2>&1 | head -n 1
  else
    printf '%s=missing\n' "$name"
  fi
}

pm2_version_readonly() {
  if ! command -v pm2 >/dev/null 2>&1; then
    printf 'pm2=missing\n'
    return
  fi

  bin="$(command -v pm2)"
  real="$(readlink -f "$bin" 2>/dev/null || printf '%s' "$bin")"
  base="$(dirname "$real")"
  for candidate in \
    "$base/../lib/node_modules/pm2/package.json" \
    "$base/../../lib/node_modules/pm2/package.json" \
    "/usr/local/lib/node_modules/pm2/package.json" \
    "/usr/lib/node_modules/pm2/package.json"; do
    if [ -r "$candidate" ]; then
      python3 - "$candidate" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
print("pm2=" + str(data.get("version", "installed-version-unknown")))
PY
      return
    fi
  done

  printf 'pm2=installed-version-unknown\n'
}

printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat /etc/os-release 2>/dev/null | sed -n 's/^PRETTY_NAME=/os=/p' || true
printf 'kernel=%s\n' "$(uname -r)"

report landscape-client landscape-client --version
report pro pro version
report k3s k3s --version
report kubectl kubectl version --client=true
report podman podman --version
report docker docker --version
report node node --version
report npm npm --version
pm2_version_readonly
report python3 python3 --version
report rustc rustc --version
report cargo cargo --version
report zellij zellij --version

if command -v apt-cache >/dev/null 2>&1; then
  for pkg in landscape-client xrdp k3s podman docker.io nodejs npm; do
    line="$(apt-cache policy "$pkg" 2>/dev/null | awk '/Installed:/ {print $2; exit}')"
    printf 'apt.%s=%s\n' "$pkg" "${line:-unknown}"
  done
fi
