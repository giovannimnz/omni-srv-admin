---
name: notebooklm-bridge-e2e
description: "Roda validação end-to-end controlada do upload NotebookLM: escreve bundle Obsidian, valida em notebook descartável e envia para Bot Conversacional somente quando aprovado. Usar para /notebooklm-bridge-e2e."
---

# NotebookLM Bridge E2E

Usar somente quando upload real tiver aprovação explícita na sessão atual.

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
bundle_run=$(uv run python execution/obsidian_bundle_export.py --write)
bundle="$bundle_run/bundle.md"
uv run python execution/nlm_e2e_upload.py \
  --bundle "$bundle" \
  --target-name "Bot Conversacional" \
  --upload-real
```

Reportar diretório da run, notebook alvo, resultado descartável, resultado real e source IDs.
