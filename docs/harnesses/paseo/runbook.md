# Paseo AI Agent Runtime — Fleet Operations Runbook

## 1. Fleet Operations via Landscape

Multi-server operations MUST be executed using Landscape Control-Plane:

```bash
# Load self-hosted Landscape environment
set -a && source /home/ubuntu/.config/omni/landscape-selfhost.env && set +a

# Fleet-wide health probe
omni landscape run fleet-paseo-status --hosts all --wait --yes

# Fleet-wide software install/update
omni landscape run fleet-paseo-install --hosts all --wait --yes

# Reapply Apache Edge Gateway configuration (srv-1 only)
omni landscape run fleet-paseo-apache-edge --hosts atius-srv-1 --wait --yes
```

## 2. Host-Level Troubleshooting

```bash
# Check systemd user service status
XDG_RUNTIME_DIR="/run/user/$(id -u)" systemctl --user status paseo-daemon.service

# View live logs
XDG_RUNTIME_DIR="/run/user/$(id -u)" journalctl --user-unit paseo-daemon.service -f

# Restart daemon
XDG_RUNTIME_DIR="/run/user/$(id -u)" systemctl --user restart paseo-daemon.service
```

## 3. Public Verification

```bash
# Verify API Health (HTTP 200)
curl -sI https://paseo.atius.io/api/health
curl -sI https://paseo.atius.com.br/api/health

# Verify SSO Redirect (HTTP 302 to /login)
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" https://paseo.atius.io/

# Verify Canonical Login Shell (HTTP 200)
curl -s -o /dev/null -w "%{http_code}\n" https://paseo.atius.io/login

# Verify WebSocket Handshake (HTTP 101)
curl -i -N --http1.1 \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
  https://paseo.atius.io/ws --max-time 2
```
