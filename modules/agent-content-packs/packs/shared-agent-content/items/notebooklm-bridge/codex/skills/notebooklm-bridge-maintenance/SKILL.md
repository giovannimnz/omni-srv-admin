---
name: notebooklm-bridge-maintenance
description: "Roda checks seguros de manutenção do NotebookLM Obsidian bridge sem upload de conteúdo real do vault. Usar para /notebooklm-bridge-maintenance, release-readiness local, auth dry-run, export dry-run e verificação fork-sync."
---

# NotebookLM Bridge Maintenance

## Padrão Seguro

Rodar a partir da raiz do repo:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_maintenance.py
```

Esse comando roda testes locais, lint, typecheck e exporter dry-run. Ele pula auth NotebookLM e fork-sync, salvo pedido explícito por flag.

## Checks Opcionais

Checar auth somente quando a sessão atual permitir verificar o profile NotebookLM isolado:

```bash
uv run python execution/nlm_maintenance.py --with-auth
```

Verificar registro fork-sync em `omni-srv-admin` sem alterar nada:

```bash
uv run python execution/nlm_maintenance.py --check-fork-sync
```

Rodar ambos:

```bash
uv run python execution/nlm_maintenance.py --with-auth --check-fork-sync
```

## Regras de Segurança

- Não passar flags de E2E upload aqui; esta skill é somente manutenção.
- Tratar falha em `auth_check` como profile isolado expirado. Refresh primário: `uv run --with rookiepy==0.5.6 python execution/nlm_camofox_auth.py refresh-from-firefox`.
- Não usar Chrome DevTools/CDP salvo aprovação explícita.
- Tratar falha em `fork_sync_registration` como sinal de drift; inspecionar antes de editar `omni-srv-admin`.
- Reportar diretório da run gerada e nomes dos checks com falha.
