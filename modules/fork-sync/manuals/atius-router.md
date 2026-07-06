---
project: atius-router
version: 6
created: 2026-06-04
last_updated: 2026-07-05
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
- `relay/channel/minimax/`
- `relay/channel/deepseek/`
- `service/openaicompat/policy.go`
- `constant/channel.go`
- `common/endpoint_type.go`
- `common/endpoint_type_test.go`
- `dto/embedding.go`
- `dto/channel_settings.go`
- `router/api-router.go`
- `web/default/src/features/channels/`
- `web/default/scripts/sync-i18n.mjs`
- `web/classic/src/constants/channel.constants.js`
- `.dockerignore`
- `controller/model.go`
- `controller/model_list_test.go`
- `service/modelcatalog/`
- `tools/clianything.py`
- `tests/test_clianything.py`
- `README.md`
- `README.en.md`
- `docs/`
- `.planning/`
- `controller/misc.go`
- `setting/operation_setting/general_setting.go`
- `web/default/src/lib/docs-link.ts`
- `web/default/src/hooks/use-top-nav-links.ts`
- `web/default/src/components/layout/types.ts`
- `web/default/src/components/layout/components/nav-link-item.tsx`
- `web/default/src/components/layout/components/top-nav.tsx`
- `web/default/src/components/layout/components/public-header.tsx`
- `web/default/src/components/layout/components/public-navigation.tsx`
- `web/default/src/components/layout/components/mobile-drawer.tsx`
- `web/default/src/features/home/components/sections/hero.tsx`
- `web/default/src/components/layout/components/footer.tsx`
- `web/default/src/features/system-settings/general/quota-settings-section.tsx`
- `web/classic/src/helpers/docs.js`
- `web/classic/src/hooks/common/useNavigation.js`
- `web/classic/src/components/layout/headerbar/index.jsx`
- `web/classic/src/components/layout/headerbar/Navigation.jsx`
- `web/classic/src/pages/Home/index.jsx`
- `web/classic/src/components/layout/Footer.jsx`
- `web/classic/src/pages/Setting/Operation/SettingsGeneral.jsx`
- `docs/atius-router-docs/src/lib/i18n.ts`
- `docs/atius-router-docs/next.config.mjs`
- `docs/atius-router-docs/middleware.ts`
- `docs/atius-router-docs/src/app/json/route.ts`
- `docs/atius-router-docs/src/app/[lang]/layout.tsx`
- `docs/atius-router-docs/src/app/[lang]/(home)/layout.tsx`
- `docs/atius-router-docs/src/components/footer.tsx`
- `docs/atius-router-docs/content/docs/pt/guide/index.mdx`
- `docs/atius-router-docs/content/docs/pt/guide/meta.json`
- `docs/atius-router-docs/content/docs/pt/guide/project-introduction.mdx`
- `docs/atius-router-docs/content/docs/pt/guide/technical-architecture.mdx`
- `scripts/smoke-docs-links.sh`
- `VERSION`
- `web/default/public/logo.png`
- `web/default/public/favicon.ico`

## 5. Como Adaptar o Fork (Rebrand)

Documentar aqui as customizações que diferenciam este fork do upstream:

- **Identidade visual:** logos, cores, naming
- **Funcionalidades extras:** Codex OAuth/device/models, Codex embeddings compartilhando a credencial OAuth do channel 5, catalogo Go-native em `/v1/models`, MiniMax/DeepSeek consolidados em um canal ativo por provider, runtime `/v1/` full-Go e normalizacao de `base_url` com `/v1`
- **Configurações locais:** endpoints, paths
- **i18n:** traduções adicionadas

Para cada item, referenciar o path em `protected_paths` e dar contexto de POR QUE
essa customização existe (issue, ticket, decisão arquitetural).

