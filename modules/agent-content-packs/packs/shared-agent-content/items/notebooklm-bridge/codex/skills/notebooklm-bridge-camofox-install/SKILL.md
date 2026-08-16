---
name: notebooklm-bridge-camofox-install
description: "Manual reproduzível de instalação do camofox-browser no host, com integração ao notebooklm-obsidian-bridge. Usar para provisionar o servidor Camofox self-hosted em SRV-1/2/3 ou em qualquer host Linux user-level."
version: "1.0.0"
author: Giovanni/Codex
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [camofox, hermes, notebooklm, runbook, install]
---

# Instalação do Camofox (camofox-browser)

Doc de origem:

- `/home/ubuntu/GitHub/notebooklm-obsidian-bridge/docs/CAMOFOX-INSTALL.md` (manual completo)
- `~/GitHub/obsidian-vault/AiSecondBrain/60-LOGS/2026-06-15-camofox-hermes-notebooklm-bridge.md` (overview)
- `~/GitHub/obsidian-vault/AiSecondBrain/60-LOGS/61-Incidents/2026-06-15-camofox-vnc-porta-colisao-e-log-permissao.md` (incident)
- `~/GitHub/obsidian-vault/AiSecondBrain/60-LOGS/2026-06-15-firefox-cookies-para-camofox.md` (Firefox -> Camofox)

## Provisionamento mínimo

```bash
# Pré-requisitos (apt)
sudo apt-get install -y xvfb x11vnc novnc websockify

# Repo + binário Camoufox (~707 MB) + GeoIP (~66 MB)
mkdir -p ~/GitHub && cd ~/GitHub
git clone --depth 1 https://github.com/jo-inc/camofox-browser.git
cd camofox-browser
npm install
```

## Service + env

```bash
mkdir -p ~/.local/state/camofox-browser/{profiles,cookies,traces,logs}
chmod 700 ~/.local/state/camofox-browser
chmod 700 ~/.local/state/camofox-browser/{profiles,cookies,traces,logs}

# Generate API key (48 hex chars)
API_KEY=$(openssl rand -hex 24)
```

Arquivo `~/.config/camofox-browser.env` (mode 600):

```bash
CAMOFOX_PORT=9377
CAMOFOX_PROFILE_DIR=/home/ubuntu/.local/state/camofox-browser/profiles
CAMOFOX_COOKIES_DIR=/home/ubuntu/.local/state/camofox-browser/cookies
CAMOFOX_TRACES_DIR=/home/ubuntu/.local/state/camofox-browser/traces
CAMOFOX_CRASH_REPORT_ENABLED=false
ENABLE_VNC=1
CAMOFOX_BROWSER_DISPLAY=:90
VNC_RESOLUTION=1366x768
VNC_PORT=5990
NOVNC_PORT=6170
CAMOFOX_VIEWPORT_WIDTH=1366
CAMOFOX_VIEWPORT_HEIGHT=768
CAMOFOX_WINDOW_WIDTH=1366
CAMOFOX_WINDOW_HEIGHT=768
CAMOFOX_AUTO_MAXIMIZE=1
NODE_ENV=production
CAMOFOX_API_KEY=$API_KEY
```

Arquivo `~/.config/systemd/user/camofox-display.service` (mode 644):

```ini
[Unit]
Description=Camofox Fixed Virtual Display

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :90 -screen 0 1366x768x24 -ac -nolisten tcp
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
```

Arquivo `~/.config/systemd/user/camofox-browser.service` (mode 644):

```ini
[Unit]
Description=Camofox Browser Server
After=network-online.target camofox-display.service
Wants=network-online.target camofox-display.service

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/GitHub/camofox-browser
EnvironmentFile=/home/ubuntu/.config/camofox-browser.env
ExecStart=/home/ubuntu/.nvm/versions/node/v24.13.1/bin/node /home/ubuntu/GitHub/camofox-browser/server.js
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
```

Ativar:

```bash
systemctl --user daemon-reload
systemctl --user enable --now camofox-display.service
systemctl --user enable --now camofox-browser.service
systemctl --user status camofox-browser.service --no-pager
```

## Validação

```bash
source /home/ubuntu/.config/camofox-browser.env
ss -tlnp | awk -v v=":$VNC_PORT" -v n=":$NOVNC_PORT" 'NR==1 || /:9377/ || index($0,v) || index($0,n)'
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xdpyinfo >/dev/null
curl -s http://127.0.0.1:9377/health
curl -I "http://127.0.0.1:${NOVNC_PORT}/vnc.html"
```

Esperado: `Xvfb` no `CAMOFOX_BROWSER_DISPLAY`, `{"ok":true,"engine":"camoufox",...}` e `HTTP 200` no noVNC.

## Integração com o bridge

```bash
# ~/.hermes/.env
CAMOFOX_URL=http://127.0.0.1:9377
```

```yaml
# ~/.hermes/config.yaml
browser:
  camofox:
    managed_persistence: true
    user_id: ""
    session_key: ""
    adopt_existing_tab: false
    rewrite_loopback_urls: false
    loopback_host_alias: host.docker.internal
```

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_camofox_auth.py prepare
# abrir a URL noVNC retornada pelo prepare
uv run python execution/nlm_camofox_auth.py import-state
uv run python execution/nlm_auth_check.py --write-run

# caminho primario rapido, quando Firefox local ja esta logado
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

## Patches locais obrigatórios

### `vnc-watcher.sh`

O upstream grava logs em `/var/log/*` (inacessível pro `systemd --user` sem sudo). Patch:

- `LOG_ROOT=${CAMOFOX_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/camofox-browser/logs}` (criado no boot)
- `WEBSOCKIFY_PID` + `trap cleanup EXIT INT TERM` para cleanup
- `X11VNC_ARGS` usa `-localhost` e aponta pra log do usuário
- O watcher religa `x11vnc` quando ele morre no mesmo `CAMOFOX_BROWSER_DISPLAY`.
- O cleanup do `server.js` deve preservar o `Xvfb` gerenciado por `camofox-display.service`.
- O noVNC usa `resize=scale`: resolução remota fixa `1366x768`, escala local ao tamanho da janela.
- O `server.js` deve ajustar a janela Camoufox para `1366x768` após cada launch.

### (Opcional) `plugins/cookies/`

Se precisar de cookie import via Netscape file (`POST /sessions/:userId/cookies` com `cookies` no body), nada a patchar — já funciona.

## Backup

```bash
tar -czf /tmp/camofox-state-$(date -I).tar.gz \
  ~/.local/state/camofox-browser/profiles/ \
  ~/.local/state/camofox-browser/logs/
cp ~/.config/systemd/user/camofox-browser.service /tmp/
cp ~/.config/camofox-browser.env /tmp/
```
