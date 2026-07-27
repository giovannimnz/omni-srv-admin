---
phase: 53-primary-relay-and-public-edge
plan: 05D2S
type: execute
wave: 15
depends_on: [53-05D2V]
gap_closure: true
execution_owner: 53-05D2S
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json
  - modules/rustdesk-fleet/tools/build-phase53-apply-command-manifest.py
  - modules/rustdesk-fleet/tools/phase53-provider-write-transport.py
  - modules/rustdesk-fleet/tools/phase53_production_apply.py
  - modules/rustdesk-fleet/tools/phase53-remote-worker.py
  - modules/rustdesk-fleet/tests/test_phase53_provider_apply.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2S-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-20/D-22, apply reuses R's source-sealed inside-governor launcher and shared Streamable HTTP client; no production factory, MCP write tool, REST mutation, SSH worker or journal is reachable before a fresh non-serializable RevalidatedAuthorityToken."
    - "OCI apply completes initialize/session/initialized/tools-list/call/response/close through the shared client, permits only exact `oci_plan` and `oci_plan_control` OperationPlan operations, and binds the provider plan ID/hash/confirmation/readback."
    - "Per D-24, Cloudflare prestate selects a branch before owner approval for each exact hostname: absent means POST create plus returned-ID/readback binding and delete-if-current rollback; present means revision/ETag CAS update plus readback and restore-if-current rollback; duplicates or mixed identity drift block."
    - "The apply manifest is branch-specific and cannot be finalized until current R receipts identify all three Cloudflare states. It binds each chosen method/path, prestate revision, expected payload digest, returned-ID rule, readback and rollback semantics."
    - "Host/nft, Apache and runtime use one source-sealed stdin-only worker sent on every invocation; no scp/sftp, installed helper, ambient script, shell fragment or PATH lookup is allowed."
    - "The exact SSH exec argv is `ssh -T -F /dev/null ... -- /usr/bin/sudo -n /usr/bin/python3 -I -` with `shell=False` and without `-n` only because stdin carries the sealed rendered worker. The canonical value-free payload is embedded into the transmitted script; template, payload and rendered SHA-256 values are all bound to the OperationPlan."
    - "The remote worker has a fixed operation allowlist for preflight/readback/apply/contain/rollback/restore. It validates its template/payload/rendered digests, exact schema and operation ID before any action, uses atomic write/fsync/rename plus prestate backup, and emits one closed receipt."
    - "A source-sealed local `preflight-only` validates every executable, source digest, callback mapping, remote binary/route/sudo-read receipt shape, worker template and rollback mapping without importing/constructing a provider or contacting a live endpoint; D2S remains inert."
    - "Q `ancestor` is proven before and after S; S owns none of the seven paths, does not absorb V's Vault route/installer/decision responsibility, and creates an exact source-only commit plus direct summary-only child."
  artifacts:
    - path: modules/rustdesk-fleet/tools/phase53-remote-worker.py
      provides: "Source-sealed one-shot stdin worker template with fixed operation allowlist and atomic apply/rollback."
    - path: modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json
      provides: "Closed branch-specific OCI/Cloudflare/SSH apply and rollback contract."
    - path: modules/rustdesk-fleet/tools/phase53-provider-write-transport.py
      provides: "Authority-gated shared-MCP/direct-REST/one-shot-SSH transport."
    - path: modules/rustdesk-fleet/tests/test_phase53_provider_apply.py
      provides: "Hermetic mixed-state Cloudflare, MCP lifecycle, worker delivery, authority ordering and zero-write tests."
  key_links:
    - from: modules/rustdesk-fleet/tools/phase53-provider-write-transport.py
      to: modules/rustdesk-fleet/tools/phase53-streamable-http.py
      via: "authority-gated OCI write tool calls use the exact R-sealed full session lifecycle"
      pattern: "oci_plan|oci_plan_control|Mcp-Session-Id"
    - from: modules/rustdesk-fleet/tools/phase53-provider-write-transport.py
      to: modules/rustdesk-fleet/tools/phase53-remote-worker.py
      via: "template+payload rendering, exact three digests and stdin to fixed `/usr/bin/python3 -I -` remote command"
      pattern: "worker_source_sha256|payload_sha256|rendered_worker_sha256"
    - from: modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json
      to: modules/rustdesk-fleet/tools/phase53_production_apply.py
      via: "prestate-selected Cloudflare branch and exact rollback callback per record"
      pattern: "create|update|delete_if_current|restore_if_current"
  prohibitions:
    - "Do not edit the seven Q-baselined D2D paths, R-sealed source, Phase 52/54, evidence, graphs, AUTONOMOUS-GOAL or historical 53-05 files."
    - "Do not call a live MCP write tool/REST mutation/SSH worker in D2S, install a remote helper, send a secret in the worker payload, or use scp/sftp/ambient shell fragments."
