#!/usr/bin/env bash
set -euo pipefail

eval "$(/home/ubuntu/.local/bin/atius-vault-env codex-acp)"
: "${OPENCLAW_GATEWAY_TOKEN:?Vault profile codex-acp did not export OPENCLAW_GATEWAY_TOKEN}"

install -d -m 0700 /home/ubuntu/.config/openclaw
umask 077
printf 'OPENCLAW_GATEWAY_TOKEN=%s\n' "$OPENCLAW_GATEWAY_TOKEN" \
  > /home/ubuntu/.config/openclaw/gateway.env
chmod 0600 /home/ubuntu/.config/openclaw/gateway.env
