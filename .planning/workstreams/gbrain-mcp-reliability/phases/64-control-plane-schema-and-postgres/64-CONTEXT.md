---
phase: 64-control-plane-schema-and-postgres
created: 2026-07-27
requirements: [CTL-01, CTL-02, CTL-03, CTL-04, CTL-05, CTL-06, OBS-01]
---

# Phase 64 Context — Control Plane, Schema and PostgreSQL

## Goal

Corrigir skills, schema, config planes, métricas e menor privilégio PostgreSQL.

## Locked Decisions

- Obsidian remains canonical; GBrain is derived.
- Preserve all unrelated services and workstreams.
- Backup-first, redacted evidence, canary-first and rollback are mandatory.
- Any plan with `autonomous: false` contains a live mutation/cost/security gate and requires explicit owner authorization at execution time.
- No duplicate scheduler or rclone bypass may be introduced.

## Scope Fence

This phase owns only: CTL-01, CTL-02, CTL-03, CTL-04, CTL-05, CTL-06, OBS-01.
Later-phase work must not be pulled forward merely because tooling is adjacent.

## Evidence Contract

Every receipt records timestamp, host, runtime version, source HEAD/generation, command class, redacted result, invariant checks and rollback state. Values matching credential patterns are forbidden.
