---
phase: 53-primary-relay-and-public-edge
plan: 05D2W
type: execute
wave: 17
depends_on: [53-05D2D]
gap_closure: true
execution_owner: 53-05D2W
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json
  - modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json
  - modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json
  - modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json
  - modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json
  - modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md
autonomous: false
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-23, frozen-only assessment is never current continuity evidence. Without current metadata it records current_metadata_collected=false, historical_equivalence_proven=false, authorizes_live=false and the known outcome insufficient."
    - "Frozen-only exit 0 means anchors are structurally complete and only eligible for comparison; exit 3 means anchors insufficient, exit 2 invalid input/schema, exit 1 internal/runtime. Exit 0 never authorizes live."
    - "A continuity-route OperationPlan binds source/tree, V policy/installer, exact Phase 52 approved public key/fingerprint, host/path/profile/capability, full runtime and authorized_keys prestates, preview, backup/journal/readback/rollback, exact hash and expiry; key generation/import/replacement/rotation and AppRole/token/ACL operations are forbidden."
    - "This plan text authorizes no write. The future route writer is unreachable until a new exact hash-bound owner approval exists; no prior approval is reused."
    - "Task 3 is the single future control-plane writer: backup/journal first; dispatcher, root bridge, derived reader and policy; sudoers only after visudo; authorized_keys last; full readback; and authorized_keys-first, reverse-order if-current rollback on failure."
    - "Current fingerprint/pair-validity uses `data-read-derived-output`, never metadata-only, and the decision is exactly `STRICT_EQUIVALENCE_PROVEN` or `NO_GO`."
    - "There is no continuity override branch. Without strict anchors and all future approvals, W ends NO_GO; H/E/F/06 are unreachable."
  artifacts:
    - path: modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json
      provides: "Frozen-only eligibility assessment, never current continuity evidence."
    - path: modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json
      provides: "Future route install/readback/rollback plan with exact prestate and branch."
    - path: modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json
      provides: "Value-free current metadata plus derived fingerprint/pair-validity observation."
    - path: modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
      provides: "Strict-equivalence or NO_GO decision."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md
      provides: "Authorizing handoff or explicit NO-GO."
  key_links:
    - from: modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json
      to: modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py
      via: "exact plan hash/expiry, prestate branch, backup/readback/rollback and owner record"
      pattern: "operation_plan_sha256|expires_at|rollback_if_current"
    - from: modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json
      to: modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
      via: "closed current metadata and server-side derived-output fingerprint/pair-validity"
      pattern: "data-read-derived-output|STRICT_EQUIVALENCE_PROVEN|NO_GO"
  prohibitions:
    - "Do not perform a route/Vault/SSH/provider write merely by executing this planning revision."
    - "Do not fabricate equivalence, introduce a continuity override, reuse an approval or add a key/AppRole/token/ACL operation."
---

<objective>
Govern the conditional continuity route, current observation and explicit continuity decision after D seals source.

Purpose: preserve NO-GO unless exact strict anchors mechanically prove continuity.
Output: frozen assessment, conditional route plan/receipt/current observation, decision and summary.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-10-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json
@modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json
@modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py
@modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py
</context>

<tasks>

<task type="auto">
  <name>Task 53-05D2W-01: Produce frozen-only anchor assessment with closed exits</name>
  <files>modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json</files>
  <action>
Read only the exact frozen Git objects/ancestry and run the V validator in `assess-frozen` mode. Write a create-only mode-0600 closed artifact with the complete/missing anchor list, immutable source commits/digests, `current_metadata_collected=false`, `historical_equivalence_proven=false`, `authorizes_live=false`, and status `eligible_for_current_comparison` or `insufficient`. Do not include a current fingerprint or name the artifact successor attestation. Exact exits are: 0 only when every frozen anchor is present and schema-valid, expressing comparison eligibility only; 3 when anchors are insufficient; 2 invalid input/schema; 1 internal/runtime. The known current result is 3/insufficient. Never manufacture equivalence to obtain rc0.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'set +e; python3 modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py assess-frozen --repo . --output modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json; rc=$?; set -e; test "$rc" = 0 -o "$rc" = 3; python3 -c "import json; from pathlib import Path; d=json.loads(Path(\"modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json\").read_text()); assert d[\"current_metadata_collected\"] is False and d[\"historical_equivalence_proven\"] is False and d[\"authorizes_live\"] is False; assert d[\"status\"] in (\"eligible_for_current_comparison\",\"insufficient\")"'</automated>
  </verify>
  <done>The known frozen state is recorded honestly as insufficient or, if newly complete, eligible only for a future current comparison.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 53-05D2W-02: Generate and review the continuity-route OperationPlan</name>
  <files>modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json, modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json</files>
  <action>
