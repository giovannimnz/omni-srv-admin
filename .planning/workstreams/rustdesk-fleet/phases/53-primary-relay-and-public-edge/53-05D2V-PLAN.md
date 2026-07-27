---
phase: 53-primary-relay-and-public-edge
plan: 05D2V
type: execute
wave: 14
depends_on: [53-05D2R]
gap_closure: true
execution_owner: 53-05D2V
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json
  - modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json
  - modules/rustdesk-fleet/tools/phase53-vault-derived-output-reader.py
  - modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py
  - modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py
  - modules/rustdesk-fleet/tools/render-phase53-vault-continuity-policy.py
  - modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py
  - modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2V-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-23, V is source-only: it defines and tests the previously absent continuity route but performs no install, credential creation, Vault read, SSH call, provider call or evidence write."
    - "Only true cluster/mount/path/version endpoints are named metadata-only. Current fingerprint/pair-validity uses a distinct server-side `data-read-derived-output` capability that emits only fingerprint/pair-validity and never raw Vault data."
    - "The closed route/policy binds absolute helper/bridge/server paths, exact server-side Vault path, transport identity, allowlisted profiles/variable names, operation IDs, output schema, owner/mode/digests, timeout/byte limits and denial of arbitrary path/tool/data output."
    - "The route reuses only the Phase 52 approved public key and fingerprint. It never generates, imports, replaces or rotates a key and never creates an AppRole, token or Vault ACL."
    - "The authorized_keys transform replaces only the exact Phase 52 prefix `restrict,no-user-rc,command=\"/usr/local/sbin/atius-vault-export-ssh-phase52\" ` with `restrict,no-user-rc,command=\"/usr/local/sbin/atius-vault-export-ssh-phase53-continuity\" `, preserving the exact suffix and all unrelated bytes; only that exact Phase 52 prestate or the already-current exact Phase 53 line is admissible."
    - "The forced dispatcher accepts zero argv, bounded `SSH_ORIGINAL_COMMAND` equal to exactly `phase53-vault-continuity-metadata-v1` or `phase53-vault-continuity-derived-v1`, empty stdin and exact `sudo -n` bridge dispatch; malformed input exits 64, while every legacy command is delegated to the Phase 52 dispatcher."
    - "Future W install enforces regular non-symlink/non-hardlink targets and exact modes: dispatcher root:root 0755, root bridge 0700, derived reader 0700, policy 0600 and sudoers 0440; `/home/ubuntu/.ssh` is ubuntu:ubuntu 0700 and `authorized_keys` is ubuntu:ubuntu 0600 with nlink=1."
    - "Validator distinguishes frozen-only, current and decision inputs; its decision is only `STRICT_EQUIVALENCE_PROVEN` or `NO_GO`, with no override branch."
    - "Q `ancestor` passes before and after V, and V's exact eight source paths plus direct summary child are independently sealed."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json
      provides: "Closed route/capability/auth/output contract."
    - path: modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py
      provides: "Restricted server-side dispatcher separating metadata from derived output."
    - path: modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py
      provides: "Transactional install/readback/rollback implementation gated by W authority."
    - path: modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py
      provides: "Frozen/current validator whose only decisions are strict equivalence or NO_GO."
    - path: modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py
      provides: "Hermetic route, capability, output, installer/rollback and decision tests."
  key_links:
    - from: modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json
      to: modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py
      via: "exact capability/path/operation/output allowlist"
      pattern: "metadata-read|data-read-derived-output|fingerprint|pair-validity"
    - from: modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py
      to: modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py
      via: "W-owned approved install ordering, exact authorized_keys transform, post-install readback and if-current rollback receipt"
      pattern: "operation_plan_sha256|authorized_keys|readback|rollback_if_current"
  prohibitions:
    - "Do not install the route, create/read credentials, call Vault/SSH/provider, write evidence or touch the seven D2D paths."
    - "Do not generate/import/replace/rotate keys, create AppRole/token/ACL state, introduce a continuity override, or alter any authorized_keys suffix/unrelated byte."
    - "Do not use eval, shell command strings, environment PATH lookup or arbitrary argv in the forced-command path."
