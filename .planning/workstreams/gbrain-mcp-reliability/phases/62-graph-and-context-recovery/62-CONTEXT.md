---
phase: 62-graph-and-context-recovery
created: 2026-07-27
requirements: [GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05]
---

# Phase 62 Context — Graph and Context Recovery

## Goal

Reindexar conteúdo com preservação, extrair links/timeline e recuperar contextual retrieval.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
