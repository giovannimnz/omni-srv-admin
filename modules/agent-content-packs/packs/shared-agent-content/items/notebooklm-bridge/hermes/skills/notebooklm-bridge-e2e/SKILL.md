---
name: notebooklm-bridge-e2e
description: "Slash command Hermes /notebooklm-bridge-e2e para validação controlada de upload de bundle NotebookLM e envio ao Bot Conversacional após aprovação."
triggers: [/notebooklm-bridge-e2e]
---

# /notebooklm-bridge-e2e

Exige aprovação explícita para upload real.

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
bundle_run=$(uv run python execution/obsidian_bundle_export.py --write)
uv run python execution/nlm_e2e_upload.py \
  --bundle "$bundle_run/bundle.md" \
  --target-name "Bot Conversacional" \
  --upload-real
```

Reportar source IDs do descartável e do notebook real.