Generate a route OperationPlan only if the frozen assessment and V source permit a decision-capable current observation and prestate proves a route action has a legitimate purpose. Use read-only prestate/preview: bind D source/tree, V source/policy/installer digests, exact server/host/path/profile/capability, the Phase 52 approved public key/fingerprint, source tree, and byte/digest/owner/mode/nlink prestates for dispatcher, bridge, derived reader, policy, sudoers, `/home/ubuntu/.ssh` and `/home/ubuntu/.ssh/authorized_keys`. The authorized_keys prestate must be either the exact Phase 52 forced-command prefix with byte-preserved suffix/unrelated lines or the exact already-current Phase 53 form; otherwise stop NO_GO. Bind backup/journal, visudo-before-sudoers, authorized_keys-last install, full readback, authorized_keys-first reverse rollback, drift refusal, unique operation ID, whole-file SHA-256 and expiry. Key generation/import/replacement/rotation and AppRole/token/ACL operations are absent. Stop before any writer. Present the exact bytes/hash to the owner. Do not create the owner record unless the response explicitly names this plan hash, expiry and install/readback/rollback scope; silence, generic approval and previous approvals are invalid.
  </action>
  <verify>
    <automated>python3 modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py validate-route-plan --repo . --plan modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json --json</automated>
  </verify>
  <what-built>A value-free future route OperationPlan; no route, key, AppRole, policy or provider state changed.</what-built>
  <how-to-verify>
1. Confirm the displayed SHA-256 equals the exact OperationPlan bytes.
2. Confirm exact Phase 52 key/fingerprint reuse, authorized_keys prefix-only transform/current idempotence and every runtime prestate.
3. Confirm backup/journal, visudo-before-sudoers, authorized_keys-last install, readback, authorized_keys-first reverse if-current rollback, source bindings and expiry.
4. Return a new exact hash-bound decision only if this route action is authorized.
  </how-to-verify>
  <resume-signal>Provide the exact hash-bound route decision, or leave W NO-GO.</resume-signal>
  <done>No route writer becomes reachable without a new exact decision for this OperationPlan.</done>
</task>

<task type="auto">
  <name>Task 53-05D2W-03: Run the sole control-plane writer and collect current value-free observation</name>
  <files>modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json, modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json, modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json</files>
  <action>
Only after Task 2 receives a valid current response, persist the owner record and invoke the V installer as the sole route control-plane writer through the R governed launcher. Revalidate exact plan bytes/hash/expiry, D/V source, the Phase 52 approved key/fingerprint and every runtime/authorized_keys prestate before any write. Create a byte-preserving backup plus fsynced journal first. Install/read back dispatcher root:root 0755, root bridge 0700, derived reader 0700 and policy 0600 as regular nlink=1 non-symlink files; validate the exact sudoers payload with visudo before installing it root:root 0440; change `/home/ubuntu/.ssh/authorized_keys` last, preserving its exact key suffix and every unrelated byte while keeping `.ssh` ubuntu:ubuntu 0700 and the file ubuntu:ubuntu 0600 nlink=1. Never generate/import/replace/rotate a key or create AppRole/token/ACL state. Record one value-free route receipt.

