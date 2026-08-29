---
phase: 18-ubuntu-pro-esm-apps-google-account-link-fleet-attach-validat
reviewed: 2026-08-29T06:55:10Z
depth: deep
files_reviewed: 16
files_reviewed_list:
  - cli/omni/__init__.py
  - cli/omni/agent_content.py
  - cli/omni/tests/test_agent_content.py
  - cli/omni/tests/test_xrdp_abnt2.py
  - cli/omni/xrdp_abnt2.py
  - cli/setup.py
  - docs/operations/ubuntu-arm64-xrdp-desktop-standard.md
  - modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md
  - modules/agent-content-packs/packs/codex-skills/manifest.yaml
  - modules/xrdp-abnt2/README.md
  - modules/xrdp-abnt2/files/fix-xrdp-abnt2-keyboard
  - modules/xrdp-abnt2/files/km-abnt2.ini
  - modules/xrdp-abnt2/files/setxkbmap-abnt2.sh
  - modules/xrdp-abnt2/files/startwm.sh
  - modules/xrdp-abnt2/files/xrdp-abnt2-reconcile.service
  - modules/xrdp-abnt2/files/xrdp-abnt2-reconcile.timer
findings:
  critical: 3
  warning: 1
  info: 0
  total: 4
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-08-29T06:55:10Z
**Depth:** deep
**Files Reviewed:** 16
**Status:** issues_found

## Summary

The wheel asset fallback is present and focused tests/syntax checks pass, but the merged implementation still has failure-masking paths in remote content sync and can falsely certify an XRDP configuration whose keyboard overrides are outside `[Globals]`. The timer's enabled/active probe also does not prove that reconciliation is runnable.

## Critical Issues

### CR-01: Remote extraction loses `bash -lc` quoting and can report success after a failed stage

**File:** `/home/ubuntu/GitHub/omni-srv-admin/cli/omni/agent_content.py:213`
**Issue:** `_ssh_run()` correctly passes `shlex.quote(command)` as the argument to the remote `bash -lc`, but `_ssh_extract_tree()` passes `remote_cmd` unquoted. SSH joins remote arguments into one command string, so the remote shell parses the semicolon-separated body itself; `bash -lc` receives only `set` as its command and the remaining operations run outside the intended `set -euo pipefail` shell. A failed `cat`, `tar`, or `mv` can therefore be hidden by the final successful cleanup, while the caller emits `applied-ssh` after it has already removed the old destination at line 207. This makes the sync destructive without a reliable success signal.
**Fix:** Use the same quoting contract as `_ssh_run`, then add a trap which removes the temporary archive without replacing the destination until extraction has completed in a staging directory. For example:

```python
proc = subprocess.run(
    _ssh_base_command(target) + ["bash", "-lc", shlex.quote(remote_cmd)],
    input=archive_bytes,
    capture_output=True,
    timeout=300,
)
```

Build into `mktemp -d` beside the destination, verify the expected extracted root, then atomically rename it; preserve the prior tree until that succeeds.

### CR-02: `agent-content sync --apply` returns success even when target validation failed

**File:** `/home/ubuntu/GitHub/omni-srv-admin/cli/omni/agent_content.py:578-589`
**Issue:** The command serializes and prints `runtime_validation` but never checks `runtime_validation["ok"]`. A nonzero validation command (or an exception, which `_run_validate_command` turns into `{ok: false}`) still produces exit code 0. Fleet automation will mark a failed Codex/Hermes sync as successful and can continue rollout using an unusable target installation.
**Fix:** Print the payload for diagnostics, then fail the Click command when validation was requested and is not successful. Treat a skipped/malformed configured validator as failure for `--apply`, or make an explicit opt-out flag the only way to accept it.

```python
if runtime_validation.get("ok") is not True:
    raise click.ClickException("sync aplicado, mas a validação do target falhou")
```

Add tests for nonzero and exception validation results, asserting nonzero CLI exit status in both text and JSON modes.

### CR-03: Reconciler and validator accept keyboard overrides outside `[Globals]`

**File:** `/home/ubuntu/GitHub/omni-srv-admin/modules/xrdp-abnt2/files/fix-xrdp-abnt2-keyboard:32-37`
**Issue:** The drift check greps the whole `xrdp.ini` and `ensure_override()` likewise replaces the first matching key anywhere (lines 63-67). If a duplicate or commented migration value exists in another section, the timer treats it as compliant and never creates the required `[Globals]` values. `validate` repeats the same whole-file mistake at `/home/ubuntu/GitHub/omni-srv-admin/cli/omni/xrdp_abnt2.py:523-536`, so it reports PASS even though XRDP will not receive the documented global keyboard overrides. This defeats the persistent repair contract after an xrdp configuration migration.
**Fix:** Restrict both repair and validation to the `[Globals]` section. Replace/append each key there, remove duplicates there deterministically, and ignore matches in every other section. Share the section-aware implementation (or invoke a small tested Python helper from the timer) and add fixtures with conflicting keys in `[Logging]`/another section.

## Warnings

### WR-01: Timer health check proves only the scheduler state, not successful reconciliation

**File:** `/home/ubuntu/GitHub/omni-srv-admin/cli/omni/xrdp_abnt2.py:376-382`
**Issue:** `is-enabled` and `is-active` can both be true while the timer's service has never run successfully (for example, a future packaged asset/permission regression or a failed execution after the delayed first trigger). The documentation and skill call this a persistent drift guard, but `validate` declares it healthy without inspecting the service result or a scheduled next trigger.
**Fix:** In addition to timer enabled/active, query `systemctl show xrdp-abnt2-reconcile.service --property=Result --property=ExecMainStatus` and `systemctl show xrdp-abnt2-reconcile.timer --property=NextElapseUSecRealtime`; fail validation on a failed service result or no next trigger. Add mocked tests for those failure states.

---

_Reviewed: 2026-08-29T06:55:10Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
