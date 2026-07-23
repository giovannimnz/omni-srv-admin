---
phase: 24
title: "Validation - Production Guard Foundation"
date: 2026-06-24
status: planned
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 24 Validation

## Validation Goal

Provar que a fundacao read-only do `production-guard` valida PM2 boot owner,
live/dump parity, namespaces, ecosystems, portas, endpoints GET/HEAD,
containers, timers e jobs sem mutar producao.

## Requirement Matrix

| Requirement | Evidence | Primary validation |
|---|---|---|
| PRG-01 | `pm2-ubuntu.service` single boot owner | `production-guard status --json` checks systemd properties |
| PRG-02 | PM2 live/dump/ecosystem parity | pytest fixtures + live doctor |
| PRG-03 | Namespace isolation | wrong namespace fixture returns BLOCK |
| PRG-04 | ecosystem contract | ecosystem parser tests for cwd/script/autorestart/restart policy/env/ports/redaction |
| PRG-05 | CLI status/doctor | `omni srv1-ops production-guard status/doctor --json` covers PM2, dump, ecosystems, ports, endpoints, containers, timers and jobs |

## Ordered Automated Battery

Run fastest/lowest complexity first while respecting prerequisites:

1. `python3 -m py_compile modules/srv1-ops/scripts/production_guard.py`
2. `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "baseline or pm2 or namespace or ecosystem or doctor"`
3. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard status --json`
4. `PYTHONPATH=cli python3 -m omni srv1-ops production-guard doctor --json`
5. `node "$HOME/.Codex/get-shit-done/bin/gsd-tools.cjs" graphify status`
6. `$gsd-verify-work 24`

## Non-Negotiable Failures

- `production-guard` runs repair, `pm2 save`, `pm2 kill` or restarts PM2.
- Any path restarts RDP/XRDP.
- ATS or Horistic apps are accepted in namespace `default` or wrong namespace.
- Launchers in `waiting restart` are accepted without recent successful
  `[CYCLE_SUMMARY]`.
- Endpoint validation sends POST requests to real trading/Telegram routes.
- Output leaks tokens, passwords, DB credentials, Cloudflare tokens or Ubuntu
  Pro tokens.
- Final Graphify status is stale or `commit_stale=true`.