---

<objective>
Implement and seal the missing restricted Vault continuity route as source-only artifacts.

Purpose: make W conditionally executable without pretending the route exists today or weakening the secret boundary.
Output: eight disjoint source paths plus a direct summary-only descendant; zero live/install action.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2R-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json
@modules/rustdesk-fleet/tools/phase53-credential-launcher.py
@modules/rustdesk-fleet/tools/phase53-provider-read-transport.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2V-01: Specify the restricted continuity route and closed capability split</name>
  <files>modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json, modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json, modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py</files>
  <behavior>
    - "Metadata capability allows only health/cluster, mount metadata and KV metadata for the one exact server path; it cannot return data values."
    - "Derived-output capability allows only current public fingerprint and pair-validity booleans computed server-side; raw private material, raw data objects and arbitrary paths are structurally impossible."
    - "Route binds absolute executable/server paths, restricted transport identity, exact profile and variable names, auth FD, operation IDs, timeout/byte/output schema and source digests."
    - "The exact Phase 52 public key/fingerprint is reused; key generation/import/replacement/rotation and AppRole/token/ACL creation are impossible."
    - "Only the exact Phase 52 authorized_keys prefix may become the exact Phase 53 prefix, with byte-identical suffix and unrelated lines; the already-current exact Phase 53 line is idempotent and every other prestate is NO-GO."
    - "Dispatcher has zero argv, empty stdin and bounded SSH_ORIGINAL_COMMAND. It dispatches exactly the two protocol strings through the exact sudo command, returns 64 for malformed input and delegates legacy commands to Phase 52."
    - "Runtime targets are regular, non-symlink, non-hardlink files with the exact owners/modes, and the sudoers payload is byte-exact and passes visudo."
    - "Frozen-only input cannot claim current_metadata_collected, historical equivalence or authorizes_live; the only non-strict decision is NO_GO."
    - "Q ancestor mismatch blocks before any V output commit."
  </behavior>
  <action>
Per D-04, D-17, D-18, D-21, D-22 and D-23, write closed contracts and hermetic RED tests. The route contract must name the exact server-side Vault path from the existing Phase 52 secret-role contract without copying a value, bind all executable/bridge/policy paths, operation IDs and output fields, and reuse only the Phase 52 approved public key/fingerprint. Use capability names `metadata-read` and `data-read-derived-output`; tests must reject calling the latter metadata-only. The policy template permits only cluster/mount/KV metadata for the exact path and the server-side derived public fingerprint/pair-validity output. It denies raw data serialization, arbitrary Vault paths, list/write/delete/admin/token operations and unbounded output.

Specify the exact runtime paths and modes: rendered dispatcher `/usr/local/sbin/atius-vault-export-ssh-phase53-continuity` root:root 0755; root bridge `/usr/local/sbin/atius-vault-continuity-bridge` root:root 0700; derived reader `/usr/local/sbin/atius-vault-continuity-derived-reader` root:root 0700; policy `/etc/atius-vault/phase53-vault-continuity-policy.json` root:root 0600; sudoers `/etc/sudoers.d/atius-vault-phase53-continuity` root:root 0440. Require regular files with nlink=1 and no symlink. Require `/home/ubuntu/.ssh` ubuntu:ubuntu 0700 and `/home/ubuntu/.ssh/authorized_keys` ubuntu:ubuntu 0600, regular, nlink=1. The exact sudoers content is `ubuntu ALL=(root) NOPASSWD: /usr/local/sbin/atius-vault-continuity-bridge phase53-vault-continuity-metadata-v1, /usr/local/sbin/atius-vault-continuity-bridge phase53-vault-continuity-derived-v1` and must pass `visudo -cf`.

