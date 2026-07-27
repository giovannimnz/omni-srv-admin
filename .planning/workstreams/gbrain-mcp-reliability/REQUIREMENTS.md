# GBrain MCP Reliability Requirements

**Milestone:** GBrain/MCP Reliability Recovery
**Created:** 2026-07-27
**Status:** Planned

## Scope

Corrigir integralmente os achados da auditoria de 2026-07-27 sem degradar o vault, o MCP público, os outros workstreams ou os backups da frota. Obsidian é a fonte Markdown canônica; GBrain é índice derivado e verificável.

## Non-Negotiable Gates

- Backup PostgreSQL verificado e restore smoke PASS antes de qualquer sync/reindex/schema/embed/role mutation.
- Rclone exclusivamente pela fila serial da frota.
- Gate humano antes de token rotation, backup service cutover, sync live, reindex/extract live, contextual retrieval com custo, metadata update, embedding catch-up, schema migration e PostgreSQL hardening.
- Evidências nunca contêm secrets, Authorization headers, DB URLs completas, corpus text ou vetores.
- Cada operação mutável tem prestate, stop conditions, readback e rollback.

## Requirements

- [ ] **BKP-01** — Existe dump PostgreSQL custom-format do banco GBrain, com SHA-256, manifesto redigido e retenção definida.
- [ ] **BKP-02** — Restore smoke em banco descartável comprova que o dump restaura e que contagens críticas batem com a origem.
- [ ] **BKP-03** — Backup SRV-1 usa exclusivamente a fila serial da frota, sem rclone paralelo ou bypass local.
- [ ] **BKP-04** — Serviço de backup tem deadline, lock, estado terminal, alerta e recuperação determinística para jobs travados.
- [ ] **BKP-05** — Backup inclui config/runtime GBrain e dump PostgreSQL sem persistir credenciais em Git, logs, Obsidian ou GBrain.
- [ ] **SEC-01** — Logs do MCP não contêm bearer/admin tokens e usam modo 0600, rotação, retenção e redaction testada.
- [ ] **SEC-02** — Rotação/revogação de tokens preserva clientes autorizados e possui rollback por Vault, sem valor secreto em evidência.
- [ ] **SEC-03** — Arquivos internos do runtime têm menor privilégio e o serviço não amplia leitura/escrita além do usuário dedicado.
- [ ] **SYNC-01** — Wrapper GBrain é compatível com PgBouncer transaction mode; startup GUCs não quebram conexão e prepared statements permanecem coerentes.
- [ ] **SYNC-02** — Sync dry-run conclui sem escrita e produz envelope JSON, diff esperado, custo e stop conditions.
- [ ] **SYNC-03** — Sync live controlado atualiza o source default ao HEAD exato do vault e reconcilia falhas anteriores sem skip silencioso.
- [ ] **SYNC-04** — Freshness deriva do timestamp/commit real; doctor, source status e observabilidade concordam dentro da tolerância.
- [ ] **SYNC-05** — Automação reutiliza sync-vault.sh com lock único, timeout, failure counter e alerta; nenhum timer concorrente é criado.
- [ ] **SYNC-06** — As três migrations de host pendentes são aplicadas ou encerradas com decisão explícita e evidência.
- [ ] **GRAPH-01** — Link/timeline extraction possui baseline, batch limitado, retomada idempotente e relatório de falhas por página.
- [ ] **GRAPH-02** — Páginas stale/nunca extraídas são processadas até o target aprovado sem inventar links nem alterar Markdown fonte.
- [ ] **GRAPH-03** — Órfãos são classificados entre legítimos, taxonomia ausente e linkagem reparável; redução é mensurada por classe.
- [ ] **GRAPH-04** — Contextual retrieval é aplicado por lote com budget/rate lease, dead-letter e fallback por página.
- [ ] **GRAPH-05** — Reindex Markdown preserva slugs, source provenance, soft-delete e conteúdo canônico do vault.
- [ ] **EMB-01** — Contrato de embedding fixa provider, endpoint público, modelo embedding-gte-v1, 768 dimensões e signature canônica.
- [ ] **EMB-02** — Metadata histórica incorreta é reparada somente quando equivalência do espaço vetorial é provada; ambiguidades exigem reembed.
- [ ] **EMB-03** — Catch-up processa somente chunks ativos missing/stale, em batches limitados, retomáveis e sem misturar espaços vetoriais.
- [ ] **EMB-04** — Cobertura e denominadores distinguem páginas/chunks ativos de soft-deleted e convergem para o target aprovado.
- [ ] **EMB-05** — Busca semântica passa corpus de aceitação com recall, idioma PT-BR, latência, dimensões e provenance verificadas.
- [ ] **CTL-01** — list_skills/get_skill publicam o diretório canônico explicitamente, confinados ao path aprovado e sem capabilities falsas.
- [ ] **CTL-02** — Pack ativo existe no catálogo, lint explícito e implícito resolvem o mesmo SHA, e cache reload é validado.
- [ ] **CTL-03** — Warnings de aliases e schema graph vazio são corrigidos ou aceitos por ADR com impacto e owner explícitos.
- [ ] **CTL-04** — Taxonomia de 107 tipos é migrada/mapeada para tipos canônicos sem catch-all mascarar perda semântica.
- [ ] **CTL-05** — File plane, DB plane e runtime efetivo usam uma fonte canônica ou drift detector fail-closed; nenhuma URL loopback obsoleta permanece ativa.
- [ ] **CTL-06** — PostgreSQL resolve collation drift, role superuser/bypassrls e exposição do PgBouncer com backup, compatibilidade e rollback testados.
- [ ] **OBS-01** — Health/stats/doctor/MCP usam definições e denominadores versionados, reproduzíveis por SQL e sem divergências silenciosas.
- [ ] **OBS-02** — Disconnects e reranker failures têm causa, cardinalidade controlada, SLO, alerta e regression test.
- [ ] **OBS-03** — Runbooks, ADRs, incident, logs, Obsidian e GBrain ficam sincronizados, linkados, redigidos e verificáveis ponta a ponta.

