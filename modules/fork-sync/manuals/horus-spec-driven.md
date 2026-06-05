---
project: horus-spec-driven
version: v2.1.0
upstream: https://github.com/open-gsd/gsd-core
created: 2026-06-05
last_updated: 2026-06-05
---

# horus-spec-driven — Manual de Atualização

## Visão Geral

horus-spec-driven é um **wrapper multi-CLI** sobre o `open-gsd/gsd-core`. Ele:

1. Vendoria o gsd-core (shallow clone em `modules/gsd-core/`)
2. Aplica **rebrand** automático: `gsd-*` → `shd-*` (dev), `shq-*` (qa), `shp-*` (params)
3. Converte o conteúdo para formato nativo de cada runtime (5 content converters + 5 frontmatter converters)
4. Instala nos runtimes configurados (Hermes, Claude Code, Codex, Gemini CLI, GitHub Copilot)
5. Inclui **horus-sdk-adapter** — reimplementação completa do `gsd-tools.cjs` (90+ subcomandos) para Hermes

## Upstream

| Campo | Valor |
|---|---|
| **Upstream** | open-gsd/gsd-core |
| **URL** | https://github.com/open-gsd/gsd-core |
| **Branch** | main |
| **Último check** | 2026-06-05 |
| **Versão atual** | v1.3.1-dev |

## Estratégia Sync

O horus-spec-driven **não é um fork** — é um wrapper. O "sync" consiste em:

1. `git clone --depth 1 open-gsd/gsd-core modules/gsd-core/`
2. `node bin/install.js install --all --global` (rebrand + content converte + install)

Arquivos protegidos (NUNCA sobrescritos):

- `bin/lib/horus-sdk-adapter/` — implementação Hermes-native do gsd-tools.cjs
- `bin/lib/content-converters/` — 5 converters por runtime
- `bin/lib/frontmatter-converters/` — 5 converters de frontmatter
- `bin/lib/subagent-adapter/` — neutralização de subagent_type
- `bin/lib/layout.js` — kind-driven install layout
- `runtimes/` — specs de paths por CLI
- `horus-spec-driven.json` — configuração do usuário
- `bin/rebrand.js` — engine de rebrand (wordlist)
- `bin/install.js` — instalador
- `bin/sync.js` — auto-update
- `docs/` — documentação completa

## Paths Protegidos

| Path | Motivo |
|---|---|
| `bin/lib/horus-sdk-adapter/` | Core do adapter Hermes (não existe no upstream) |
| `bin/lib/content-converters/` | Adaptações runtime-specific |
| `bin/lib/frontmatter-converters/` | Formatação de header por runtime |
| `bin/lib/subagent-adapter/` | Neutralização de subagents Claude-centric |
| `bin/lib/layout.js` | Layout kind-driven portado do gsd-core |
| `runtimes/` | Specs de paths por CLI |
| `horus-spec-driven.json` | Config do usuário (runtimes, prefixos) |
| `bin/rebrand.js` | Engine de rebrand (wordlist) |
| `bin/install.js` | Pipeline install |
| `bin/sync.js` | Pipeline sync |
| `docs/` | Documentação (ARCHITECTURE, GSD-SDK-MAPPING, REBRAND, RUNTIMES, CONVERTERS) |
| `README.md`, `SETUP.md`, `CHANGELOG.md`, `LICENSE` | Documentação pública |

## Rebrand

O horus-spec-driven renomeia `gsd-*` → `shd-*` / `shq-*` / `shp-*` com wordlist dinâmica:

| Categoria | Prefixo | Substrings de gatilho | Exemplo |
|---|---|---|---|
| horus-spec-driven Development | `shd` | (default) | `gsd-new-project` → `shd-new-project` |
| horus-spec-driven QA | `shq` | validate, verify, audit, review, eval, secure, check | `gsd-validate-phase` → `shq-validate-phase` |
| horus-spec-driven Params | `shp` | config, settings, params, profile-user | `gsd-config` → `shp-config` |

## Breaking Changes (v2.0.0 → v2.1.0)

- **v2.0**: apenas rebrand de filename (incorreto para Hermes)
- **v2.1**: content converters + frontmatter converters + layout kind-driven + horus-sdk-adapter

## Troubleshooting

### "modules/gsd-core/ missing"

```bash
rm -rf modules/
node bin/install.js install --runtime=hermes --global
```

### Slash command não aparece após install

Reinicie o Hermes (cache de skills). Verifique `~/.hermes/skills/hsd/<name>/SKILL.md`.

### Referências a `gsd-tools` no body do skill

Essas referências são normais (mantidas para documentação). O `<horus_sdk_adapter>` no skill body instrui o agente a usar `node ~/.hermes/skills/hsd/horus-sdk-adapter/index.cjs`.

## Histórico

| Data | Ação | Versão | Status |
|---|---|---|---|
| 2026-06-05 | Reconstrução completa (wrapper + converters + adapter) | v2.1.0 | success |
| 2026-06-05 | v2.0 inicial (rebrand-only, deprecated) | v2.0.0 | deprecated |
| 2026-05 | Fork legacy do get-shit-done + caveman | v1.x | archived |
