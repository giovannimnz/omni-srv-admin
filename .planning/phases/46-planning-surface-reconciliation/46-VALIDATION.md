# Phase 46 Validation - Planning Surface Reconciliation

## Automated Gates

1. `gsd-tools query validate.health` returns `healthy` with zero errors and zero warnings.
2. `gsd-tools query stats.json` reports milestone v1.8 and Phase 47 as the current open phase after Phase 46 completion.
3. `gsd-tools query roadmap.analyze` returns Phases 46-50 in numeric order and recognizes their plans.
4. `config.json` parses and emits no unknown-key warning.
5. Every requirement in v1.8 appears exactly once in traceability and no requirement is unmapped.
6. Every phase directory is represented in ROADMAP as canonical, historical or superseded.
7. Every active Phase 46-50 has a PLAN and VALIDATION file.
8. `git diff --check` and merge-marker scans pass.

## Stop Conditions

- Any rename would break historical paths referenced by commits, docs or knowledge stores.
- Phase status cannot be supported by a summary, live evidence or an explicit superseded classification.
- A concurrent session changes one of the six planning source files during reconciliation.

## Rollback

Restore the six planning files from
`C:\Users\muniz\.codex\backups\omni-planning-reorder-20260712T0500` and remove
only the newly created Phase 46-50 directories after verifying their resolved
paths are inside `.planning/phases`.

## Evidence

- before/after health and stats JSON
- phase-directory inventory
- requirements coverage count
- final diff review
- Obsidian and GBrain checkpoint
