# /notebooklm-bridge-smoke

Roda somente o smoke test sintético do NotebookLM.

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

Cleanup só pode rodar quando o ID do notebook criado pelo smoke for conhecido:

```bash
uv run python execution/nlm_smoke.py --synthetic --write-run --cleanup
```

Reportar:

- status do auth;
- diretório da run smoke;
- notebook id criado;
- `marker_found` true/false;
- status do cleanup, se solicitado.
