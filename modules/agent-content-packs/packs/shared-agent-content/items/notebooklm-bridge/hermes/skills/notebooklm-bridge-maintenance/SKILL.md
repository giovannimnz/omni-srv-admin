---
name: notebooklm-bridge-maintenance
description: "Roda checks seguros de manutenção do NotebookLM Obsidian bridge sem upload de conteúdo real do vault. Usar para /notebooklm-bridge-maintenance, release-readiness local, auth dry-run, exporter dry-run e verificação fork-sync."
---

# NotebookLM Bridge Maintenance

Rodar a partir da raiz do repo:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_maintenance.py
```

Checks live opcionais:

```bash
uv run python execution/nlm_maintenance.py --with-auth
uv run python execution/nlm_maintenance.py --check-fork-sync
uv run python execution/nlm_maintenance.py --with-auth --check-fork-sync
```

Regras:

- Sem upload NotebookLM neste comando.
- Camofox/Hermes é o navegador primário para refresh/auth.
- Chrome DevTools/CDP é fallback secundário e exige aprovação explícita.
- Reportar diretório da run e nomes dos checks com falha.
