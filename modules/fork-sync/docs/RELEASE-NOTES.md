# Release Notes PT-BR — fork-sync

> Documentação do módulo `core/release_notes.py` e comandos `fork-sync release`.

## Problema original

Releases do nosso fork eram pobres:

- **Upstream** (ex: `iOfficeAI/AionUi v2.1.10`): release doc completa — Highlights,
  ACP Session Reliability, Clearer Error Messages, Bug Fixes, Under the Hood,
  What's Changed, Contributors, Assets
- **Nosso fork** (`giovannimnz/AionUi v2.1.10-rf2`): uma linha —
  "Sync release based on upstream vv2.1.10. Generated automatically by fork-sync"

Resultado: histórico de releases do fork inútil pra auditoria, changelog e
comunicação de mudanças.

## Solução

Módulo `core/release_notes.py` faz:

1. **Busca** release v{version} do upstream via `gh api` (incluindo body + assets + autor)
2. **Parseia** estrutura: detecta `##` e `###` headings, classifica em:
   - Destaques (highlights, com sub-seções virando prefixo)
   - Correções de Bugs
   - Nos Bastidores (under the hood)
   - O Que Mudou (compare com tag anterior, via API)
   - Contribuidores (autores dos commits)
   - Binários e Artefatos (assets com tamanho e link)
   - Mudanças Específicas deste Fork (arquivos divergentes)
3. **Traduz** prosa pra PT-BR via `deep-translator` (GoogleTranslator)
   - Cache em `.translate-cache/` (hash sha256)
   - Fallback gracioso: mantém inglês se tradução falhar
4. **Adiciona** marca d'água do fork:
   - Link pro upstream + fork
   - Tag + data de sincronização
   - Atribuição ao fork-sync
5. **Mescla** com mudanças locais do fork (se houver)

## Comandos

```bash
# Gerar release notes (mostra no terminal, sem salvar)
fork-sync release preview aionui --upstream-version 2.1.10

# Gerar release notes (com summary JSON, salvar local)
fork-sync release generate aionui --upstream-version 2.1.10 --rf 2 --save-local

# Sem tradução (inglês original)
fork-sync release generate aionui --upstream-version 2.1.10 --no-translate

# Com arquivos alterados do fork
fork-sync release generate aionui --upstream-version 2.1.10 \
    --changed-files src/rebrand/file.ts \
    --changed-files README.md

# Listar releases geradas localmente
fork-sync release list aionui
```

## Saída

Estrutura PT-BR (sempre canônica):

```markdown
# v2.1.10-rf2

Esta é uma versão de estabilidade e confiabilidade focada em...

## Destaques
- **Confiabilidade da sessão ACP** — Os modelos agora permanecem...
- **Mensagens de erro mais claras** — Erros de workspace path agora mostram...

## Correções de Bugs
- A configuração "perto da bandeja" agora é salva corretamente...

## Nos Bastidores
- Falhas de inicialização do backend agora reportam diagnósticos...

## O Que Mudou
- `01e0271` fix(desktop): persist close-to-tray setting (#3150) — @kaizhou-lab
- `79e8fa4` chore(docs): update WeChat group QR code to wx-10 — @IceyLiu
- ...

## Contribuidores
Agradecimentos aos contribuidores do upstream nesta release:
- @IceyLiu
- @kaizhou-lab
- @piorpua

## Binários e Artefatos
Binários compilados do upstream (rebuild opcional via `fork-sync deploy`):
- [AionUi-2.1.10-linux-amd64.deb](...) — 218 MB
- [AionUi-2.1.10-linux-arm64.deb](...) — 163 MB
- ...

---

🔗 **Upstream original:** https://github.com/iOfficeAI/AionUi
📦 **Repositório fork:** https://github.com/giovannimnz/AionUi
🏷️ **Tag:** `v2.1.10-rf2` • **Sincronizado em:** 2026-06-04
🤖 **Gerado automaticamente por:** [fork-sync](https://github.com/giovannimnz/fork-sync)
```

