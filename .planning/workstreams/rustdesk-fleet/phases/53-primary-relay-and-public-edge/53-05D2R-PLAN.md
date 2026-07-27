---
phase: 53-primary-relay-and-public-edge
plan: 05D2R
type: execute
wave: 13
depends_on: [53-05D2Q]
gap_closure: true
execution_owner: 53-05D2R
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json
  - modules/rustdesk-fleet/contracts/phase53-provider-readers.json
  - modules/rustdesk-fleet/tools/phase53-credential-launcher.py
  - modules/rustdesk-fleet/tools/phase53-streamable-http.py
  - modules/rustdesk-fleet/tools/build-phase53-reader-command-manifest.py
  - modules/rustdesk-fleet/tools/phase53-provider-read-transport.py
  - modules/rustdesk-fleet/tools/phase53_production_adapters.py
  - modules/rustdesk-fleet/tests/test_phase53_provider_readers.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2R-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-22, the real process chain is `omni` → `systemd-run` → `/usr/bin/flock` → the R launcher → `execve(target)`: flock remains the lock-holding parent, the launcher is a governed descendant that hydrates only allowlisted Vault profiles/variable names in memory and creates all credential/identity/known-host FDs itself, and the target replaces the launcher process."
    - "The launcher does not rely on parent-opened non-stdio FDs. It uses memfd/pipe or an opened-then-unlinked mode-0600 known-hosts file under a mode-0700 private temp directory, seals memfds where supported, makes only allowlisted FDs inheritable, marks every other non-stdio FD close-on-exec, supplies an allowlisted env, redacts errors and leaves no secret/temp path after the target exits."
    - "Per D-18/D-22, one source-sealed Streamable HTTP client serves read and later apply paths: exact endpoint/TLS/auth FD, initialize, `Mcp-Session-Id`, `notifications/initialized`, `tools/list`, exact tool allowlist, `tools/call`, structured response validation and session close; OCI identity is server `oci-admin` at the Atius endpoint, while Cloudflare uses its separately declared direct REST contract."
    - "Reader mode permits only OCI `oci_read` operations `inventory.get`, `network.security_list`, `peering.drg_status`, `peering.inventory`; no plan/control/write tool can be listed or called."
    - "Cloudflare read mode calls only GET `/client/v4/zones/{zone_id}/dns_records?type=A&name={fqdn}&per_page=100` for the exact three names with `X-Auth-Email` and `X-Auth-Key` from separate FDs; zero results means absent, one exact A result means present, and duplicate/conflicting results block."
    - "Per D-23, R does not claim that a safe Phase 53 Vault continuity route exists. It exposes only a generic closed reader command/capability interface that V can specialize without modifying launcher, MCP lifecycle or secret transport."
    - "R hydrates only profiles actually declared by the invoked sealed policy. It has no built-in `atius-mcp`/`cloudflare`/Vault profile assumption and rejects a requested profile/variable/capability absent from that policy."
    - "Per D-19, receipts have one collection observation_id, distinct receipt_id values, route/tool/provider operation ID, timestamps/TTL, revision or canonical revision digest, payload/semantic digests, exact safe flags and closed schemas; exactly six ordered capacity samples share one capacity-policy digest and bind raw counters plus independently derived results."
    - "The exact seven Q-baselined D2D paths pass the reusable Q `ancestor` policy at R entry and post-suite. R owns none of them and performs no authority/evidence/runtime/provider write."
  artifacts:
    - path: modules/rustdesk-fleet/tools/phase53-credential-launcher.py
      provides: "Governor-compatible non-persistent credential/SSH launcher that creates inherited FDs inside the governed process."
    - path: modules/rustdesk-fleet/tools/phase53-streamable-http.py
      provides: "Shared strict MCP Streamable HTTP lifecycle for OCI read/apply consumers."
    - path: modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json
      provides: "Closed absolute command, launcher, endpoint, profile/name, route and FD contract."
    - path: modules/rustdesk-fleet/contracts/phase53-provider-readers.json
      provides: "Closed generic receipt and capability schemas; provider-specific Vault continuity is owned by V."
    - path: modules/rustdesk-fleet/tests/test_phase53_provider_readers.py
      provides: "Standalone literal-wrapper smoke plus governed MCP/REST/SSH/Vault adversarial tests."
  key_links:
    - from: cli/omni/srv1_ops.py
      to: modules/rustdesk-fleet/tools/phase53-credential-launcher.py
      via: "systemd-run creates the governed scope, flock remains launcher parent and lock holder, and the launcher opens allowlisted FDs before replacing itself with the target"
      pattern: "systemd-run|flock|execve|inheritable"
    - from: modules/rustdesk-fleet/tools/phase53-provider-read-transport.py
      to: modules/rustdesk-fleet/tools/phase53-streamable-http.py
      via: "OCI reader passes auth FD and exact read tool/operation allowlist through the complete shared MCP lifecycle"
      pattern: "Mcp-Session-Id|notifications/initialized|tools/list|tools/call"
    - from: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
      to: modules/rustdesk-fleet/tests/test_phase53_provider_readers.py
      via: "before/after recomputation of tracked/status/type/mode/size/SHA-256 for all seven paths"
      pattern: "baseline_sha256|dirty_paths_unchanged"
  prohibitions:
    - "Do not edit the seven Q-baselined D2D paths, Phase 52/54, AUTONOMOUS-GOAL, 53-05/53-05-SUMMARY, evidence or graph files."
    - "Do not implement or invoke the Phase 53 Vault continuity route, read a Vault data endpoint, call a live write tool, use ambient SSH config, persist credentials or print helper output."
