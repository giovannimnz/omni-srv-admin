# Phase 52 — Operational Decisions

**Status:** Approved
**approval_status:** approved
**Accountable/operator:** Giovanni Muniz
**Approved at:** `2026-07-22T00:51:46Z`
**Secret material present:** false

## Approved capacity constants

| Field | Approved value |
|---|---:|
| `combined_daily_log_budget_bytes` | `134217728` |
| `log_retention_days` | `30` |
| `log_reserve_30d_bytes` | `4026531840` |
| `state_growth_budget_bytes` | `4294967296` |
| `backup_a_reserve_bytes` | `4294967296` |
| `backup_b_reserve_bytes` | `4294967296` |

Unset, zero, negative, overflowed, stale, or omitted reservation terms block admission.

## Backup placement and retention

- Backup A: local on the selected candidate.
- Backup B: off-host through the existing managed `modules/fleet-backup` GDrive path.
- Retain both until Phase 57 has `PASS` plus 30 days.
- Any deletion requires a new explicit approval; reaching the retention date is not deletion authority.

## Candidate mutation authority

- `atius-srv-2`: no cleanup, reclamation, pruning, deletion, or destructive storage remediation authorized.
- `atius-srv-3`: no cleanup, reclamation, pruning, deletion, or destructive storage remediation authorized.
- On capacity failure, persist exact current `NO-GO` evidence and continue in strict order.
- Only after a candidate passes current capacity admission, the full gate may create bounded isolated reversible state: pinned artifact staging/load, state-only backups A/B, a disposable isolated restore runtime, redacted evidence, and verified rollback removal of the disposable drill artifacts.
- These writes do not authorize unrelated cleanup or storage reclamation. Missing authorization, containment, target isolation, or capacity for any bounded write is candidate `NO-GO` followed by safe rollback and fallback.

## Horistic full gate

After current `NO-GO` evidence exists for both Atius candidates, `horistic-srv` may be evaluated only through the complete supply-chain, byte/inode/reservation, Vault, two-backup, isolated restore, rollback, security, and topology-impact gate. Raw disk headroom alone is insufficient.

## Temporal topology review contract

- Phase 52: record the Horistic co-location impact before placement selection.
- Before Phase 53: review server placement, public listeners, resources, rollback, and legacy-path preservation.
- Before Phase 54: review separate server/client identities, evidence and resources; Windows-origin direct/relay proof; joint reboot recovery; separate rollback domains.
- Before Phase 57: review actual independent failure-domain capacity and failover/failback. Horistic co-location is not independent DR.

Future Phase 54/57 review artifacts are not prerequisites for starting Phase 53. Each affected phase is blocked only until its own just-in-time review is present and passing.

## Scope boundary

This approval contains no Vault values, credentials, cleanup target allowlist, Windows installation authority, production deployment authority, DNS/edge authority, or standby/failover claim.
