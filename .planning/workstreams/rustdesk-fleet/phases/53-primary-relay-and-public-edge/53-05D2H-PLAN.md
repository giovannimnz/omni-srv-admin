---
phase: 53-primary-relay-and-public-edge
plan: 05D2H
type: execute
wave: 18
depends_on: [53-05D2W]
gap_closure: true
execution_owner: 53-05D2H
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/edge-probes.json
  - modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
  - modules/rustdesk-fleet/evidence/phase53/lifecycle.json
  - modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
  - modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "The exact seven canonical 05F destinations are inventoried and then absent before any new authority collection."
    - "Every existing regular file is moved by exact path to a mode-0700 recoverable quarantine; a mode-0600 prepared manifest is fsynced before the first move and updated atomically after each move."
    - "Symlink, directory, special file, conflicting pointer, unexpected path, hash mismatch or partial state blocks; no broad glob/find/rm/mv, stash, revert or clean is allowed."
    - "The stable pointer is written last and binds the complete manifest/generation/digests; every backup remains byte-verifiable and restorable to its exact original path."
    - "Per D-19/D-24, ledger semantics are honest: provider_mutation=false, network_mutation=false, live_runtime_mutation=false, housekeeping_filesystem_mutation=true, recoverable=true, synthetic=false and secret_material_present=false."
    - "H creates no OperationPlan, owner approval, provider journal or live runtime action; quarantine writes are local recoverable housekeeping and are not mislabeled read-only."
    - "H is structurally ineligible when W is NO_GO. Its first check requires a current W summary/decision whose branch is exactly STRICT_EQUIVALENCE_PROVEN; source presence, frozen assessment, mismatch/unproven continuity or any override is insufficient."
    - "Only 53-05D2H-SUMMARY.md enters Git; quarantine bytes remain outside Git and payload content is never copied into the summary."
  artifacts:
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
      provides: "Value-free receipt for an honest recoverable housekeeping filesystem mutation and exact-seven absent prestate."
  key_links:
    - from: /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json
      to: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
      via: "manifest SHA-256, generation/operation IDs, seven paths, scoped flags and absent proof"
      pattern: "housekeeping_filesystem_mutation|recoverable|canonical_paths_absent"
  prohibitions:
    - "Do not delete, truncate, overwrite, parse as authority or commit any stale evidence byte."
    - "Do not contact host/OCI/Cloudflare/DNS/Vault/RustDesk runtime or create authority."
---

<objective>
Recoverably quarantine the seven stale 05F destinations and publish an honest value-free housekeeping receipt.

Purpose: produce an exact absent precondition for fresh 05E authority without laundering stale evidence or claiming that local filesystem mutation was read-only.
Output: recoverable private quarantine plus one summary-only Git commit.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2W-SUMMARY.md
@modules/rustdesk-fleet/evidence/phase53/vault-continuity-decision.json
</context>

<tasks>

<task type="auto">
  <name>Task 53-05D2H-01: Execute exact recoverable local housekeeping with scoped mutation flags</name>
  <files>modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json, modules/rustdesk-fleet/evidence/phase53/edge-probes.json, modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json, modules/rustdesk-fleet/evidence/phase53/lifecycle.json, modules/rustdesk-fleet/evidence/phase53/rollback-drill.json, modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json, modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json</files>
  <action>
Before any filesystem mutation, validate W's exact current decision and summary bindings. Accept only `STRICT_EQUIVALENCE_PROVEN`; if W is missing, NO_GO, mismatch/unproven, stale or overridden, stop with zero housekeeping. Then use one local Python transaction over the seven literal paths in `<files>`. Resolve each below repo root with lstat and accept only absent or regular non-symlink files. Compute original size/SHA-256 and derive a generation ID from the sorted inventory. Create `/var/tmp/omni-rustdesk-phase53-quarantine/<generation-id>` mode 0700; atomically write/fsync mode-0600 `manifest.json` with status prepared, source/backup mappings, hashes, empty moved set, unique operation ID, D2D source/tree, W decision/hash/branch, chronology/expiry and exact scoped flags `provider_mutation=false`, `network_mutation=false`, `live_runtime_mutation=false`, `housekeeping_filesystem_mutation=true`, `recoverable=true`, `synthetic=false`, `secret_material_present=false`.

