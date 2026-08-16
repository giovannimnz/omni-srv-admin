# /notebooklm-bridge-camofox-refresh

Renova a sessão NotebookLM pelo navegador primário Camofox/Hermes.

Rodar:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
uv run python execution/nlm_auth_check.py --write-run
```

Se o Firefox local não tiver sessão válida:

```bash
uv run python execution/nlm_camofox_auth.py prepare
# abrir a URL noVNC retornada pelo prepare
uv run python execution/nlm_camofox_auth.py import-state
uv run python execution/nlm_auth_check.py --write-run
```

Reportar:

- diretório da run Camofox;
- diretório da run `auth-check`;
- `status`, `token_fetch`;
- confirmação de que Chrome DevTools não foi usado e nenhum upload real foi feito.
