# /notebooklm-bridge-status

Mostra o status atual do bridge.

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
git status --short --branch
uv run pytest
uv run ruff check .
uv run mypy .
uv run python execution/obsidian_bundle_export.py --dry-run
```

Se precisar renovar auth, usar Camofox primário:

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

Reportar:

- branch Git e estado dirty;
- status de testes/lint/tipos;
- contagens do dry-run: incluídos, bloqueados, secrets;
- se o gate de upload real ao NotebookLM continua fechado.
