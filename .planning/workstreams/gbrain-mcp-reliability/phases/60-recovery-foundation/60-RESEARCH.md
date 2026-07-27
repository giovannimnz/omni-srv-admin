# Phase 60 Research — Recovery Foundation

See `../../RESEARCH.md` for the shared baseline.

## Phase-specific surfaces

Goal: Backups restauráveis, fila serial, secret hygiene e conectividade PgBouncer antes de qualquer mutação de corpus.
Owned requirements: BKP-01, BKP-02, BKP-03, BKP-04, BKP-05, SEC-01, SEC-02, SEC-03, SYNC-01.

The executor must re-read live state before mutation; this research is planning evidence, not live authority. Use repo-managed scripts and tests first. If installed GBrain source must change, require exact version/hash and preserve a byte-identical backup outside Git.

## Third adversarial review baseline — 2026-07-27

Read-only probes confirmed:

- Database `gbrain`: PostgreSQL 17.10, 113 MB, 61 public tables; no GBrain dump/restore artifact found in the searched repo and backup paths.
- `backup-srv1-daily.service`: `activating/start` since 2026-07-23; `TimeoutStartSec=infinity`, `RuntimeMaxSec=infinity`, `TimeoutStopSec=2h`. `TimeoutStopSec` does not bound normal start runtime.
- Live process tree: backup shell plus `rclone copy` sleeping for more than three days; remote partial snapshot exists. Preserve it and never purge during recovery.
- Current SRV-1 backup calls `rclone copy`, `lsf` and `purge` directly and copies `~/.gbrain/`; the configured remote is plain `type=drive`, no rclone `crypt` remote exists.
- The active queue script `/home/ubuntu/scripts/rclone-fleet-queue.sh` differs by SHA from the repo script. The live script advertises parallel cross-server execution, which violates the standing serial-fleet contract.
- Queue defects requiring fixtures: SSH exit code must be captured before another command; `rclone check` nonzero must fail regardless of output text; snapshot id must reach the backup script/remote/verify target unchanged; deployed bytes must match approved SHA.
- MCP service uses shell append, `UMask=0002`, and omits `--suppress-bootstrap-token`. GBrain source prints bootstrap token across a label plus two value lines unless suppression is enabled. The existing log has three such multiline banners and mode `0664`; scanners must be multiline-aware and never emit values.

Corrections to delegated claims:

- Do not claim `pg_dump` universally fails through transaction-mode PgBouncer. Prefer direct PostgreSQL for isolation after identity checks, and test the actual command path.
- `TimeoutStopSec=7200` is not a runtime deadline for a oneshot still starting. Use `RuntimeMaxSec`/`TimeoutStartSec` plus subprocess/network timeouts.
- `--retries` counts do not solve a silent stall without a deadline.
- A successful string match is not verification; command exit code, target identity and checksum are mandatory.
