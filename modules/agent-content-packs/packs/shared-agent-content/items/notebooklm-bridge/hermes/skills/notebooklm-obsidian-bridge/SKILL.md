---
name: notebooklm-obsidian-bridge
description: "Skill Hermes para o NotebookLM Obsidian bridge local. Usar para /notebooklm-obsidian-bridge, auth checks, export dry-runs do Obsidian, uploads controlados, extração Bot Conversacional e operações do bridge."
version: "1.0.0"
author: Giovanni/Codex
license: MIT
platforms: [linux, windows]
triggers:
  - /notebooklm-obsidian-bridge
  - NotebookLM Obsidian bridge
  - Bot Conversacional
  - notebooklm-py
metadata:
  hermes:
    tags: [notebooklm, obsidian, bridge, codex, openai, upload-validation]
    related_skills: [obsidian-doc-mandatory, md-repo, md-doc, codex, hermes-agent]
---

# NotebookLM Obsidian Bridge

Operar `/home/ubuntu/GitHub/notebooklm-obsidian-bridge` com segurança.

## Regras

- Usar PT-BR com Giovanni.
- Manter auth em `NOTEBOOKLM_HOME=/home/ubuntu/.local/state/notebooklm-obsidian-bridge/notebooklm-home`.
- Usar `NOTEBOOKLM_PROFILE=obsidian-spike`.
- Usar Camofox/Hermes como navegador primário para refresh/auth; Chrome DevTools/CDP é fallback secundário com aprovação explícita.
- Nunca commitar cookies, `storage_state.json`, tokens, credenciais, HAR ou `.env`.
- Preferir comandos dry-run/read-only, salvo upload explicitamente aprovado.

## Comandos

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run pytest
uv run ruff check .
uv run mypy .
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
uv run python execution/nlm_auth_check.py --write-run
uv run python execution/obsidian_bundle_export.py --dry-run
```

Upload controlado após aprovação:

```bash
bundle_run=$(uv run python execution/obsidian_bundle_export.py --write)
uv run python execution/nlm_e2e_upload.py \
  --bundle "$bundle_run/bundle.md" \
  --target-name "Bot Conversacional" \
  --upload-real
```
