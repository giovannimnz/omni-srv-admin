---
phase: 44
plan: 44-01
status: completed
completed_at: 2026-07-05
requirements:
  - PKI-01
  - PKI-02
  - PKI-03
  - PKI-04
---

# 44-01 Summary - Fleet PKI Resource Surface

## Completed

- Added `omni fleet trust-pki` CLI resource.
- Added host rendering from inventory or DbOmniFleet.
- Added `onboard-host` as the high-level flow for newly registered servers.
- Added `reconcile-host` and `rotate-host` for IP/SAN drift handling.
- Added PKI command allowlist entries for local fallback and migration-backed
  `TbFleetCommands`.
- Added module docs, OpenSSL templates and focused tests.

## Validation

```bash
PYTHONPATH="cli;%TEMP%\codex-pytest-omni-srv-admin" python -m pytest -q cli\omni\tests\test_fleet_pki.py modules\fleet-control-plane\tests\test_m004_contract.py
# 24 passed

PYTHONPATH=cli python -m omni fleet trust-pki preflight --json
# valid true for atius-srv-1, atius-srv-2, atius-srv-3, horistic-srv

PYTHONPATH=cli python -m omni fleet trust-pki onboard-host --host horistic-srv --json
# valid JSON, full onboarding sequence rendered

PYTHONPATH=cli python -m omni fleet trust-pki reconcile-host --host horistic-srv --observed-san-json '{"dns":["horistic-srv"],"ip":["10.1.1.44"]}' --json
# drift detected for changed IP/SAN

PYTHONPATH=cli python -m omni fleet trust-pki rotate-host --host horistic-srv --observed-san-json '{"dns":["horistic-srv"],"ip":["10.1.1.44"]}' --json
# valid JSON, leaf rotation sequence rendered

PYTHONPATH=cli python -m omni fleet validate-inventory --json
# inventory JSON valid

git diff --check
# passed with Windows LF/CRLF warnings only
```

## Remaining Gate

The live mutation runner still blocks `--execute` for mutating PKI stages until
Phase 44-02 installs and verifies the remote bootstrap scripts.
