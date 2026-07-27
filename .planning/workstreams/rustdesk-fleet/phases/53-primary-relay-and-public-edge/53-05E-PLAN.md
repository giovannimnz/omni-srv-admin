---
phase: 53-primary-relay-and-public-edge
plan: 05E
type: execute
wave: 19
depends_on: [53-05D2H]
gap_closure: true
execution_owner: 53-05E
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
  - modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json
  - modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
  - modules/rustdesk-fleet/evidence/phase53/capacity-current.json
  - modules/rustdesk-fleet/evidence/phase53/preflight.json
  - modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
  - modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md
autonomous: false
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Task 1 writes only a mode-0700 private non-repo generation plus the exclusive mode-0600 private orchestration state and performs zero canonical repo write."
    - "The closed result table is exact: rc0 means valid current observation, W `STRICT_EQUIVALENCE_PROVEN` and a complete bundle; rc3 means valid current observation but mismatch/unproven continuity and a non-authorizing attestation; every other rc has zero authority artifacts."
    - "Route unavailable, missing frozen-only assessment or missing current observation never maps to rc3 and never creates successor attestation."
    - "Task 2 exists only for rc0, leaves the generation and canonical repo read-only, reviews the exact private OperationPlan bytes/hash, then persists only a private hash-bound owner-response artifact and an atomic `approved` orchestration-state update. It creates no canonical owner record or summary."
    - "Task 3 is the only canonical writer and the only summary writer. rc0 revalidates exact reviewed bytes, owner response and currentness, promotes dependencies transactionally, writes OperationPlan last as the generation marker, then writes owner record and summary."
    - "On rc3, Task 3 promotes only the non-authorizing successor attestation, a blocked generation marker and blocked summary. It creates no OperationPlan, owner record, apply instance or 05F eligibility."
    - "Both collection and promotion preserve rc3 under `set -e` by using `set +e`, capturing rc, restoring `set -e` and branching on 0/3/other before any assertion."
    - "The exact `/var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json` contract carries the absolute generation path, branch rc, source/W/H digests, TTL, reviewed OperationPlan SHA and owner-response path/digest across separate task shells; only rc0 plus status `approved`, a current exact owner response and W strict equivalence can advance."
  artifacts:
    - path: /var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json
      provides: "Value-free private cross-task state with exact generation, rc, source/W/H, TTL, review and owner-response bindings."
    - path: modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json
      provides: "Non-authorizing mismatch/unproven projection; never route-unavailable or frozen-only."
    - path: modules/rustdesk-fleet/evidence/phase53/preflight.json
      provides: "rc0 apply-instance/preflight binding or rc3 blocked generation marker."
    - path: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      provides: "rc0-only OperationPlan, written last in the promoted authority generation."
    - path: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
      provides: "rc0-only exact owner record created by Task 3."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md
      provides: "Single-writer rc0 eligible or rc3 blocked handoff."
  key_links:
    - from: modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
      to: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      via: "rc0 requires current STRICT_EQUIVALENCE_PROVEN; mismatch/unproven is rc3 and never authorizes"
      pattern: "STRICT_EQUIVALENCE_PROVEN|NO_GO|rc3"
    - from: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      to: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
      via: "Task 2 reviews exact private bytes; Task 3 revalidates and persists exact response"
      pattern: "operation_plan_sha256|expires_at|owner_response_sha256"
  prohibitions:
    - "Do not write a canonical artifact in Tasks 1 or 2, accept arbitrary rc3, reuse approval, call a writer/provider or dispatch 05F."
    - "Do not call fingerprint/pair-validity metadata-only, fabricate W continuity or create successor attestation from frozen-only/route-unavailable input."
---

<objective>
Generate and review authority in private storage, then promote exactly one closed rc0 or rc3 branch through a single canonical writer.

Purpose: prevent permissive rc3 handling, partial canonical generations and duplicate summary writers.
Output: rc0 owner-bound OperationPlan handoff or rc3 non-authorizing blocked projection.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/STATE.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
@modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json
@modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
@modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json
@modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json
@modules/rustdesk-fleet/tools/phase53-credential-launcher.py
@modules/rustdesk-fleet/tools/build-phase53-authority-plan.py
</context>

<tasks>

<task type="auto">
  <name>Task 53-05E-01: Generate and validate one private authority generation</name>
  <files>/var/tmp/omni-rustdesk-phase53-authority/&lt;generation-id&gt;/, /var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json</files>
  <action>
