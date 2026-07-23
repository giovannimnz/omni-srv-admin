---
status: complete
phase: 27-production-guard-horistic-remote-rename-drift
source:
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/27-production-guard-horistic-remote-rename-drift/27-SUMMARY.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/27-production-guard-horistic-remote-rename-drift/27-01-SUMMARY.md
started: 2026-06-24T17:22:14-03:00
updated: 2026-06-26T07:10:00-03:00
---

## Current Test

number: 4
name: Phase 27 Validation Battery
expected: |
  The focused Phase 27 validation battery compiles `production_guard.py`, keeps webhook checks POST-free, passes the targeted pytest selector, exposes the new read-only remote Apache and rename-drift checks in `status/doctor`, confirms Horistic public/API/webhook endpoints with safe methods, and leaves Graphify fresh.
awaiting: none

## Tests

### 1. Remote Horistic Apache Check
expected: Running `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json` reports a `remote_horistic_apache` check. The check uses SSH read-only inspection against `horistic@10.1.1.4`, confirms Apache is enabled and active, sees ports 80 and 443 listening, validates `sites-enabled`, and reports `apache2ctl` as pass. The overall command may still be `block` because of pre-existing environment issues outside Phase 27.
result: [passed]
notes: |
  `production-guard status --json` reports `remote_horistic_apache` as `pass` with SSH read-only Apache inspection against `horistic@10.1.1.4`, service enabled/active, ports 80/443 listening, `sites-enabled` present, and `apache2ctl -S` passing. The overall command remains `block` because of pre-existing environment issues and because the rename detector correctly flags the still-active legacy remote vhost reference.

### 2. Rename Drift Detector
expected: Running `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json` reports a `rename_drift` check that classifies legacy `horistic-srv-1` references with `warn` or `block` findings only. It does not rename folders, edit Apache vhosts, create symlinks, or mutate PM2 state.
result: [passed]
notes: |
  `rename_drift` is present and classifies historical references as `warn` and the active `/etc/apache2/sites-enabled/remote.horistic-srv-1.atius.com.br.conf` reference as `block`, without renaming folders, creating symlinks, editing Apache, or mutating PM2 state.

### 3. Webhook Health Safety
expected: The production guard baseline includes `horistic-webhook-health` with method `HEAD` for `https://webhook.horistic.com/`, and the phase safety scan does not find real webhook checks using POST through `requests`, `urllib`, `curl`, or `method: POST`.
result: [passed]
notes: |
  The runtime scan confirms `horistic-webhook-health` uses `HEAD`, public webhook health responds `200`, and no real webhook health implementation uses `requests.post`, `urllib` POST, `curl -X POST`, or `method: POST`. The only regex hit is the documentation warning in `docs/operations/production-guard.md`, not executable code.

### 4. Phase 27 Validation Battery
expected: The Phase 27 validation battery compiles `production_guard.py`, passes the focused pytest selector `apache or remote or rename or drift or webhook`, confirms Horistic public/API/webhook health endpoints with safe methods, and leaves Graphify fresh.
result: [passed]
notes: |
  `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py` passed, focused pytest passed (`7 passed`), `status --json` and `doctor --json` executed with the new Phase 27 checks visible, Horistic public/API/webhook health endpoints returned `200` through safe methods, and Graphify remained fresh (`stale=false`, `commit_stale=false`).

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