Then collect current cluster/mount/path/version metadata through true metadata operations and current fingerprint/pair-validity only through `data-read-derived-output`. Persist only closed value-free fields and digests; never raw data. Any write/readback failure must restore authorized_keys first, then every invocation-created/replaced target in reverse order, only while its current digest equals the journaled installed digest; unexpected drift refuses rollback and leaves an explicit NO_GO receipt. This task is a future executor instruction; the current planning run performs none of these operations.
  </action>
  <verify>
    <automated>python3 modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py validate-current --repo . --route-plan modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json --route-approval modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json --route-receipt modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json --current modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json --json</automated>
  </verify>
  <done>The approved route is exact/read-back/recoverable and current observation is value-free, or rollback leaves an explicit NO-GO.</done>
</task>

<task type="checkpoint:decision" gate="blocking-human">
  <name>Task 53-05D2W-04: Decide strict equivalence or NO_GO</name>
  <files>modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md</files>
  <decision>Whether current continuity mechanically proves strict historical equivalence.</decision>
  <context>Run the V decision validator over the frozen assessment, current observation, route receipt and exact owner bindings. If every immutable/current anchor matches, write `STRICT_EQUIVALENCE_PROVEN`; every other result is `NO_GO` and non-authorizing.</context>
  <action>Run the automated decision validator. Persist `STRICT_EQUIVALENCE_PROVEN` and the summary only when it mechanically proves every equality with exact source/route/current hashes. Otherwise persist `NO_GO` and a non-authorizing summary. No operator override can change a failed comparison.</action>
  <options>
    <option id="strict">
      <name>Strict equivalence</name>
      <pros>Advances only when all immutable/current anchors mechanically match.</pros>
      <cons>Known frozen evidence is currently insufficient, so this branch is expected to remain unavailable.</cons>
    </option>
    <option id="no-go">
      <name>Keep NO-GO</name>
      <pros>Preserves the current truth and performs no downstream housekeeping/authority/live work.</pros>
      <cons>H, E, F and 06 remain unreachable.</cons>
    </option>
  </options>
  <verify>
    <automated>python3 modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py decide --repo . --frozen modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json --current modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json --route-receipt modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json --decision modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json --json</automated>
  </verify>
  <resume-signal>Select strict only after validator PASS; otherwise keep NO_GO.</resume-signal>
  <done>Summary authorizes H only for `STRICT_EQUIVALENCE_PROVEN`; every other outcome is explicit NO_GO.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53W-HISTORY | Spoofing/Repudiation | frozen anchors | critical | mitigate | Frozen-only artifact never claims currentness, attestation or equivalence. |
| T53W-WRITE | Elevation | route control plane | critical | mitigate | Separate current OperationPlan/approval, single writer, readback and rollback. |
| T53W-DATA | Information Disclosure | fingerprint path | critical | mitigate | Distinct server-side derived-output capability; raw data never leaves server. |
| T53W-GAP | Repudiation | historical continuity | critical | mitigate | Only mechanical strict equivalence authorizes; mismatch or missing proof is NO_GO with no override branch. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Governed identity continuity | 05D2W | COVERED | Honest NO-GO or exact authorizing decision. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Identity/source continuity before live | 05D2W | COVERED | All downstream lanes depend on W. |
| RESEARCH | Currentness, secret boundary, rollback | 05D2W | COVERED | Separate plan/approval/writer/decision. |
| CONTEXT | D-04, D-17, D-18, D-19, D-20, D-22, D-23, D-24 | Route, receipts, authority and continuity branches | 05D2W | COVERED | No continuity override is implied. |
| CONTEXT | Deferred Ideas | Client rollout/migration/standby | excluded | EXCLUDED | No deferred scope. |

No source item is missing.

<verification>
- Closed exits distinguish frozen eligibility, insufficiency, invalid input and runtime failure.
- Route writer is guarded by a separate exact approval and rollback.
- Authorized_keys continuity, install ordering, full readback and authorized_keys-first reverse rollback are receipt-bound.
- Decision output is only strict equivalence or NO_GO.
</verification>

<success_criteria>
1. W owns seven paths and exactly four tasks.
2. Known frozen-only state remains insufficient/non-authorizing.
3. No current planning action performs a route or Vault write.
4. Downstream plans are reachable only after an exact authorizing decision.
</success_criteria>

<output>Create W artifacts only under future checkpoints. Without strict equivalence, stop NO_GO before H.</output>