Use the stable private root `/var/tmp/omni-rustdesk-phase53-authority`, requiring it to be a non-symlink mode-0700 directory owned by the current uid, and create a new mode-0700 generation beneath it. Reserve `/var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json` before collection: any existing path, including a dangling symlink, is terminal `NO_GO` until an expiry-aware cleanup verifies the exact current uid, regular-file type, mode, nlink and generation binding; never overwrite or unlink an unvalidated pre-existing path. The state is a value-free, duplicate-key-closed JSON regular file created only after exact rc validation with `O_CREAT|O_EXCL|O_NOFOLLOW`, mode 0600, current uid, `nlink=1`, file fsync and parent-directory fsync. Its exact keys are `schema`, `version`, `status`, `generation_path`, `branch_rc`, `source_binding_sha256`, `w_summary_path`, `w_summary_sha256`, `w_decision_path`, `w_decision_sha256`, `h_summary_path`, `h_summary_sha256`, `h_quarantine_pointer_path`, `h_quarantine_pointer_sha256`, `h_quarantine_manifest_path`, `h_quarantine_manifest_sha256`, `created_at`, `expires_at`, `reviewed_operation_plan_sha256`, `owner_response_path` and `owner_response_sha256`; reject missing or extra keys. Initial values are schema `omni.rustdesk.phase53.authority-orchestration`, version `1`, status `collected`, the confined absolute generation path, branch rc integer `0` or `3`, SHA-256 bindings copied from the validated generation/source and exact W/H inputs, RFC3339 UTC creation/expiry with lifetime at most 30 minutes and not beyond the private OperationPlan expiry, and null review/owner fields.

Validate Q/R/V/S/D chains, W frozen assessment, route OperationPlan, route approval, route receipt, current observation and decision, plus H receipt and the exact stable pointer `/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json` before collection. Require that pointer to name `/var/tmp/omni-rustdesk-phase53-quarantine/&lt;generation-id&gt;/manifest.json`; recompute the pointer bytes SHA-256 and manifest bytes SHA-256, require the latter to equal the pointer's `manifest_sha256`, and bind both digests plus the exact H summary digest into the private state. Invoke the R launcher through the actual `omni`→`systemd-run`→`/usr/bin/flock` chain, hydrating only profiles actually required by the sealed reader and V route policies. Execute D's `collect-and-plan` into the private generation with every explicit flag: `--repo`, `--generation`, `--reader-command-manifest`, `--apply-command-manifest`, `--vault-route-contract`, `--vault-route-policy`, `--vault-frozen-assessment`, `--vault-route-plan`, `--vault-route-approval`, `--vault-route-receipt`, `--vault-current-observation`, `--vault-continuity-decision`, `--housekeeping-receipt` and `--housekeeping-quarantine-pointer`. Collect current topology, supply, capacity, Vault, host, OCI, Cloudflare and Apache receipts read-only. Fingerprint/pair-validity comes only from W's `data-read-derived-output` observation; no route write occurs.

