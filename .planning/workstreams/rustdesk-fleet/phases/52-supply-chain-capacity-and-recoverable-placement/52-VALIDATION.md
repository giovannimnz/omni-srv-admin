---
phase: 52
slug: supply-chain-capacity-and-recoverable-placement
status: passed
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-20
updated: 2026-07-22T22:37:00Z
---

# Phase 52 — Validation Strategy

> Complete task-level map for immutable supply, approved exact capacity, zero-cleanup fallback, Vault-only recovery, candidate-scoped full gates and report/Graphify closeout.

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest 7.4.4 + Python 3.12.3 standard library |
| Focused suite | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q` |
| Full suite | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests -q` |
| Live gate | `omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/validate_phase52.py --repo . --json-out .planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-GATE-REPORT.json --markdown-out .planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-GATE-REPORT.md` |
| CPU policy | Every pytest full/focused run and CPU-heavy image/hash/archive/restore/Graphify operation uses the `builds` profile. |

## Per-Task Verification Map

| Task ID | Plan/Wave | Requirements | Threats | Secure behavior | Automated command | W0 dependency | Status |
|---|---|---|---|---|---|---|---|
| 52-01-01 | 01/1 | SCP-04 | T52-SUPPLY-TAG, T52-SUPPLY-OCI | Exact pins/schema/architecture; drift and mutable refs fail closed | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'supply and not live'` | validator + test file | pass |
| 52-01-02 | 01/1 | SCP-04 | T52-SUPPLY-ASSET, T52-WINDOWS-EARLY | Fresh official resolution; MSI staged only; no target build/install | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k supply` | supply observation | pass |
| 52-02-01 | 02/2 | SRV-01 | T52-CAP-ROUND, T52-CAP-OMIT, T52-CAP-FINAL, T52-PLACEMENT | D-04/D-05 exact constants, bounded-write allowlist and eight-stage vector including capacity_finalize; partial selection rejected | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'capacity or placement'` | capacity/placement contracts + fixtures | pass |
| 52-02-02 | 02/2 | SRV-01 | T52-REMEDIATION, T52-SSH | Approval digest exact, two samples/candidate, mutation false, no new checkpoint | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'capacity or approval or placement'` | capacity proposal | pass |
| 52-03-01 | 03/3 | SRV-01 | T52-CLEANUP, T52-TOCTOU | D-06 rejects destructive/unallowlisted mutation while keeping this preflight read-only; bounded writes remain gated on capacity PASS | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'zero_cleanup or capacity or routing'` | live capacity seam | pass |
| 52-03-02 | 03/3 | SRV-01 | T52-SERIAL, T52-COLOC-CAP | Persisted srv2/srv3 NO-GO precede Horistic preflight; no placement yet | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'capacity or placement or routing'` | capacity evidence set | pass |
| 52-04-01 | 04/4 | SRV-05 | T52-VAULT-ACCESS, T52-VAULT-LEAK, T52-DISTINCTNESS | Exact refs, tmpfs/modes/no-output, aggregate-only distinctness | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'vault or hydrate or secret'` | Vault helper + secret tests | pass |
| 52-04-02 | 04/4 | SRV-07 | T52-BACKUP-KEY, T52-BACKUP-CORRUPT, T52-RESTORE-NET | Independent A/B, state-only, fresh restore, rollback blocks on failure | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'backup or restore or rollback or sqlite or fingerprint'` | restore engine + invalid fixtures | pass |
| 52-05-01 | 05/5 | SCP-04, SRV-01, SRV-05, SRV-07 | T52-FALLBACK, T52-BACKUP, T52-CAP-FINAL, T52-COLOCATION | Failure at every stage including capacity_finalize safely rolls back, persists NO-GO and reaches fallback; A/B independence and final capacity exact | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'candidate_chain or fallback or backup_independence or capacity_finalize or topology'` | candidate runner | pass |
| 52-05-02 | 05/5 | SCP-04, SRV-01, SRV-05, SRV-07 | T52-VAULT-LEAK, T52-RESTORE, T52-CAP-FINAL, T52-WINDOWS | Live full chain selects first complete PASS only after materialized-byte reconciliation and verified rollback; Windows remains false | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'candidate or vault or backup or restore or capacity_finalize or rollback or placement'` | three candidate records + summary | pass |
| 52-06-01 | 06/6 | SCP-04, SRV-01, SRV-05, SRV-07 | T52-REPORT, T52-TEMPORAL, T52-LEAK | Exact current checks and actual selected-host Phase 53 review; future reviews not prerequisites | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'report or currentness or topology or windows_boundary'` | integrated report + Phase53 review | pass |
| 52-06-02 | 06/6 | SCP-04, SRV-01, SRV-05, SRV-07 | T52-WRITER, T52-REPORT | Governed full suite, parity/ledger/Phase48, parsed Graphify booleans both false | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests -q` | report parity + ledger | pass |
| 52-07-01 | 07/7 | SCP-04, SRV-05, SRV-07 | T52-VAULT-LEAK, T52-BACKUP-KEY | Versioned control-plane, bounded secret transport, dry-run, fault injection and secret scan | `omni srv1-ops resources run builds -- python3 -m pytest modules/fleet-backup/tests/test_phase52_backup_b.py modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q` | Gate A managed sources | pass |
| 52-07-02 | 07/7 | SRV-01, SRV-05, SRV-07 | T52-CAS, T52-ROLLBACK, T52-LIVE | Two-reviewer exact seal, seven create-only Vault writes and full live candidate vector | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py -q` | Gate B transaction + seal | pass |
| 52-07-03 | 07/7 | SCP-04, SRV-01, SRV-05, SRV-07 | T52-REPORT, T52-WRITER | Independent report/ledger/topology regeneration, full suite, secret scan and post-commit Graphify | `omni srv1-ops resources run builds -- python3 -m pytest modules/rustdesk-fleet/tests modules/fleet-backup/tests/test_phase52_backup_b.py -q` | closeout artifacts | pass |

## Requirement and Threat Closure

| Requirement | Primary tasks | Required live proof |
|---|---|---|
| SCP-04 | 52-01-01, 52-01-02, 52-05-01/02, 52-06-01/02 | Fresh official resolutions, exact pins/architecture, candidate input digests, report PASS |
| SRV-01 | 52-02-01/02, 52-03-01/02, 52-05-01/02, 52-06-01/02 | Exact D-04 reservations, D-06 zero-cleanup, ordered current candidate stage vectors |
| SRV-05 | 52-04-01, 52-05-01/02, 52-06-01/02 | Exact approved refs, aggregate distinctness, tmpfs/modes/cleanup, no secret material |
| SRV-07 | 52-04-02, 52-05-01/02, 52-06-01/02 | Independent verified A/B, fresh isolated restore, SQLite/fingerprint equality, rollback inactive |

Every high/critical threat in Plans 01–07 has an automated negative or live assertion. A stage failure yields FAIL/BLOCKED and a persisted candidate `NO-GO`; it cannot be converted to PASS or terminate the authorized fallback loop before the next candidate record is written.

## Required Negative Coverage

- Supply: mutable reference, changed commit/digest/checksum, wrong architecture, missing asset, target build/install attempt.
- Capacity/placement: one-byte 78/80 boundaries, inode boundary, omitted/zero/negative/overflow reservation, stale/different mount, order bypass, partial stage vector and stored-verdict drift; capacity_finalize also covers fresh used1/currentness, same mount, actual A/B above 4 GiB, materialized-byte/reservation mismatch, retained log/state/image terms and checked-add overflow.
- Approval/cleanup: approval digest mismatch, wrong accountable/timestamp/value, every cleanup/remediation/reclamation/pruning/deletion/destructive or unallowlisted storage action on srv2/srv3, bounded-write attempt before capacity PASS, glob/symlink/broad target.
- Vault: unknown ref, duplicate values detected without output, secret sentinel in argv/stdout/stderr/report/archive, permissive/non-tmpfs runtime and cleanup failure.
- Backup/restore: non-independent generation, same destination, input-digest mismatch, missing/corrupt B, private key archive entry, active source, wrong DB/image/fingerprint, public listener and active restored service.
- Temporal/report: missing Phase 52 or Phase 53 review, Phase 54/57 falsely required now, duplicate/stale check, parity/ledger drift, Phase 48 change, secret finding, Graphify stale/commit_stale.

## Wave 0 Requirements

- [x] `modules/rustdesk-fleet/contracts/supply-chain.json`
- [x] `modules/rustdesk-fleet/contracts/capacity-policy.json`
- [x] `modules/rustdesk-fleet/contracts/placement-decision.json`
- [x] `modules/rustdesk-fleet/tools/validate_phase52.py`
- [x] `modules/rustdesk-fleet/tools/rustdesk-vault-hydrate`
- [x] `modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py`
- [x] Phase 52 invalid fixtures and redacted evidence/report outputs

`wave_0_complete=true` porque todos os implementation files existem. `nyquist_compliant=true` significa que cada task finalizada possui rota automatizada concreta e nenhuma task está sem mapping.

## Final Sign-Off Gate

- [x] Fifteen finalized task IDs map one-to-one to Plans 01–07.
- [x] The exact governed full suite passes: 616 tests.
- [x] Candidate fallback tests cover failure at supply, capacity, Vault, backup, restore, capacity_finalize and rollback.
- [x] Every reached capacity_finalize proves fresh same-mount used1/inodes, checked materialized-byte reconciliation, actual A/B within their 4 GiB reserves, retained unmaterialized log/state/image terms, and final 80% inequality before selection.
- [x] Backup independence assertion is parenthesized and also verifies generation IDs, destinations and input digests.
- [x] Phase 53 review passes now; Phase 54/57 reviews are future just-in-time gates only.
- [x] Reports/ledger are current and secret-free; Windows install/access remains Phase 54.
- [x] Parsed Graphify JSON ends with `stale=false` and `commit_stale=false` after the final closeout commit.

**Approval source:** Giovanni Muniz, `2026-07-22T00:51:46Z`; exact values remain in `52-OPERATIONAL-DECISIONS.md`, without secrets.