Define frozen-only assessment, current observation and continuity decision as separate closed schemas. Strict requires complete immutable/current anchors; every mismatch, missing anchor or unproven relation produces `NO_GO`. RED must exercise exact Phase 52→Phase 53 prefix replacement with suffix/unrelated-byte preservation, already-current idempotence, all other prestates, modes/owners/nlink, sudoers validation, zero argv, bounded original command, empty stdin, exact sudo dispatch, legacy Phase 52 delegation, install drift, readback mismatch, rollback and strict/NO_GO decisions without any real endpoint.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
  </verify>
  <done>RED fixes the exact Phase 52 key continuity, forced-command protocols, runtime ownership/modes, capability split and strict-or-NO_GO semantics.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2V-02: Implement bridge, renderer, transactional installer and validator without live calls</name>
  <files>modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json, modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json, modules/rustdesk-fleet/tools/phase53-vault-derived-output-reader.py, modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py, modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py, modules/rustdesk-fleet/tools/render-phase53-vault-continuity-policy.py, modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py, modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py</files>
  <action>
Implement the rendered forced dispatcher, bridge and derived reader as fixed command/operation tables. The dispatcher receives zero argv, requires empty stdin, bounds and parses `SSH_ORIGINAL_COMMAND` without eval, shell command strings, PATH lookup or arbitrary argv, maps only `phase53-vault-continuity-metadata-v1` and `phase53-vault-continuity-derived-v1` to exact absolute `sudo -n /usr/local/sbin/atius-vault-continuity-bridge <protocol>` invocations, exits 64 for malformed Phase 53 input, and delegates legacy commands byte-for-byte to `/usr/local/sbin/atius-vault-export-ssh-phase52`. Metadata operations return only the closed metadata fields required by D-23. The derived-output reader opens the one exact secret path server-side, computes public fingerprint and pair-validity, clears buffers and returns only those derived fields plus value-free revision/provenance; it never emits raw data to the launcher or caller. Integrate with R only through the sealed generic policy/FD interface.

Implement policy renderer and transactional installer primitives with `assess|preview|apply|rollback|readback`, but do not invoke them in V. `assess` accepts only an exact Phase 52 authorized_keys line or the exact already-current Phase 53 line, preserving the Phase 52-approved suffix/fingerprint and every unrelated byte. `preview` creates a value-free deterministic operation set. `apply` refuses without exact unexpired W OperationPlan and owner record. It validates all regular-file/owner/mode/nlink prestates and stages dispatcher, bridge, reader and policy before validated sudoers, with authorized_keys last. It never creates a key, AppRole, token or ACL. Rollback restores authorized_keys first, then other installed targets in reverse order, only when current digests match the invocation record; drift is a refusal. In V tests, all transport endpoints are hermetic fakes and counters prove install/Vault/SSH/provider calls remain zero. Implement validator decisions as only `STRICT_EQUIVALENCE_PROVEN` or `NO_GO`, with no stored-verdict trust.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py --disable-warnings</automated>
    <automated>python3 -m py_compile modules/rustdesk-fleet/tools/phase53-vault-derived-output-reader.py modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py modules/rustdesk-fleet/tools/render-phase53-vault-continuity-policy.py modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py</automated>
  </verify>
  <done>All route components preserve the exact Phase 52 key and forced-command boundary, are hermetically rollback-testable, and V itself performs zero live/install action.</done>
</task>

<task type="auto">
  <name>Task 53-05D2V-03: Prove Q equality and seal eight source paths plus summary</name>
  <files>modules/rustdesk-fleet/contracts/phase53-vault-continuity-route.json, modules/rustdesk-fleet/contracts/phase53-vault-continuity-policy.json, modules/rustdesk-fleet/tools/phase53-vault-derived-output-reader.py, modules/rustdesk-fleet/tools/phase53-vault-continuity-bridge.py, modules/rustdesk-fleet/tools/install-phase53-vault-continuity-route.py, modules/rustdesk-fleet/tools/render-phase53-vault-continuity-policy.py, modules/rustdesk-fleet/tools/validate-phase53-vault-continuity.py, modules/rustdesk-fleet/tests/test_phase53_vault_continuity.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2V-SUMMARY.md</files>
  <action>
