---
name: notebooklm-bridge-camofox-refresh
description: "Slash command Hermes /notebooklm-bridge-camofox-refresh para refresh primario de auth via Firefox -> Camofox/Hermes -> notebooklm-py."
triggers: [/notebooklm-bridge-camofox-refresh]
---

# /notebooklm-bridge-camofox-refresh

Camofox/Hermes e o navegador primario do bridge. Chrome DevTools/CDP e fallback
secundario e exige aprovacao explicita.

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
uv run python execution/nlm_auth_check.py --write-run
```

Se o Firefox local nao tiver sessao valida, usar o caminho visual:

```bash
uv run python execution/nlm_camofox_auth.py prepare
# abrir a URL noVNC retornada pelo prepare
uv run python execution/nlm_camofox_auth.py import-state
uv run python execution/nlm_auth_check.py --write-run
```

Reportar run dirs, `status`, `token_fetch` e confirmar que nenhum upload real foi feito.
