---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-14
status: superseded-for-m005-by-gdrive-dr
branch: docs/m005-gate-review-20260614
mode: read-only-evidence-to-runbook
---

# Phase 13 OCI Rollback Path - 2026-06-14

## 2026-06-15 M005 Decision

This OCI snapshot gate is superseded for M005.

User decision: do not require OCI snapshot IDs because the snapshots would add
storage cost. The M005 rollback gate is now:

```text
GDrive backup bundle + checksum + restore drill validado
```

This document remains useful as a future paid/OCI rollback option, but it is no
longer a release blocker for M005.

## Verdict

Rollback is only partially closed.

Current evidence is enough for:

- cluster-level rollback from K3s/etcd and local host backups;
- PVC/archive recovery from the local backup bundle;
- manual rebuild of a node if the operator accepts a slower rebuild path.

Current evidence is not enough for:

- deterministic OCI infrastructure rollback at the boot-volume/block-volume layer;
- proving that each OCI account has a restorable point-in-time snapshot/backup for the exact pre-M005 state;
- restoring a destroyed or unrecoverable node from a known OCI snapshot OCID without opening the OCI console and rediscovering everything manually.

Formal M005 gate status: `SUPERSEDED`. Use the GDrive DR gate in `13-01-PLAN.md`.

## Evidence that exists now

### Cluster/application recovery evidence

- K3s HA cluster is live on `atius-srv-1`, `atius-srv-2`, `atius-srv-3`.
- Post-bootstrap etcd snapshot exists: `atius-post-bootstrap-20260614-000034-atius-srv-1-1781406035`.
- Preflight critical host backups exist:
  - SRV-1: `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-1-20260613-235405.tgz`
  - SRV-2: `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-2-20260613-235406.tgz`
  - SRV-3: `/home/ubuntu/.backups/k3s-preflight/critical-ATIUS-SRV-3-20260614-025406.tgz`
- Crash-consistent PVC backup bundle exists: `/home/ubuntu/.backups/k3s-local-path/20260614-150944`
- Repo/vault history already records that formal OCI snapshot IDs were not captured at bootstrap time.

### OCI account evidence that exists now

Read-only checks confirmed:

- `oci` CLI is absent locally and on SRV-2/SRV-3.
- `/home/ubuntu/.oci` is absent locally and on SRV-2/SRV-3.
- prior gate review states the same absence locally and on SRV-1/SRV-2/SRV-3.
- OCI instance metadata is readable from IMDS and gives instance/account identity, but not volume snapshot/backup OCIDs.

## OCI account matrix

| Host | Role | Region | Tenancy / account OCID | Compartment OCID | Instance OCID | Local `oci` CLI | Local `~/.oci` | Formal OCI rollback artifact recorded |
|---|---|---|---|---|---|---|---|---|
| SRV-1 / `atius-srv-1` | control-plane, etcd | `sa-saopaulo-1` | `ocid1.tenancy.oc1..aaaaaaaa2jk4xdv5vhonmqiqqq552rstygttzo4o44gfrr7rvyo6yraykm2q` | `ocid1.compartment.oc1..aaaaaaaa5s4cimfur7gpfukjsqjhvywbdh66hngxmpj4iexmb6vwwmix76ta` | `ocid1.instance.oc1.sa-saopaulo-1.antxeljr7yjj2jacsuaeho7denrimjq3rcdwiu6tquznfyzojh3y6gp6byxa` | no | missing | no |
| SRV-2 / `atius-srv-2` | control-plane, etcd | `sa-saopaulo-1` | `ocid1.tenancy.oc1..aaaaaaaak3xdo2qehjkfvmbd7yf2u3mne4vspsyvog5lcaxngr22ct5prgja` | `ocid1.compartment.oc1..aaaaaaaanlmccbworgkibnxgfk2kmxfy5ksnnflgql4fz55xengo4ondt74q` | `ocid1.instance.oc1.sa-saopaulo-1.antxeljrgeqoebicatf5mokc32esnepjhlfuwjveyfkcniekdsvqwwnpk77a` | no | missing | no |
| SRV-3 / `atius-srv-3` | control-plane, etcd | `sa-saopaulo-1` | `ocid1.tenancy.oc1..aaaaaaaauynth7zyfuwkrkca7dth7wskpee3bv46wxsv7tm4idjata5aszna` | `ocid1.tenancy.oc1..aaaaaaaauynth7zyfuwkrkca7dth7wskpee3bv46wxsv7tm4idjata5aszna` | `ocid1.instance.oc1.sa-saopaulo-1.antxeljrkwnr6vycazn2fwpnp724cleupoxy6qu2cgqm7j6ln2jw43jyogsq` | no | missing | no |

## What is missing per OCI account

The missing item is not just "a snapshot ID". The gate only closes when the operator records the full restore chain below for each account.

### Mandatory per-host OCI restore chain

For each of SRV-1, SRV-2 and SRV-3, record:

1. `instance_ocid`
2. `tenancy_ocid`
3. `compartment_ocid`
4. `region`
5. `availability_domain`
6. `shape`
7. `boot_volume_ocid`
8. `boot_volume_backup_or_snapshot_ocid`
9. `boot_volume_backup_or_snapshot_name`
10. `boot_volume_backup_or_snapshot_time_created`
11. `boot_volume_backup_or_snapshot_lifecycle_state`
12. every attached block volume OCID, if any
13. the corresponding block-volume backup/snapshot OCID for each attached block volume
14. restore target notes:
    - same instance overwrite vs new boot volume restore;
    - same subnet/VNIC reuse vs reattach/new instance path;
    - expected hostname/private IP/public IP after restore.

