# /notebooklm-bridge-maintenance

Roda checks seguros de manutenção do NotebookLM Obsidian bridge.

Comando padrão:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_maintenance.py
```

Flags opcionais:

- `--with-auth`: inclui auth check no profile NotebookLM isolado.
- `--check-fork-sync`: verifica o registro fork-sync em `omni-srv-admin`.

Não fazer upload de conteúdo real do vault neste comando.

Se auth estiver expirado e for pedido refresh, usar Camofox primário:

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
```

Chrome DevTools/CDP é fallback secundário e exige aprovação explícita.
