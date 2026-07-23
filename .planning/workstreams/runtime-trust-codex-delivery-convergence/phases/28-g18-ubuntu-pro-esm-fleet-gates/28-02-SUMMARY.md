---
phase: 28-g18-ubuntu-pro-esm-fleet-gates
plan: 02
subsystem: infra
tags: [ubuntu-pro, esm, apt, landscape, xrdp, pm2, k3s, oci, g18, runbook]

requires:
  - phase: 28-g18-ubuntu-pro-esm-fleet-gates
    provides: Read-only redacted Ubuntu Pro/ESM inventory and backup manifest from 28-01
  - phase: 15-m005-oci-snapshots
    provides: OCI snapshot and restore-drill workflow with pending-vs-real snapshot distinction
  - phase: 18-ubuntu-pro-esm-apps-google-account-link-fleet-attach-validat
    provides: Prior Pro attach, Landscape, apt upgrade, and RDP lessons
provides:
  - Canonical G18 upgrade gate runbook for Phase 29
  - Per-host PASS/BLOCK checklist for SRV-1, SRV-2, and SRV-3
  - Phase 29 handoff with operator approval record and rollback protocol
affects: [phase-28, phase-29, g18, ubuntu-pro, esm, apt, landscape, xrdp, oci]

tech-stack:
  added: []
  patterns:
    - Docs-only GSD execution under explicit no-commit/no-live-mutation constraint
    - PASS/BLOCK gate with clearing artifact for every blocker
    - Operator approval record requiring host, report path, snapshot/exception, backup path, package scope, posture, and timestamp

key-files:
  created:
    - docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-SUMMARY.md
  modified:
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md

key-decisions:
  - "Keep Phase 28 strictly docs-only: no apt mutation, service restart, Landscape mutation, webhook POST, or PM2/XRDP action."
  - "Treat pending-* OCI snapshot IDs as blockers for live mutation unless the operator signs a no-OCI-restore exception."
  - "Require one approval record per host; chat approval alone is insufficient unless it includes all audit fields."
  - "Keep token/account/contract values out of artifacts; record only token-path metadata and redacted Pro status."

patterns-established:
  - "Phase 29 gates must name both the blocker and the artifact that clears it."
  - "Rollback guidance must avoid generic downgrade commands and rely on captured package versions per host."
  - "RDP/XRDP rollback references preserve display :1 posture and require explicit Phase 29 approval before restart/repair."

requirements-completed: [G18-02]

duration: 18m
completed: 2026-06-24
status: complete
---

# Phase 28 Plan 02: G18 Upgrade Gates Summary

**Per-host G18 upgrade gates, rollback protocol, and Phase 29 handoff from the redacted Pro/ESM inventory**

## Performance

- **Duration:** 18m
- **Started:** 2026-06-24T22:14:06Z
- **Completed:** 2026-06-24T22:32:00Z
- **Tasks:** 2/2
- **Files created:** 4
- **Files modified:** 2 planning state files
- **Commits:** skipped by explicit operator constraint

## Accomplishments

- Created the canonical runbook `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md`.
- Created the per-host PASS/BLOCK checklist at `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md`.
- Created the Phase 29 handoff at `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md`.
- Converted 28-01 inventory facts into actionable blockers for token path, real OCI snapshots, Landscape posture, disk warnings, package rollback artifacts, and written operator checkpoint.

## Task Commits

No commits were made. The operator explicitly constrained this execution with: "Do not commit. The parent Codex runtime is under a no-git-unless-explicit policy."

Task completion is tracked by files on disk only:

1. **Task 1: Create per-host upgrade gate checklist** - commit skipped
2. **Task 2: Write rollback protocol and Phase 29 handoff** - commit skipped

## Files Created/Modified

- `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` - canonical G18 Phase 29 gate/runbook and rollback protocol.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md` - per-host gate checklist generated from 28-01 inventory.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md` - explicit handoff from read-only Phase 28 to gated Phase 29.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-SUMMARY.md` - this summary.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` - progress, session, metrics, and decisions updated for Phase 28 completion.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` - Phase 28 marked 2/2 plans complete.

## Gate Results

| Host | Overall status | Primary blockers |
|---|---|---|
| atius-srv-1 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real OCI snapshot missing; disk 86% warning; Landscape registration no; rollback artifacts/checkpoint missing. |
| atius-srv-2 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real OCI snapshot missing; disk 86% warning; Landscape registration no; rollback artifacts/checkpoint missing. |
| atius-srv-3 | BLOCK | Fresh Phase 29 bundle pending; token path missing; real OCI snapshot missing; Landscape registration no; PM2 posture needs operator acceptance; rollback artifacts/checkpoint missing. |

## Decisions Made

- Kept Phase 28 docs-only and did not run live apt, service, Landscape, PM2, XRDP, or webhook actions.
- Treated `pending-*` OCI snapshot IDs as not valid for live restore; Phase 29 needs real `ocid1.image...` IDs or signed exceptions.
- Required one approval record per host with snapshot/exception, backup path, package scope, expected reboot/service posture, and signed timestamp.
- Kept rollback guidance artifact-driven; no generic package downgrade command was added.

## Deviations from Plan

None - plan executed exactly as written, except that all commits were skipped due to the explicit operator no-commit constraint.

## Issues Encountered

- The repository was already dirty with many unrelated modified/untracked files. Only Plan 28-02 artifacts were created.
- Graphify status was checked before execution and was fresh; the specific query returned no nodes, so the plan's referenced files remained the source of truth.
- Per-task and final GSD commits were skipped because the operator explicitly prohibited commits.
- `G18-02` remains pending in `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` because Phase 29 still owns the live mutation execution and post-upgrade validation portion.

## Verification

Executed:

```bash
test -s docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md
test -s .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md
test -s .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md
rg -n "G18-02|atius-srv-1|atius-srv-2|atius-srv-3|operator approval|snapshot ID|backup path|rollback|Phase 29-only|No Phase 28 live mutation" docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md
```

## No Live Mutation Evidence

This plan created Markdown artifacts only. It did not run live apt upgrade, apt update, apt full-upgrade, autoremove, package install/remove, XRDP/RDP restart, PM2 restart, Landscape mutation, or webhook POST.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None beyond the plan threat model. This plan added docs/checklists only and introduced no new network endpoint, auth path, file-access implementation, or schema boundary.

## User Setup Required

Before Phase 29 mutation:

- Restore an approved Ubuntu Pro token path or sign a no-attach-fallback exception for each host.
- Provide a real OCI image snapshot ID or sign a no-OCI-restore exception for each host.
- Review/accept SRV-1 and SRV-2 disk warning state.
- Resolve or accept Landscape SaaS/client registration posture.
- Generate a fresh preflight bundle and signed operator approval record per host.

## Next Phase Readiness

Phase 29 has the required runbook, checklist, rollback protocol, and approval-record format. It remains blocked from live package mutation until the listed host blockers are cleared or explicitly accepted by signed exception.

## Self-Check: PASSED

- Found all created files: runbook, per-host gate checklist, Phase 29 handoff, and summary.
- Found updated state files: `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` and `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md`.
- Verification commands from `28-02-PLAN.md` passed.
- Secret scan found no account emails, account IDs, contract IDs, 64-character token/hash values, or token assignments in the new artifacts.
- Stub-pattern scan found no tracked stub markers in the new artifacts.
- Graphify status checked after file changes; fallback `~/.codex/gsd-core/bin/gsd-tools.cjs` reported `commit_stale=false`.

---
*Phase: 28-g18-ubuntu-pro-esm-fleet-gates*
*Completed: 2026-06-24*
