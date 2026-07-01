---
status: complete
phase: 24-production-recovery-guard-ats-horistic
source:
  - 24-01-SUMMARY.md
started: 2026-06-24T16:53:30Z
updated: 2026-06-24T17:06:30Z
---

## Current Test

[testing complete]

## Tests

### 1. Production Guard baseline is present
expected: The repository has a versioned baseline at `modules/srv1-ops/configs/production-guard.yaml`. It declares the PM2 unit contract, namespace counts for `atius` and `horistic`, critical ports, GET/HEAD-only endpoints, ecosystems, containers, timers and systemd job classification without secrets.
result: pass

### 2. Status command exposes the read-only guard
expected: Running `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json` prints structured JSON with `command`, `timestamp`, `overall`, `summary`, `checks` and `redaction_fields`. It inspects live PM2, dump parity, launchers, ecosystems, local ports, endpoints, containers, services and timers without repair, restart, `pm2 save`, `pm2 kill` or POST requests.
result: pass

### 3. Doctor command includes systemd job classification
expected: Running `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json` prints the same guard report plus `systemd_jobs`, separating critical blockers such as `default.target` from noisy backup/rclone jobs.
result: pass

### 4. Live blockers are visible without mutation
expected: On this host, `status --json` and `doctor --json` execute successfully but report `overall: block` because current live state has blockers. The report still shows PM2 live/dump namespace parity as passing and lists concrete blockers instead of trying to repair them.
result: pass

### 5. Automated regression coverage passes
expected: `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py` succeeds, and `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "baseline or pm2 or namespace or ecosystem or doctor"` reports the selected tests passing.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