Capture collection rc using the literal shell structure `set +e; <governed collection>; rc=$?; set -e; case "$rc" in 0|3) ... ;; *) ... ;; esac`; never let shell abort before rc capture. Validate the complete private generation with `validate-generation`, duplicate-key-closed schemas and exact source/TTL/revision/prestate/digest bindings before exclusively creating state. For rc0 require exactly the six private files and OperationPlan-last, current observation valid, W decision `STRICT_EQUIVALENCE_PROVEN`, all three Cloudflare branches current, and inert apply preflight. For rc3 require exactly the non-authorizing attestation plus blocked preflight marker; forbid OperationPlan, approval, topology, admission, capacity and apply instance. Route unavailable, missing frozen assessment, missing/malformed/stale current observation or malformed W/H input is rc2/rc1, never rc3 and never creates state. Write no canonical repo path or summary. Retain only the invocation-created state/generation until their bounded expiry; cleanup may remove them only after revalidating the exact state inode, owner/mode/nlink/TTL and generation confinement, and must never remove a mismatched or pre-existing object.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'ROOT=$(git rev-parse --show-toplevel); PRIVATE_ROOT=/var/tmp/omni-rustdesk-phase53-authority; STATE="$PRIVATE_ROOT/current-phase53-orchestration.json"; if test ! -e "$PRIVATE_ROOT" -a ! -L "$PRIVATE_ROOT"; then umask 077; mkdir "$PRIVATE_ROOT"; fi; test -d "$PRIVATE_ROOT" -a ! -L "$PRIVATE_ROOT"; test "$(stat -c %a "$PRIVATE_ROOT")" = 700 -a "$(stat -c %u "$PRIVATE_ROOT")" = "$(id -u)"; test ! -e "$STATE" -a ! -L "$STATE"; GEN=$(mktemp -d "$PRIVATE_ROOT/generation.XXXXXX"); chmod 700 "$GEN"; set +e; omni srv1-ops resources run builds -- "$ROOT/modules/rustdesk-fleet/tools/phase53-credential-launcher.py" --reader-policy "$ROOT/modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json" -- /usr/bin/python3 "$ROOT/modules/rustdesk-fleet/tools/build-phase53-authority-plan.py" collect-and-plan --repo "$ROOT" --generation "$GEN" --reader-command-manifest "$ROOT/modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json" --apply-command-manifest "$ROOT/modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json" --vault-route-contract "$ROOT/modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json" --vault-route-policy "$ROOT/modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json" --vault-frozen-assessment "$ROOT/modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json" --vault-route-plan "$ROOT/modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json" --vault-route-approval "$ROOT/modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json" --vault-route-receipt "$ROOT/modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json" --vault-current-observation "$ROOT/modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json" --vault-continuity-decision "$ROOT/modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json" --housekeeping-receipt "$ROOT/.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md" --housekeeping-quarantine-pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json; rc=$?; set -e; case "$rc" in 0|3) python3 "$ROOT/modules/rustdesk-fleet/tools/build-phase53-authority-plan.py" validate-generation --repo "$ROOT" --generation "$GEN" --expect "rc$rc"; env ROOT="$ROOT" GEN="$GEN" RC="$rc" STATE="$STATE" python3 -c "import hashlib,json,os,stat; from datetime import datetime,timedelta,timezone; from pathlib import Path; reject=lambda pairs: (_ for _ in ()).throw(ValueError(\"duplicate key\")) if len(pairs)!=len({k for k,_ in pairs}) else dict(pairs); load=lambda p: json.loads(Path(p).read_bytes(),object_pairs_hook=reject); digest=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); root=Path(os.environ[\"ROOT\"]); gen=Path(os.environ[\"GEN\"]).resolve(); state=Path(os.environ[\"STATE\"]); rc=int(os.environ[\"RC\"]); w_summary=root/\".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md\"; w_decision=root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json\"; h_summary=root/\".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md\"; h_pointer=Path(\"/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json\"); pointer=load(h_pointer); h_manifest=Path(pointer[\"manifest_path\"]); assert digest(h_manifest)==pointer[\"manifest_sha256\"]; preflight=load(gen/\"preflight.json\"); now=datetime.now(timezone.utc).replace(microsecond=0); expires=now+timedelta(minutes=30); data={\"schema\":\"omni.rustdesk.phase53.authority-orchestration\",\"version\":1,\"status\":\"collected\",\"generation_path\":str(gen),\"branch_rc\":rc,\"source_binding_sha256\":preflight[\"execution_source_tree_sha256\"],\"w_summary_path\":str(w_summary),\"w_summary_sha256\":digest(w_summary),\"w_decision_path\":str(w_decision),\"w_decision_sha256\":digest(w_decision),\"h_summary_path\":str(h_summary),\"h_summary_sha256\":digest(h_summary),\"h_quarantine_pointer_path\":str(h_pointer),\"h_quarantine_pointer_sha256\":digest(h_pointer),\"h_quarantine_manifest_path\":str(h_manifest),\"h_quarantine_manifest_sha256\":digest(h_manifest),\"created_at\":now.isoformat().replace(\"+00:00\",\"Z\"),\"expires_at\":expires.isoformat().replace(\"+00:00\",\"Z\"),\"reviewed_operation_plan_sha256\":None,\"owner_response_path\":None,\"owner_response_sha256\":None}; raw=(json.dumps(data,sort_keys=True,separators=(\",\",\":\"))+\"\\n\").encode(); fd=os.open(state,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); os.write(fd,raw); os.fsync(fd); os.close(fd); st=os.lstat(state); assert stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o600 and st.st_uid==os.getuid() and st.st_nlink==1; dfd=os.open(state.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW); os.fsync(dfd); os.close(dfd)" ;; *) test -z "$(find "$GEN" -mindepth 1 -maxdepth 1 -print -quit)"; exit "$rc" ;; esac'</automated>
  </verify>
  <done>A complete private rc0/rc3 generation exists, or non-rc0/rc3 failure has zero authority artifacts; canonical repo paths remain untouched.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 53-05E-02: Review exact rc0 OperationPlan bytes without writing</name>
  <files>/var/tmp/omni-rustdesk-phase53-authority/current-phase53-owner-response.json, /var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json</files>
  <action>If the exact state path is absent, expired, malformed, not schema-closed, not a current-uid mode-0600 regular file with `nlink=1`, or its status/branch is not `collected`/integer `0`, do not enter this checkpoint. rc3 is terminal `NO_GO` for owner review and must never request or persist an owner response. Load the absolute generation path only from state; require confinement beneath the mode-0700 private root, revalidate the generation as rc0, recompute all source/W/H summary, decision, pointer and manifest digests from their state-bound exact paths, and require the pointer still names the same manifest and digest. Open the private OperationPlan with `O_NOFOLLOW`, compute its exact SHA-256, require it to equal its closed-schema self binding, and display those exact bytes/hash, expiry, D source/tree, Q/R/V/S chains, W strict decision/hash, H receipt, current topology/supply/capacity/Vault/host/OCI/Cloudflare/Apache prestates, branch-specific rollback and typed confirmations.