---

<objective>
Create the governor-compatible generic credential launcher, shared MCP client and bounded read transport interface required by later provider-specific routes.

Purpose: make generic reads executable without parent-FD assumptions, ambient config, secret persistence or a false claim that the Vault route already exists.
Output: eight source paths, an exact source-only commit and a direct summary-only descendant; no authority or live write.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@cli/omni/srv1_ops.py
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/STATE.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2C-SUMMARY.md
@modules/rustdesk-fleet/evidence/phase52/full-gate-summary.json
@modules/rustdesk-fleet/evidence/phase52/candidate-horistic-srv.json
@modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2R-01: Specify generic launcher, MCP and receipt transport in RED</name>
  <files>modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json, modules/rustdesk-fleet/contracts/phase53-provider-readers.json, modules/rustdesk-fleet/tests/test_phase53_provider_readers.py</files>
  <behavior>
    - "The standalone `--literal-governor-smoke` mode calls the real wrapper exactly once and observes `omni` → `systemd-run` → `/usr/bin/flock` → launcher/target without recursively invoking governed pytest."
    - "The target retains the launcher PID after exec, its immediate parent executable is `/usr/bin/flock`, a `systemd-run` ancestor exists, and target plus flock are in the same `omni-builds.slice`."
    - "An FD created by the launcher and explicitly allowlisted survives exec; ambient and unrelated FDs do not."
    - "A second nonblocking acquisition of the same lock conflicts while the target is alive and succeeds after target exit, proving the parent flock owns lock lifetime."
    - "Only exact allowlisted credential/identity/known-host FDs survive; unrelated FDs close and the target environment contains only allowlisted non-secret names."
    - "Fake Vault helper values never appear in argv, env, stdout, stderr, pytest output, process listing capture, manifest or persistent files; private temp/known-host paths are absent after use."
    - "MCP tests require initialize, session header, initialized notification, tools/list allowlist, tools/call response validation and close in order; missing/wrong content types, session, server name, tool or close fail."
    - "OCI reader can call only the exact four `oci_read` operations and cannot reach `oci_plan` or `oci_plan_control`."
    - "Cloudflare GET classifies absent/present exactly and rejects duplicates, wrong type/name/content, proxy, AAAA/CNAME, wrong zone, missing auth FD and mutable response drift."
    - "A sealed policy may expose generic `metadata-read` or `data-read-derived-output` capability labels, but R neither supplies their provider route nor permits raw returned values; provider-specific tests belong to V."
    - "No requested profile, variable, endpoint, tool or capability absent from the sealed policy can be hydrated or invoked."
    - "Six capacity samples preserve exact order, common policy digest, raw counters and independent threshold derivation."
    - "Q baseline mismatch before or after R fails before source commit."
  </behavior>
  <action>