## Traceability

| Requirement | Owner phase | Planned evidence |
|---|---:|---|
| BKP-01 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| BKP-02 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| BKP-03 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| BKP-04 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| BKP-05 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| SEC-01 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| SEC-02 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| SEC-03 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| SYNC-01 | 60 | `60-VERIFICATION.md` + requirement-specific receipt |
| SYNC-02 | 61 | `61-VERIFICATION.md` + requirement-specific receipt |
| SYNC-03 | 61 | `61-VERIFICATION.md` + requirement-specific receipt |
| SYNC-04 | 61 | `61-VERIFICATION.md` + requirement-specific receipt |
| SYNC-05 | 61 | `61-VERIFICATION.md` + requirement-specific receipt |
| SYNC-06 | 61 | `61-VERIFICATION.md` + requirement-specific receipt |
| GRAPH-01 | 62 | `62-VERIFICATION.md` + requirement-specific receipt |
| GRAPH-02 | 62 | `62-VERIFICATION.md` + requirement-specific receipt |
| GRAPH-03 | 62 | `62-VERIFICATION.md` + requirement-specific receipt |
| GRAPH-04 | 62 | `62-VERIFICATION.md` + requirement-specific receipt |
| GRAPH-05 | 62 | `62-VERIFICATION.md` + requirement-specific receipt |
| EMB-01 | 63 | `63-VERIFICATION.md` + requirement-specific receipt |
| EMB-02 | 63 | `63-VERIFICATION.md` + requirement-specific receipt |
| EMB-03 | 63 | `63-VERIFICATION.md` + requirement-specific receipt |
| EMB-04 | 63 | `63-VERIFICATION.md` + requirement-specific receipt |
| EMB-05 | 63 | `63-VERIFICATION.md` + requirement-specific receipt |
| CTL-01 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| CTL-02 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| CTL-03 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| CTL-04 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| CTL-05 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| CTL-06 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| OBS-01 | 64 | `64-VERIFICATION.md` + requirement-specific receipt |
| OBS-02 | 65 | `65-VERIFICATION.md` + requirement-specific receipt |
| OBS-03 | 65 | `65-VERIFICATION.md` + requirement-specific receipt |

## Coverage Contract

- Total requirements: 33.
- Cada requirement possui owner phase único.
- PLANs podem referenciar requirements de fases anteriores apenas para regressão; o owner permanece único.
- Closeout exige 33 PASS; BLOCK/UNKNOWN não é convertido em PASS por waiver implícito.
