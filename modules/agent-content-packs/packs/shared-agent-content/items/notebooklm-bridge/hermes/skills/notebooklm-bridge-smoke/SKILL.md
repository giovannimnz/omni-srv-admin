---
name: notebooklm-bridge-smoke
description: "Slash command Hermes /notebooklm-bridge-smoke para auth NotebookLM e smoke test sintético descartável."
triggers: [/notebooklm-bridge-smoke]
---

# /notebooklm-bridge-smoke

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

Rodar cleanup somente em notebooks criados pelo smoke.
