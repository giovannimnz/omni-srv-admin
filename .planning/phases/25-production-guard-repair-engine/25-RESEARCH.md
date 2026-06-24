---
phase: 25
title: "Research - Production Guard Repair Engine"
date: 2026-06-24
status: complete
requirements:
  - PRG-06
  - PRG-10
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 25 Research

## Finding 1: Repair must depend on read-only truth

Repair without a trusted status baseline can make PM2 drift worse. Phase 25 must
load Phase 24 status/doctor output first and refuse apply when critical findings
exist.

## Finding 2: Safe actions are narrow

Candidate safe actions:

- Start a missing PM2 app from canonical ecosystem with exact `--only <app>`.
- Start a known PM2 stack from canonical ecosystem when all names are expected.
- Start exact known Podman containers.
- Start exact known systemd units that are explicitly allowlisted and documented
  as non-disruptive.

Unsafe without a separate gate:

- `pm2 kill`.
- PM2 daemon restarts.
- RDP/XRDP restarts.
- Apache remote mutation.
- Folder rename/move/symlink repair.
- Real webhook POST.
- `pm2 save` when health is not fully green.

## Finding 3: Audit is part of the product

The operator needs to know exactly what would happen before apply. Dry-run output
must include command preview, reason, risk, expected side effect and rollback note.

## Plan Implication

Implement a planner/apply split:

- `repair --dry-run --json`: always safe.
- `repair --apply --scope <scope> --target <target> --yes-i-understand-production-risk`: guarded.
- Audit file in a non-secret location with redaction enforced by tests.
