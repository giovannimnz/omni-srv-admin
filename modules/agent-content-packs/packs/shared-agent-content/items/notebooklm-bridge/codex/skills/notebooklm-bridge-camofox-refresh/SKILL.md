---
name: notebooklm-bridge-camofox-refresh
description: "Refresh primario de auth do NotebookLM usando Firefox -> Camofox/Hermes -> notebooklm-py. Usar para /notebooklm-bridge-camofox-refresh ou quando auth estiver expirada."
---

# NotebookLM Bridge Camofox Refresh

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

Reportar:

- run_dir do refresh/import;
- run_dir do auth check;
- se `status: ok` e `token_fetch: true`;
- que nenhum upload real ao NotebookLM foi feito.
