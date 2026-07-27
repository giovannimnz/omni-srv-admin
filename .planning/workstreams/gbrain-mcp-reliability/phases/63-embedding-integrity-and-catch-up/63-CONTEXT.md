---
phase: 63-embedding-integrity-and-catch-up
created: 2026-07-27
requirements: [EMB-01, EMB-02, EMB-03, EMB-04, EMB-05]
---

# Phase 63 Context — Embedding Integrity and Catch-up

## Goal

Reconciliar provenance/signatures e completar embeddings 768d com quality gates.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: EMB-01, EMB-02, EMB-03, EMB-04, EMB-05.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
