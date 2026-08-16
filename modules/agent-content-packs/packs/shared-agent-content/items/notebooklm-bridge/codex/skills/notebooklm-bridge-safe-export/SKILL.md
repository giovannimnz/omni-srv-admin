---
name: notebooklm-bridge-safe-export
description: "Roda dry-run seguro de export Obsidian com allowlist para NotebookLM. Usar para preparar ou inspecionar bundle sem upload, ou para /notebooklm-bridge-safe-export."
---

# NotebookLM Bridge Safe Export

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/obsidian_bundle_export.py \
  --vault /home/ubuntu/GitHub/obsidian-vault/AiSecondBrain \
  --dry-run
```

Reportar quantidade incluída, bloqueada, possíveis secrets, palavras, bytes e diretório da run. Não fazer upload.
