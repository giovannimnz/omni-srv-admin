---
gsd_state_version: 1.0
workstream: gbrain-mcp-reliability
milestone: v2.0
milestone_name: GBrain MCP Reliability Recovery
current_phase: 60
current_phase_name: recovery-foundation
status: planned
last_updated: "2026-07-27T08:52:00-03:00"
last_activity: 2026-07-27
last_activity_desc: Full correction milestone planned and structurally verified; no live repair executed
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 19
  completed_plans: 0
  percent: 0
---

# Project State

## Current Position

Phase: 60 — Recovery Foundation
Plan: 60-01 is next
Status: PLANNED and structurally verified; execution begins with the agent-owned read-only/backup harness, while declared live mutations remain checkpoint-gated

## Core Value

GBrain remains a derived, recoverable knowledge index for the canonical Obsidian vault, with truthful health, least privilege, serial backups and no secret leakage.

## Decisions

- Workstream is isolated under `.planning/workstreams/gbrain-mcp-reliability/`.
- Execution is strict serial by phase: 60→61→62→63→64→65.
- Existing `sync-vault.sh` remains the only scheduler; no competing GBrain timer will be created.
- Existing `rclone-fleet-queue.sh` remains the only GDrive transport.
- `gbrain 0.42.36.0` is the installed runtime; unrelated npm `gbrain@1.3.1` must not replace it.
- Runtime source patches, if still required, are hash-bound, backed up and upgrade-fail-closed.
- “100%” may only be declared after 33 requirements and E2E acceptance are PASS.

## Blockers

- No verified PostgreSQL restore evidence yet.
- Sync live, corpus recovery, embeddings, schema and PostgreSQL changes remain unapproved live mutations.
- Token rotation requires an explicit owner gate.

## Session Continuity

Last session: 2026-07-27
Stopped at: Planning and checker complete; Phase 60 Plan 01 is the next executable unit.
Resume file: None
