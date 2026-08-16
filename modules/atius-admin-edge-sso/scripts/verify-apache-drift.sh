#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$MODULE_DIR/configs/apache"
AVAILABLE_DIR=/etc/apache2/sites-available
ENABLED_DIR=/etc/apache2/sites-enabled
files=(
  grafana.atius.com.br.conf
  portainer.atius.com.br.conf
  docker.atius.com.br.conf
  docker.atius.com.br-le-ssl.conf
)

for name in "${files[@]}"; do
  cmp -s "$SOURCE_DIR/$name" "$AVAILABLE_DIR/$name" || {
    echo "DRIFT source/sites-available: $name" >&2
    exit 1
  }
  test -L "$ENABLED_DIR/$name" || {
    echo "DRIFT sites-enabled is not a symlink: $name" >&2
    exit 1
  }
  cmp -s "$AVAILABLE_DIR/$name" "$ENABLED_DIR/$name" || {
    echo "DRIFT sites-available/sites-enabled: $name" >&2
    exit 1
  }
done

sudo -n apache2ctl -t >/dev/null
echo "atius-admin-edge-sso-apache-drift=PASS files=${#files[@]}"
