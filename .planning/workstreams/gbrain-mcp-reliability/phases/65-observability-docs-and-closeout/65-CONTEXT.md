---
phase: 65-observability-docs-and-closeout
created: 2026-07-27
requirements: [OBS-02, OBS-03]
---

# Phase 65 Context — Observability, Docs and Closeout

## Goal

Fechar causas de falha, regressão MCP, documentação e aceite integral.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: OBS-02, OBS-03.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
