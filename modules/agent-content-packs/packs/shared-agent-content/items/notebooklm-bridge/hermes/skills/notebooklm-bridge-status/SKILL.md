---
name: notebooklm-bridge-status
description: "Slash command Hermes /notebooklm-bridge-status para status do bridge, auth check, testes e export dry-run."
triggers: [/notebooklm-bridge-status]
---

# /notebooklm-bridge-status

Executar o workflow de status:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
git status --short --branch
uv run pytest
uv run ruff check .
uv run mypy .
uv run python execution/nlm_auth_check.py --write-run
uv run python execution/obsidian_bundle_export.py --dry-run
```

Se auth falhar e a tarefa pedir refresh, usar Camofox primário:

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

Chrome DevTools/CDP é fallback secundário e exige aprovação explícita.

Resumir branch, checks, auth, contagens do export e gate de upload.