Per D-18/D-19/D-21/D-22/D-23, write closed JSON contracts and at least eighteen adversarial tests covering every behavior above before implementation. The reader manifest must bind the absolute launcher, Python, SSH, ssh-keygen, approved credential helper and transport paths with owner/mode/SHA-256; allowlisted profiles and variable names without values; exact endpoint/CA/hostname/content-type contracts; exact SSH private/public route user/host/port/identity/known-host fingerprint; byte/time limits; fixed cwd; and an empty-by-default environment. It must never contain credential values or depend on inherited parent FDs.

Add a standalone CLI mode to the existing `test_phase53_provider_readers.py`: `--literal-governor-smoke`. It invokes `omni srv1-ops resources run builds -- <absolute-launcher> ... -- <absolute-target-helper>` exactly once and must not run pytest through that wrapper. The target helper reports only value-free process metadata and keeps the launcher PID across exec. Assert its immediate parent executable is `/usr/bin/flock`, a `systemd-run` ancestor exists, target and flock share `omni-builds.slice`, only the launcher-allowlisted FD survives, and ambient/unrelated FDs are absent. While target is held alive, a separate nonblocking flock attempt on the same lock must fail; after target exit it must succeed. Do not change the resource governor, do not add a no-fork flock option, and do not let governed pytest reacquire the capacity-1 build semaphore.

Model provider routes as closed policy entries with exact capability, route and output-schema identifiers. Include negative tests proving an absent provider-specific route cannot be inferred from a generic capability label and that only profiles actually referenced by the policy are hydrated. V will supply the Vault-specific route/audit in disjoint paths. RED must fail because the launcher/client/transports are not implemented, not because fixtures are malformed.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'set +e; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_provider_readers.py --disable-warnings; rc=$?; set -e; test "$rc" = 1'</automated>
  </verify>
  <done>Behavior-first tests make every launcher, protocol, provenance and Vault NO-GO edge explicit before implementation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2R-02: Implement the inside-governor launcher and generic read transports</name>
  <files>modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json, modules/rustdesk-fleet/contracts/phase53-provider-readers.json, modules/rustdesk-fleet/tools/phase53-credential-launcher.py, modules/rustdesk-fleet/tools/phase53-streamable-http.py, modules/rustdesk-fleet/tools/build-phase53-reader-command-manifest.py, modules/rustdesk-fleet/tools/phase53-provider-read-transport.py, modules/rustdesk-fleet/tools/phase53_production_adapters.py, modules/rustdesk-fleet/tests/test_phase53_provider_readers.py</files>
  <action>
Implement `phase53-credential-launcher.py` as the command executed by the existing `/usr/bin/flock` child of the governed `systemd-run` scope, with one closed CLI: `--reader-policy <absolute-path>`, optional `--apply-policy <absolute-path>`, repeatable `--profile <allowlisted-name>`, then `-- <absolute-target> <argv...>`. Validate its own Git/source digest and both supplied policies first. Invoke only the absolute approved Vault helper with one allowlisted profile at a time, capture output in memory, parse only exact allowlisted variable names without shell/eval, reject duplicates/unknowns, and never echo values. Copy each allowed value or explicit SSH identity into a separately named memfd/pipe; apply Linux memfd seals where supported. Create known-hosts under a private mode-0700 TMPDIR, verify exact host keys with absolute ssh-keygen, open it read-only, unlink/rmdir before exec, and expose only `/proc/self/fd/N`. Enumerate `/proc/self/fd`, set close-on-exec on every non-stdio FD, clear it only on exact allowlisted descriptors, remove secret variables from the final env, then `os.execve` the absolute final target so target keeps the launcher PID while flock remains its parent and lock holder. Emit only closed value-free exit/error codes.

