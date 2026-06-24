---
phase: 24
title: "Research — ATS/Horistic Production Recovery Guard"
date: 2026-06-24
status: complete
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

# Phase 24 Research

## Finding 1: PM2 boot protection exists, but needs contract tests

Current protection:

- `pm2-ubuntu.service` is enabled and active.
- Unit is `Type=oneshot` + `RemainAfterExit=yes`.
- It runs `pm2 resurrect` with `PM2_HOME=/home/ubuntu/.pm2`.
- Repo source already documents it as the single boot owner.

Gap:

- There is no single command in `omni-srv-admin` that verifies live unit,
  dump, PM2 daemon, ecosystems and namespaces together.

Plan implication:

- Add a production guard validator with strict JSON output and explicit
  pass/warn/block status.

## Finding 2: Live PM2 and dump are currently aligned

Observed:

- PM2 live counts: `atius: 12`, `horistic: 5`.
- Dump counts: `atius: 12`, `horistic: 5`.
- No live app missing from dump.
- No dump app missing from live.
- No ATS/Horistic process in wrong namespace.

Plan implication:

- Encode this as baseline and allow override in a small config file, not as
  hidden shell assumptions.

## Finding 3: `waiting restart` is ambiguous

The two unified launchers are intentionally one-shot pollers:

- Logs say `MODE: one-shot (PM2 restart_delay handles polling)`.
- Logs include `[CYCLE_SUMMARY]` and exit so PM2 schedules the next cycle.

Risk:

- PM2 status `waiting restart` can also hide a broken restart loop.
- Current `inviolable-watchdog` accepts `waiting restart` without checking
  last cycle recency or fatal errors.

Plan implication:

- Create launcher health rules:
  - status may be `online` or `waiting restart`;
  - latest `[CYCLE_SUMMARY]` must be recent;
  - fatal patterns in recent logs block;
  - restart count delta over window warns/blocks;
  - PM2 restart loop without successful summary blocks.

## Finding 4: Repair must be scoped and conservative

Safe actions:

- Start missing apps from canonical ecosystem with `pm2 start ecosystem.config.js
  --only <app> --update-env`.
- Start missing stack from ecosystem when namespace has multiple missing apps.
- Start known existing Podman containers by exact name.
- Start a systemd unit when the unit is known and the action does not kill RDP.

Unsafe actions without human gate:

- `pm2 kill`.
- Restarting `pm2-ubuntu.service` while production apps are online.
- Rewriting `dump.pm2` before live state is verified healthy.
- Apache remote mutation without config backup.
- Rename/move production folders.
- POSTing real webhook payloads.

Plan implication:

- Implement `repair --dry-run` first, `repair --apply --scope <scope>` only with
  explicit flags and audit snapshot.

## Finding 5: Horistic proxy is remote

Validated state:

- Host: `horistic-srv` (`horistic@10.1.1.4`).
- Apache unit: default Ubuntu unit in `/usr/lib/systemd/system/apache2.service`.
- Status: enabled, active.
- Drop-ins: none.
- Ports: 80/443 listening.
- Public Horistic endpoints returned 200.

Plan implication:

- Guard must model SRV-1 app runtime and Horistic remote proxy separately.
- A local SRV-1-only check is incomplete for Horistic.

## Finding 6: Rename drift should be first-class

Known pattern:

- Host rename `horistic-srv-1` -> `horistic-srv` was operationally safe, but
  old names can remain in vhosts, GDrive paths, inventory notes or workspace
  folders.

Plan implication:

- Add a detector that classifies:
  - stale-but-benign reference;
  - active path referenced by PM2 cwd/script;
  - active Apache vhost/ref;
  - missing symlink or folder;
  - rename requiring explicit live gate.

## Recommended Implementation Shape

- `modules/srv1-ops/configs/production-guard.yaml`
- `modules/srv1-ops/scripts/production_guard.py`
- `cli/omni/srv1_ops.py` subcommands:
  - `omni srv1-ops production-guard status --json`
  - `omni srv1-ops production-guard doctor --json`
  - `omni srv1-ops production-guard repair --dry-run`
  - `omni srv1-ops production-guard repair --apply --scope pm2-app`
- `modules/srv1-ops/systemd/production-guard.service`
- `modules/srv1-ops/systemd/production-guard.timer`
- `docs/operations/production-guard.md`
- tests in `cli/omni/tests/test_srv1_production_guard.py`

Minimum status/doctor coverage:

- PM2 system unit and legacy unit state.
- PM2 live/dump parity and namespace isolation.
- ATS/Horistic ecosystem parser for `autorestart`, `restart_delay`,
  `max_restarts`, cwd/script existence, minimum env keys, app-owned ports and
  redacted env output.
- Local critical ports and public GET endpoints.
- Known containers and repeated watchdog relaunch findings.
- Required timers/services and `systemctl --user list-jobs` classification.
- Remote Horistic Apache unit, listener, `apache2ctl -S`, `sites-enabled`,
  expected vhosts/proxy targets and stale active hostname refs.

## Pitfalls

- Do not mark launchers healthy just because PM2 says `waiting restart`.
- Do not let repair rewrite `dump.pm2` while apps are missing or namespaces are
  wrong.
- Do not conflate Horistic app runtime on SRV-1 with Apache proxy on
  `horistic-srv`.
- Do not run live POST tests against Telegram/webhook routes.
- Do not rename production folders automatically.
- Do not touch existing dirty worktree files without selective staging.
