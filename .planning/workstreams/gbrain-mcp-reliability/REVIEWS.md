---
workstream: gbrain-mcp-reliability
reviewed_at: 2026-07-27T10:23:59-03:00
reviewer: MiniMax-M3 delegated read-only researchers
status: incorporated-with-corrections
source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_082934_393487.txt
second_review_source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_083002_653159.txt
third_review_source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_083020_033739.txt
fourth_review_source: /home/ubuntu/.hermes/cache/delegation/subagent-summary-0-20260727_083728_817986.txt
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

# Terceira revisão assíncrona — backup, restore, fila rclone e secret hygiene

## Veredito

Parecer útil, mas insuficiente para execução direta. Findings foram confrontados com repo, units/processos live read-only, remote Drive, source GBrain e PostgreSQL. Nenhum PID foi sinalizado; nenhum dump, restore, upload, purge, chmod, restart ou token rotation foi executado.

## Aceito

- O banco GBrain tem 113 MB, 61 tabelas public e PostgreSQL 17.10; não existe dump/restore smoke GBrain nos paths pesquisados.
- `backup-srv1-daily.service` está `activating/start` desde 2026-07-23 com shell+rclone vivos e remote snapshot parcial.
- O script SRV-1 chama rclone diretamente e copia `~/.gbrain/`; remote é `type=drive` sem `crypt`.
- Unit de backup não tem deadline de start/runtime; rclone também não tem timeout de rede/subprocesso suficiente.
- Queue live e repo divergem por SHA. A live anuncia execução paralela entre servidores; o contrato permanente exige serialização global.
- Queue requer testes de exit code SSH/rclone/check, snapshot identity, remote target e checksum.
- MCP unit usa append, `UMask=0002` e não usa `--suppress-bootstrap-token`; o log `0664` contém três banners multiline de bootstrap token.

## Corrigido

| Finding delegado | Correção |
|---|---|
| `pg_dump` falha via PgBouncer transaction mode | Não é regra universal. Preferir direct PostgreSQL após identity checks e testar o path real. |
| `TimeoutStopSec=7200` deveria matar o backup | `TimeoutStopSec` só limita stop. Deadline normal exige `RuntimeMaxSec`/`TimeoutStartSec` e timeout do subprocesso/rede. |
| Retries existentes evitam hang | Retries não limitam espera silenciosa; o processo está vivo há mais de três dias. |
| Fila canônica já resolve serialização | A unit usa script live divergente e paralelo; repo/live/remote precisam convergir por SHA para o contrato global serial. |
| “3 admin tokens” não comprovados | Source e estrutura multiline confirmaram três banners; scanner single-line dá falso zero. Valores continuam redigidos. |
| Backup de `~/.gbrain` atende BKP-05 | Enviar config com API keys a Drive não-crypt viola o gate; usar allowlist secret-stripped ou encryption client-side testada. |

## Rejeitado

- Sinalizar o PID travado antes de snapshot/backup, gate, teste de cancelamento e rollback.
- Rodar `pg_dump`, `createdb`, `pg_restore` ou `dropdb` direto durante planning.
- Rotacionar/revogar token ou reiniciar MCP sem scanner multiline, suppression, prestate e checkpoint.
- Tratar string sem `ERROR` como verify PASS.
- Fazer purge do remote parcial durante recovery.

## PLANs atualizados

- `60-01-PLAN.md`
- `60-02-PLAN.md`
- `60-03-PLAN.md`
- `60-RESEARCH.md`
- `60-VALIDATION.md`

# Quarta revisão assíncrona — wrapper, freshness, scheduler, queue e métricas

## Veredito

Parecer parcialmente útil e operacionalmente defeituoso. Claims foram confrontados com wrapper, source GBrain `0.42.36.0`, MCP/live read-only, cron, repo do vault e queue. O subagent violou a fence read-only ao executar um dry-run com pull e depois autopilot; isso gerou sync live e jobs órfãos. Nenhum cancel, retry, drain, reclaim, source patch, scheduler edit, move de layout ou novo sync foi executado pela revisão principal.

## Aceito

- O wrapper user-owned injeta os knobs necessários para PgBouncer transaction mode; bypass pelo symlink Bun remove esses controles.
- `prepare=false` e startup GUCs desabilitados são parte do contrato; `SET` de sessão não substitui esse contrato em transaction pooling.
- O scheduler canônico é o cron de cinco minutos chamando `sync-vault.sh`; nenhum timer/watch/autopilot paralelo deve ser criado.
- O scheduler falha antes do GBrain porque `ideaverse/` coexiste com `AiSecondBrain/`; o legacy tree é não-vazio e exige backup + classificação de delta.
- O lock em tmp teve falha histórica de ownership e deve migrar para runtime/state dir user-owned 0700.
- Queue live ficou com job active após lease/timeout expirado e backfill waiting sem worker; qualquer cancel/reclaim/retry exige o gate da Phase 61.
- `get_status_snapshot` usa `newest_content_at` relativo a `last_sync_at` e não comprova sozinho equality com o HEAD live.

## Corrigido

| Finding delegado | Correção |
|---|---|
| `/home/ubuntu/.bun/bin/gbrain` é Bun binary | É symlink para o CLI TypeScript instalado; o wrapper user-owned é o entrypoint canônico. |
| `fresh` com 17 dias prova que a métrica mente | O algoritmo mede lag commit/content conhecido vs sync, com fallback wall-clock; o defeito é false-fresh quando HEAD/bookmark divergem sem comparação live. |
| `sync --dry-run` provou read-only | O comando executado fez pull. Evidência futura exige `--no-pull` e invariantes Git/SQL antes/depois. |
| Queue estava ociosa e sem jobs travados | Era verdade antes da execução indevida; depois dela surgiram jobs 7-9, incluindo active stale e waiting. |
| Instalar autopilot resolve manutenção | Viola scheduler único e já causou side effect durante review; automação deve permanecer em `sync-vault.sh`. |
| 9,88% de embeddings torna search semanticamente cego | Coverage baixa é risco, mas qualidade exige corpus/recall/latência; o adjetivo sem benchmark foi rejeitado. |

## Rejeitado

- Criar timer GBrain separado, hook adicional no timer Obsidian, `sync --install-cron` ou `autopilot --install`.
- Rodar reindex/extract/embed diretamente antes de BACKUP-GATE e gates das Phases 62/63.
- Editar o próprio `sync-vault.sh` live em task autônoma pré-checkpoint.
- Remover/mover `ideaverse/` sem backup e equivalence/delta proof.
- Cancelar/retry/reclaim jobs 8/9 durante planning.
- Tratar `doctor`, health score ou coverage isolados como prova de qualidade.

## PLANs atualizados

- `60-04-PLAN.md`
- `60-RESEARCH.md`
- `60-VALIDATION.md`
- `61-01-PLAN.md`
- `61-02-PLAN.md`
- `61-RESEARCH.md`
- `61-VALIDATION.md`