Implement `phase53-streamable-http.py` as a reusable library with exact OCI/Atius MCP endpoint identity and auth FD. Perform initialize with required Accept/Content-Type, validate serverInfo.name, preserve `Mcp-Session-Id`, send initialized notification, list tools, require the exact mode allowlist, call one tool, reject JSON-RPC errors/isError/unknown content/raw streams/oversize responses, and close the session. It must explicitly reject Cloudflare URLs because Cloudflare uses direct REST.

Implement reader manifest build/validate plus `phase53-provider-read-transport.py` and `phase53_production_adapters.py`. OCI uses the shared client read allowlist. Cloudflare uses the exact GET query and separate email/key FDs. SSH uses `/usr/bin/ssh -n -F /dev/null` with BatchMode, IdentitiesOnly, StrictHostKeyChecking, explicit `/proc/self/fd/N` identity and known-hosts paths. Provider-specific routes are loaded only from an exact sealed policy entry and return a closed value-free envelope; an absent entry fails before transport construction. R must not contain a Vault path, operation, raw-data reader or continuity verdict. Remove synthetic callbacks/default previews; every preview is locally derived from current prestate plus desired ordered operations.
  </action>
  <verify>
    <automated>/usr/bin/python3 modules/rustdesk-fleet/tests/test_phase53_provider_readers.py --literal-governor-smoke</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_provider_readers.py --disable-warnings</automated>
    <automated>python3 -m py_compile modules/rustdesk-fleet/tools/phase53-credential-launcher.py modules/rustdesk-fleet/tools/phase53-streamable-http.py modules/rustdesk-fleet/tools/build-phase53-reader-command-manifest.py modules/rustdesk-fleet/tools/phase53-provider-read-transport.py modules/rustdesk-fleet/tools/phase53_production_adapters.py</automated>
  </verify>
  <done>The standalone smoke proves the real systemd-run→flock→launcher/target ancestry, shared slice, FD boundary and lock lifetime exactly once; governed pytest covers generic MCP/REST/SSH behavior without reacquiring its own wrapper.</done>
</task>

<task type="auto">
  <name>Task 53-05D2R-03: Recheck Q, seal eight reader paths and create the direct summary child</name>
  <files>modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json, modules/rustdesk-fleet/contracts/phase53-provider-readers.json, modules/rustdesk-fleet/tools/phase53-credential-launcher.py, modules/rustdesk-fleet/tools/phase53-streamable-http.py, modules/rustdesk-fleet/tools/build-phase53-reader-command-manifest.py, modules/rustdesk-fleet/tools/phase53-provider-read-transport.py, modules/rustdesk-fleet/tools/phase53_production_adapters.py, modules/rustdesk-fleet/tests/test_phase53_provider_readers.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2R-SUMMARY.md</files>
  <action>
