---
phase: 28-g18-ubuntu-pro-esm-fleet-gates
plan: 01
subsystem: infra
tags: [ubuntu-pro, esm, apt, landscape, xrdp, pm2, k3s, oci, g18]

requires:
  - phase: 18-ubuntu-pro-esm-apps-google-account-link-fleet-attach-validat
    provides: Ubuntu Pro attach, ESM Apps/Infra enablement, Landscape context, and prior apt upgrade history
  - phase: 15-m005-oci-snapshots
    provides: OCI snapshot metadata and rollback workflow
provides:
  - Read-only redacting Ubuntu Pro/ESM inventory collector
  - Canonical operations note for G18 Pro/ESM inventory fields
  - Current redacted per-host SRV-1/SRV-2/SRV-3 G18 inventory and backup manifest
affects: [phase-28, phase-29, g18, ubuntu-pro, esm, landscape]

tech-stack:
  added: [python-stdlib]
  patterns:
    - Hard-coded read-only SSH probe allowlist
    - Built-in self-test for redaction and mutation-command rejection
    - Token file metadata collection via stat only

key-files:
  created:
    - scripts/g18-pro-esm-inventory.py
    - docs/operations/g18-ubuntu-pro-esm-inventory.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-SUMMARY.md
  modified: []

key-decisions:
  - "Use Python stdlib only; no new package dependency for Phase 28 prep."
  - "Keep account/contract identity as present/redacted, never exact values."
  - "Use cached apt state only; do not run apt update or any package mutation."
  - "Skip all commits because the operator explicitly set a no-commit constraint."

patterns-established:
  - "Read-only fleet collectors must expose their remote command allowlist via --dry-run-commands."
  - "Collectors touching production hosts must self-test mutation rejection before live probes."
  - "Ubuntu Pro token audits record stat metadata only and never read or hash token contents."

requirements-completed: [G18-01, G18-02]

duration: 9m18s
completed: 2026-06-24
status: complete
---

# Phase 28 Plan 01: G18 Ubuntu Pro/ESM Fleet Inventory Summary

**Read-only, redacted Ubuntu Pro/ESM fleet inventory for SRV-1/SRV-2/SRV-3 with backup gate inputs for Phase 29**

## Performance

- **Duration:** 9m18s
- **Started:** 2026-06-24T22:01:21Z
- **Completed:** 2026-06-24T22:10:39Z
- **Tasks:** 2/2
- **Files created:** 4
- **Commits:** skipped by explicit operator constraint

## Accomplishments

- Created `scripts/g18-pro-esm-inventory.py`, a Python stdlib collector that only accepts `atius-srv-1`, `atius-srv-2`, and `atius-srv-3`.
- Added `--self-test`, `--dry-run-commands`, `--hosts`, and `--output`.
- Captured current Pro/ESM, apt source, upgradable package, token metadata, disk, Landscape, XRDP, PM2, K3s, OCI snapshot, and GDrive backup state.
- Wrote the canonical field/redaction runbook at `docs/operations/g18-ubuntu-pro-esm-inventory.md`.
- Generated `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md` without exposing account IDs, contract IDs, emails, token contents, hashes, API keys, or webhook secrets.

## Task Commits

No commits were made. The operator explicitly constrained this execution with: "Do not commit. The parent Codex runtime is under a no-git-unless-explicit policy."

Task completion is tracked by files on disk only:

1. **Task 1: Build read-only redacting inventory collector** - commit skipped
2. **Task 2: Generate redacted fleet inventory and backup manifest** - commit skipped

## Files Created/Modified

- `scripts/g18-pro-esm-inventory.py` - read-only SSH inventory collector with redaction and mutation-command self-test.
- `docs/operations/g18-ubuntu-pro-esm-inventory.md` - operations note describing fields, scope, redaction policy, forbidden commands, and Phase 29 gate use.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md` - current redacted per-host G18 inventory.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-SUMMARY.md` - this summary.

## Inventory Results

