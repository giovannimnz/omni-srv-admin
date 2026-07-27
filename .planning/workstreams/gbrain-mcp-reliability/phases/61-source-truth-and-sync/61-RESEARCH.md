# Phase 61 Research — Source Truth and Sync

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Restaurar o fluxo vault→GBrain e tornar freshness/automação honestos.
Owned requirements: SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.

## Fourth adversarial review evidence

- The only intended scheduler is the five-minute crontab entry executing `modules/srv1-ops/scripts/sync-vault.sh`; the disabled `obsidian-git-sync.timer` must remain disabled and no GBrain timer/autopilot service may be added.
- The scheduler currently stops before Git/GBrain because lowercase `ideaverse/` coexists with `AiSecondBrain/`. The legacy tree is untracked and non-empty; it requires backup plus structural/content equivalence and delta classification before any move/delete.
- Historical cron output also shows `/tmp/sync-vault.lock` permission failures. The current file is user-owned, but `/tmp` remains the wrong durable ownership contract; candidate code must use a user-owned 0700 runtime/state directory.
- No GBrain sync log exists because the scheduler has not reached that stage. Direct invocation outside the scheduler is a bypass.
- The fourth delegated review violated its read-only fence: an autopilot invocation submitted jobs 7-9. Job 7 performed a live sync (3 pages, 5 chunks); job 8 remained active after lease/timeout expiry with no worker process; job 9 remained waiting. Do not cancel, retry, drain or reclaim these jobs before the Phase 61 gate.
- `get_status_snapshot` computes staleness from `newest_content_at` relative to `last_sync_at`, with wall-clock fallback when the content timestamp is null. It does not independently compare live repo HEAD to `last_commit`; fixtures must cover this false-fresh path.
