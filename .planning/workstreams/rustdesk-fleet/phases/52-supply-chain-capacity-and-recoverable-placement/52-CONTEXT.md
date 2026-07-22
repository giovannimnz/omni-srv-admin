# Phase 52: Supply Chain, Capacity and Recoverable Placement - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning
**Source:** Operator decision during autonomous Phase 52 planning

<domain>
## Phase Boundary

Phase 52 proves immutable RustDesk artifact provenance, exact capacity admission, Vault-only secret authority, explicit recoverable placement, and a real isolated backup/restore before Phase 53 may deploy the public primary. It does not install the RustDesk client on `GIOVANNI-W11-PC`; that remains mandatory Phase 54 work after Phases 52 and 53 pass.

</domain>

<decisions>
## Implementation Decisions

- **D-01:** Authorized placement candidates — evaluate `atius-srv-2`, then `atius-srv-3`, then `horistic-srv`, with no implicit promotion.

- `atius-srv-2` remains the preferred primary candidate and must pass the complete Phase 52 gate.
- If `atius-srv-2` fails, `atius-srv-3` may be evaluated through the same complete gate.
- Giovanni Muniz explicitly authorizes use of `horistic-srv` as a recoverable-placement candidate when the Atius server candidates remain `NO-GO`.
- Authorization is not admission: `horistic-srv` must pass current byte, inode, reservation, supply-chain, Vault, backup/restore, rollback, and security gates before selection.

- **D-02:** Horistic co-location truth — a selected Horistic primary is colocated with the future Phase 54 Linux canary and never counts as independent DR.

- If selected, `horistic-srv` must be recorded as a colocated server candidate because it is also the mandatory Linux canary target in Phase 54.
- Planning must keep server and future client identities, services, resource accounting, reboot evidence, and rollback domains distinct.
- Selection must trigger explicit Phase 53, Phase 54, and Phase 57 topology/test review; it must not silently redefine the existing roadmap.

- **D-03:** Windows delivery remains mandatory — Phase 52 verifies/stages the MSI only; Phase 54 installs it and proves real access.

- The RustDesk client is not installed on `GIOVANNI-W11-PC`.
- Phase 52 may verify and preserve the pinned MSI as a downstream input, but must not install it or claim Windows access complete.
- Phase 54 must install the verified client and prove real access to the Atius servers after the primary/edge gates pass.

- **D-04:** Capacity budgets approved — use exactly the approved log, state and two-backup byte reservations below.

- `combined_daily_log_budget_bytes=134217728` (128 MiB/day) for `log_retention_days=30`, reserving `4026531840` bytes.
- `state_growth_budget_bytes=4294967296` (4 GiB).
- Reserve two backups independently: `backup_a_reserve_bytes=4294967296` and `backup_b_reserve_bytes=4294967296` (4 GiB each; 8 GiB total).
- Unset, zero, negative, stale, overflowed, or partially omitted reservation terms remain fail-closed.

- **D-05:** Backup destinations and retention approved — backup A is local, B uses managed GDrive, and deletion always requires new approval.

- Backup A remains local on the selected candidate and backup B is replicated through the existing managed `modules/fleet-backup` GDrive path.
- Both backups are retained until Phase 57 has `PASS` plus 30 days.
- Deletion before or after that point requires a new explicit approval; Phase 52 does not infer deletion authority from retention expiry.

- **D-06:** Zero-cleanup on Atius candidates — no cleanup/remediation/reclamation/pruning/deletion or other destructive storage mutation is authorized on `atius-srv-2` or `atius-srv-3`.

- After a candidate passes the complete current capacity pre-gate, Phase 52 may perform only the bounded, isolated and reversible writes required by the approved full gate: pinned artifact staging/load, state-only backup A/B creation, a disposable isolated restore runtime, evidence writes, and verified rollback removal of those disposable drill artifacts.
- Those bounded writes are not cleanup/remediation authority. If their exact authorization, containment, target isolation, or capacity is absent, persist current `NO-GO`, run only safe rollback for already-created disposable drill artifacts, and continue to the next candidate.
- If either host fails current capacity admission, persist its exact `NO-GO` evidence and continue to the next candidate without remediation.

- **D-07:** Full gate and temporal topology reviews — Horistic receives the complete gate; Phase 53/54/57 reviews occur immediately before their own phases.

- After current `NO-GO` evidence for both Atius candidates, evaluate `horistic-srv` through the complete supply, byte/inode/reservation, Vault, two-backup, isolated restore, rollback, security, and topology-impact gate.
- Phase 52 records the topology impact now. Separate just-in-time reviews remain mandatory before Phase 53, Phase 54, and Phase 57; future review artifacts are not required to begin Phase 53, but each affected phase is blocked until its own review exists and passes.

### Operational approval record

- Accountable/operator: Giovanni Muniz
- Approved at: `2026-07-22T00:51:46Z`
- Scope: D-04 through D-07 exactly; no secret values and no broader destructive authority.

### the agent's Discretion

- Exact contract, validator, evidence, backup, and report file names inside the existing `modules/rustdesk-fleet` pattern.
- Exact contract, validator, evidence, and report serialization for D-04 through D-07, provided the approved values and fail-closed semantics are preserved.

</decisions>

<canonical_refs>
## Canonical References

- `.planning/workstreams/rustdesk-fleet/ROADMAP.md` — phase ownership, dependencies, advance gates, and Windows Phase 54 boundary.
- `.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md` — `SCP-04`, `SRV-01`, `SRV-05`, and `SRV-07` acceptance contract.
- `.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-RESEARCH.md` — current official artifact pins, capacity observations, restore architecture, and planning risks.
- `.planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-VERIFICATION.md` — verified upstream governance and explicit deferred Windows installation.
- `modules/rustdesk-fleet/contracts/secret-roles.json` — approved Vault paths and roles without values.
- `modules/rustdesk-fleet/evidence/ledger.json` — canonical requirement/evidence inventory.

</canonical_refs>

<specifics>
## Specific Ideas

- Current read-only snapshots place both `atius-srv-2` and `atius-srv-3` above the locked `<=78%` predeploy threshold; neither may receive a deploy based on stale or rounded data.
- `horistic-srv` currently passes only the raw disk threshold. The full admission report must still decide `GO` or `NO-GO`.

</specifics>

<deferred>
## Deferred Ideas

- Public primary deployment, native listeners, DNS/edge, monitoring, and Atius operational API: Phase 53.
- RustDesk installation and access proof on `GIOVANNI-W11-PC`: Phase 54.
- Production standby, failover, and failback: Phase 57.

</deferred>

---

*Phase: 52-supply-chain-capacity-and-recoverable-placement*
*Context gathered: 2026-07-20*