### Why this is mandatory

Without items 7-14, the rollback path remains ambiguous in three different ways:

- the operator may know the instance but not the boot volume that must be restored;
- the operator may have a snapshot visible in the console but not know whether it is pre-M005 and complete;
- the operator may restore storage but still not know the exact attachment/network shape needed to bring the node back with the same addressing.

## Exact rollback path available today

### Path A - cluster/data rollback without OCI rebuild

Use only if the nodes are still alive and the issue is logical/software-level.

1. Stop new M005 mutations.
2. Preserve fresh diagnostics before reverting.
3. Restore K3s state from the saved etcd snapshot.
4. Restore PVC/application data from `/home/ubuntu/.backups/k3s-local-path/20260614-150944`.
5. If needed, unpack the per-host `critical-ATIUS-SRV-*` archives to recover host-side configs/scripts/secrets that were captured preflight.

This path is evidence-backed now.

### Path B - host rebuild rollback without formal OCI snapshot IDs

Use only if a node is damaged and Path A is insufficient.

1. Recreate or repair the OCI instance manually in the correct account/region.
2. Reapply baseline OS/networking by hand.
3. Restore host files from the `critical-ATIUS-SRV-*` archive.
4. Rejoin/rebuild K3s from cluster backup material.

This path is possible but slow and operator-dependent. It is not a clean rollback gate.

### Path C - deterministic OCI infrastructure rollback

Desired path:

1. Open the correct OCI account for the target host.
2. Locate the exact pre-M005 boot-volume backup/snapshot OCID.
3. Restore the boot volume from that artifact.
4. Restore any extra block volumes from their matching backup/snapshot OCIDs.
5. Reattach/recreate the instance with the same network placement and expected IP behavior.
6. Validate host boot, WireGuard, K3s membership, and edge services.

This path is currently blocked because the required OCIDs and restore notes are not recorded.

## Manual collection path in OCI console

Repeat once in each OCI account:

1. Switch to the account/tenancy that owns the target server.
2. Confirm `Region = sa-saopaulo-1`.
3. Open the target instance by `Instance OCID` or display name:
   - `atius-srv-1`
   - `atius-srv-2`
   - `atius-srv-3`
4. Record from the instance page:
   - instance OCID
   - compartment
   - availability domain
   - shape
   - VNIC/private IP/public IP references
5. Open the attached boot volume record and record:
   - boot volume OCID
   - latest pre-M005 backup/snapshot OCID
   - backup/snapshot name
   - creation timestamp
   - lifecycle state
6. Open attached block volumes, if any, and record for each:
   - block volume OCID
   - matching pre-M005 backup/snapshot OCID
   - creation timestamp
   - lifecycle state
7. Capture one explicit restore note per host:
   - "restore in place" or "restore to new volume/new instance"
   - whether the original IP identity is preserved automatically or requires reattachment/manual reassignment.

## API/CLI collection path

Run from any trusted workstation that has OCI API access for the target account. It does not need to be SRV-1/2/3, but it must be authenticated into the correct tenancy.

For each account, collect the same fields from these OCI object families:

1. Compute instance
2. Boot volume attachments
3. Boot volume backups/snapshots
4. Block volume attachments
5. Block volume backups/snapshots
6. VNIC/network attachment data needed to restore the host identity

Minimum output that must be persisted for the gate:

- the OCIDs listed in "Mandatory per-host OCI restore chain";
- human-readable names;
- creation times;
- lifecycle states;
- enough network attachment detail to rebuild the node without guessing.

If CLI is used, the operator must save the raw command output or a sanitized JSON extract, not only copy/paste an OCID by hand.

## Non-ambiguous gate closure criteria

The OCI rollback gate closes only when all conditions below are true:

1. There is one recorded OCI restore chain for SRV-1.
2. There is one recorded OCI restore chain for SRV-2.
3. There is one recorded OCI restore chain for SRV-3.
4. Each chain includes both the source volume OCIDs and the pre-M005 backup/snapshot OCIDs.
5. Each chain states how the restored node will recover network identity.
6. The recorded artifacts are stored in repo/vault/runbook form where the operator can use them during an outage without browsing history.
7. The recorded snapshot/backup timestamp is explicitly pre-M005 or explicitly accepted as the chosen rollback point.

If any one of those is missing, the gate remains `BLOCK`.

## Recommended follow-up artifact

After collecting the OCI data, append or create a short structured record with one block per host:

```text
host:
account_tenancy_ocid:
compartment_ocid:
region:
availability_domain:
shape:
instance_ocid:
boot_volume_ocid:
boot_volume_backup_or_snapshot_ocid:
boot_volume_backup_or_snapshot_name:
boot_volume_backup_or_snapshot_time_created:
attached_block_volumes:
  - volume_ocid:
    backup_or_snapshot_ocid:
    time_created:
network_restore_notes:
rollback_point_accepted_by:
rollback_point_accepted_at:
```

That is the smallest record that removes ambiguity.
