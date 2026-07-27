# GBrain MCP Reliability Recovery Plan

Status: planned and structurally verified on 2026-07-27. No live correction has been applied.

## Canonical planning surfaces

- Workstream: `.planning/workstreams/gbrain-mcp-reliability/`
- Requirements: `.planning/workstreams/gbrain-mcp-reliability/REQUIREMENTS.md`
- Roadmap: `.planning/workstreams/gbrain-mcp-reliability/ROADMAP.md`
- Research: `.planning/workstreams/gbrain-mcp-reliability/RESEARCH.md`
- State: `.planning/workstreams/gbrain-mcp-reliability/STATE.md`
- Verification: `.planning/workstreams/gbrain-mcp-reliability/PLANNING-VERIFICATION.md`
- Audit source: Obsidian `60-LOGS/2026-07-27-gbrain-http-mcp-verificacao.md`

## Delivery sequence

| Phase | Purpose | Plans | Live gate |
|---:|---|---:|---|
| 60 | Restore foundation, serial backup, secret hygiene, PgBouncer runtime | 4 | backup cutover, token rotation, wrapper switch |
| 61 | Sync contract, truthful freshness, source convergence | 2 | controlled sync |
| 62 | Reindex, extraction, orphan classification, contextual retrieval | 3 | corpus writes and provider cost |
| 63 | Embedding contract, metadata reconciliation, catch-up | 3 | metadata writes and provider cost |
| 64 | Skills, schema, taxonomy, config planes, PostgreSQL hardening | 4 | schema and database mutation |
| 65 | Failure root cause, E2E acceptance, documentation closeout | 3 | disposable E2E writes |

Strict order: 60 → 61 → 62 → 63 → 64 → 65.

## Non-negotiable rules

- A restorable PostgreSQL dump gates every corpus/schema/embedding mutation.
- GDrive traffic goes through the fleet queue, one job at a time across hosts.
- `sync-vault.sh` remains the only scheduler.
- No secret, database URL, raw vector or corpus payload enters Git, planning evidence, Obsidian or GBrain documentation.
- An operation that cannot prove rollback does not run.
- “100% operational” is only valid after all 33 requirements and Phase 65 E2E acceptance are PASS.

## Resume

Execute Phase 60 Plan 01 first. Do not start from embeddings: the source and backup foundation must be corrected before derived indexes.
