---
project: atius-router
version: 2
created: 2026-06-04
last_updated: 2026-06-11
generator: fork-sync manuals generate
---

# Manual de Atualização — atius-router

> Documento vivo. Cada sync/deploy/incidente relevante deve atualizar este manual.
> Versionado no git junto com `sync.yaml`. CLI regenera com `fork-sync manuals regen atius-router`.

## 1. Visão Geral

- **Projeto:** `atius-router`
- **Display name:** `Atius Router`
- **Estratégia de merge:** `theirs`
- **Deploy Docker:** sim

## 2. Upstreams

| # | Nome | URL | Role |
|---|------|-----|------|
| 1 | `Atius Router` | https://github.com/QuantumNous/new-api | primary |

## 3. Estratégia de Sync — Passo a Passo

1. **Estratégia:** `theirs`
2. Dry-run sempre antes; se o fork estiver sujo, criar checkpoint local antes do sync real
3. Merge real usa `--no-commit` + restauração dos `protected_paths`
4. Se restar conflito fora de `protected_paths`, o merge é abortado
5. **Deploy Docker:** rodar separadamente depois do sync

## 4. Paths Protegidos (rebrand)

Estes paths são preservados em conflito (nunca sobrescritos pelo upstream):

- `integration/middleware/`
- `Dockerfile.fast`
- `docker-compose.yml`
- `i18n/locales/pt.yaml`
- `i18n/i18n.go`
- `web/default/src/i18n/locales/*.json`
- `web/default/src/i18n/config.ts`
- `controller/codex_*.go`
- `service/codex_*.go`
- `relay/channel/codex/`
- `service/openaicompat/policy.go`
- `dto/channel_settings.go`
- `router/api-router.go`
- `web/default/src/features/channels/`
- `README.md`
- `README.en.md`
- `docs/`
- `.planning/`
- `VERSION`
- `web/default/public/logo.png`
- `web/default/public/favicon.ico`

## 5. Como Adaptar o Fork (Rebrand)

Documentar aqui as customizações que diferenciam este fork do upstream:

- **Identidade visual:** logos, cores, naming
- **Funcionalidades extras:** Codex OAuth/device/models + middleware
- **Configurações locais:** endpoints, paths
- **i18n:** traduções adicionadas

Para cada item, referenciar o path em `protected_paths` e dar contexto de POR QUE
essa customização existe (issue, ticket, decisão arquitetural).

Exemplo:
- `web/default/public/logo.png` — Logo do Atius, não usar o do new-api upstream
- `i18n/locales/pt.yaml` — Tradução PT-BR adicionada manualmente
- `controller/codex_*.go` — Fluxos do canal Codex fora do upstream

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
| 2 | 2026-06-11 | Paths protegidos realinhados com o fork atual e sync runner com preflight/checkpoint |

---

_Mantenha este manual sincronizado com `sync.yaml`. Se mudar a estratégia, regenere:_
```bash
fork-sync manuals regenerate atius-router
```