After the resume signal supplies a new exact hash-bound owner response, accept its value-free JSON bytes through the checkpoint channel/stdin, not an ambient shell variable. Exclusively create `/var/tmp/omni-rustdesk-phase53-authority/current-phase53-owner-response.json` with `O_CREAT|O_EXCL|O_NOFOLLOW`, mode 0600, current uid, `nlink=1`, file fsync and directory fsync; any pre-existing path is `NO_GO`, never overwrite it. Validate duplicate-key-closed response schema, current Giovanni identity, decision, OperationPlan hash, expiry and every typed confirmation, then compute its bytes SHA-256. Atomically update only the private state: create a same-directory mode-0600 sibling with `O_CREAT|O_EXCL|O_NOFOLLOW`, copy every unchanged field, set status `approved`, set `reviewed_operation_plan_sha256` to the recomputed hash and set `owner_response_path`/`owner_response_sha256` to the exact current response path/digest; fsync the sibling, re-lstat the original state and require the previously validated inode/owner/mode/nlink, replace that exact inode without following it, and fsync the directory. Re-open and revalidate the approved state. Do not mutate the generation or create canonical files, canonical owner record or summary.</action>
  <verify>
    <automated>python3 -c 'import hashlib,json,os,stat,subprocess; from datetime import datetime,timezone; from pathlib import Path; state=Path("/var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json"); reject=lambda pairs: (_ for _ in ()).throw(ValueError("duplicate key")) if len(pairs)!=len({k for k,_ in pairs}) else dict(pairs); load=lambda p: json.loads(Path(p).read_bytes(),object_pairs_hook=reject); digest=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); st=os.lstat(state); assert stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o600 and st.st_uid==os.getuid() and st.st_nlink==1; d=load(state); assert d["schema"]=="omni.rustdesk.phase53.authority-orchestration" and d["version"]==1 and d["status"]=="approved" and d["branch_rc"]==0; assert datetime.now(timezone.utc)<datetime.fromisoformat(d["expires_at"].replace("Z","+00:00")); gen=Path(d["generation_path"]); response=Path(d["owner_response_path"]); assert gen.is_absolute() and gen.parent==state.parent and digest(response)==d["owner_response_sha256"]; plan=gen/"edge-forwarder-operation-plan.json"; reviewed=digest(plan); assert reviewed==d["reviewed_operation_plan_sha256"]; assert all(digest(d[pkey])==d[hkey] for pkey,hkey in (("w_summary_path","w_summary_sha256"),("w_decision_path","w_decision_sha256"),("h_summary_path","h_summary_sha256"),("h_quarantine_pointer_path","h_quarantine_pointer_sha256"),("h_quarantine_manifest_path","h_quarantine_manifest_sha256"))); subprocess.run(["python3","modules/rustdesk-fleet/tools/build-phase53-authority-plan.py","validate-generation","--repo",".","--generation",str(gen),"--expect","rc0","--require-operation-plan-sha",reviewed],check=True)'</automated>
  </verify>
  <what-built>A private complete rc0 authority bundle, exact reviewed OperationPlan, private owner-response artifact and approved private orchestration state; no canonical authority artifact.</what-built>
  <how-to-verify>
