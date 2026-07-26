# Phase 54 — Fail-closed validation contract

## Canonical interface

`modules/fleet-control-plane/scripts/phase54_network_gate.py` remains read-only and is the only producer of canonical gate status:

`python3 modules/fleet-control-plane/scripts/phase54_network_gate.py final --plan 54-NN [--stage preflight|stability|preview|approval|apply|sync] --evidence <evidence.json> --gate <gate.json> --redact`

`python3 modules/fleet-control-plane/scripts/phase54_network_gate.py assert-review-gate --evidence <54-REVIEW-EVIDENCE.json> --gate <54-REVIEW-GATE.json>`

Every invocation of `final`, including preview/approval/apply intermediates, receives only the canonical `54-NN-EVIDENCE.json`. Raw OperationPlans, approvals, stability captures, architecture decisions and device receipts are artifacts referenced by path plus SHA-256 from canonical evidence; they are never passed as `--evidence`. Each plan's last task emits the durable gate. Plan 54-02 runs the complete `assert-review-gate` command first, then the complete predecessor `assert-gate`, then adapters; Plans 54-04..54-10 run the complete predecessor `assert-gate` first, with canonical evidence/gate and the predecessor terminal stage.

Canonical plan IDs are only `54-01..54-10`. Multi-step plans use the explicit stage allowlist above; concatenated pseudo-IDs such as `54-09-preview` are invalid. Unknown or missing required stage yields `BLOCK`.

Graphify semantic input formally excludes terminal runtime receipts `54-*-EVIDENCE.json`, `54-*-GATE.json` and `54-*-APPROVAL.json`; these are validated by the gate runner, not knowledge-graph sources. Plan 10 writes all semantic docs and SUMMARY before the final Graphify build, then writes only allowlisted runtime receipts. It never writes VERIFICATION. A final read-only `graphify status` runs after the terminal gate and must still report fresh.

## Status semantics

- Canonical output: `PASS`, `WARN`, `BLOCK`, `UNKNOWN`.
- Required check failure, timeout, absent/malformed artifact, stale/expired approval, drift, secret hit, partial write, asynchronous UNKNOWN or legacy `BLOCKED` input yields output `BLOCK` and non-zero exit.
- `WARN` is advisory only and requires `owner`, `reason`, `expires_at`; no required check may be WARN.
- Evidence cannot nominate its own final status. The runner derives status from plan-specific observed checks.

## Evidence schema

Evidence contains exact `check_inputs` IDs only; adapter, argv, command, host, tool, exit/result and observations are forbidden. Immutable `PROBE_REGISTRY[(plan,stage,check_id)]` selects a typed spec. The runner executes fixed argv with absolute executable, `shell=false`, closed stdin, sanitized env, timeout/output cap and emits `phase54.check-observation.v1`; fabricated receipts are ignored. Local 54-01 specs execute the portable workstream init wrapper, bounded pytest subsets, adversarial checks, secret scan and Graphify status/query requiring both `stale=false` and `commit_stale=false`. Physical 54-02..10 owner probes are implemented in `modules/fleet-control-plane/scripts/phase54_probe_adapters.py` and covered by `modules/fleet-control-plane/tests/test_phase54_probe_adapters.py`; each plan must pass `adapters-ready --plan 54-NN --smoke`. Every observation must carry `read_only=true`, `mutation_performed=false`, `secret_material_present=false`, a non-empty request ID and observed SHA-256. Stage contracts are derived only by the runner from canonical evidence, receipts, approvals and readbacks.

`BASE_REQUIRED_CHECK_IDS["54-02"]` includes runner-owned `independent_review_gate`; it is never delegated to a physical adapter or trusted from executor-authored evidence.

## Independent review schemas

- `phase54.review-evidence.v1` permits exactly: `schema`, `phase`, `status`, `planner_identity`, `reviewer_identity`, `started_at`, `finished_at`, `expires_at`, `scope`, `blockers`, `warnings`, `redacted`.
- `scope` is the ordered exact 14-file set: `54-CONTEXT.md`, `54-RESEARCH.md`, `54-VALIDATION.md`, `54-VALIDATION-CONTRACT.md`, and `54-01-PLAN.md` through `54-10-PLAN.md`. Each entry permits only `path` and lowercase SHA-256; missing, duplicate, reordered, extra or unknown entries block.
- `phase54.review-gate.v1` permits exactly: `schema`, `phase`, `status`, `planner_identity`, `reviewer_identity`, `started_at`, `finished_at`, `expires_at`, `evidence_path`, `evidence_sha256`, `scope_sha256`, `blockers`, `warnings`, `redacted`.
- Both artifacts require phase 54, `status=PASS`, `blockers=[]`, `warnings=[]`, distinct identities, fresh ordered timestamps, future expiry, no secret material and `redacted=true`. The gate must be newer than the evidence and colocated with it.
- The runner resolves `evidence_path`, recomputes its SHA-256, recomputes the canonical scope digest, and recomputes every current file hash. Drift, stale/expired receipts, malformed/unknown fields and self-review return `BLOCK`.