| Host | Pro attached | ESM Apps | ESM Infra | Upgradable total | ESM Apps upgrades | Reboot required | Disk | Landscape | Sensitive services |
|---|---:|---|---|---:|---:|---|---|---|---|
| atius-srv-1 | true | enabled | enabled | 44 | 15 | no | `/`, `/boot`, `/var` at 86% warning | registration check returned no; client active | xrdp, xrdp-sesman, pm2-ubuntu, k3s active |
| atius-srv-2 | true | enabled | enabled | 10 | 3 | no | `/`, `/boot`, `/var` at 86% warning | registration check returned no; client active | xrdp, xrdp-sesman, pm2-ubuntu, k3s active |
| atius-srv-3 | true | enabled | enabled | 21 | 15 | no | `/`, `/boot`, `/var` at 61% ok | registration check returned no; client active | xrdp, xrdp-sesman, k3s active; pm2-ubuntu inactive/not-found |

## Phase 29 Gate Inputs

- Ubuntu Pro is attached and ESM Apps/Infra are enabled on all three hosts.
- Approved token file paths returned missing on all three hosts; Phase 29 must not rely on detach/attach fallback until the token path is restored or an alternate gate is approved.
- OCI snapshot metadata is present in repo inventory for all three hosts, but values are still `pending-*` style offline records from Phase 15.
- GDrive backup base is present for SRV-1/SRV-2/SRV-3.
- SRV-1 and SRV-2 disk usage is at warning level; review before any package mutation.
- Landscape client service is active/enabled, but `landscape-config --is-registered` returned no on all three; Phase 29 needs SaaS/UI validation or agent re-registration gate.

## Verification

Executed:

```bash
python3 -m py_compile scripts/g18-pro-esm-inventory.py
python3 scripts/g18-pro-esm-inventory.py --self-test
python3 scripts/g18-pro-esm-inventory.py --dry-run-commands
python3 scripts/g18-pro-esm-inventory.py --hosts atius-srv-1,atius-srv-2,atius-srv-3 --output .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md
test -s .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md
rg -n "G18-01|G18-02|atius-srv-1|atius-srv-2|atius-srv-3|No live mutation executed" .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md
rg -n "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}|\\b[ac]A[A-Za-z0-9_-]{12,}\\b|[A-Fa-f0-9]{64}" .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md || true
```

The secret scan returned no matches.

## No Live Mutation Evidence

Only read-only SSH probes were run. The collector self-test rejects these mutation classes:

- `apt update`, `apt upgrade`, `apt full-upgrade`, install/remove/purge/autoremove.
- `pro attach`, `pro detach`, `pro refresh`, `pro enable`, `pro disable`.
- `systemctl start/stop/restart/reload/enable/disable`.
- non-registration `landscape-config` mutation.
- `pm2 restart`, `pm2 kill`, `pm2 save`, `pm2 resurrect`.
- webhook POST via `curl`, `http`, or `wget`.

Phase 28 did not run live apt upgrade, apt full-upgrade, autoremove, package install/remove, XRDP/RDP restart, PM2 restart, Landscape mutation, or webhook POST.

## Decisions Made

- Kept the collector dependency-free to avoid package installation during a read-only/prep phase.
- Reported token state through file metadata only; no token read/hash/copy was performed.
- Treated current apt cache as the source for upgradable package counts because `apt update` is a mutation and is forbidden in Phase 28.
- Did not update git history or make per-task commits because the user explicitly prohibited commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Landscape validator false positive**
- **Found during:** Task 1 self-test
- **Issue:** The mutation-command regex rejected `command -v landscape-config`, even though it is a binary presence check.
- **Fix:** Normalized that exact binary detection in the validator while still allowing only `landscape-config --is-registered`.
- **Files modified:** `scripts/g18-pro-esm-inventory.py`
- **Verification:** `python3 scripts/g18-pro-esm-inventory.py --self-test`
- **Committed in:** skipped by operator constraint

