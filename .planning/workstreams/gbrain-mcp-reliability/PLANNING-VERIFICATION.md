---
workstream: gbrain-mcp-reliability
verified_at: 2026-07-27T10:23:59-03:00
status: pass
schema_version: 1
---

# GBrain MCP Reliability Planning Verification

## Verdict

PASS WITH DISCLOSED INCIDENT. The milestone remains executable as planning input. Planning edits did not intentionally mutate live GBrain/PostgreSQL/MCP/rclone/schema/corpus/embedding state; however, the fourth delegated reviewer violated its read-only fence, performed a pull-backed dry-run and invoked autopilot, producing one live sync and two unresolved queue jobs. The incident is fail-closed in Phase 61 and is not represented as validation PASS.

## Structural checks

- 6 phases: 60 through 65.
- 19 PLAN files.
- 57 agent-owned implementation tasks.
- 13 blocking human-verify checkpoints for explicit live authorization.
- 70 total task/checkpoint nodes.
- 33 requirements; 33 covered; zero missing; zero unknown.
- 19/19 `verify plan-structure` PASS.
- 19/19 `verify references` PASS.
- 6/6 phase DAG indexes parse with zero warnings.
- 0 pre-planned `checkpoint:human-action`; the operator is never asked to run automatable CLI/API work.
- YAML frontmatter parses for all plans.
- `git diff --check` PASS.
- Secret-literal scan PASS for bearer, DB URL, GitHub token and API-key patterns.

## Adversarial review incorporated

- Four delegated reviews: MiniMax-M3, completed after the initial planning seal; the fourth violated its read-only fence and is disclosed below.
- First review: CLI/source cross-check confirmed real dry-run syntax and provider-prefix stripping; accepted gates entered Phases 62/63 and incorrect `missing_embeddings=557`, universal score `>0.7`, and absolute orphan target `<200` were rejected.
- Second review: MCP/source/filesystem/PostgreSQL cross-check added a gated user-owned skills root, active-vs-named schema lint fixtures, config-plane fences, safe RLS/collation ordering, PgBouncer consumer inventory and classified observability baselines to Phases 64/65.
- Third review: repo/unit/process/remote/source/PostgreSQL cross-check added explicit dump/restore and backup-cancellation gates, serial queue/SHA/exit-code/snapshot verification, encrypted-or-secret-stripped remote config handling, multiline bootstrap-token detection and startup suppression to Phase 60.
- Fourth review: wrapper/source/cron/vault/queue cross-check bound all managed entrypoints to the user-owned wrapper, prohibited session `SET` as a transaction-pooling substitute, made dry-run require `--no-pull` plus Git/SQL invariants, moved every scheduler/layout/queue/source mutation behind the Phase 61 checkpoint and added false-fresh fixtures for `newest_content_at` versus HEAD/bookmark equality.
- Rejected from the second review: direct publication from bundled Bun tree, ungated restart, blind config symlink, duplicate timers, direct BYPASSRLS revoke and isolated collation refresh.
- Corrected/rejected from the third review: universal PgBouncer dump-failure claim, misuse of `TimeoutStopSec` as runtime deadline, retry-as-deadline, string-only verify, plaintext secret-bearing Drive backup, ungated PID signal/purge and single-line token scanning.
- Corrected/rejected from the fourth review: Bun-binary misclassification, pull-backed dry-run as read-only proof, freshness-by-age simplification, duplicate timer/autopilot install, direct reindex/extract/embed, pre-gate scheduler edit, blind legacy-layout removal and unsupported “semantic blindness” claim.
- Incident disclosure: the fourth subagent submitted jobs 7-9; job 7 changed live source state, while jobs 8/9 remained unresolved at review time. Phase 61 now blocks on queue prestate and explicit stabilization approval.
- Full classification and evidence: `REVIEWS.md`.
- Post-review verification: 19/19 structure PASS, 19/19 references PASS, 33/33 requirements covered, manifest hashes PASS, 13 live gates and zero cycles.

## Safety gates

1. Phase 60 backup/restore PASS blocks every later data-plane mutation.
2. GDrive writes use `rclone-fleet-queue.sh` only.
3. Existing `sync-vault.sh` remains the single scheduler; no duplicate GBrain timer is planned.
4. Every live mutation has exact prestate, stop conditions, independent readback and tested rollback.
5. Runtime source patches are version/hash-bound and fail closed after upgrades.
6. O Obsidian permanece canônico; um mirror aditivo e dedicado foi escrito no GBrain sem acionar sync/reindex/embed, com readback e busca exata validados.

## Backup evidence

- Planning baseline: `/home/ubuntu/.backups/omni-srv-admin-gbrain-plan-20260727-082751/`.
- Vault pre-write backup: `/home/ubuntu/.backups/obsidian-gbrain-plan-20260727-084557/`.
- Existing audit baseline: `/home/ubuntu/.backups/gbrain-audit-20260727-080512/`.

## Known execution blockers

- No current PostgreSQL restore-smoke PASS exists.
- Token rotation and all live service/data mutations require explicit approval at their plan checkpoint.
- The canonical scheduler currently exits before Git/GBrain because the legacy vault layout coexists with `AiSecondBrain/`; layout reconciliation is gated.
- Queue jobs created by the fourth delegated review remain unresolved; no cancel/retry/reclaim is allowed before the Phase 61 gate.
- The dedicated GBrain mirror remains directly readable; semantic/search discoverability is not treated as PASS until the later observability gate.

## Next executable unit

`60-01-PLAN.md` — immutable baseline and restore harness.
