---
name: notebooklm-bridge-smoke
description: "Roda validação de auth NotebookLM e smoke test sintético descartável do bridge. Usar para validação sintética NotebookLM ou para /notebooklm-bridge-smoke."
---

# NotebookLM Bridge Smoke

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_auth_check.py --write-run
uv run python execution/nlm_smoke.py --synthetic --write-run
```

Se auth estiver expirado, refresh primário:

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

Chrome DevTools/CDP é fallback secundário e exige aprovação explícita.

Cleanup permitido somente para notebook criado pelo smoke:

```bash
uv run python execution/nlm_smoke.py --synthetic --write-run --cleanup
```

Reportar status do auth, diretório da run smoke, notebook id, resultado do marcador e status do cleanup.
