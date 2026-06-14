---
project: notebooklm-py
version: 1
created: 2026-06-14
last_updated: 2026-06-14
owner_module: omni-srv-admin/modules/fork-sync
---

# Manual de Atualização — notebooklm-py

## 1. Objetivo

`notebooklm-py` é o fork real de `teng-lin/notebooklm-py` usado pelo
`notebooklm-obsidian-bridge`. O bridge é standalone; este módulo gerencia sync
com upstream, política de versão, release notes e validações depois de merges.

## 2. Source of Truth

| Item | Path |
|---|---|
| Config do projeto | `projects/notebooklm-py/sync.yaml` |
| Fork local | `/home/ubuntu/GitHub/forks/notebooklm-py` |
| Bridge dependente | `/home/ubuntu/GitHub/notebooklm-obsidian-bridge` |
| Upstream | `https://github.com/teng-lin/notebooklm-py.git` |
| Fork GitHub | `https://github.com/giovannimnz/notebooklm-py` |

## 3. Rotina Automática

O PM2 daily sync chama:

```bash
fork-sync sync-all --apply
```

`sync-all --apply` sempre roda dry-run antes e só aplica projetos seguros:

- sem dirty files;
- sem conflitos fora de `protected_paths`;
- sem protected paths obsoletos;
- com `can_apply: true`.

Para validar manualmente sem aplicar:

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync notebooklm-py --dry-run
```

Para aplicar somente quando o dry-run estiver seguro:

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync sync-all --apply
```

## 4. Versionamento

O `sync.yaml` usa:

```yaml
version_scheme:
  suffix: "-rf"
  tag_template: "v{upstream_version}{suffix}{counter}"
  counter_dir: "~/.fork-sync/{project}/versions/{upstream_version}"
```

Quando o upstream não publicar tag semântica no fluxo local, o dry-run expõe
`upstream_version` como prefixo do SHA upstream. Para release notes locais:

```bash
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync release generate notebooklm-py \
  --upstream-version <versao-ou-sha> \
  --save-local
```

Depois de um sync relevante, registrar o histórico do manual:

```bash
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync manuals record-sync notebooklm-py \
  --status success \
  --version <tag-ou-sha> \
  --notes "sync upstream validado pelo bridge"
```

## 5. Validações Pós-Sync

Depois de um merge real, `post_sync` roda no bridge:

```bash
uv run pytest
uv run ruff check .
uv run mypy .
uv run python execution/obsidian_bundle_export.py --dry-run
uv run python execution/nlm_maintenance.py --skip-local-checks --skip-export --check-fork-sync
```

Esses comandos não fazem upload real, não abrem navegador e não renovam auth.
Falha em qualquer check deixa o resultado do sync como erro operacional, mesmo
que o merge Git já tenha sido aplicado.

## 6. Guardrails

- Não adicionar cookies, tokens, `storage_state.json`, HAR ou `.env` ao fork.
- Não configurar upload NotebookLM no `post_sync`.
- Não colocar paths em `protected_paths` antes de eles existirem no fork.
- Resolver conflitos fora de `protected_paths` manualmente; o motor não deve
  mascarar divergência de código.
- Manter decisões do bridge documentadas no vault Obsidian, não no fork upstream.

## 7. Estado em 2026-06-14

Dry-run real:

| Campo | Valor |
|---|---|
| Branch | `main` |
| Ahead | `0` |
| Behind | `2` |
| Dirty files | `[]` |
| Protected paths | `[]` |
| Can apply | `true` |

O merge real não foi aplicado durante a criação deste manual; o PM2 daily sync
ou um operador pode aplicar com `sync-all --apply` quando desejar executar o
ciclo de update.
