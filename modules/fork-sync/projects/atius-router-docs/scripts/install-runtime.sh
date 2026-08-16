#!/usr/bin/env bash
set -euo pipefail

readonly PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SOURCE_UNIT="$PROJECT_ROOT/runtime/atius-router-docs.service"
readonly USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
readonly TARGET_UNIT="$USER_SYSTEMD_DIR/atius-router-docs.service"

if [[ ! -f "$SOURCE_UNIT" ]]; then
  printf 'ERROR: canonical unit missing: %s\n' "$SOURCE_UNIT" >&2
  exit 1
fi

mkdir -p "$USER_SYSTEMD_DIR"

if [[ -f "$TARGET_UNIT" ]] && ! cmp -s "$SOURCE_UNIT" "$TARGET_UNIT"; then
  readonly BACKUP_DIR="${ATIUS_ROUTER_DOCS_UNIT_BACKUP_DIR:-$HOME/backups/atius-router-docs-systemd}"
  mkdir -p "$BACKUP_DIR"
  cp --preserve=all "$TARGET_UNIT" \
    "$BACKUP_DIR/atius-router-docs.service.$(date -u +%Y%m%dT%H%M%SZ).bak"
fi

install -m 0644 "$SOURCE_UNIT" "$TARGET_UNIT"
systemctl --user daemon-reload
systemctl --user enable --now atius-router-docs.service

for attempt in $(seq 1 30); do
  if curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:3003/en/docs/; then
    printf 'atius-router-docs runtime: healthy (attempt=%s)\n' "$attempt"
    exit 0
  fi
  sleep 2
done

printf 'ERROR: atius-router-docs did not become healthy on 127.0.0.1:3003\n' >&2
systemctl --user status --no-pager atius-router-docs.service >&2 || true
exit 1
