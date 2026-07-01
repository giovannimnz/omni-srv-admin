---
phase: 31-omni-fleet-collectors-and-desired-state-profiles
plan: 02
status: complete
completed_at: 2026-06-25
requirements_addressed:
  - GOV-04
  - GOV-05
---

# Phase 31 / Plan 31-02 — Summary

Added desired-state profile foundation:

- `modules/fleet-control-plane/migrations/0004_governance_profiles.sql`
- `cli/omni/fleet_governance.py`
- `omni fleet profiles managed-apps`

The initial profile seed is `modules/managed-apps/configs/programs.json`, covering managed programs, repositories, policies and customizations.

Update execution remains gated through the existing `TbUpdatePlans`, `queue-update` and local agent approval model. No generic SSH apply path was added.

Tests were added but not run in this pass.

