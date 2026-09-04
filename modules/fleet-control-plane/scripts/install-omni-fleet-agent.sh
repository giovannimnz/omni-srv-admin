#!/usr/bin/env bash
set -euo pipefail

ROOT="${OMNI_SRV_ADMIN:-$HOME/GitHub/omni-srv-admin}"
UNIT_SRC="$ROOT/modules/fleet-control-plane/systemd/omni-fleet-agent.service"
UNIT_DST="$HOME/.config/systemd/user/omni-fleet-agent.service"
ENV_DST="/etc/omni-srv-admin/fleet-agent.env"
DB_CACHE_DST="$HOME/.config/omni-srv-admin/fleet-db.env"

host_id="${1:-${OMNI_HOST_ID:-}}"
if [[ -z "$host_id" ]]; then
  short_host="$(hostname | tr '[:upper:]' '[:lower:]')"
  case "$short_host" in
    atius-srv-1|srv1|atius) host_id="atius-srv-1" ;;
    atius-srv-2|srv2|zentrius) host_id="atius-srv-2" ;;
    atius-srv-3|srv3) host_id="atius-srv-3" ;;
    atius-srv-4|srv4) host_id="atius-srv-4" ;;
    *) host_id="$short_host" ;;
  esac
fi

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "missing unit source: $UNIT_SRC" >&2
  exit 1
fi

if [[ ! -f /etc/omni-srv-admin/fleet-db.env ]]; then
  echo "missing /etc/omni-srv-admin/fleet-db.env; configure PgBouncer DB env first" >&2
  exit 1
fi

# The agent is user-level systemd, so it cannot read the root-only hydration
# cache directly. Materialize a mode-0600 user cache from that Vault-derived
# cache; the unit pins this path through OMNI_FLEET_DB_ENV.
install -d -m 0700 "$HOME/.config/omni-srv-admin"
sudo install -o "$(id -u)" -g "$(id -g)" -m 0600 \
  /etc/omni-srv-admin/fleet-db.env "$DB_CACHE_DST"

mkdir -p "$HOME/.config/systemd/user"
cp "$UNIT_SRC" "$UNIT_DST"

sudo install -d -m 0755 /etc/omni-srv-admin
tmp_env="$(mktemp)"
cat >"$tmp_env" <<EOF
OMNI_HOST_ID=$host_id
OMNI_AGENT_INTERVAL_SECONDS=30
OMNI_REPO_DIR=$ROOT
EOF
sudo install -m 0644 "$tmp_env" "$ENV_DST"
rm -f "$tmp_env"

systemctl --user daemon-reload
systemctl --user enable --now omni-fleet-agent.service
systemctl --user --no-pager status omni-fleet-agent.service
