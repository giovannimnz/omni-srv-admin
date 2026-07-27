---
phase: 60-recovery-foundation
status: planned
nyquist: required
---

# Phase 60 Validation Strategy

## Test layers

1. Unit/fixture tests for every new parser, guard, patcher and state transition.
2. Dry-run against redacted snapshots/live read-only state.
3. Canary mutation only after preflight and explicit gate where required.
4. Readback against an independent surface (SQL, MCP, systemd, remote checksum or semantic query).
5. Rollback rehearsal before broad apply.
6. Phase verification maps every owned requirement to evidence.

## Third adversarial review gates

- First `pg_dump` + restore-smoke is a live mutation gate: exact source identity, PostgreSQL major, local 0700 destination, unique marked target, timeout, free space, checksum, cleanup and rollback must be approved before execution.
- Backup recovery/deploy is a separate live gate: preserve local logs and remote partial snapshot; no purge; capture process tree and SHA of repo/live/remote scripts; test signal escalation, queue, unit and rollback before cancelling PID or running `systemctl`.
- `TimeoutStopSec` is not accepted as a normal runtime deadline. Require `RuntimeMaxSec`/`TimeoutStartSec` and subprocess/network timeout fixtures.
- Queue PASS requires global serialization across the fleet, exact snapshot identity, nonzero SSH/rclone/check propagation, remote target existence and checksum. Any deployed-vs-repo SHA drift blocks apply.
- GBrain config containing API keys must not be copied plaintext to plain `type=drive`; use secret-stripped allowlist or tested client-side encryption.
- Secret scanner PASS requires multiline bootstrap-token fixture; service PASS requires `--suppress-bootstrap-token`, `UMask=0077`, mode 0600/journald and restart scan.

## Stop conditions

- Backup/restore gate not PASS.
- Live PostgreSQL source/target identity or pg tool major unresolved.
- Restore target lacks harness marker or cleanup proof.
- Backup process/remote partial snapshot not preserved before cancel and not reconciled.
- Managed CLI entrypoint bypasses the user-owned wrapper or source hashes/version drift.
- Sync dry-run lacks `--no-pull` or changes Git/SQL prestate.
- Queue repo/live/remote SHA drift or cross-server parallel mode.
- SSH/rclone/check exit code, snapshot identity or checksum unproven.
- Plaintext secret-bearing config selected for plain Drive remote.
- Bootstrap token suppression or multiline redaction test absent.
- Source HEAD/generation drift.
- Secret detected in output/artifact.
- Unknown/malformed evidence.
- Active/deleted denominator ambiguity.
- Error budget, cost cap or timeout exceeded.
- Rollback unavailable or untested.

## Required phase artifact

Create `60-VERIFICATION.md` with PASS/BLOCK/UNKNOWN per requirement, commands, evidence paths and residual risk. The phase cannot close on summary-only evidence.
