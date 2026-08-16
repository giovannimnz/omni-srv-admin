---
name: notebooklm-bridge-safe-export
description: "Slash command Hermes /notebooklm-bridge-safe-export para dry-runs seguros de export Obsidian sem upload NotebookLM."
triggers: [/notebooklm-bridge-safe-export]
---

# /notebooklm-bridge-safe-export

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/obsidian_bundle_export.py --dry-run
```

Reportar contagens e diretório da run. Não fazer upload.
