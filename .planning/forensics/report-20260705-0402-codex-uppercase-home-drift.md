# Forensic Report

**Generated:** 2026-07-05T04:02:00-03:00
**Problem:** `atius-srv-1` had an unexpected uppercase `~/.Codex` directory. The canonical Codex runtime root must be `~/.codex`.

---

## Evidence Summary

### Remote Host State

- Host: `atius-srv-1.atius.internal`
- User home: `/home/ubuntu`
- Canonical root: `~/.codex`
- Stray root before fix: `~/.Codex`
- `~/.Codex` top-level entries before fix: `gsd-core` only
- `~/.Codex/gsd-core`: symlink to `/home/ubuntu/.codex/gsd-core`
- Files physically under `~/.Codex`: `0`
- Backup before removal: `/home/ubuntu/.codex/backups/uppercase-Codex-cleanup-20260705T040047-0300`

### Timeline Evidence

- `~/.Codex/gsd-core` symlink ctime/mtime: 2026-06-14 15:29:29 -0300
- `~/.Codex` parent ctime/mtime: 2026-06-24 18:31:37 -0300
- `~/.codex/gsd-install-state.json` records migration activity at 2026-06-14T18:29:09Z:
  - `2026-06-02-rename-get-shit-done-to-gsd-core`
  - `2026-06-09-prune-stale-pristine-get-shit-done`
- Shell history contained a later manual `cd .Codex`, but no command proving creation.

### Active References

- Before fix, active global docs referenced `~/.Codex/gsd-core`:
  - `~/.codex/AGENTS.md`
  - `~/.codex/CODEX.md`
- Historical project artifacts still contain archived `~/.Codex/get-shit-done` references and should be treated as stale unless intentionally preserving history.

## Anomalies Checked

### Uppercase Runtime Root Drift - Confidence HIGH

**Evidence:** `~/.Codex` existed while the canonical runtime state and install manifests lived under `~/.codex`.

**Interpretation:** The uppercase path was a compatibility/remnant path, not an active runtime root.

### Duplicate Runtime Content - Confidence LOW

**Evidence:** `~/.Codex` had zero physical files and only a symlink to `~/.codex/gsd-core`.

**Interpretation:** No unique content needed migration.

### Stale Instruction Drift - Confidence HIGH

**Evidence:** `~/.codex/AGENTS.md` and `~/.codex/CODEX.md` referenced `$HOME/.Codex/gsd-core`.

**Interpretation:** Active instructions could have caused future commands to depend on or recreate the forbidden uppercase path.

### Missing Artifact / Migration Drift - Confidence MEDIUM

**Evidence:** GSD install state shows `get-shit-done` to `gsd-core` migrations on 2026-06-14, while older notes and phase artifacts still mention `~/.Codex/get-shit-done`.

**Interpretation:** The issue likely came from legacy mixed-case docs during the migration, not from a currently useful alternate install.

### Crash / Interruption - Confidence LOW

**Evidence:** No unique files were abandoned under `~/.Codex`; canonical `~/.codex/gsd-core` remained present after cleanup.

**Interpretation:** This was not a partial interrupted install requiring recovery from `~/.Codex`.

## Fix Applied

1. Backed up the uppercase directory and active global docs.
2. Replaced active `$HOME/.Codex/gsd-core` references in `~/.codex/AGENTS.md` and `~/.codex/CODEX.md` with `$HOME/.codex/gsd-core`.
3. Removed `~/.Codex` only after verifying it contained exactly one symlink entry: `gsd-core -> /home/ubuntu/.codex/gsd-core`.
4. Wrote durable records:
   - Obsidian: `AiSecondBrain/61-Incidents/2026-07-05-codex-uppercase-home-drift.md`
   - GBrain slug: `aisecondbrain/61-incidents/2026-07-05-codex-uppercase-home-drift`

## Validation

- `test ! -e ~/.Codex`: PASS
- `test -d ~/.codex/gsd-core`: PASS
- Active global docs grep for `.Codex`: no matches
- `node ~/.codex/gsd-core/bin/gsd-tools.cjs graphify status`: `stale=false`, `commit_stale=false`
- GBrain `get` for incident slug: PASS
- Obsidian file exists on the authoritative `atius-srv-1` vault filesystem: PASS

## Root Cause Hypothesis

The most likely root cause is legacy mixed-case GSD/Codex documentation and migration residue from the `get-shit-done` to `gsd-core` transition around 2026-06-14. The uppercase directory was a symlink wrapper pointing back to the canonical lowercase runtime, not an independent install.

## Recommended Actions

1. Do not recreate `~/.Codex`.
2. Use `$CODEX_HOME:-$HOME/.codex` and `~/.codex/gsd-core` for all active commands.
3. Treat old `~/.Codex/get-shit-done` references in archived phase artifacts as historical.
4. When editing current runbooks, replace any remaining active `~/.Codex` references with `~/.codex`.

---

*Report generated via `$gsd-forensics` flow. Existing local dirty worktree state was left untouched except for this new report file.*