Move each existing file with exact `os.replace`, chmod backup 0600, fsync source/destination directories, update/fsync the manifest after each move and re-read each backup through O_NOFOLLOW. On interruption, preserve the exact partial manifest and block. After all moves, prove backup hashes and lexical absence of all seven originals, finalize status/semantic digest, then atomically create the mode-0600 stable pointer with the same scoped flags. Existing pointer/generation is accepted only if every byte/state/digest matches; otherwise block. Never interpret payloads beyond hashing.
  </action>
  <verify>
    <automated>env REPO_ROOT="$(git rev-parse --show-toplevel)" python3 -c 'import hashlib,json,os; from pathlib import Path; repo=Path(os.environ["REPO_ROOT"]).resolve(); rels=["modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json","modules/rustdesk-fleet/evidence/phase53/edge-probes.json","modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json","modules/rustdesk-fleet/evidence/phase53/lifecycle.json","modules/rustdesk-fleet/evidence/phase53/rollback-drill.json","modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json","modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json"]; p=json.loads(Path("/var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json").read_text()); flags={"provider_mutation":False,"network_mutation":False,"live_runtime_mutation":False,"housekeeping_filesystem_mutation":True,"recoverable":True,"synthetic":False,"secret_material_present":False}; assert all(p.get(k) is v for k,v in flags.items()); mpath=Path(p["manifest_path"]); raw=mpath.read_bytes(); assert hashlib.sha256(raw).hexdigest()==p["manifest_sha256"]; d=json.loads(raw); assert d["status"]=="complete" and all(d.get(k) is v for k,v in flags.items()); assert sorted(d["canonical_paths"])==sorted(rels) and all(not os.path.lexists(repo/r) for r in rels); assert all(Path(x["backup"]).is_file() and hashlib.sha256(Path(x["backup"]).read_bytes()).hexdigest()==x["sha256"] for x in d["files"])'</automated>
  </verify>
  <done>The exact stale bytes are recoverable, all seven destinations are absent and the receipt honestly records local housekeeping mutation only.</done>
</task>

<task type="auto">
  <name>Task 53-05D2H-02: Commit only the value-free housekeeping summary</name>
  <files>.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md</files>
  <action>
Create `53-05D2H-SUMMARY.md` with D2D source/summary ancestors, stable pointer path, manifest/generation/operation IDs and digests, start/completion/expiry, exact seven paths, moved count, `canonical_paths_absent=true`, all scoped flags from Task 1, and exact rollback instructions using only manifest mappings. Include no stale payload content. Commit exactly the summary with a literal pathspec. Prove its commit changes only the summary and repeats no generic read-only/mutation-performed claim.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'SUMMARY=.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md; test "$(git diff-tree --root --no-commit-id --name-only -r HEAD)" = "$SUMMARY"; rg -q "housekeeping_filesystem_mutation=true" "$SUMMARY"; rg -q "recoverable=true" "$SUMMARY"; ! rg -q "^(read_only|mutation_performed)=" "$SUMMARY"; git diff --check'</automated>
  </verify>
  <done>The sole Git change is an honest value-free summary that hands exact absent state to a new 05E process.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53H-LOSS | Tampering/Availability | stale bytes | critical | mitigate | Prepared per-file manifest, atomic moves, fsync, post-move hashes and exact restore mappings. |
| T53H-LAUNDER | Tampering/Repudiation | housekeeping receipt | critical | mitigate | Payload never interpreted; scoped flags truthfully identify filesystem mutation and no provider/runtime mutation. |
| T53H-SCOPE | Elevation | filesystem targets | high | mitigate | Seven literal paths, lstat/O_NOFOLLOW and no broad/destructive command. |
| T53H-SECRET | Information Disclosure | quarantine | high | mitigate | 0700/0600, no payload copy to Git/log and no secret fetch. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Recoverable current authority preparation | 05D2H | COVERED | Exact stale destinations are recoverably cleared. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Protect all future evidence destinations | 05D2H | COVERED | Absence and recovery protect every lane. |
| RESEARCH | Recoverable housekeeping | 05D2H | COVERED | No provider/runtime action occurs. |
| CONTEXT | D-17, D-19, D-23, D-24 | W eligibility, stale quarantine, provenance and scoped flags | 05D2H | COVERED | NO-GO cannot reach housekeeping; flags remain honest. |
| CONTEXT | Deferred Ideas | Clients, migration, standby | excluded | EXCLUDED | No deferred scope is introduced. |

No source item is missing.

<verification>
- Pointer/manifest validator proves exact recovery bytes, seven-path absence and scoped flags.
- Summary-only Git check proves no evidence byte is committed.
</verification>

<success_criteria>
1. Every stale byte is recoverable and every canonical destination is absent.
2. Local housekeeping filesystem mutation is explicitly true; provider/network/live-runtime mutation is explicitly false.
3. No authority/provider/network action occurs.
4. Only the value-free summary enters Git.
</success_criteria>

<output>Create and commit only `53-05D2H-SUMMARY.md`, then stop. 05E begins in a new process.</output>