## OperationPlan rules

- One immutable `phase54.operation-plan.v1` per write group, with exact filename, owner, plan/stage, allowlisted operations, timestamps/expiry, non-empty input hashes and exact rollback receipt path/hash. Approval is `phase54.approval.v1`; apply is `phase54.apply-receipt.v1`; rollback is `phase54.rollback-receipt.v1`. Invented hashes or `receipt_state=PASS` never substitute receipt content.
- The only accepted typed confirmation is the literal `APPROVE <plan> <sha256-completo>`; `APROVAR`, `APPROVE BACKUP`, `APPROVE RETIREMENT` and any other variant block. Confirmation is never auto-generated or auto-approved and is stored in a separate immutable `54-NN-APPROVAL.json`, never inside the approved OperationPlan.
- Approval expires before apply if live readbacks, input hashes or target set drift.
- Apply reads the approved artifact from disk; it never reconstructs commands from prose.
- OCI public-IP operations never contain release/delete. Baseline 54-02 may record the old private binding. Plans 54-05/10 require same public OCID/address plus target `10.31.1.31`, private-IP/VNIC/subnet/VCN OCIDs from the approved 54-05 OperationPlan, and a matching `phase54.public-ip-readback.v1`; equality with the old private OCID is invalid.

## Wave lineage

Plans `54-02..54-10` require the immediate predecessor gate `PASS`, fresh, hash-valid, complete and matching the predecessor evidence. Plan 54-01 is reexecuted fresh and committed atomically before 54-02 begins; every successor, including 54-01→54-02, requires a verified source commit/blob pin. Null-source and uncommitted lineage are invalid. Older ancestors are not live-reexecuted: exact stage/name/directory/required IDs plus commit-pinned evidence/gate/runner hashes form a bounded, cycle-safe `chain_sha256`. Plan 54-02 only consumes/asserts 54-01 and never modifies its artifacts; its backup writes require an immutable backup-only OperationPlan, exact anti-drift and rollback receipts, and typed approval. Plans 54-04/05/06/07/08/09 require the relevant immutable OperationPlan, exact per-plan anti-drift/rollback/apply artifacts and typed approval. Plan 54-09 persists `54-09-STABILITY-EVIDENCE.json` plus `54-09-STABILITY-GATE.json`; preview must bind both exact hashes before retirement approval/apply. Plan 54-10 completes knowledge writes in preflight, freezes the exact semantic manifest, receipts and Graphify freshness/query relevance in `54-10-KNOWLEDGE-FREEZE.json`, then runs a separately fresh read-only sync that rejects drift and every mutation/write/apply signal.

`54-REVIEWS.md` remains the human audit trail and is not write authorization. Only the strict machine artifacts above satisfy the independent-review precondition, and they still cannot authorize operations.

## Required plan gates

| Plan | Required proof |
|---|---|
| 54-01 | workstream config routing; forged/stale/tampered/UNKNOWN/partial evidence rejected by tests |
| 54-02 | fresh reissued 54-01 gate; independent review gate; baseline public binding; exact local SRV1/SRV3/BE3 `phase54.backup-receipt.v1` receipts explicitly non-authorizing; approval only for OCI boot or named refreshes |
| 54-03 | external builder commit/receipt exact 10.31 literals; no target 10.21; VCN architecture decision |
| 54-04 | target VCN/subnet/DRG/routes/security ACTIVE and bidirectional |
| 54-05 | target `10.31.1.31` plus private-IP/VNIC/subnet/VCN OCIDs matching approved OperationPlan and readback; same public OCID/address/label |
| 54-06 | immutable DNS transaction plus separate evidence: FreeIPA A/PTR/FQDN/SOA/NS, resolver forwarding, services and rollback |
| 54-07 | hash-approved BE3/WG hub target map; S23 read-only at LAN `192.168.1.10`, WG `10.100.100.10`, MAC `64:1B:2F:C2:DC:A3`; S20 `.9` rollback retained; no collisions/duplicate AllowedIPs |
| 54-08 | separate staged OperationPlan/approval; no S23 write; `.11` handshake; receipt proves `.9` peer and AllowedIP absent; defer blocks sync completion |
| 54-09 | two stable matrices >=15 minutes; branch-safe retirement targets by OCID; literal typed confirmation; same-plan apply receipt and terminal readback |
| 54-10 | knowledge convergence completed before freeze; exact five-artifact 54-05 anchor plus current binding digest; fresh read-only retirement/public-binding readback, zero live 10.21 and no mutation/write/apply indicator |

## Independent verifier ownership

`54-10-GATE.json` closes execution only. The executor must not create or set status in `54-VERIFICATION.md`. After the final execution gate is PASS, an independent `gsd-verifier` reads live evidence and creates `54-VERIFICATION.md`; only that artifact may mark the phase verified/complete.