Run the Q validator with policy `ancestor` before tests and after tests, using Q's exact source/summary commits. Run `/usr/bin/python3 modules/rustdesk-fleet/tests/test_phase53_provider_readers.py --literal-governor-smoke` outside any governor, then run the ordinary reader pytest suite once through the governed lane; never nest the wrapper. Commit exactly the eight R source paths with literal pathspecs. Create a direct summary-only child recording source commit/tree, exact path list and per-path digests, baseline digest plus before/after equality, systemd-run/flock/launcher/target ancestry evidence, FD/lock-lifetime result, MCP test results, `vault_route_implemented=false`, `vault_route_invoked=false`, `authority_created=false`, `provider_writes=0`, `runtime_writes=0`. Commit only the summary and prove direct ancestry. No R summary may imply that a continuity route or equivalence exists.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'SOURCE_COMMIT=$(git rev-parse HEAD^); SUMMARY_COMMIT=$(git rev-parse HEAD); test "$(git rev-parse "${SUMMARY_COMMIT}^")" = "$SOURCE_COMMIT"; EXPECTED=$(printf "%s\n" modules/rustdesk-fleet/contracts/phase53-provider-readers.json modules/rustdesk-fleet/contracts/phase53-reader-command-manifest.json modules/rustdesk-fleet/tests/test_phase53_provider_readers.py modules/rustdesk-fleet/tools/build-phase53-reader-command-manifest.py modules/rustdesk-fleet/tools/phase53-credential-launcher.py modules/rustdesk-fleet/tools/phase53-provider-read-transport.py modules/rustdesk-fleet/tools/phase53-streamable-http.py modules/rustdesk-fleet/tools/phase53_production_adapters.py | LC_ALL=C sort); test "$(git diff-tree --root --no-commit-id --name-only -r "$SOURCE_COMMIT" | LC_ALL=C sort)" = "$EXPECTED"; test "$(git diff-tree --root --no-commit-id --name-only -r "$SUMMARY_COMMIT")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2R-SUMMARY.md"; git diff --check'</automated>
  </verify>
  <done>Eight reader/launcher source paths and a direct summary-only child are sealed while Q remains byte-equal and live authority remains NO-GO.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53R-FD | Information Disclosure/Tampering | governed credential inheritance | critical | mitigate | Standalone smoke proves systemd-run→flock→launcher/target; launcher creates/seals FDs, allowlists inheritable descriptors and execves the target while flock retains the lock. |
| T53R-MCP | Spoofing/Elevation | OCI Streamable HTTP | critical | mitigate | Full session lifecycle, server/tool/operation allowlist, auth FD, response validation and explicit close. |
| T53R-ROUTE | Spoofing/Elevation | provider route registry | critical | mitigate | Exact sealed policy entry required; generic transport cannot invent a Vault capability or route. |
| T53R-CF | Tampering | DNS prestate | high | mitigate | Exact GET query, separate auth FDs, duplicate rejection and canonical revision digest. |
| T53R-SSH | Spoofing | host readers | high | mitigate | Explicit user/host/port, isolated opened/unlinked known-host FD, exact fingerprint and no ambient config. |
| T53R-BASE | Tampering | seven carry-forward paths | high | mitigate | Q metadata/SHA equality before and after with zero ownership overlap. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Current observable authority inputs | 05D2R | COVERED | Generic governed transport exists; V owns the absent Vault route. |
| REQ | SRV-02, SRV-03, SRV-04, SRV-06, OPS-01 | Runtime/edge/DNS/lifecycle/API observations | 05D2R | COVERED | Exact read receipts cover all five requirements. |
| RESEARCH | Value-free provider preflight and strict SSH/MCP | 05D2R | COVERED | No write route is reachable. |
| CONTEXT | D-04, D-05, D-06, D-17, D-18, D-19, D-21, D-22, D-23 | Secrets, topology, source, receipts, baseline and generic launcher/MCP boundary | 05D2R | COVERED | R exposes the interface; V supplies the provider-specific continuity route. |
| CONTEXT | Deferred Ideas | Client rollout, migration and standby | excluded | EXCLUDED | No deferred scope appears. |

No source item is missing.

<verification>
- A standalone smoke invokes the real wrapper exactly once and proves the process/cgroup/FD/lock contract; at least eighteen governed tests cover the complete generic MCP/REST/SSH boundaries without nesting the wrapper.
- Git-object checks prove an exact eight-path source commit and direct summary-only child.
- Q baseline equality proves R touched none of the seven D2D paths.
</verification>

<success_criteria>
1. Credential/SSH FDs survive because the governed launcher creates them after systemd-run/flock and replaces itself with the target; flock remains the immediate parent and lock holder.
2. The shared MCP client completes and validates the full Streamable HTTP lifecycle.
3. Cloudflare reads, SSH reads, capacity receipts and local previews are executable and value-free.
4. A provider-specific Vault route cannot be inferred or invoked from the generic interface; V is the only source owner for that route.
5. R owns exactly eight source paths plus its summary and preserves Q byte-for-byte.
</success_criteria>

<output>Create the eight-path R source commit and direct `53-05D2R-SUMMARY.md` child; stop for 53-05D2V. No live authority or Vault continuity route is created.</output>
