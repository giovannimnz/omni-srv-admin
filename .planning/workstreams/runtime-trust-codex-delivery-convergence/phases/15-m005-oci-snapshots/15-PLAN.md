---
phase: 15
padded: 15
slug: m005-oci-snapshots
name: M005 OCI Snapshots
date: 2026-06-15
status: ready
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - OCI-01
  - OCI-02
  - OCI-03
---

# Phase 15: M005 OCI Snapshots

## Goal

Fechar o follow-up de M005 sobre OCI snapshot workflow: criar snapshots
formais para SRV-1/2/3 antes de operações de risco, registrar IDs no
inventário e no DbOmniFleet, validar restore drill end-to-end.

## Motivation

M005 fechou com 4 follow-ups abertos. O mais importante é rollback
formal: hoje, se uma operação em produção quebrar um node, o caminho de
recuperação é "reinstalar e re-aderir ao K3s manualmente", o que pode
levar horas. Com snapshots OCI versionados, o mesmo cenário é
"clonar do snapshot, validar K3s rejoins, done".

## Tasks

### Task 1: oci-snapshot CLI command

Add `omni srv oci snapshot preflight` and `omni srv oci snapshot routine`
to `cli/omni/srv1_ops.py` (or new module `cli/omni/oci.py`).

`preflight` is interactive: confirms user gate, calls OCI API
`instance action stop` if needed, then `createImage`, captures
`ImageId`, prints to stdout and stores in
`/home/ubuntu/.local/state/omni/oci-last-snapshot.json`.

`routine` is non-interactive: runs `createImage` (without stop), stores
ID. Called by systemd timer weekly.

### Task 2: inventory + DbOmniFleet registration

Update `inventory/hosts/<srv>.yaml`:

```yaml
oci:
  last_snapshot_id: "ocid1.image.oc1.iad.aaaaaaa..."
  last_snapshot_at: "2026-06-15T08:00:00Z"
  routine_schedule: "weekly Sun 04:00 BRT"
```

Mirror to `DbOmniFleet` via the existing `omni fleet config set`
command (key: `srv.<host_id>.oci.snapshot_id`).

### Task 3: restore drill validation

Add `omni srv oci restore-drill <snapshot_id> [--dry-run]`:

- Reads snapshot ID from inventory or CLI arg
- Calls OCI API `launchInstance` with `sourceDetails: { sourceType: "image", imageId: <id> }`
- Waits for `RUNNING` state
- SSH to new instance, validates `kubectl get nodes` shows it Ready
- Tears down: `terminateInstance`
- Logs the drill to `/home/ubuntu/.logs/oci/restore-drill-<ts>.log`

### Task 4: runbook + phase-SUMMARY

- `docs/operations/oci-snapshots.md` — full source of truth
- 15-SUMMARY.md — tasks, deviations, verification

## Success Criteria

- [ ] `omni srv oci snapshot preflight` interactive, gated
- [ ] `omni srv oci snapshot routine` non-interactive, systemd timer
- [ ] `inventory/hosts/<srv>.yaml` shows `last_snapshot_id` and `last_snapshot_at`
- [ ] `omni srv oci restore-drill <id>` can be dry-run without OCI calls
- [ ] At least 1 successful drill on SRV-1 (or DR runbook + dry-run if user defers live)
- [ ] `docs/operations/oci-snapshots.md` exists and is the source of truth

## Risks

- **Cost:** OCI block storage ~$0.025/GB/month. 200GB snapshot × 3 nodes = ~$15/month total. Documented as "minimal cost vs. time savings on rollback".
- **Snapshot during heavy IO:** snapshots of running instances are crash-consistent (not application-consistent). For PM2 daemons, we may need `pm2 save` first. Documented.
- **Quorum during restore drill:** if the drill runs while K3s is mid-operation, the new node could disrupt etcd. Gate required.

## Out of Scope

- Application-level backups (PM2 dump, DB dumps) — already covered by GDrive backup flow
- Cross-region snapshots — would require OCI Object Storage bucket + cross-region replication; defer to M008 if needed
- Snapshot retention policy — start with "keep 4 weekly, delete older" and tune later

## Next Phase Readiness

Phase 16 (Cloudflare Access) and Phase 17 (Observability) are independent and can run in parallel after 15-01 lands.