## Integração com `bin/create-release.sh`

O script bash legado foi refatorado para chamar `fork-sync release generate --json`
e extrair o campo `body` via `jq` (ou Python fallback). Zero duplicação de lógica.

```bash
# Fluxo end-to-end (automático via cron ou manual)
bin/sync.sh aionui ~/GitHub/forks/AionUi
#   ↓
# 1. sync.sh detecta nova release upstream
# 2. merge + commit
# 3. create-release.sh → fork-sync release generate → cria tag + release no GitHub
```

## Cache de tradução

- Localização: `.translate-cache/<sha256>.txt`
- Hit: pula chamada de rede
- Miss: traduz e cacheia
- Limpar: `rm -rf .translate-cache/` (forçar re-traduzir)

## Tradutor: GoogleTranslator (deep-translator)

- Default em `core/release_notes.py`
- Custo: zero (Google Translate free tier)
- Qualidade: aceitável pra release notes (termos técnicos repetem)
- Limite: 4500 chars por request (chunking automático)

**Alternativas** (opt-in):
- `m2m100` — modelo local, sem rede (precisa `pip install transformers torch`)
- LLM (OpenAI/MiniMax) — melhor qualidade, custo $$$ — implementar via
  `_translate_text` substituindo o default

## Heurística de tag anterior

```python
def _prev_version_hint(version: str) -> str:
    """v2.1.10 → v2.1.9, v3.0.0 → v2.0.0 (rollover minor)."""
```

Usado pelo `compare API` pra listar commits entre tags. Se a heurística
errar (upstream pulou versões), usuário pode passar `--upstream-version`
explícito ou editar `sync.yaml` com campo `release.previous_version`.

## Configuração no `sync.yaml` (futuro)

```yaml
release:
  translate: true           # default
  translator: google        # google | m2m100 | openai | minimax
  custom_sections:          # adicionar seções próprias
    - title: "Customizações Atius"
      include_glob: ["**/atius-*", "i18n/locales/pt-BR.*"]
  omit_sections:            # remover seções upstream (raro)
    - contributors
```

(v1.3+ — schema v2)

## Estrutura de arquivos

```
fork-sync/
├── manuals/
│   └── <projeto>/
│       ├── <projeto>.md                 # manual geral
│       └── releases/                    # release notes geradas
│           ├── v2.1.10-rf2.md
│           ├── v2.1.11-rf1.md
│           └── ...
├── .translate-cache/                    # cache de tradução (gitignored)
└── cli/fork_sync/core/release_notes.py  # módulo principal
```

## Testes manuais

```bash
# 1. Release real do upstream
fork-sync release generate aionui --upstream-version 2.1.10 --rf 2

# 2. Release hipotética (sem upstream response)
# (só funciona se você tem um v3.0.0-rc1 simulado)

# 3. Comparação: sem tradução
fork-sync release generate aionui --upstream-version 2.1.10 --rf 2 --no-translate

# 4. Com fork changes
fork-sync release generate atius-router --upstream-version v2.11.1 --rf 1 \
    --changed-files web/default/public/logo.png \
    --changed-files i18n/locales/pt-BR.yaml
```

## Limitações conhecidas

- **Sub-seções upstream viram prefixo de bullet:** "**ACP Session Reliability** — text..."
  Funciona pra release notes curtos; pra docs muito longos pode ficar estranho.
- **Sem tradução de tabelas:** tabelas markdown em upstream passam em inglês.
- **Assets .sha256 listados:** polui um pouco. Filtro futuro: só binários principais.
- **Heurística de tag anterior pode falhar:** se upstream pula versão
  (v2.1.10 → v2.2.0), a heurística vira v2.1.10 → v2.1.9 (errado).
  Solução: `previous_version` no sync.yaml (futuro).
