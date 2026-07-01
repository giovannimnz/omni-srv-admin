# Phase 29 Handoff: G18 Controlled Upgrade

**From:** Phase 28 Plan 02  
**To:** Phase 29 - G18 Controlled Upgrade, RDP and Landscape SaaS Validation  
**Mode:** handoff only; no Phase 28 live mutation

## No Phase 28 Live Mutation

No Phase 28 live mutation was executed. Phase 28 created preparation artifacts
only:

- `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md`
- `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-02-G18-UPGRADE-GATES.md`
- `.planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-PHASE29-HANDOFF.md`

Phase 29-only work:

- Live apt package mutation.
- Post-mutation Microsoft RDP/XRDP validation.
- Landscape SaaS UI confirmation.
- PM2 or XRDP restart/repair, if explicitly approved.
- Any Landscape re-registration or configuration mutation.

## Entry Gate For Phase 29

Phase 29 must start with the G18 gate still considered BLOCK until all host
approval records exist.

Required approval record per host:

```text
G18 Phase 29 operator approval

host:
inventory_report_path:
preflight_bundle_path:
snapshot_id_or_exception:
backup_path:
package_scope:
expected_reboot_posture:
expected_service_restart_posture:
rdp_validation_owner:
landscape_saas_validation_owner:
rollback_path:
operator_name:
signed_timestamp:
approval_statement:
```

Required approval statement:

```text
I approve Phase 29 package mutation for <host> using <package_scope>.
I have reviewed the inventory, snapshot/exception, backup path, rollback path,
and expected no-reboot/no-service-restart posture.
```

The approval must name the report path and backup path. "Approved in chat" is
not enough unless the chat text also includes host, scope, snapshot/exception,
backup path, posture, and timestamp.

## Current Blockers To Resolve Or Accept

| Blocker | Host(s) | Phase 29 requirement |
| --- | --- | --- |
| Fresh inventory missing for mutation window | SRV-1, SRV-2, SRV-3 | Regenerate inventory within 2h of mutation start. |
| Ubuntu Pro token path missing | SRV-1, SRV-2, SRV-3 | Restore approved token path metadata or sign no-attach-fallback exception. |
| Real OCI snapshot missing | SRV-1, SRV-2, SRV-3 | Provide real `ocid1.image...` ID or sign no-OCI-restore exception. |
| Landscape local registration returned no | SRV-1, SRV-2, SRV-3 | Provide SaaS/client evidence or sign exception before mutation. |
| Disk warning | SRV-1, SRV-2 | Accept 86% disk state with available bytes or create cleanup/checkpoint note. |
| PM2 posture ambiguous | SRV-3 | Confirm `pm2-ubuntu` not-found is expected for sandbox or create separate note. |
| Package rollback bundle missing | SRV-1, SRV-2, SRV-3 | Capture `dpkg --get-selections`, upgradable list, kernel, Pro status, and `pro collect-logs`. |

## Package Scope Handoff

Baseline from Phase 28 inventory:

| Host | Total upgradable | ESM Apps | ESM Infra | Non-ESM |
| --- | ---: | ---: | ---: | ---: |
| atius-srv-1 | 44 | 15 | 0 | 29 |
| atius-srv-2 | 10 | 3 | 0 | 7 |
| atius-srv-3 | 21 | 15 | 0 | 6 |

Phase 29 must record one explicit package scope per host:

- ESM Apps only.
- ESM Apps plus selected infra/security packages.
- All currently safe upgrades.
- Explicit include/exclude list.

Do not infer scope from the inventory alone. The package scope is an operator
approval field.

## Snapshot And Backup Handoff

OCI state from Phase 28 is not a live restore guarantee:

| Host | Current inventory snapshot | Status |
| --- | --- | --- |
| atius-srv-1 | `pending-250f...a298a94c` | BLOCK: pending/offline, not real OCI restore point |
| atius-srv-2 | `pending-ef73...9692c21e` | BLOCK: pending/offline, not real OCI restore point |
| atius-srv-3 | `pending-5c21...0e9d2d49` | BLOCK: pending/offline, not real OCI restore point |

Phase 29 must either:

1. Provide a real OCI image snapshot ID for each mutated host, or
2. Include a signed exception acknowledging that rollback will not have an OCI
   image restore path.

Backup path baseline:

| Host | GDrive backup base |
| --- | --- |
| atius-srv-1 | `ATIUS-SRV/SRV-1/Backup` |
| atius-srv-2 | `ATIUS-SRV/SRV-2/Backup` |
| atius-srv-3 | `ATIUS-SRV/SRV-3/Backup` |

The approval record must name the fresh backup/checkpoint path actually used
for the Phase 29 window, not just the baseline base path.

## Rollback Handoff

Use `docs/operations/g18-ubuntu-pro-esm-upgrade-gates.md` as the rollback
source for Phase 29.

Required rollback inputs:

- Pre-mutation `dpkg --get-selections`.
- Pre-mutation upgradable list.
- Package scope and apt logs from the mutation window.
- Pre-mutation kernel capture.
- Redacted Pro status and `pro collect-logs` path.
- Apt source manifest.
- RDP/XRDP baseline reference and config backup path if XRDP is touched.
- Landscape SaaS/client evidence.
- Real OCI snapshot ID or signed exception.

Rollback decision rules:

- Package issues with SSH intact: use package-level rollback from captured
  package versions and selections.
- Pro/ESM source/attach issues: use redacted Pro status, source manifest, and
  approved secret path without exposing token values.
- Landscape issues: observe client and SaaS state first; re-registration is a
  gated Phase 29 action.
- RDP issues: preserve display `:1` primary posture from the network map; any
  XRDP restart/repair must be explicitly approved.
- Host inaccessible or corrupted: use OCI restore only if a real snapshot ID
  exists.

## RDP/XRDP Handoff

Canonical current target:

- Human XRDP range: `:1..14`.
- Primary display for SRV-1/SRV-2/SRV-3: `:1`.
- VNC mapping for primary display: `5901`.
- Resolution is controlled by the RDP client for the human XRDP range.
- `:15..30` is reserved for headless/browser helpers.
- `:31..60` is legacy/overflow only.

Phase 29 should validate Microsoft RDP after mutation, but Phase 28 does not
restart or change XRDP.

## Landscape Handoff

Phase 28 local inventory found:

- `landscape-client` active/enabled on SRV-1, SRV-2, SRV-3.
- `landscape-config --is-registered` returned no on all three.
- Landscape client package version: `24.02-0ubuntu5.7`.

Phase 29 must decide whether SaaS UI evidence is enough, whether the local
registration check needs investigation, or whether a re-registration action is
approved. Self-hosted Landscape remains out of scope for G18.

## Completion Criteria For Phase 29

Phase 29 can close G18-02/G18-03/G18-04/G18-05 only after:

1. Approved package mutation executes within the recorded scope.
2. Post-mutation Pro/ESM state is captured and still attached/enabled.
3. `apt list --upgradable` and reboot-required state are captured after mutation.
4. Microsoft RDP works on SRV-1, SRV-2, and SRV-3 or a blocker is documented.
5. Landscape SaaS UI shows all three online or a blocker is documented.
6. PM2, K3s, Apache edges, and observability checks are run without unauthorized restart.
7. Rollback artifacts are retained with no secret leakage.

## Handoff Status

Phase 28 is complete when the runbook, checklist, handoff, and summary exist.
Phase 29 is not approved to mutate hosts until the approval records above are
filled and signed.

