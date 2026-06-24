---
phase: 25
title: "Validation - Production Guard Repair Engine"
date: 2026-06-24
status: planned
requirements:
  - PRG-06
  - PRG-10
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 25 Validation

## Ordered Automated Battery

1. `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
2. `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "repair or audit or forbidden"`
3. `! rg -n "pm2 kill|systemctl (restart|stop) xrdp|xrdp-sesman|curl .*POST|requests\\.post|urllib.*POST" modules/srv1-ops/scripts cli/omni`
4. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard repair --dry-run --json`
5. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
6. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
7. `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
8. `$gsd-verify-work 25`

## Non-Negotiable Failures

- Dry-run executes commands.
- Apply can run without scope, target, explicit risk flag and snapshot.
- Any code path permits `pm2 kill`, RDP/XRDP restart, Apache mutation or webhook POST.
- Repair writes secrets to JSON, audit logs or docs.
