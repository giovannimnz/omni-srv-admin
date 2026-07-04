# Wayland Managed Runtime

## Ownership

- runtime de `wayland.atius.com.br` é administrado a partir do `omni-srv-admin`
- source repo permanece `~/GitHub/wayland`
- rebuild/reapply pós-update fica em `modules/fleet/scripts/`

## Commands

```bash
cd ~/GitHub/omni-srv-admin
bash modules/fleet/scripts/wayland-srv3-postinstall-hook.sh
bash modules/fleet/scripts/wayland-srv3-update.sh
bash modules/fleet/scripts/wayland-srv3-update.sh --pull
```

## Guarantees

- botão pré-chat `Conversar na pasta` visível no WebUI
- diretório padrão de `Conversar na pasta`: `/home/ubuntu/GitHub`
- idioma padrão da tela de login: `Português (Brasil)` quando não existe
  preferência salva
- runtime source-standalone em `~/GitHub/wayland/dist-server/server.mjs`
- `WAYLAND_DISABLE_AUTO_UPDATE=1` sempre ativo neste deployment

## Validation Baseline

- `https://wayland.atius.com.br/api/auth/status` -> `200`
- `admin / Bkfigt!546` -> login público com sucesso
- `/api/auth/user` -> `200` com cookie de sessão
