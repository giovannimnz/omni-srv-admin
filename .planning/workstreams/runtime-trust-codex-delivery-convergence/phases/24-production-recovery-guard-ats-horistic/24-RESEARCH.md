---
phase: 24
title: "Research - Production Guard Foundation"
date: 2026-06-24
status: complete
requirements:
  - PRG-01
  - PRG-02
  - PRG-03
  - PRG-04
  - PRG-05
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 24 Research

## Finding 1: PM2 boot protection exists, but needs a validator

Current protection:

- `pm2-ubuntu.service` is enabled and active.
- Unit is `Type=oneshot` + `RemainAfterExit=yes`.
- It runs `pm2 resurrect` with `PM2_HOME=/home/ubuntu/.pm2`.
- Repo source documents it as the single boot owner.

Gap:

- There is no single command in `omni-srv-admin` that verifies live unit, dump,
  PM2 daemon, ecosystems and namespaces together.

Plan implication:

- Add `production-guard status/doctor` with strict JSON and explicit
  `pass/warn/block/unknown`.

## Finding 2: Live PM2 and dump are currently aligned

Observed:

- PM2 live counts: `atius: 12`, `horistic: 5`.
- Dump counts: `atius: 12`, `horistic: 5`.
- No live app missing from dump.
- No dump app missing from live.
- No ATS/Horistic process in wrong namespace.

Plan implication:

- Encode this as baseline config, not hidden shell assumptions.

## Finding 3: `waiting restart` is ambiguous

The unified launchers are intentionally one-shot pollers:

- Logs say `MODE: one-shot (PM2 restart_delay handles polling)`.
- Logs include `[CYCLE_SUMMARY]` and exit so PM2 schedules the next cycle.

Risk:

- PM2 status `waiting restart` can also hide a broken restart loop.
- Current watchdog accepts `waiting restart` without checking last cycle recency
  or fatal errors.

Plan implication:

- Create launcher health rules:
  - status may be `online` or `waiting restart`;
  - latest `[CYCLE_SUMMARY]` must be recent;
  - fatal patterns in recent logs block;
  - restart count delta over window warns/blocks.

## Finding 4: Ecosystem validation must be contract-based

The guard should validate:

- namespace;
- `cwd` and `script` exist;
- `autorestart`, `restart_delay`, `max_restarts`;
- minimum env keys without printing secret values;
- expected app-owned port;
- app names and counts by namespace.

Plan implication:

- Build a parser/test fixture for ATS and Horistic `ecosystem.config.js`.

## Finding 5: Status must include more than PM2

Production incidents also involved:

- Apache remote state;
- containers relaunched by watchdog;
- user timers/services;
- stuck jobs such as `default.target start waiting`;
- public endpoints.

Plan implication:

- Phase 24 status/doctor covers containers, timers, jobs and safe GET/HEAD
  endpoints. Remote Apache deep validation remains Phase 27, but Phase 24 must
  reserve the model/config hooks.

## Pitfalls

- Do not mark launchers healthy just because PM2 says `waiting restart`.
- Do not run `pm2 save` or any repair in this phase.
- Do not run live POST tests against Telegram/webhook/trading routes.
- Do not leak tokens, passwords, DB credentials, Cloudflare tokens or Ubuntu
  Pro tokens in JSON, logs or docs.