---

<objective>
Implement and seal the inert production apply factory, complete OCI session, closed Cloudflare create/update branches and one-shot remote worker.

Purpose: make every future 05F mutation executable and reversible only after exact current authority, while D2S itself remains zero-write.
Output: six source paths, exact source-only commit and direct summary-only child.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2R-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2V-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json
@modules/rustdesk-fleet/tools/phase53-credential-launcher.py
@modules/rustdesk-fleet/tools/phase53-streamable-http.py
@modules/rustdesk-fleet/tools/phase53-provider-read-transport.py
@modules/rustdesk-fleet/tools/phase53_production_adapters.py
@modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2S-01: Specify authority, remote worker and Cloudflare branches in RED</name>
  <files>modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json, modules/rustdesk-fleet/tests/test_phase53_provider_apply.py</files>
  <behavior>
    - "Import/factory/journal/provider counters remain zero without a fresh RevalidatedAuthorityToken or on any OperationPlan/source/manifest/H/revision/owner drift."
    - "OCI write calls repeat the full MCP lifecycle and allow exactly `oci_plan`/`oci_plan_control` operations bound to the OperationPlan."
    - "Cloudflare mixed 3-record states choose create or update independently; zero/one/multiple query results map to absent/present/block."
    - "Create binds POST returned ID and exact readback; rollback deletes only if current ID/content/revision equals the created poststate."
    - "Update requires current revision/ETag CAS, exact readback and restore only if current state equals the applied poststate."
    - "Duplicate names, wrong zone/type/content, revision drift, create conflict, readback mismatch and delete/restore drift block and contain."
    - "Worker uses exact ssh-with-stdin argv, never `-n` on the worker call, validates source/payload/rendered digests and rejects unknown operations/fields."
    - "Remote binary/route/sudo capability preflight is represented by a value-free read receipt; D2S local preflight contacts no endpoint and performs no write."
    - "Apply, containment rollback, rollback and restore-production have distinct operation IDs, journals and receipt chains."
    - "Q validator policy ancestor passes before and after the suite."
    - "No V route/policy/installer/validator path is modified or invoked; Vault continuity remains a separate W gate."
  </behavior>
  <action>
Per D-17/D-20/D-21/D-22/D-23/D-24, create a closed apply-manifest contract and at least eighteen adversarial tests before implementation. The generic contract may describe both Cloudflare branches, but the final manifest instance must contain one branch per exact record selected from the current reader receipt. Bind exact methods and paths: absent uses POST `/client/v4/zones/{zone_id}/dns_records`; present uses PATCH `/client/v4/zones/{zone_id}/dns_records/{record_id}` with `If-Match` when an upstream ETag exists and always a canonical `prestate_revision_sha256` equality gate; readback uses GET by returned/existing ID; rollback uses DELETE for create-if-current or PATCH restore for update-if-current. Separate email/key FDs are mandatory. V's route/policy/installer/validator paths are read-only dependencies and cannot be invoked in S.

