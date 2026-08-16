# /notebooklm-bridge-camofox-display

Configura e valida o display virtual fixo do Camofox.

Contrato:

- `CAMOFOX_BROWSER_DISPLAY` lido de `/home/ubuntu/.config/camofox-browser.env`
- resolução remota fixa `1366x768`
- noVNC com `resize=scale`
- viewport Playwright `1366x768`
- janela Camoufox maximizada/preenchendo o display por padrão

Validar:

```bash
systemctl --user status camofox-display.service camofox-browser.service --no-pager
source /home/ubuntu/.config/camofox-browser.env
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xdpyinfo | grep dimensions
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xwininfo -root | grep -E 'Width|Height'
DISPLAY="$CAMOFOX_BROWSER_DISPLAY" xdotool search --onlyvisible --name Camoufox getwindowgeometry %@
curl -I "http://127.0.0.1:${NOVNC_PORT}/vnc.html"
```

URL:

```text
http://127.0.0.1:${NOVNC_PORT}/vnc.html?autoconnect=1&resize=scale
```
