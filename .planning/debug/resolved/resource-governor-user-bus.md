---
status: resolved
trigger: "resource-governor intercepts npm and native make builds, then systemd-run --user fails with Failed to connect to bus: No such file or directory"
created: 2026-07-12
updated: 2026-07-12
---

## Symptoms

- expected: npm global updates and installer native-module builds run under the 20 percent host CPU guardrail.
- actual: the builds profile prints CPUQuota=80%, invokes systemd-run --user, and exits before running npm or make.
- errors: Failed to connect to bus: No such file or directory; node-gyp reports make exit code 1.
- timeline: reproduced on atius-srv-1 on 2026-07-12.
- reproduction: npm install -g @openai/codex; ./install.sh in codex-desktop-linux when electron-rebuild invokes make.

## Current Focus

- hypothesis: confirmed; stale XRDP bus, static parent quota, and lost working directory combined to break guarded builds.
- test: inject stale bus, force parent to 20%, execute a scoped command, run npm global update, and compile Codex Desktop native modules.
- expecting: commands execute on canonical user bus, preserve cwd, and retain cpu.max=80000/100000.
- next_action: none
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-07-12T23:04:52-03:00
  result: canonical `/run/user/1001/bus` executed `systemd-run --user`; inherited `/tmp/dbus-*` failed.
- timestamp: 2026-07-12T23:07:35-03:00
  result: starting from `cpu.max=20000 100000`, guarded `/usr/bin/true` returned 0 and left `cpu.max=80000 100000`.
- timestamp: 2026-07-12T23:09:45-03:00
  result: guarded `/usr/bin/pwd` launched from `/tmp` printed `/tmp`.
- timestamp: 2026-07-12T23:08:08-03:00
  result: `npm install -g @openai/codex` completed and all post-build jobs scheduled without bus errors.
- timestamp: 2026-07-12T23:19:00-03:00
  result: Codex Desktop native modules reached `Rebuild Complete`; later installer failure was unrelated bundle patch drift.

## Eliminated

## Resolution

- root_cause: XRDP exported an unlinked private DBus socket; helpers preserved it with `setdefault`; the static parent slice reasserted 20% of one core; wrapper changed cwd to the Omni repo.
- fix: force dynamic canonical user-manager env locally, set runtime slice quota from total host percentage, and preserve caller cwd via PYTHONPATH-based CLI invocation.
- verification: 4 focused tests, shell/Python syntax checks, stale-bus live scope, effective cgroup read, npm global update, and native Electron rebuild.
- files_changed: cli/omni/srv1_ops.py, cli/omni/tests/test_resource_governor.py, modules/srv1-ops/scripts/build-cpu-guard-wrapper.sh, modules/srv1-ops/scripts/resource-governor-cgroup-init.sh, modules/srv1-ops/scripts/resource-governor-status.py, modules/srv1-ops/scripts/resource-governor-patcher.py, docs/operations/resource-governor.md
