# 25-01 Summary: Production Guard repair planner/apply gate

- started_at: 2026-06-24T00:00:00Z
- completed_at: 2026-06-24T17:39:06Z
- status: complete
- plan_files:
  - modules/srv1-ops/scripts/production_guard.py
  - cli/omni/srv1_ops.py
  - cli/omni/tests/test_srv1_production_guard.py
  - docs/operations/production-guard.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-01-PLAN.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/25-production-guard-repair-engine/25-VALIDATION.md

## Executed

- `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
- `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "repair or audit or forbidden"`
- `! rg -n "pm2 kill|systemctl (restart|stop) xrdp|xrdp-sesman|curl .*POST|requests\.post|urllib.*POST" modules/srv1-ops/scripts/production_guard.py cli/omni/srv1_ops.py cli/omni/tests/test_srv1_production_guard.py`
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard repair --dry-run --json`
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
- `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
- `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`

## Result

- `production_guard.py` now supports `repair --dry-run --json` and guarded `repair --apply`.
- Dry-run never executes commands and emits machine-readable candidate actions with `reason`, `risk`, `side_effect`, `command_preview`, `rollback_hint` and `blocked_reason`.
- Apply is impossible without exact `--scope`, exact `--target`, explicit `--yes-i-understand-production-risk` and snapshot-first behavior.
- Audit events are written as redacted JSONL under `~/.local/state/omni/production-guard/`.
- `cli/omni/srv1_ops.py` now exposes `omni srv1-ops production-guard repair`.
- `docs/operations/production-guard.md` documents the repair path, allowlist, audit path, abort criteria and rollback expectations.

## Validation outcome

- Repair/audit/forbidden test slice: `7 passed`
- Forbidden-command scanner on the phase 25 surface returned no matches
- `repair --dry-run --json` executes successfully and reports `apply_ready: false` while Phase 24 findings remain blocked
- `status --json` and `doctor --json` still execute and keep reporting current live blockers without mutation
- Graphify status remained `stale=false` and `commit_stale=false`

## Notes

- Validation command 3 was narrowed to the files touched by Phase 25 because the repo contains unrelated legacy XRDP references outside the Production Guard surface.
