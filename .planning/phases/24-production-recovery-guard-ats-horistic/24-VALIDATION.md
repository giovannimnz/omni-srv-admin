---
phase: 24
title: "Validation Architecture — ATS/Horistic Production Recovery Guard"
date: 2026-06-24
status: planned
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
  - PRG-06
  - PRG-07
  - PRG-08
  - PRG-09
  - PRG-10
---

# Phase 24 Validation Architecture

## Validation Goal

Provar que ATS e Horistic possuem protecao operacional reproduzivel no
`omni-srv-admin`: boot PM2, namespaces, dump/ecosystem parity, remote Apache,
containers/services, reboot/login checks, repair gates e rename drift detector.

## Requirement Matrix

| Requirement | Evidence | Primary validation |
|---|---|---|
| PRG-01 | `pm2-ubuntu.service` single boot owner | `production-guard status --json` checks systemd properties |
| PRG-02 | PM2 live/dump/ecosystem parity | pytest fixtures + live doctor |
| PRG-03 | Namespace isolation | wrong namespace fixture returns BLOCK |
| PRG-04 | ecosystem contract | ecosystem parser tests for cwd/script/autorestart/restart policy/env/ports/redaction |
| PRG-05 | CLI status/doctor | `omni srv1-ops production-guard status/doctor --json` covers PM2, dump, ecosystems, ports, remote Apache, containers, timers and systemd jobs |
| PRG-06 | Guarded repair | dry-run tests; forbidden-command scanner |
| PRG-07 | Boot/login protocol | `systemd-analyze verify --user` + docs checks |
| PRG-08 | Remote Horistic Apache | remote check fixture + optional live SSH read-only check for unit, ports, `apache2ctl -S`, `sites-enabled`, vhosts and endpoints |
| PRG-09 | Rename drift detector | missing cwd/script and stale rename refs fixtures |
| PRG-10 | Audit/no secrets/docs | redaction tests + runbook grep |

## Plan Gates

| Plan | Gate | Pass condition |
|---|---|---|
| 24-01 | Read-only truth gate | Validator reports PM2/dump/ecosystem/namespace status without mutation. |
| 24-02 | Repair apply gate | Dry-run exists; apply requires scope/target/operator approval and snapshots. |
| 24-03 | Live install gate | Boot/login units are versioned; live install is explicitly approved and read-only. |
| 24-04 | Remote/rename gate | Remote Apache and rename drift checks are read-only and classify findings. |

## Minimum Automated Suite

```bash
python3 -m py_compile modules/srv1-ops/scripts/production_guard.py
PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q
systemd-analyze verify --user \
  modules/srv1-ops/systemd/production-guard.service \
  modules/srv1-ops/systemd/production-guard.timer \
  modules/srv1-ops/systemd/production-guard-login.service
PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json
PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json
PYTHONPATH=cli python3 -m omni srv1-ops production-guard repair --dry-run --json
node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status
```

## Non-Negotiable Failures

- `production-guard` runs `pm2 kill` or restarts `pm2-ubuntu.service`
  automatically.
- Any path restarts RDP/XRDP without an explicit human checkpoint.
- `pm2 save` runs when live PM2, dump and namespaces are not healthy.
- ATS or Horistic apps are accepted in namespace `default` or wrong namespace.
- Launchers in `waiting restart` are accepted without recent successful
  `[CYCLE_SUMMARY]`.
- Remote Horistic Apache is assumed healthy from SRV-1 local checks only.
- Remote Horistic vhosts are not checked with read-only `apache2ctl -S` /
  `sites-enabled` evidence.
- Webhook validation sends POST requests to real trading/Telegram routes.
- Rename detector moves folders, edits vhosts or creates symlinks without gate.
- Output leaks tokens, passwords, DB credentials, Cloudflare tokens or Ubuntu
  Pro tokens.
- Final Graphify status is stale or `commit_stale=true`.
