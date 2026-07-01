---
phase: 28-g18-ubuntu-pro-esm-fleet-gates
verified: 2026-06-24T22:26:32Z
status: passed
score: "10/10 must-haves verified"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "Live apt upgrade execution and post-mutation RDP/Landscape/regression validation"
    addressed_in: "Phase 29"
    evidence: "ROADMAP Phase 29 success criteria cover gated apt upgrade, Microsoft RDP/XRDP validation, Landscape SaaS evidence, PM2/K3s/Apache/observability checks and repeatable regression runbook."
---

# Phase 28: G18 Ubuntu Pro/ESM Fleet Gates Verification Report

**Phase Goal:** Consolidar estado Ubuntu Pro/ESM dos SRV-1/SRV-2/SRV-3, preparar upgrade com backup/checkpoint e travar todos os gates antes de qualquer apt upgrade live.  
**Verified:** 2026-06-24T22:26:32Z  
**Status:** passed  
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | SRV-1/SRV-2/SRV-3 have Ubuntu Pro/ESM state documented per host. | VERIFIED | `28-01-G18-INVENTORY.md` has per-host sections for `atius-srv-1`, `atius-srv-2`, `atius-srv-3` with attached state, `esm-apps`, `esm-infra`, kernel, OS and Pro client data (lines 50-65, 183-198, 288-303). |
| 2 | Token/account/attach status and apt sources, including DEB822, are clear without secret leakage. | VERIFIED | Inventory records `account identity` and `contract identity` as `present/redacted`; token paths are metadata-only and missing, not copied; apt sources list one-line and DEB822 files per host. Secret scan over phase artifacts returned no emails, account/contract IDs, 64-char hashes or token assignments. |
| 3 | Apt sources, ESM services, pending packages, held packages, reboot flag, disk and sensitive service state are captured per host. | VERIFIED | Inventory contains apt source tables, upgradable package totals, held package sections, reboot state, disk capacity and `landscape-client`/`xrdp`/`xrdp-sesman`/`pm2-ubuntu`/`k3s` state for each host. |
| 4 | Backup/snapshot/checkpoint readiness is visible before Phase 29 can mutate hosts. | VERIFIED | Inventory includes OCI snapshot metadata and GDrive backup base per host; gate docs classify pending OCI snapshots and missing checkpoint artifacts as `BLOCK` with clearing artifacts. |
| 5 | Operator has a per-host preflight checklist before any package mutation. | VERIFIED | `28-02-G18-UPGRADE-GATES.md` defines the gate rule and PASS/BLOCK checklist for all three hosts, with every host currently `BLOCK` until Phase 29 evidence exists. |
| 6 | Snapshot, backup and checkpoint requirements are explicit for SRV-1/SRV-2/SRV-3. | VERIFIED | `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` requires per-host bundle files, real `ocid1.image...` or exception, backup path and `checkpoint.md` with host/scope/snapshot/backup/posture/timestamp. |
| 7 | Phase 29 cannot proceed without operator approval record and fresh inventory. | VERIFIED | Runbook and handoff require one approval record per host; chat approval is insufficient unless it includes host, scope, snapshot/exception, backup path, posture and timestamp. |
| 8 | Phase 28 artifacts do not execute or authorize live apt upgrade, apt update, service restart, PM2/XRDP action, Landscape mutation or webhook POST. | VERIFIED | `scripts/g18-pro-esm-inventory.py --self-test` passed; `--dry-run-commands` listed only read-only probes. Forbidden-command scan found matches only in documentation/prohibition text and self-test rejection strings, not in executable probe allowlist. |
| 9 | Rollback protocol covers OCI restore path, package rollback inputs, Pro/ESM attachment/source state, Landscape state and XRDP references. | VERIFIED | Runbook rollback table covers package rollback, Pro/ESM source/attach regression, Landscape client/SaaS state, RDP/XRDP login regression, OCI restore, and no-real-snapshot exception paths. |
| 10 | Rollback and post-upgrade smoke-test handoff are ready for Phase 29 scope. | VERIFIED | `28-PHASE29-HANDOFF.md` defines Phase 29 entry blockers, package scope, snapshot/backup handoff, rollback inputs, RDP/XRDP posture, Landscape handoff and completion criteria. Detailed live execution and post-upgrade validation are deferred to Phase 29 by roadmap. |