1. Confirm the displayed SHA-256 equals the reviewed private OperationPlan bytes.
2. Confirm W decision is exactly strict equivalence.
3. Confirm all current prestates, Cloudflare branches, rollback/restore and expiry.
4. Return a new exact owner response bound to this hash and expiry.
  </how-to-verify>
  <resume-signal>Provide the exact current hash-bound owner response, or leave AWAITING_OWNER_HASH_APPROVAL.</resume-signal>
  <done>Only an exact rc0 response bound in the approved private state can reach Task 3; the checkpoint wrote no generation or canonical bytes.</done>
</task>

<task type="auto">
  <name>Task 53-05E-03: Promote one canonical branch as the sole writer</name>
  <files>modules/rustdesk-fleet/evidence/phase53/topology-discovery.json, modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json, modules/rustdesk-fleet/evidence/phase53/candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/capacity-current.json, modules/rustdesk-fleet/evidence/phase53/preflight.json, modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json, modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md</files>
  <action>
Load every cross-task value only from `/var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json`; do not consume any ambient handoff variable. Before constructing promotion argv, require the private root to be a current-uid non-symlink mode-0700 directory and the state to be a duplicate-key-closed current-uid regular mode-0600 file with `nlink=1`, exact schema/version/key set, valid RFC3339 timestamps, lifetime at most 30 minutes and current unexpired TTL. Require its absolute generation path confined directly beneath the private root, generation directory mode/owner/nlink, and branch rc integer 0 or 3. Open every state-bound file and generation artifact with `O_NOFOLLOW`; recompute and compare source binding, W summary/decision, H summary/quarantine pointer/quarantine manifest and generation digests, require the pointer still names the state-bound manifest and its digest, and rerun `validate-generation` for the state branch before any canonical write. This task is the only canonical writer and summary writer.

For rc0, require state status `approved`, recompute the exact private OperationPlan SHA and require it to equal `reviewed_operation_plan_sha256`, then load the owner response only from the absolute state-bound `owner_response_path`. Require that response to be a current-uid mode-0600 regular file with `nlink=1`, recompute its bytes digest against `owner_response_sha256`, and revalidate current identity, decision, reviewed plan hash, expiry and typed confirmations. Recollect the current lightweight revision/prestate set through the governed launcher; any drift blocks with zero canonical write. Construct `promote-generation` argv from the state-loaded generation/hash/response plus every explicit source/W/H flag from Task 1, including exactly `--housekeeping-quarantine-pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json`; never substitute a repo path. Require canonical destinations absent. Promote the exact rc0 set using exclusive mode-0600 no-replace files and fsync; write `edge-forwarder-operation-plan.json` last as the generation marker, re-read exact bytes, then write the owner record and `53-05E-SUMMARY.md`. Summary records `05f_eligible=true`, rc0 and zero provider/live writes.

