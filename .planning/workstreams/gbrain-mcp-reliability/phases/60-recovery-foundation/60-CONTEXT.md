---
phase: 60-recovery-foundation
created: 2026-07-27
requirements: [BKP-01, BKP-02, BKP-03, BKP-04, BKP-05, SEC-01, SEC-02, SEC-03, SYNC-01]
---

# Phase 60 Context — Recovery Foundation

## Goal

Backups restauráveis, fila serial, secret hygiene e conectividade PgBouncer antes de qualquer mutação de corpus.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: BKP-01, BKP-02, BKP-03, BKP-04, BKP-05, SEC-01, SEC-02, SEC-03, SYNC-01.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
