# /notebooklm-bridge-e2e

Roda o fluxo aprovado de upload controlado para NotebookLM.

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
bundle_run=$(uv run python execution/obsidian_bundle_export.py --write)
bundle="$bundle_run/bundle.md"
uv run python execution/nlm_e2e_upload.py \
  --bundle "$bundle" \
  --target-name "Bot Conversacional" \
  --upload-real
```

Reportar:

- diretório da run do bundle;
- alvo NotebookLM selecionado;
- resultado do notebook descartável;
- resultado do upload real para `Bot Conversacional`;
- source IDs;
- path do checkpoint no vault.