For rc3, require state status `collected`, null `reviewed_operation_plan_sha256`, `owner_response_path` and `owner_response_sha256`, plus valid current observation and exact mismatch/unproven classification. Promote only `phase52-successor-attestation.json`, then a closed blocked `preflight.json` generation marker, then the blocked summary. Attestation has `authorizes_live=false`, `historical_equivalence_proven=false`; no OperationPlan, approval, topology/admission/capacity/apply instance exists and `05f_eligible=false`. rc3 must not enter Task 2 and must never request owner approval, authority or provider action. For every other rc, write nothing, including no summary. On promotion failure, clean only paths created by this invocation; never overwrite. Capture promotion rc with `set +e`, store it, restore `set -e`, require it to equal the state-bound branch rc, then case on 0/3/other so rc3 is never lost. Never dispatch 05F. After a successful promotion, retain the exact private state/generation/response only until the recorded expiry for audit; expiry cleanup must revalidate state inode, root confinement, owner/mode/nlink and all recorded paths before removing only those exact invocation-created objects.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'ROOT=$(git rev-parse --show-toplevel); STATE=/var/tmp/omni-rustdesk-phase53-authority/current-phase53-orchestration.json; set +e; python3 -c "import hashlib,json,os,stat,subprocess,sys; from datetime import datetime,timezone; from pathlib import Path; root=Path(sys.argv[1]); state=Path(sys.argv[2]); reject=lambda pairs: (_ for _ in ()).throw(ValueError(\"duplicate key\")) if len(pairs)!=len({k for k,_ in pairs}) else dict(pairs); load=lambda p: json.loads(Path(p).read_bytes(),object_pairs_hook=reject); digest=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); expected={\"schema\",\"version\",\"status\",\"generation_path\",\"branch_rc\",\"source_binding_sha256\",\"w_summary_path\",\"w_summary_sha256\",\"w_decision_path\",\"w_decision_sha256\",\"h_summary_path\",\"h_summary_sha256\",\"h_quarantine_pointer_path\",\"h_quarantine_pointer_sha256\",\"h_quarantine_manifest_path\",\"h_quarantine_manifest_sha256\",\"created_at\",\"expires_at\",\"reviewed_operation_plan_sha256\",\"owner_response_path\",\"owner_response_sha256\"}; private=state.parent; pst=os.lstat(private); assert stat.S_ISDIR(pst.st_mode) and stat.S_IMODE(pst.st_mode)==0o700 and pst.st_uid==os.getuid(); rst=os.lstat(state); assert stat.S_ISREG(rst.st_mode) and stat.S_IMODE(rst.st_mode)==0o600 and rst.st_uid==os.getuid() and rst.st_nlink==1; d=load(state); assert set(d)==expected and d[\"schema\"]==\"omni.rustdesk.phase53.authority-orchestration\" and d[\"version\"]==1 and d[\"branch_rc\"] in (0,3); created=datetime.fromisoformat(d[\"created_at\"].replace(\"Z\",\"+00:00\")); expires=datetime.fromisoformat(d[\"expires_at\"].replace(\"Z\",\"+00:00\")); assert created<=datetime.now(timezone.utc)<expires and 0<(expires-created).total_seconds()<=1800; gen=Path(d[\"generation_path\"]); assert gen.is_absolute() and gen.parent==private and not gen.is_symlink(); gst=os.lstat(gen); assert stat.S_ISDIR(gst.st_mode) and stat.S_IMODE(gst.st_mode)==0o700 and gst.st_uid==os.getuid(); assert all(digest(d[pkey])==d[hkey] for pkey,hkey in ((\"w_summary_path\",\"w_summary_sha256\"),(\"w_decision_path\",\"w_decision_sha256\"),(\"h_summary_path\",\"h_summary_sha256\"),(\"h_quarantine_pointer_path\",\"h_quarantine_pointer_sha256\"),(\"h_quarantine_manifest_path\",\"h_quarantine_manifest_sha256\"))); pointer=load(d[\"h_quarantine_pointer_path\"]); assert d[\"h_quarantine_pointer_path\"]==\"/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json\" and pointer[\"manifest_path\"]==d[\"h_quarantine_manifest_path\"] and pointer[\"manifest_sha256\"]==d[\"h_quarantine_manifest_sha256\"]; preflight=load(gen/\"preflight.json\"); assert preflight[\"execution_source_tree_sha256\"]==d[\"source_binding_sha256\"]; branch=d[\"branch_rc\"]; rc0_ok=branch==0 and d[\"status\"]==\"approved\" and d[\"reviewed_operation_plan_sha256\"]==digest(gen/\"edge-forwarder-operation-plan.json\") and isinstance(d[\"owner_response_path\"],str) and isinstance(d[\"owner_response_sha256\"],str); rc3_ok=branch==3 and d[\"status\"]==\"collected\" and d[\"reviewed_operation_plan_sha256\"] is None and d[\"owner_response_path\"] is None and d[\"owner_response_sha256\"] is None; assert rc0_ok or rc3_ok; response=Path(d[\"owner_response_path\"]) if branch==0 else None; ost=os.lstat(response) if branch==0 else None; assert branch==3 or (stat.S_ISREG(ost.st_mode) and stat.S_IMODE(ost.st_mode)==0o600 and ost.st_uid==os.getuid() and ost.st_nlink==1 and digest(response)==d[\"owner_response_sha256\"]); owner=load(response) if branch==0 else {}; assert branch==3 or owner[\"operation_plan_sha256\"]==d[\"reviewed_operation_plan_sha256\"]; cmd=[\"omni\",\"srv1-ops\",\"resources\",\"run\",\"builds\",\"--\",str(root/\"modules/rustdesk-fleet/tools/phase53-credential-launcher.py\"),\"--reader-policy\",str(root/\"modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json\"),\"--\",\"/usr/bin/python3\",str(root/\"modules/rustdesk-fleet/tools/build-phase53-authority-plan.py\"),\"promote-generation\",\"--repo\",str(root),\"--generation\",str(gen),\"--reader-command-manifest\",str(root/\"modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json\"),\"--apply-command-manifest\",str(root/\"modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json\"),\"--vault-route-contract\",str(root/\"modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json\"),\"--vault-route-policy\",str(root/\"modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json\"),\"--vault-frozen-assessment\",str(root/\"modules/rustdesk-fleet/evidence/phase53/phase52-frozen-anchor-assessment.json\"),\"--vault-route-plan\",str(root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-operation-plan.json\"),\"--vault-route-approval\",str(root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-owner-approval.json\"),\"--vault-route-receipt\",str(root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-route-receipt.json\"),\"--vault-current-observation\",str(root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-current-observation.json\"),\"--vault-continuity-decision\",str(root/\"modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json\"),\"--housekeeping-receipt\",str(root/\".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md\"),\"--housekeeping-quarantine-pointer\",\"/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json\"]; cmd.extend([\"--reviewed-operation-plan-sha\",d[\"reviewed_operation_plan_sha256\"],\"--owner-response\",str(response)]) if branch==0 else None; result=subprocess.run(cmd); sys.exit(result.returncode if result.returncode==branch else 2)" "$ROOT" "$STATE"; rc=$?; set -e; case "$rc" in 0) test -f "$ROOT/modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json" -a -f "$ROOT/modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json" ;; 3) test -f "$ROOT/modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json" -a -f "$ROOT/modules/rustdesk-fleet/evidence/phase53/preflight.json"; test ! -e "$ROOT/modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json" -a ! -e "$ROOT/modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json" -a ! -e "$ROOT/modules/rustdesk-fleet/evidence/phase53/topology-discovery.json" -a ! -e "$ROOT/modules/rustdesk-fleet/evidence/phase53/candidate-admission.json" -a ! -e "$ROOT/modules/rustdesk-fleet/evidence/phase53/capacity-current.json" ;; *) exit "$rc" ;; esac; test -f "$ROOT/.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md"'</automated>
  </verify>
  <done>Exactly one canonical writer produced an rc0 05F-eligible handoff or rc3 non-authorizing blocked handoff; no other rc wrote authority artifacts.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53E-RC | Elevation | result classification | critical | mitigate | Exact rc0/rc3 predicates; route/frozen/current failures cannot masquerade as rc3. |