Exemplo:
- `web/default/public/logo.png` — Logo do Atius, não usar o do new-api upstream
- `i18n/locales/pt.yaml` — Tradução PT-BR adicionada manualmente
- `controller/codex_*.go` — Fluxos do canal Codex fora do upstream
- `controller/model.go` / `service/modelcatalog/` — `/v1/models` Go-owned, sem `pricing_version` publico, com ordenacao deterministica por provider/versao/variante
- `relay/common/relay_utils.go` — normaliza `base_url` com slash final ou `/v1`, evitando `/v1/v1`
- `common/endpoint_type.go` / `relay/channel/minimax/` / `relay/channel/deepseek/` — MiniMax type=35 e DeepSeek type=43 roteiam OpenAI/Anthropic/embeddings automaticamente sem canais duplicados
- `web/default/src/lib/docs-link.ts` / `web/classic/src/helpers/docs.js` —
  botões `Docs` sempre same-origin e localizados: `/en/docs` em ingles e
  `/pt/docs` em portugues. Nao restaurar `https://docs.newapi.pro`.
- `controller/misc.go` — sanitiza `data.docs_link` em `/api/status`; valores
  vazios, `/docs` ou `https://docs.newapi.pro` voltam para `/en/docs`.
- `docs/atius-router-docs/src/app/json/route.ts` / `middleware.ts` — mantem
  `/docs.json`, `/docs/openapi.json`, `/json` e `/json/` como OpenAPI JSON
  local do docs app, sem depender do sidecar `model-detailed`.
- `docs/atius-router-docs/content/docs/pt/guide/*` — garante que os cards PT
  do guia nao gerem 404 em `/pt/docs/guide/project-introduction` e
  `/pt/docs/guide/technical-architecture`.
- `tools/clianything.py` — `phase19-apply` aplica consolidacao e `clone-keyed` bloqueia recriacao de split channels por padrao
- `.dockerignore` — Protege o build contra runtime data/logs/backups no worktree de producao

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

- Antes de sync real, ler `projects/atius-router/UPSTREAM-SYNC-GUARDS.md`.
- Se `/v1/models` voltar a depender de `model-detailed`, abortar o merge e restaurar `controller/model.go` + `service/modelcatalog/`.
- Se `pricing_version` aparecer no payload publico de `/v1/models`, abortar o merge e restaurar o contrato Go.
- Se `text-embedding-3-*` sair do channel 5 `OpenAI - Codex` para um canal OpenAI separado ativo, abortar o merge; a regra do fork e compartilhar a credencial OAuth do Codex.
- Se MiniMax ou DeepSeek voltarem a depender de canais ativos separados por protocolo (`*-OpenAI-Compatible`, `*-Anthropic-Compatible`, `*-Embeddings`), abortar o merge e restaurar a consolidacao Go-native.
- `429 insufficient_quota` em Codex embeddings depois de selecionar o channel 5 e quota/licenca upstream, nao necessariamente falha local de roteamento.
- Se `/v1/` voltar a apontar para `model-detailed`, `127.0.0.1:3300`, `127.0.0.1:3399` ou pod port `3001`, abortar o sync/deploy e restaurar o runtime full-Go.
- Se um provider `base_url=https://.../v1` gerar `/v1/v1/...`, restaurar `relay/common/relay_utils.go` e os testes de normalizacao.
- Se qualquer botão `Docs`, `/api/status.data.docs_link`, `/docs.json`,
  `/docs/openapi.json`, `/json` ou `/json/` voltar a apontar para
  `docs.newapi.pro` ou HTML do Go SPA, abortar o sync/deploy e restaurar os
  paths protegidos de Docs.

## 8. Histórico de Versões do Manual

| Versão | Data | Mudança |
|--------|------|---------|
| 1 | 2026-06-04 | Geração inicial via `fork-sync manuals generate` |
| 2 | 2026-06-11 | Paths protegidos realinhados com o fork atual e sync runner com preflight/checkpoint |
| 3 | 2026-06-18 | Guardas de sync para `/v1/models` Go-native, Codex embeddings no channel 5 e `.dockerignore` de runtime |
| 4 | 2026-06-18 | Guardas para consolidacao MiniMax/DeepSeek em canal unico, label `OpenAI - Codex` e CLIAnything anti-split |
| 5 | 2026-06-18 | Runtime `/v1/` full-Go definitivo, model-detailed retired e normalizacao de `base_url` com `/v1` |
| 6 | 2026-07-05 | Docs same-origin `/en/docs`/`/pt/docs`, sanitizer de `/api/status.docs_link`, OpenAPI JSON local e páginas PT protegidas |

---

_Mantenha este manual sincronizado com `sync.yaml`. Se mudar a estratégia, regenere:_
```bash
fork-sync manuals regenerate atius-router
```