Run Q `ancestor` at entry and after the V suite. Commit exactly the eight V source paths with literal pathspecs, then create a direct summary-only child with source/tree/path digests, Q/R bindings, exact Phase 52 key/fingerprint reuse, authorized_keys transform, runtime path/mode table, protocol strings, sudoers digest, route/capability policy digests and explicit `route_installed=false`, `authorized_keys_changed=false`, `current_metadata_collected=false`, `authority_created=false`, `provider_calls=0`, `vault_calls=0`, `ssh_calls=0`. Prove exact source diff, direct summary-only diff and Q/R→V ancestry. Do not create any evidence, install or authority artifact.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'SOURCE=$(git rev-parse HEAD^); SUMMARY=$(git rev-parse HEAD); test "$(git rev-parse "${SUMMARY}^")" = "$SOURCE"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE" | wc -l)" = 8; test "$(git diff-tree --no-commit-id --name-only -r "$SOURCE" "$SUMMARY")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2V-SUMMARY.md"; python3 modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py ancestor --repo . --baseline .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json --source-commit "$(git show -s --format=%H "$(git log -1 --format=%H -- .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json)")" --summary-commit "$(git log -1 --format=%H -- .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md)" --summary-path .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md; git diff --check'</automated>
  </verify>
  <done>V owns eight source paths plus one summary, Q remains exact, and no route exists live yet.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53V-DATA | Information Disclosure | Vault derived output | critical | mitigate | Server-side computation emits only fingerprint/pair-validity; raw data schema is impossible. |
| T53V-ROUTE | Elevation | restricted bridge/policy | critical | mitigate | Exact path/operation/output allowlist, absolute source bindings and denied admin/write operations. |
| T53V-INSTALL | Tampering | future route installation | critical | mitigate | Fresh W OperationPlan, prestate/backup/readback and if-current rollback. |
| T53V-CRED | Elevation | Phase 52 restricted identity | critical | mitigate | Reuse only the approved key/fingerprint; generation, import, replacement, rotation, AppRole, token and ACL paths are absent. |
| T53V-AK | Tampering | authorized_keys continuity | critical | mitigate | Exact prefix-only transform preserves suffix/unrelated bytes; exact prestate/current-state gate, authorized_keys-last install and if-current rollback. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Safe continuity observation route | 05D2V | COVERED | Source exists without claiming live deployment. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Identity/source continuity | 05D2V | COVERED | Restricted output protects all live requirements. |
| RESEARCH | Value-free secret hydration and rollback | 05D2V | COVERED | Server-side derived output and transactional installer. |
| CONTEXT | D-04, D-17, D-18, D-19, D-21, D-22, D-23 | Secret boundary, transport, source and continuity | 05D2V | COVERED | Exact route and decision semantics are tested. |
| CONTEXT | Deferred Ideas | Client rollout/migration/standby | excluded | EXCLUDED | No deferred scope. |

No source item is missing.

<verification>
- Hermetic tests prove route capability separation, exact Phase 52 authorized_keys continuity, modes/sudoers/forced-command behavior, install/readback/rollback and strict-or-NO_GO decisions.
- Git checks prove exact eight source paths and direct summary child with Q preserved.
</verification>

<success_criteria>
1. V owns nine paths total.
2. Metadata and derived-output capabilities are distinct.
3. The future route is installable and reversible only under W authority.
4. V performs zero live/install/secret call.
</success_criteria>

<output>Create the V source/summary pair and stop for 53-05D2S.</output>
