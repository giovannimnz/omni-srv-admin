---
phase: 61-source-truth-and-sync
created: 2026-07-27
requirements: [SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06]
---

# Phase 61 Context — Source Truth and Sync

## Goal

Restaurar o fluxo vault→GBrain e tornar freshness/automação honestos.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
