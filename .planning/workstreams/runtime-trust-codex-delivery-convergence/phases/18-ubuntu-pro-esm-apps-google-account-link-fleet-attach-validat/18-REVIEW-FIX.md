---
phase: 18-ubuntu-pro-esm-apps-google-account-link-fleet-attach-validat
fixed_at: 2026-08-29T08:22:00Z
review_path: 18-REVIEW.md
iterations: 6
findings_in_scope: 14
fixed: 14
skipped: 0
status: all_fixed
---

# Phase 18: XRDP fleet review fix report

## Result

The post-merge adversarial loop was reduced to a clean follow-up diff and
converged with zero Critical or Warning findings. The final deep review covers
the behavior changed relative to `origin/main`; older generic agent-content
defects are not activated by this delivery.

## Fixed boundaries

- XRDP 0.9.24 keymaps use the xfree86/base indexes for arrows, navigation,
  Delete, Print Screen and ABNT_C1.
- `[Globals]` validation requires exactly one expected value for each managed
  override; the repairer detects duplicate/conflicting values as drift, creates
  a snapshot, then normalizes them.
- The POSIX repair script runs under Ubuntu `mawk`; the reserved `index` local
  variable was removed.
- Install rolls back tracked files with exact mode, uid and gid and restores
  the prior state of `xrdp`, `xrdp-sesman`, reconcile service and timer after a
  late failure.
- Missing packages fail before the XRDP transaction unless
  `--install-packages` explicitly accepts the non-rollbackable package-manager
  boundary.
- A fresh install runs the reconcile oneshot synchronously before validation;
  the health check requires a real execution timestamp and a scheduled timer.
- No success path restarts `xrdp` or `xrdp-sesman`.
- Wheel `omni 0.2.5`, content-pack manifest, runbook and Codex skill
  `$xrdp-abnt2-fleet` are aligned. Versioned source:
  `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`.
- `agent-content sync --apply` for `ssh-linux` now fails before any remote
  writer is invoked; SSH dry-run remains available. The remote transaction
  engine is intentionally deferred rather than shipped partially.

## Verification

- Final GSD review: `clean`, depth `deep`, 11 files, 0 findings.
- Focused tests: 35 passed in the final review; local rerun had 28 XRDP tests
  and 7 agent-content tests passing.
- The reconciler was executed in a temporary filesystem using Ubuntu `mawk`;
  duplicate desired/conflicting overrides produced a backup and exactly one
  canonical live value.
- `agent-content-validate-all.sh`: all Hermes, Codex and shared packs valid.
- `py_compile`, `sh -n`, `git diff --check` and Graphify freshness passed.

## Residual UAT

SSH cannot prove physical keyboard events. A new Microsoft RDP session on each
host must still exercise arrows, Delete, Print Screen, `/`, `?`, AltGr and
clipboard. That is an operator UAT gate, not an unresolved code-review finding.

## Post-merge timer hotfix

The first local 0.2.5 install correctly failed closed and rolled back because
the health probe queried only `NextElapseUSecRealtime`; this timer is scheduled
on the monotonic clock. The hotfix accepts a finite schedule in either realtime
or monotonic form, rejects empty, `0`, `n/a` and `infinity`, and pins the exact
properties requested from systemd. The final hotfix review is `clean` and the
focused suite passes 30 tests. XRDP/Xvnc remained active through the failed
install and rollback.

## Final live rollout

After PRs #20 and #21 merged, all four repos fast-forwarded to `22aa555ce`.
Each host created a new per-host backup, applied without XRDP restart, and
returned `validate=PASS`, `diff=CLEAN`, timer active/scheduled, reconcile
`Result=success` and `ExecMainStatus=0`. All five managed keymaps converge on
SHA-256 `cdd4e2def3657b451fdef8d9c2038e28112f1df2498e768f3c8ddd5eb0a34237`.
SRV-1 and SRV-2 kept their active Xvnc `:1` sessions. Horistic's packaged CLI
was rebuilt as `omni 0.2.5` under a verified 80% CPU quota on its four-vCPU
host and passed the same validate/diff gates.

## Canonical skill closeout — 2026-09-04

`$xrdp-abnt2-fleet` now owns the complete agent workflow for inventory-derived
scope, read-only audit, diagnosis, serial reconcile, rollback verification,
timer health, wheel/content-pack parity, Landscape boundaries, GSD/GitHub and
Obsidian/GBrain closeout. It includes Codex UI metadata and a conditional
legacy Hermes boundary; executable behavior remains solely in the canonical
module/CLI.

`skill-creator` validation, content-pack file hashes/bytes, all-pack validation,
inventory YAML parsing and an independent realistic forward-test passed. Active
docs and inventories reference the source skill; dangerous historical
procedures retain their chronology behind explicit evidence-only redirects.
