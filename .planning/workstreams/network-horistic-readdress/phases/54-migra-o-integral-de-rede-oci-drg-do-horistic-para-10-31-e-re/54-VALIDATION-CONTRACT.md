# Phase 54 — Fail-closed validation contract

## Canonical interface

`modules/fleet-control-plane/scripts/phase54_network_gate.py` remains read-only and is the only producer of canonical gate status:

`python3 modules/fleet-control-plane/scripts/phase54_network_gate.py final --plan 54-NN [--stage preflight|stability|preview|approval|apply|sync] --evidence <evidence.json> --gate <gate.json> --redact`

Each plan's last task runs this command. The next plan first invokes `assert-gate` (added by Plan 01) to recompute evidence SHA-256, previous-gate lineage, schema, plan ID, freshness and required checks.

Canonical plan IDs are only `54-01..54-10`. Multi-step plans use the explicit stage allowlist above; concatenated pseudo-IDs such as `54-09-preview` are invalid. Unknown or missing required stage yields `BLOCK`.

Graphify semantic input formally excludes terminal runtime receipts `54-*-EVIDENCE.json`, `54-*-GATE.json` and `54-*-APPROVAL.json`; these are validated by the gate runner, not knowledge-graph sources. Plan 10 writes all semantic docs, SUMMARY and VERIFICATION before the final Graphify build, then writes only allowlisted runtime receipts. A final read-only `graphify status` runs after the terminal gate and must still report fresh.

## Status semantics

- Canonical output: `PASS`, `WARN`, `BLOCK`, `UNKNOWN`.
- Required check failure, timeout, absent/malformed artifact, stale/expired approval, drift, secret hit, partial write, asynchronous UNKNOWN or legacy `BLOCKED` input yields output `BLOCK` and non-zero exit.
- `WARN` is advisory only and requires `owner`, `reason`, `expires_at`; no required check may be WARN.
- Evidence cannot nominate its own final status. The runner derives status from plan-specific observed checks.

## Evidence schema

Every required result records `id`, `required`, `adapter/command_id`, redacted arguments, `started_at`, `finished_at`, `timeout_seconds`, `exit_code`, `observed`, `expected`, `result`, and artifact hashes. OCI writes also require `operation_plan_sha256`, `input_hashes`, `approval_typed`, `approval_expires_at`, `anti_drift_readback_sha256`, `opc_request_id`, receipt state and rollback transaction hash.

## OperationPlan rules

- One immutable OperationPlan per write group.
- Typed confirmation must name the plan ID and full SHA-256; it is never auto-generated or auto-approved. Confirmation is stored in a separate immutable `54-NN-APPROVAL.json`, never inside the approved OperationPlan.
- Approval expires before apply if live readbacks, input hashes or target set drift.
- Apply reads the approved artifact from disk; it never reconstructs commands from prose.
- OCI public-IP operations never contain release/delete. Poll same OCID and label `horistic-srv-1` to terminal `RESERVED/ASSIGNED`; UNKNOWN blocks new mutations. Reverse starts only from an authoritative terminal state.

## Wave lineage

Plans `54-02..54-10` require the immediate predecessor gate `PASS`, fresh, hash-valid, complete and matching the predecessor evidence. Plans 54-04/05/06/07/09/10 additionally require the relevant immutable OperationPlan and typed-approval receipt. Approved OperationPlans/transactions are immutable; observations always go to separate evidence artifacts.

## Required plan gates

| Plan | Required proof |
|---|---|
| 54-01 | workstream config routing; forged/stale/tampered/UNKNOWN/partial evidence rejected by tests |
| 54-02 | live inventory, all backups, restore staging, public-IP OCID/binding, DNS/edge baseline |
| 54-03 | external builder commit/receipt exact 10.31 literals; no target 10.21; VCN architecture decision |
| 54-04 | target VCN/subnet/DRG/routes/security ACTIVE and bidirectional |
| 54-05 | VNIC/private `.31`, host/K3s dual-path, public IP same OCID/label `horistic-srv-1` in `RESERVED/ASSIGNED`, reverse only from known terminal state |
| 54-06 | immutable DNS transaction plus separate evidence: FreeIPA A/PTR/FQDN/SOA/NS, resolver forwarding, services and rollback |
| 54-07 | hash-approved BE3/WG hub target map; S23 unchanged; S20 `.9` rollback retained; no collisions/duplicate AllowedIPs |
| 54-08 | device receipts, `.11` handshake before `.9` retirement, private then public Horistic SSH and encrypted fallbacks |
| 54-09 | two stable matrices >=15 minutes; branch-safe retirement targets by OCID; plan hash/expiry/anti-drift and typed confirmation |
| 54-10 | retirement readback with zero live 10.21; full matrix; all sync receipts; final gate emitted after docs/knowledge/Graphify/notifications |
