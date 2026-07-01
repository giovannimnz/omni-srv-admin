---
phase: 31-omni-fleet-collectors-and-desired-state-profiles
plan: 01
status: complete
completed_at: 2026-06-25
requirements_addressed:
  - GOV-03
---

# Phase 31 / Plan 31-01 — Summary

Implemented `cli/omni/fleet_collectors.py` and wired `omni fleet agent collect-programs`.

Collector coverage:

- `dpkg-query`
- `snap list`
- `python3 -m pip list --format=json`
- `uv pip list --format=json`
- `npm ls -g --depth=0 --json`
- `pnpm list -g --depth=0 --json`
- `cargo install --list`
- `pm2 jlist`
- `systemctl list-units --type=service --all`
- `podman ps/images`
- `docker ps/images`

The command writes local cache under `~/.logs/fleet/programs` and can upsert observations to `TbPrograms`/`TbVersions` through PgBouncer with `--db`.

Tests were added but not run in this pass.

