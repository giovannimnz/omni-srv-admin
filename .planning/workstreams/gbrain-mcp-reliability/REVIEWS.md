---
workstream: gbrain-mcp-reliability
reviewed_at: 2026-07-27T09:34:14-03:00
reviewer: MiniMax-M3 delegated read-only researchers
status: incorporated-with-corrections
source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_082934_393487.txt
second_review_source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_083002_653159.txt
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

# Segunda revisão assíncrona — MCP skills, schema, config, PostgreSQL e observabilidade

## Veredito

Parecer parcialmente útil. Mudanças incorporadas somente após confronto com MCP live, source do GBrain `0.42.36.0`, filesystem e PostgreSQL read-only. Nenhuma config, role, policy, collation, bind, serviço ou timer foi mutado.

## Aceito

- `mcp.skills_dir` tem precedência DB-plane → file-plane e `gbrain config set` é comando suportado.
- `list_skills` está bloqueado sem root remoto explícito; `mcp.publish_skills=true` sozinho gera banner otimista.
- Pack ativo é `home-config`; lint implícito retorna 59 warnings e schema graph retorna 15 nodes/0 edges.
- Configs file-plane atuais são byte-idênticas, mas continuam duas superfícies operacionais.
- Role `gbrain` é superuser+bypassrls; 61 tabelas têm RLS, zero policies; collation diverge 2.35/2.39.
- PgBouncer está em transaction mode e escuta loopback mais redes privadas; requer matriz de consumidores antes de hardening.
- Log MCP está `0664` e contém seis linhas com keywords sensíveis; hardening permanece na Phase 60.
- Métricas de disconnect/reranker precisam de classificação e baseline antes de SLO/alerta.

## Corrigido

| Finding delegado | Correção |
|---|---|
| Publicar direto do tree global Bun | Criar root user-owned, estável e versionável; bundled tree não é Git-tracked e muda em upgrade. |
| `schema_lint(pack='gbrain-base-v2')` gera 59 warnings | Essa chamada retorna `pack_not_found`; o lint do active pack usa `pack=''`. |
| 100% schema coverage prova convergência | Catch-all torna coverage cosmética; exigir mapa e amostragem canônica. |
| `REFRESH COLLATION VERSION` resolve mismatch | Ensaiar `REINDEX` e testes de ordering/search antes de refresh. |
| Revogar BYPASSRLS diretamente | Com 61 tabelas RLS e zero policies, criar estratégia/policies e role runtime antes. |
| Restringir PgBouncer a loopback | Inventariar consumidores de todos os binds antes de qualquer remoção. |
| 124/24h e 518/7d como thresholds | São baselines de investigação; thresholds vêm depois da classificação. |

## Rejeitado

- Restart do MCP sem gate explícito e rollback.
- Symlink cego entre as duas config homes.
- Quatro timers separados de sync/extract/reindex/embed; contradiz scheduler único da Phase 61.
- Alegação de “3 admin tokens em claro”: scanner redigido confirmou keywords sensíveis, não valores/tipos suficientes para essa conclusão.
- Alterar RLS, roles, collation ou binds durante planejamento.

## PLANs atualizados

- `64-01-PLAN.md`
- `64-02-PLAN.md`
- `64-03-PLAN.md`
- `64-04-PLAN.md`
- `64-VALIDATION.md`
- `65-01-PLAN.md`
- `65-VALIDATION.md`