Specify the worker template and payload/rendering protocol. Canonicalize a value-free payload, compute payload SHA, render it only into the marked constant slot of the source-sealed template with template SHA and expected rendered SHA, then send the complete rendered script as stdin to the fixed remote Python command. No secret value may appear in payload or script. Tests must exercise mixed absent/present states, duplicate refusal, CAS/readback/rollback drift, exact remote stdin delivery, sudo denial and interruption before/after each atomic boundary.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_provider_apply.py --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
  </verify>
  <done>RED makes every authority, MCP, Cloudflare branch, worker delivery and rollback condition explicit.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2S-02: Implement inert manifests, shared-MCP apply and one-shot remote worker</name>
  <files>modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json, modules/rustdesk-fleet/tools/build-phase53-apply-command-manifest.py, modules/rustdesk-fleet/tools/phase53-provider-write-transport.py, modules/rustdesk-fleet/tools/phase53_production_apply.py, modules/rustdesk-fleet/tools/phase53-remote-worker.py, modules/rustdesk-fleet/tests/test_phase53_provider_apply.py</files>
  <action>
Implement `build-phase53-apply-command-manifest.py build|validate|preflight-only`. `build` requires a validated reader manifest plus the complete current Cloudflare prestate receipts and writes a mode-0600 canonical branch-specific manifest. `validate` recomputes executable/source/route/operation/worker/rollback digests. `preflight-only` performs local file/config/schema checks only and returns `provider_constructed=false`, `provider_calls=0`, `provider_writes=0`, `remote_worker_invocations=0`, `housekeeping_filesystem_mutation=false`; it must not import the apply module or contact a provider/host.

Implement `phase53-provider-write-transport.py` so its first operation is validation of a non-serializable fresh `RevalidatedAuthorityToken`. OCI imports R's shared MCP client and uses only the exact plan/control lifecycle. Cloudflare implements the branch-specific direct REST methods, current reread/revision equality, returned-ID binding and branch-specific rollback. Host/nft, Apache and runtime render `phase53-remote-worker.py`, validate all three digests locally, and run `/usr/bin/ssh -T -F /dev/null` with explicit BatchMode/IdentitiesOnly/StrictHostKeyChecking/identity/known-host FDs and fixed remote argv `/usr/bin/sudo -n /usr/bin/python3 -I -`; use `shell=False`, omit `-n` only for this stdin-bearing call, cap bytes/time and accept only a closed receipt.

Implement the worker as isolated stdlib-only code with a fixed operation table. `preflight` may check exact binary paths, route identity, sudo authorization and source/payload digests without writes; apply operations use literal destinations, O_NOFOLLOW, prestate hash/revision checks, mode/owner enforcement, backup then atomic fsync/rename, exact readback and separate contain/rollback/restore IDs. It is transmitted every time and never installed. `phase53_production_apply.py` maps only OperationPlan operations to these transports after token validation. Run all tests against hermetic fake MCP/HTTP/SSH/sudo endpoints; production network remains unreachable in S.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_provider_apply.py --disable-warnings</automated>
    <automated>python3 -m py_compile modules/rustdesk-fleet/tools/build-phase53-apply-command-manifest.py modules/rustdesk-fleet/tools/phase53-provider-write-transport.py modules/rustdesk-fleet/tools/phase53_production_apply.py modules/rustdesk-fleet/tools/phase53-remote-worker.py</automated>
  </verify>
  <done>Apply is executable hermetically through the shared MCP client, closed Cloudflare branches and stdin-only worker, yet local preflight remains inert and no production call occurs.</done>
</task>

<task type="auto">
  <name>Task 53-05D2S-03: Recheck Q, seal six apply paths and create the direct summary child</name>
  <files>modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json, modules/rustdesk-fleet/tools/build-phase53-apply-command-manifest.py, modules/rustdesk-fleet/tools/phase53-provider-write-transport.py, modules/rustdesk-fleet/tools/phase53_production_apply.py, modules/rustdesk-fleet/tools/phase53-remote-worker.py, modules/rustdesk-fleet/tests/test_phase53_provider_apply.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2S-SUMMARY.md</files>
  <action>
