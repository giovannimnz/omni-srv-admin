---
project: hermes-os
version: 1
created: 2026-06-04
last_updated: 2026-06-04
generator: fork-sync manuals generate
---

# Manual de Atualização — hermes-os

> Documento vivo. Cada sync/deploy/incidente relevante deve atualizar este manual.
> Versionado no git junto com `sync.yaml`. CLI regenera com `fork-sync manuals regen hermes-os`.

## 1. Visão Geral

- **Projeto:** `hermes-os`
- **Display name:** `hermes-os`
- **Estratégia de merge:** `merge`
- **Deploy Docker:** não

## 2. Upstreams

| # | Nome | URL | Role |
|---|------|-----|------|
| 1 | `hermes-os` | https://github.com/fathah/hermes-desktop | primary |

## 3. Estratégia de Sync — Passo a Passo

1. **Estratégia:** `merge`
2. Merge padrão do git, com `protected_paths` preservando rebrand

## 4. Paths Protegidos (rebrand)

Estes paths são preservados em conflito (nunca sobrescritos pelo upstream):

- `README.md`
- `package.json`

## 5. Como Adaptar o Fork (Rebrand)

Documentar aqui as customizações que diferenciam este fork do upstream:

- **Identidade visual:** logos, cores, naming
- **Funcionalidades extras:** patches próprios
- **Configurações locais:** endpoints, paths
- **i18n:** traduções adicionadas

Para cada item, referenciar o path em `protected_paths` e dar contexto de POR QUE
essa customização existe (issue, ticket, decisão arquitetural).

Exemplo:
- `web/default/public/logo.png` — Logo do Atius, não usar o do new-api upstream
- `i18n/locales/pt-BR.yaml` — Tradução PT-BR adicionada manualmente

Se adicionar rebrand:
1. Adicionar path em `protected_paths` no `sync.yaml`
2. Documentar aqui com justificativa
3. Incrementar `version:` no frontmatter deste manual

## 6. Como Reagir a Breaking Changes do Upstream

1. **Verificar release notes do upstream:**
   ```bash
   gh release list --repo <UPSTREAM_URL>
   ```
2. **Comparar últimos N commits:**
   ```bash
   git fetch upstream
   git log --oneline upstream/<branch> -20
   ```
3. **Rodar sync em dry-run:**
   ```bash
   fork-sync sync <PROJETO> --dry-run
   ```
4. **Aplicar mudanças de rebrand (se necessário):**
   - Editar paths protegidos
   - Atualizar este manual (incrementar `version:` no frontmatter)
5. **Sync real:**
   ```bash
   fork-sync sync <PROJETO>
   ```
6. **Validar:**
   - Rodar testes do projeto (se existirem)
   - Verificar rebrand visualmente
   - Commit + push

## 7. Troubleshooting Específico

_Documentar aqui problemas recorrentes deste fork._

## 8. Histórico de Versões do Manual

| Versão | Data | Mudança |
|--------|------|---------|
| 1 | 2026-06-04 | Geração inicial via `fork-sync manuals generate` |

---

_Mantenha este manual sincronizado com `sync.yaml`. Se mudar a estratégia, regenere:_
```bash
fork-sync manuals regenerate hermes-os
```