**2. [Rule 1 - Bug] Fixed webhook POST rejection**
- **Found during:** Task 1 self-test
- **Issue:** `curl -X POST ...` was not rejected because the regex used an invalid word-boundary expectation before `-X`.
- **Fix:** Reworked the POST patterns for `curl`, `http`, and `wget`.
- **Files modified:** `scripts/g18-pro-esm-inventory.py`
- **Verification:** `python3 scripts/g18-pro-esm-inventory.py --self-test`
- **Committed in:** skipped by operator constraint

**3. [Rule 1 - Bug] Fixed probe table parsing**
- **Found during:** Task 2 report verification
- **Issue:** `stat -c` emitted literal `\t`, so apt source metadata parsed empty; `systemctl` output line breaks broke service rows.
- **Fix:** Switched probe delimiters to `|`, captured service state before printing, and labeled disk rows by requested path.
- **Files modified:** `scripts/g18-pro-esm-inventory.py`
- **Verification:** regenerated inventory and confirmed apt sources/services/disk rows with `rg`
- **Committed in:** skipped by operator constraint

**4. [Rule 1 - Bug] Reduced over-redaction of apt source filenames**
- **Found during:** Task 2 report inspection
- **Issue:** Generic token-like redaction masked a long apt source filename that was not a secret.
- **Fix:** Restricted generic token-like matching to long alphanumeric/underscore strings while keeping email/account/contract/hash redaction.
- **Files modified:** `scripts/g18-pro-esm-inventory.py`
- **Verification:** `python3 scripts/g18-pro-esm-inventory.py --self-test` and regenerated inventory
- **Committed in:** skipped by operator constraint

**Total deviations:** 4 auto-fixed (2 blocking/validation, 2 report correctness).
**Impact on plan:** All fixes were necessary for the collector to satisfy the plan's correctness and safety criteria. No scope was added.

## Issues Encountered

- The repository was already dirty with many unrelated modified/untracked files before this execution. Only Plan 28-01 files were created or modified.
- Graphify status path from AGENTS.md (`~/.Codex/get-shit-done/bin/gsd-tools.cjs`) did not exist; the available fallback at `~/.codex/gsd-core/bin/gsd-tools.cjs` reported Graphify fresh (`commit_stale=false`).
- Per-task and final GSD commits were skipped because the operator explicitly prohibited commits.

## Known Stubs

None.

## Threat Flags

None beyond the plan threat model. The new SSH collector uses the planned local repo -> SRV SSH trust boundary and writes only redacted Markdown.

## TDD Gate Compliance

Task 1 used the planned built-in `--self-test` gate. Formal TDD RED/GREEN commits were not created because commits were explicitly prohibited for this execution.

## User Setup Required

Before Phase 29 mutation:

- Restore or explicitly approve an alternate Ubuntu Pro token path if detach/attach fallback is still needed.
- Review SRV-1/SRV-2 disk warning state.
- Validate or re-register Landscape SaaS state because the local registration check returned no on all three hosts.

## Next Phase Readiness

Plan 28-02 can consume `28-01-G18-INVENTORY.md` to produce the upgrade runbook, per-host checklist, and rollback protocol. Phase 29 must remain gated until token-path, disk-warning, Landscape, backup/snapshot, and operator approval checks are closed.

## Self-Check: PASSED

- Found all created files: collector, operations doc, inventory report, and summary.
- `python3 -m py_compile scripts/g18-pro-esm-inventory.py` passed.
- `python3 scripts/g18-pro-esm-inventory.py --self-test` passed.
- Inventory report contains G18-01/G18-02, all three required hosts, and "No live mutation executed".
- Secret scan found no account emails, account IDs, contract IDs, or 64-character token/hash values in the inventory or summary.
- Graphify status checked after file changes; fallback `~/.codex/gsd-core/bin/gsd-tools.cjs` reported `commit_stale=false`.

---
*Phase: 28-g18-ubuntu-pro-esm-fleet-gates*
*Completed: 2026-06-24*
