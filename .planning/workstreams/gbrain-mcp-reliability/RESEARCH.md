# GBrain MCP Reliability Research

## Baseline

Audit source: Obsidian `60-LOGS/2026-07-27-gbrain-http-mcp-verificacao.md`.
Runtime: `gbrain 0.42.36.0`, Bun/TypeScript, PostgreSQL through PgBouncer, public MCP at `https://mcp.atius.com.br/gbrain`.
Embedding contract: `https://router.atius.com.br/v1`, `embedding-gte-v1`, 768 dimensions.

## Confirmed Implementation Surfaces

- `modules/srv1-ops/scripts/sync-vault.sh` already runs GBrain after successful vault Git reconciliation every five minutes. Fix this chain; do not add a second timer.
- `modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh` currently calls rclone directly and excludes PostgreSQL data.
- `modules/fleet-backup/scripts/rclone-fleet-queue.sh` is the required serial transport, but needs typed artifact jobs and stronger exit-code handling.
- `modules/srv1-ops/systemd/backup-srv1-daily.service` lacks a runtime deadline.
- Installed GBrain source injects `statement_timeout` and `idle_in_transaction_session_timeout` as startup parameters; the active PgBouncer rejects at least `statement_timeout`.
- GBrain supports `sync --dry-run`, `sync --no-embed`, `embed --stale --dry-run --catch-up`, schema inspection/mutation and MCP skills publication.
- `mcp.skills_dir` is file-plane supported and wins over autodetection.
- Existing repo docs are `docs/operations/codex-gbrain-obsidian-mcp.md` and `docs/operations/gbrain-embedding-migration.md`.

## Planning Decisions

1. Recovery foundation precedes corpus work.
2. Source truth precedes graph/context; graph/context precedes embeddings.
3. Metadata repair never asserts vector equivalence without provenance proof.
4. Schema/taxonomy and PostgreSQL privilege work happen after retrieval recovery to reduce simultaneous variables.
5. Runtime patches are not ad-hoc edits in global node_modules: use a version/hash-bound patch manager with byte backup and rollback.
6. All data-plane mutations use canary→readback→batch expansion, with explicit stop conditions.
7. All output artifacts are redacted and schema-versioned.

## Known Risks

- Restore drill may expose extension/collation/grant dependencies not visible in a dump-only check.
- Vault HEAD may advance during long reindex/embed runs; every batch must pin source generation.
- Orphan count cannot safely be forced to zero; legitimate roots and taxonomy gaps exist.
- Embedding metadata is historically inconsistent; dimension equality is insufficient evidence of semantic-space equality.
- Removing superuser/bypassrls may reveal undocumented DDL/maintenance dependencies.
- GBrain runtime upgrades may invalidate source hashes and must stop patch application.
