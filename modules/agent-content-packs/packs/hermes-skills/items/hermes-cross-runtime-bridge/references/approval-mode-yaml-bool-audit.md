# approvals.mode audit when YAML `off` becomes boolean `False`

Use this when auditing or synchronizing Hermes approval settings on a peer runtime.

## Problem
YAML 1.1 may parse bare `off` as boolean `False`.

That creates three different views of the same setting:
1. raw file text shows `approvals.mode: off`
2. generic `yaml.safe_load()` / `load_config()` may return `False`
3. Hermes approval runtime may normalize that boolean back to the semantic mode `off`

## Verified pattern
On `atius-srv-1` the following were all true at once:
- `config.yaml` text contained `approvals.mode: off`
- `hermes_cli.config.load_config()` returned `approvals.mode = False`
- `tools.approval._get_approval_mode()` returned `off`
- `tools.approval.is_approval_bypass_active()` returned `True`

So a raw config read alone was insufficient to conclude whether YOLO was actually active.

## Audit procedure
When validating approvals on a peer runtime, check in this order:

1. Textual file state
   - inspect the exact `approvals:` block in `config.yaml`
2. Loader state
   - inspect what `hermes_cli.config.load_config()` returns for `approvals.mode`
3. Runtime state
   - inspect `tools.approval._get_approval_mode()`
   - inspect `tools.approval.is_approval_bypass_active()`
4. Environment state
   - inspect `HERMES_YOLO_MODE` in login shells if shell-level persistence is relevant

## Interpretation rule
- If raw YAML / `load_config()` returns boolean `False`, do **not** immediately report misconfiguration.
- First verify whether the approval runtime normalizes it back to semantic `off`.
- Report both layers explicitly: `loader sees False; approval runtime resolves off`.

## Safer config-writing rule
When writing or normalizing config files, prefer the quoted string form:
- `approvals.mode: 'off'`

This removes ambiguity for generic YAML readers while preserving Hermes semantics.

## Hooks are separate
`approvals.mode` / YOLO does not imply shell-hook auto-accept.
Audit these independently:
- `HERMES_ACCEPT_HOOKS`
- `hooks_auto_accept`
- hook-resolution logic in `agent.shell_hooks`