Run `validate-phase53-dirty-baseline.py ancestor` before and after the exact S suite, using the exact Q source/summary commits; this recomputes the complete tracked/XY/lstat/type/mode/size/O_NOFOLLOW SHA-256 tuple and Git chain. Run `preflight-only` and require all zero-call/zero-write flags. Commit exactly the six S source paths, then create a direct summary-only child recording source commit/tree, exact per-path digests, R and V source bindings, worker template digest, Cloudflare branch test matrix, baseline equality, `provider_constructed=false`, `provider_writes=0`, `remote_worker_invocations=0`, `runtime_writes=0`. Commit only the summary and prove direct ancestry.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'SOURCE_COMMIT=$(git rev-parse HEAD^); SUMMARY_COMMIT=$(git rev-parse HEAD); test "$(git rev-parse "${SUMMARY_COMMIT}^")" = "$SOURCE_COMMIT"; EXPECTED=$(printf "%s\n" modules/rustdesk-fleet/contracts/phase53-apply-command-manifest.json modules/rustdesk-fleet/tests/test_phase53_provider_apply.py modules/rustdesk-fleet/tools/build-phase53-apply-command-manifest.py modules/rustdesk-fleet/tools/phase53-provider-write-transport.py modules/rustdesk-fleet/tools/phase53-remote-worker.py modules/rustdesk-fleet/tools/phase53_production_apply.py | LC_ALL=C sort); test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE_COMMIT" | LC_ALL=C sort)" = "$EXPECTED"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SUMMARY_COMMIT")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2S-SUMMARY.md"; git diff --check'</automated>
  </verify>
  <done>Six inert apply source paths and a direct summary-only child are sealed while Q remains byte-equal and no production operation ran.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53S-EARLY | Elevation/Tampering | apply factory | critical | mitigate | Fresh non-serializable token precedes import/factory/journal/provider actions. |
| T53S-MCP | Spoofing/Elevation | OCI write session | critical | mitigate | Shared full lifecycle, exact tools/operations, provider plan hash and close. |
| T53S-CF | Tampering | DNS create/update | critical | mitigate | Prestate-selected branch, canonical revision/ETag CAS, ID-bound readback and branch-specific rollback. |
| T53S-WORKER | Tampering/Elevation | remote host apply | critical | mitigate | Source/payload/rendered digests, fixed stdin-only Python command and fixed operation allowlist. |
| T53S-ROLLBACK | Availability | containment/rollback/restore | critical | mitigate | Separate IDs/journals, exact current-state guards and atomic backup/fsync/rename. |
| T53S-BASE | Tampering | seven carry-forward paths | high | mitigate | Q equality before/after with no ownership overlap. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Implementable reversible primary transaction | 05D2S | COVERED | Concrete transports exist but remain inert. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Runtime, edge, DNS, lifecycle and API apply | 05D2S | COVERED | Exact operation/rollback allowlists cover all requirements. |
| RESEARCH | Transactional apply and recovery | 05D2S | COVERED | Atomic worker plus distinct containment/rollback/restore. |
| CONTEXT | D-06, D-08, D-13, D-14, D-17, D-20, D-21, D-22, D-23, D-24 | Topology, order, lifecycle, rollback, source, authority, baseline, launcher/MCP, Vault boundary and DNS branches | 05D2S | COVERED | Literal hermetic tests enforce every locked decision without absorbing V/W. |
| CONTEXT | Deferred Ideas | Client rollout, migration and standby | excluded | EXCLUDED | No deferred scope appears. |

No source item is missing.

<verification>
- At least eighteen adversarial tests cover mixed Cloudflare state, MCP write lifecycle, stdin worker, authority ordering and recovery.
- Local preflight reports zero factory/call/write/worker invocation.
- Exact six-path source and direct summary commits pass Git-object checks while Q remains equal.
</verification>

<success_criteria>
1. OCI apply uses the shared complete MCP lifecycle and only owner-bound plan/control operations.
2. Each Cloudflare record has a prestate-selected create or CAS-update path with matching delete/restore rollback.
3. Host/Apache/runtime assets execute through a source-sealed one-shot stdin worker with no install or scp.
4. D2S preflight is inert; all production actions require fresh authority.
5. S owns six source paths plus its summary and preserves Q byte-for-byte.
</success_criteria>

<output>Create the six-path S source commit and direct `53-05D2S-SUMMARY.md` child; stop for 53-05D2D. No live provider/host call is performed.</output>
