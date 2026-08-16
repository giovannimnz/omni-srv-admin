# /notebooklm-bridge-safe-export

Gera relatório seguro de export do Obsidian.

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/obsidian_bundle_export.py \
  --vault /home/ubuntu/GitHub/obsidian-vault/ideaverse \
  --dry-run
```

Reportar:

- diretório da run;
- quantidade incluída;
- quantidade bloqueada;
- quantidade de possíveis secrets;
- se faz sentido considerar `--write` como próximo passo.

Não fazer upload para NotebookLM.
