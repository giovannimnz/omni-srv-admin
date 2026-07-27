---
workstream: gbrain-mcp-reliability
reviewed_at: 2026-07-27T09:16:00-03:00
reviewer: MiniMax-M3 delegated read-only researcher
status: incorporated-with-corrections
source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_082934_393487.txt
---

# Revisão assíncrona — grafo, contextual retrieval e embeddings

## Veredito

Parecer útil, incorporado após confronto com a CLI e o source instalados do GBrain `0.42.36.0`. Nenhum comando live de reindex, extract ou embed foi executado durante a revisão.

## Aceito

- Smoke do endpoint deve provar HTTP 200 e 768 dimensões.
- `gbrain embed --all --dry-run` existe e entra no preflight.
- `gbrain extract all --source db --dry-run --json` e `gbrain reindex --markdown --dry-run --no-embed` são comandos reais.
- Contextual retrieval precisa fechar coverage e readback 5/5.
- Extraction lag, graph-signals coverage e entity link coverage passam a ter gates diagnósticos.
- Órfãos são reavaliados somente depois de extract/reindex/CR, com amostra de falsos órfãos.
- Metadata converge para model, dimensions e signature canônicos.
- Qualidade semântica usa corpus fixo versionado e comparação pré/pós.

## Corrigido

| Finding delegado | Correção |
|---|---|
| `missing_embeddings PASS se =557` | PASS é `0` no corpus ativo elegível. `557` é contagem embedded, não missing. |
| Signature resumida como `openai:gpt...:768` | Contrato: `openai:embedding-gte-v1:768`. |
| 3.942 missing vs auditoria 3.941 | Recalcular live; nenhum baseline stale vira gate. |
| Prefix stripping incerto | Source confirmou: `parseModelId()` separa provider/model e `resolveEmbeddingProvider()` envia `parsed.modelId` ao SDK. |

## Rejeitado

- Score universal de busca `>0.7`: escala depende de embedding/reranker e não é comparável sem baseline.
- Alvo absoluto `<200 órfãos`: incentiva edges cosméticos. Usa-se redução relativa + classificação.
- Colocar reavaliação de órfãos depois do embed: contradiz a própria dependência. Ordem mantida como sync → extract/reindex/CR → órfãos → embeddings.
- Confiar em `doctor` sem readback SQL/MCP/amostral.

## Evidência de source

- `src/core/ai/model-resolver.ts:35-55`: `openai:embedding-gte-v1` vira provider `openai` + model `embedding-gte-v1`.
- `src/core/ai/gateway.ts:1099-1110`: `resolveEmbeddingProvider()` retorna e instancia com `parsed.modelId`.
- `src/core/ai/gateway.ts:1128-1131`: o SDK recebe `modelId`, não o provider-prefixed string.
- `src/commands/reindex.ts:142-147`: `--markdown` é obrigatório.
- `src/commands/extract.ts:710-725`: `links|timeline|all`, `--dry-run` e sweep stale estão implementados.

## PLANs atualizados

- `62-02-PLAN.md`
- `62-03-PLAN.md`
- `62-VALIDATION.md`
- `63-01-PLAN.md`
- `63-03-PLAN.md`
- `63-VALIDATION.md`
