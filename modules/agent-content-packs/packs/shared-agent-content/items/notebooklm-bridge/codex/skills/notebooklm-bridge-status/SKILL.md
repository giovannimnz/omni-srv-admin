---
name: notebooklm-bridge-status
description: "Checa status do repo NotebookLM Obsidian bridge, validações e export dry-run. Usar quando pedirem status do bridge ou /notebooklm-bridge-status."
---

# NotebookLM Bridge Status

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
git status --short --branch
uv run pytest
uv run ruff check .
uv run mypy .
uv run python execution/nlm_auth_check.py --write-run
uv run python execution/obsidian_bundle_export.py --dry-run
```

Se `auth_check` falhar e o pedido incluir refresh de sessão, usar o navegador primário:

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

Não usar Chrome DevTools/CDP salvo aprovação explícita.

Reportar branch, estado dirty, checks, diretório da run de auth, diretório da run do exporter e se upload real já foi feito.
