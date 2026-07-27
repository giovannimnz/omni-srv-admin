---
phase: 64-control-plane-schema-and-postgres
status: planned
nyquist: required
---

# Phase 64 Validation Strategy

## Test layers

1. Unit/fixture tests for every new parser, guard, patcher and state transition.
2. Dry-run against redacted snapshots/live read-only state.
3. Canary mutation only after preflight and explicit gate where required.
4. Readback against an independent surface (SQL, MCP, systemd, remote checksum or semantic query).
5. Rollback rehearsal before broad apply.
6. Phase verification maps every owned requirement to evidence.

## Gates comprovados da segunda revisão assíncrona

- Skills publication: `mcp.skills_dir` é lido no DB plane primeiro e no file plane como fallback; publicação live exige root user-owned, manifesto/realpath confinement, backup da config/unit, aprovação e restart com canary público.
- O tree bundled `/home/ubuntu/.bun/install/global/node_modules/gbrain/skills` tem 52 skills e `RESOLVER.md`, mas não é Git-tracked e pode ser substituído por upgrade; não é target durável.
- Schema lint: `schema_lint(pack='')` carrega o active `home-config`; `schema_lint(pack='gbrain-base-v2')` retorna `pack_not_found` no lookup nomeado. Ambos entram nos fixtures.
- Schema coverage 100% com catch-all não prova taxonomia canônica; exigir mapa old→canonical/alias/exception e amostragem.
- Configs atuais têm SHA idêntico, mas symlink/cópia cega é proibido sem ownership, atomic replace, upgrade behavior e rollback comprovados.
- PostgreSQL baseline a recalcular no gate: role superuser+bypassrls, 61 tabelas RLS, zero policies, collation catalog/runtime 2.35/2.39.
- Sequência no restore descartável: policies/role runtime antes de retirar bypass; `REINDEX` + ordering/search tests antes de `REFRESH COLLATION VERSION`.
- PgBouncer escuta múltiplas redes; nenhum bind é removido antes de inventário de consumidores autorizados.

## Stop conditions

- Backup/restore gate not PASS.
- Source HEAD/generation drift.
- Secret detected in output/artifact.
- Unknown/malformed evidence.
- Active/deleted denominator ambiguity.
- Error budget, cost cap or timeout exceeded.
- Rollback unavailable or untested.

## Required phase artifact

Create `64-VERIFICATION.md` with PASS/BLOCK/UNKNOWN per requirement, commands, evidence paths and residual risk. The phase cannot close on summary-only evidence.