| T53E-PARTIAL | Tampering | canonical generation | critical | mitigate | Private generation, full revalidation, exclusive promotion and one writer. |
| T53E-APPROVAL | Spoofing/Repudiation | owner gate | critical | mitigate | rc0-only canonical-read-only checkpoint, exclusive private response and atomic exact hash/expiry state binding. |
| T53E-SUMMARY | Repudiation | summary | high | mitigate | Only Task 3 writes the canonical summary. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Current owner-reviewable transaction | 05E | COVERED | rc0 exact or rc3 non-authorizing. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Authority bundle | 05E | COVERED | Current receipts and rollback branches cover all requirements. |
| RESEARCH | Read-only currentness and owner gate | 05E | COVERED | Private generation precedes canonical promotion. |
| CONTEXT | D-04, D-05, D-06, D-08, D-17, D-18, D-19, D-20, D-22, D-23, D-24 | Secret, topology, source, W continuity, ordering and branches | 05E | COVERED | Exact rc table and single writer implement decisions. |
| CONTEXT | Deferred Ideas | Client rollout/migration/standby | excluded | EXCLUDED | No deferred scope. |

No source item is missing.

<verification>
- Literal commands classify rc0/rc3 and reject all other results without authority artifacts.
- Only Task 3 owns canonical writes and summary.
- OperationPlan is last within rc0 generation; rc3 has no OperationPlan/approval/apply instance.
</verification>

<success_criteria>
1. Task 1 is private-only; Task 2 leaves generation/canonical paths read-only and updates only the private response/state binding.
2. rc3 cannot hide route/frozen/current failure.
3. Task 3 is the sole canonical and summary writer.
4. 05F eligibility is explicit and never inferred from file presence.
</success_criteria>

<output>Create the single-writer rc0 or rc3 handoff and stop. Never dispatch 53-05F automatically.</output>
