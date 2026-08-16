---
name: notebooklm-bridge-camofox-display
description: "Configura e valida o display virtual fixo do Camofox em 1366x768 com noVNC em resize=scale e janela Camoufox maximizada. Usar quando Giovanni pedir ajuste de resolução/display/noVNC do Camofox."
---

# Camofox Display Fixo

Usar para manter o Camofox no display declarado por `CAMOFOX_BROWSER_DISPLAY` com resolução remota fixa e escala local no noVNC.

## Contrato

- `Xvfb` fixo em `1366x768x24`.
- noVNC em `resize=scale`, nunca `resize=remote`.
- `CAMOFOX_VIEWPORT_WIDTH=1366` e `CAMOFOX_VIEWPORT_HEIGHT=768`.
- `CAMOFOX_WINDOW_WIDTH=1366`, `CAMOFOX_WINDOW_HEIGHT=768`, `CAMOFOX_AUTO_MAXIMIZE=1`.
- Browser Camoufox movido para `0,0` e redimensionado para preencher o display após cada launch.

## Validação

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

## Segurança

- Reiniciar `camofox-display.service`/`camofox-browser.service` pode recriar a sessão visual Camofox.
- Não reiniciar `xrdp` para esta manutenção.
- Não usar Chrome DevTools/CDP para auth NotebookLM.
