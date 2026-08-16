---
name: notebooklm-obsidian-bridge
description: "Opera o NotebookLM Obsidian bridge local com segurança: auth checks, smoke sintético, extração read-only, export dry-run do Obsidian, uploads controlados e validação."
allowed-tools:
  - Read
  - Bash
---

# NotebookLM Obsidian Bridge

Usar esta skill ao trabalhar em `/home/ubuntu/GitHub/notebooklm-obsidian-bridge` ou quando Giovanni pedir algo sobre a ponte NotebookLM/Obsidian.

## Regras

- Responder em PT-BR, salvo pedido em outro idioma.
- Manter auth isolado com `NOTEBOOKLM_HOME=/home/ubuntu/.local/state/notebooklm-obsidian-bridge/notebooklm-home`.
- Usar Camofox/Hermes como navegador primário para refresh/auth; Chrome DevTools/CDP é fallback secundário com aprovação explícita.
- Nunca expor ou commitar cookies NotebookLM, tokens, `storage_state.json`, `credentials.json`, `.env`, dumps HAR ou exports brutos de auth.
- Preferir comandos dry-run e read-only.
- Não fazer upload de conteúdo real do vault para NotebookLM sem aprovação explícita na sessão atual.

## Checks Padrão

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run pytest
uv run ruff check .
uv run mypy .
uv run python execution/obsidian_bundle_export.py --dry-run
```

## Auth

```bash
uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox
uv run python execution/nlm_auth_check.py --write-run
```

## Smoke Sintético

```bash
uv run python execution/nlm_smoke.py --synthetic --write-run
```

Cleanup somente para notebooks criados pelo comando smoke:

```bash
uv run python execution/nlm_smoke.py --synthetic --write-run --cleanup
```

## Extração Read-Only

```bash
uv run python execution/nlm_extract.py \
  --notebook-id 9d8f951a-ea64-44c0-bb60-294a5104dd90 \
  --read-only \
  --learning-loop \
  --write-vault-summary
```

## Relatório

Sempre reportar:

- checks executados e pass/fail;
- diretório da run para NotebookLM/export;
- se o trabalho tocou dados reais do NotebookLM;
- se o hard-gate de upload continua fechado.
