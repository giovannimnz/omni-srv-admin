# Contribuindo

Obrigado por considerar contribuir com `fork-sync`!

## Princípios

1. **Zero secrets no repo** — ler [`SECRETS.md`](SECRETS.md) antes de qualquer coisa
2. **Config é código** — adicionar fork = adicionar `projects/<name>/sync.yaml`
3. **Bash não desaparece** — backward compat 100% com scripts legados
4. **PT-BR primeiro** — docs e mensagens em português (código/paths em inglês)

## Como contribuir

### Reportar bug
Abrir issue em https://github.com/giovannimnz/fork-sync/issues com:
- Comando exato que falhou
- Output completo (`fork-sync --json ... | jq` ajuda)
- Versão (`fork-sync version`)
- SO e versão Python

### Adicionar novo fork (projeto)
1. Criar branch: `git checkout -b feat/add-<nome>-fork`
2. Criar `projects/<nome>/sync.yaml` (use [`templates/basic.yaml`](templates/basic.yaml))
3. (Opcional) `projects/<nome>/deploy.yaml` se for Docker
4. (Opcional) `projects/<nome>/.gitmodules` se usar submodules
5. Atualizar tabela de "Projetos atualmente configurados" no README
6. `fork-sync projects show <nome>` deve listar sem erro
7. `fork-sync sync <nome> --dry-run` deve rodar
8. PR com descrição curta

### Adicionar comando CLI
1. Editar `cli/fork_sync/cli.py` (adicionar @cli.command ou subgrupo)
2. Manter backward compat com bash scripts
3. Adicionar ao REPL em `cli/fork_sync/core/repl.py` se for user-facing
4. Adicionar entrada no `fork-sync --help`
5. Testar `fork-sync --json <comando>` retorna JSON válido
6. Atualizar README seção "Uso Rápido"

### Adicionar template
1. Criar `templates/<nome>.yaml` com sync.yaml de exemplo
2. Documentar no README seção "Adicionar Novo Fork"

## Antes do PR

```bash
# 1. Rodar auditoria de secrets
gitleaks detect --source . --verbose

# 2. Testar CLI
fork-sync projects list
fork-sync version

# 3. Verificar YAML de todos os projetos
for p in projects/*/sync.yaml; do python3 -c "import yaml; yaml.safe_load(open('$p'))" && echo "OK: $p" || echo "FAIL: $p"; done

# 4. Testar imports
cd cli && python3 -c "from fork_sync.cli import main; main(['--help'])"
```

## Estilo de código

- **Python:** PEP 8 + type hints. Usar `ruff` se disponível.
- **YAML:** 2 espaços de indentação, kebab-case em nomes de projeto, snake_case em chaves.
- **Bash:** `shellcheck` clean. `set -euo pipefail` no topo.
- **Mensagens de commit:** convenção `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.

## Releases

Maintainer (Giovanni) corta releases seguindo [SemVer](https://semver.org/):
- `MAJOR` (1.x → 2.x) — breaking change no schema `sync.yaml` ou na CLI
- `MINOR` (1.0 → 1.1) — novo comando/projeto, backward compat
- `PATCH` (1.0.0 → 1.0.1) — bugfix, docs

Cada release atualiza `VERSIONS.md`.
