---
name: notebooklm-bridge-camofox-display
description: "Slash command Hermes /notebooklm-bridge-camofox-display para configurar/validar display virtual Camofox 1366x768, noVNC resize=scale e janela maximizada."
triggers: [/notebooklm-bridge-camofox-display]
---

# /notebooklm-bridge-camofox-display

Contrato operacional:

- `Xvfb` fixo em `1366x768x24`, display lido de `CAMOFOX_BROWSER_DISPLAY`.
- noVNC em `resize=scale`, nao `resize=remote`.
- viewport Playwright `1366x768`.
- janela Camoufox em `0,0` com tamanho `1366x768` apos cada launch.

Validar:

```bash
systemctl --user status camofox-display.service camofox-browser.service --no-pager
source /home/ubuntu/.config/camofox-browser.env
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xdpyinfo | grep dimensions
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xwininfo -root | grep -E 'Width|Height'
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xdotool search --onlyvisible --name Camoufox getwindowgeometry %@
curl -I "http://127.0.0.1:${NOVNC_PORT}/vnc.html"
```

URL humana:

```text
http://127.0.0.1:${NOVNC_PORT}/vnc.html?autoconnect=1&resize=scale
```

Nao reiniciar `xrdp` para esta manutencao.