**Score:** 10/10 truths verified (0 present, behavior-unverified)

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | Live apt upgrade execution and post-mutation RDP/Landscape/regression validation. | Phase 29 | ROADMAP Phase 29 success criteria require gated apt upgrade, Microsoft RDP/XRDP validation, Landscape SaaS online/blocker evidence, PM2/K3s/Apache/observability checks and repeatable regression runbook. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/g18-pro-esm-inventory.py` | Read-only, redacting fleet inventory collector | VERIFIED | Exists, 922 lines, Python compiles, self-test passes, host allowlist rejects unsupported hosts, and probe allowlist is read-only. |
| `docs/operations/g18-ubuntu-pro-esm-inventory.md` | Canonical inventory procedure and field definitions | VERIFIED | Defines command, allowed hosts, collected fields, redaction policy, forbidden mutations and Phase 29 gate use. |
| `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md` | Current redacted per-host inventory and backup manifest | VERIFIED | Covers all three required hosts with Pro/ESM, token metadata, apt sources, package, service, disk and backup/snapshot state. |
| `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` | Canonical Phase 29 gate/runbook and rollback protocol | VERIFIED | Defines hard boundary, source inputs, PASS/REVIEW/BLOCK semantics, preflight bundle, per-host gates, approval record and rollback protocol. |
| `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md` | Per-host gate checklist generated from 28-01 inventory | VERIFIED | Contains PASS/BLOCK gate checklist for SRV-1/SRV-2/SRV-3 and exact clearing artifacts for each blocker. |
| `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md` | Explicit handoff from read-only Phase 28 to gated Phase 29 | VERIFIED | Names Phase 29-only work, current blockers, approval fields, package scope, snapshot/backup handoff, rollback inputs and completion criteria. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/g18-pro-esm-inventory.py` | `inventory/hosts/atius-srv-{1,2,3}.yaml` | `load_host_inventory()` | VERIFIED | The automated key-link checker missed this because the literal filename is constructed. Manual evidence: script allowlist at line 27, path construction at line 172, `--dry-run-commands` output lists all three inventory files. |
| `scripts/g18-pro-esm-inventory.py` | `28-01-G18-INVENTORY.md` | default output and `write_text()` | VERIFIED | Default output path is defined in the script and `main()` writes rendered Markdown to that path. |
| `28-01-G18-INVENTORY.md` | `28-02-G18-UPGRADE-GATES.md` | checklist consumes current inventory facts | VERIFIED | Checklist states it is produced from `28-01-G18-INVENTORY.md` and repeats current per-host package, disk, Landscape, token and snapshot facts. |
| `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` | Phase 29 handoff/roadmap | Phase 29-only mutation gates | VERIFIED | Runbook and handoff identify live apt mutation, RDP validation, Landscape confirmation and PM2/XRDP repair as Phase 29-only gated work. |
| `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` | `docs/operations/oci-snapshots.md` and `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` | rollback/source inputs | VERIFIED | Both referenced docs exist; OCI doc covers snapshot/restore drill gates and network map covers XRDP `:1`/`5901` posture. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/g18-pro-esm-inventory.py` | `hosts`, `probes`, parsed host report | Host YAML plus SSH read-only probes in `collect_host()` | Yes | FLOWING - host YAML provides SSH/OCI/GDrive metadata and probe output populates Pro, token, apt, package, disk, service and Landscape fields. |
| `28-01-G18-INVENTORY.md` | per-host inventory tables | Generated report from collector | Yes | FLOWING - report includes concrete host targets, Pro/ESM states, package counts and backup/snapshot metadata for each SRV. |
| `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` | fleet baseline and per-host gate statuses | `28-01-G18-INVENTORY.md` | Yes | FLOWING - baseline table and per-host gates mirror actual inventory facts and convert missing inputs into BLOCK/REVIEW items. |
| `28-02-G18-UPGRADE-GATES.md` | PASS/BLOCK checklist | `28-01-G18-INVENTORY.md` plus runbook gate semantics | Yes | FLOWING - each host checklist includes current evidence and clearing artifacts. |
| `28-PHASE29-HANDOFF.md` | Phase 29 blockers/scope/rollback inputs | 28-02 gates and roadmap Phase 29 boundary | Yes | FLOWING - handoff preserves current blockers and defines Phase 29-only work. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Collector syntax and local safety tests pass. | `python3 -m py_compile scripts/g18-pro-esm-inventory.py && python3 scripts/g18-pro-esm-inventory.py --self-test` | `self-test: ok` | PASS |
| Dry-run lists read-only commands without SSH probes. | `python3 scripts/g18-pro-esm-inventory.py --dry-run-commands` | Printed command classes and `No SSH probes were executed in this mode.` | PASS |
| Unsupported host is rejected. | `python3 scripts/g18-pro-esm-inventory.py --hosts atius-srv-1,evil-host --dry-run-commands` | Exit 2 with `unsupported host(s): evil-host; allowed: atius-srv-1, atius-srv-2, atius-srv-3` | PASS |
| Inventory report contains all host state sections. | `rg -n "^## atius-srv-[123]$|Ubuntu Pro attached|esm-apps|esm-infra|### Apt sources|### Upgradable packages|### Sensitive service state|### Backup and snapshot manifest" 28-01-G18-INVENTORY.md` | Found required sections for all three hosts. | PASS |
| Gate/runbook/handoff contain required G18-02 markers. | `test -s ... && rg -n "G18-02|atius-srv-1|atius-srv-2|atius-srv-3|operator approval|snapshot ID|backup path|rollback|Phase 29-only|No Phase 28 live mutation" ...` | Found all required markers in runbook, checklist and handoff. | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| Conventional phase probes | `find scripts -path '*/tests/probe-*.sh' -type f` | No `probe-*.sh` files found or declared for this phase. | SKIP - not applicable |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| G18-01 | 28-01 | Operator can see Ubuntu Pro/ESM state for SRV-1/SRV-2/SRV-3, including token/account, attach status, services, apt sources and pending items by host. | SATISFIED | `28-01-G18-INVENTORY.md` covers all required fields per host and redacts token/account/contract details. |
| G18-02 | 28-01, 28-02 | Operator can execute an ESM Apps/infra apt upgrade plan with preflight, snapshot/backup/checkpoint and explicit gate before live mutation. | SATISFIED for Phase 28 scope | Runbook/checklist/handoff provide preflight, snapshot/backup/checkpoint blockers, approval record, rollback protocol and Phase 29-only mutation boundary. Live execution remains Phase 29 by roadmap and user constraint. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| - | - | No `TBD`, `FIXME`, `XXX`, `TODO`, placeholder/stub patterns, hardcoded rendered empty data, or console-only handlers found in Phase 28 artifacts. | none | No blocker. |
| phase artifacts | various | Forbidden command strings | info | Matches are explicit prohibition text or self-test rejected examples only; executable probe allowlist is read-only and `--self-test` passed. |
| phase artifacts | various | Secret scan | none | No emails, account/contract IDs, 64-character hashes or token assignments found in phase reports/docs. |

### Human Verification Required

None. The phase deliverable is repository/runbook readiness and read-only collector behavior. Live host mutation and post-upgrade validation are intentionally deferred to Phase 29.

### Gaps Summary

No blocking gaps found. Phase 28 achieved the goal: current Pro/ESM state is documented, token/source/package/service/backup gate inputs are visible, Phase 29 mutation gates are locked behind explicit approval and fresh preflight evidence, and Phase 28 artifacts do not execute or authorize live mutation.

---

_Verified: 2026-06-24T22:26:32Z_  
_Verifier: the agent (gsd-verifier)_
