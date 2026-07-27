# Phase 53: Primary Relay and Public Edge - Context

**Gathered:** 2026-07-22
**Status:** Ready for planning
**Source:** Autonomous discussion after Phase 52 PASS and operator authorization to plan and execute

<domain>
## Phase Boundary

Phase 53 deploys the production RustDesk Server OSS primary on the selected `horistic-srv`, publishes only the approved native edge, proves persistence/resource/security behavior, and exposes a separate authenticated/redacted ATIUS operational API. It does not install either canary client; `horistic-srv` and `GIOVANNI-W11-PC` client installation remains Phase 54, while installation on the three Atius servers remains Phase 55.

</domain>

<decisions>
## Decisions

### Server and colocated-client separation

- **D-01:** Production `hbbs` and `hbbr` use rootless Podman Quadlets on `horistic-srv`, pinned to the Phase 52 ARM64 child digest. No tag-only or auto-update path is allowed.
- **D-02:** The Phase 53 server owns a dedicated state, service, resource, evidence and rollback domain. Future Phase 54 client assets on the same host must not share or mutate those paths.
- **D-03:** The two server containers share the approved combined ceiling of `0.8 CPU` and `1 GiB RAM`; every per-container allocation must sum within that ceiling. Logs are bounded and retained according to the approved Phase 52 budgets.
- **D-04:** Server identity is hydrated from the approved Vault reference through private bounded transport. Evidence records only the public fingerprint and value-free metadata.

### Native edge and external proof

- **D-05:** `rustdesk.atius.com.br`, `rustdesk-id.atius.com.br` and `rustdesk-relay.atius.com.br` are Cloudflare DNS-only A records for the reserved public address `137.131.140.20`; `rustdesk.atius.com.br` remains the general client endpoint, while `rustdesk-id.atius.com.br` and `rustdesk-relay.atius.com.br` are the explicit ID and relay endpoints. Proxying, AAAA and CNAME records are forbidden. This decision supersedes D-05 gathered on 2026-07-22 by explicit Giovanni instruction on 2026-07-25.
- **D-06:** The current public edge/forwarder is `atius-srv-1`, using reserved/assigned public IPv4 `137.131.140.20` on VNIC private IPv4 `10.0.0.238`; the RustDesk backend remains `horistic-srv` at `10.21.1.21`. The edge performs nftables prerouting DNAT plus forwarding and a deterministic return-path/SNAT policy across OCI/DRG for `34099/TCP->10.21.1.21:21115`, `34100/TCP+UDP->10.21.1.21:21116` and `34101/TCP->10.21.1.21:21117`. Backend ingress accepts those native ports only from the proved DRG/SNAT return identity `10.11.1.11`; `10.0.0.238` is only the public-VNIC owner and must never be conflated with backend ingress source. `ct status dnat` and `ct original proto-dst` distinguish translated flows from direct-native attempts; direct-public `21114` through `21119` and every non-allowlisted listener remain closed. This supersedes every earlier single-host/local-redirect interpretation of D-06.
- **D-07:** External proof originates outside `horistic-srv`; use `GIOVANNI-W11-PC` via private SSH first as the primary TCP/UDP probe source, with a second independent external probe when practical. Localhost or same-host scans never satisfy the gate.
- **D-08:** Edge publication is ordered and reversible: preflight/backup, host+OCI/Cloudflare change, external positive and negative probes, then commit. Any failed probe restores the previous DNS/firewall/ingress state and keeps Phase 54 blocked.

### Operational API and monitoring

- **D-09:** The ATIUS operational API uses a separate HTTPS hostname, recommended `rustdesk-ops.atius.com.br`, and never populates the RustDesk client `API Server` field or opens TCP `21114`.
- **D-10:** Expose versioned read-only endpoints for health, readiness, status and redacted metric summaries. Authentication is mandatory; credentials remain in Vault/runtime hydration and responses/logs never expose keys, passwords, client IDs or reusable tokens.
- **D-11:** Readiness derives from current service state, exact listeners, fingerprint continuity, resource ceilings, disk/log growth and bounded restart counters. A process merely being active is insufficient.
- **D-12:** Direct/relay byte counters and failure summaries are observability inputs only. They do not claim session transport until later canary/matrix phases correlate controller, target, UI/log evidence and `hbbr` deltas.

### Persistence and rollback

- **D-13:** The gate requires three controlled restarts and one real host boot, preserving public fingerprint, state database, exact listeners, resource limits, log bounds and API readiness.
- **D-14:** Server rollback restores the predeploy state without uninstalling or reconfiguring RustGuac, XRDP, AnyDesk, NoMachine or noVNC. It also must not touch the future RustDesk client domain on Horistic.
- **D-15:** No standby or independent DR claim is made in Phase 53. `horistic-srv` is the primary; Phase 57 must select a separate failure domain.
- **D-16:** RustDesk migrates with Horistic when the backend moves to `10.31.1.31`, but that destination is `executable=false` throughout Phase 53. The handoff becomes executable only after the Phase 54 Horistic migration has independently completed and produced current topology authority.
- **D-17:** The existing `edge-forwarder-operation-plan.json` is stale, unapproved and bound to an older source. It is forbidden as an execution input or approval hash. The 05D2C seal is an immutable historical ancestor but non-authorizing. The exact remainder is `Q(w12) → R(w13) → V(w14) → S(w15) → D(w16) → W(w17) → H(w18) → E(w19) → F(w20) → 06(w21)`. Q creates a reusable full baseline validator/test and seals the seven-path value-free baseline. R adds only the generic inside-governor launcher/shared MCP/read transport. V adds source-only the restricted Vault continuity route, without installing or invoking it. S adds branch-complete apply transports. D verifies Q as its first action, implements `collect-and-plan`, `validate-generation` and `promote-generation`, consumes the seven paths and derives the superseding aggregate from summary-bound Q/R/V/S sources plus the exact seven D paths. W is the sole governed conditional route-install/current-observation/continuity-decision gate. H runs only after W proves strict equivalence. No historical count, hash, confirmation, override or prior approval is authority.
- **D-18:** Production observation collection requires a plan-owned value-free command-manifest builder plus explicit bounded reader transports; an absent callback, generic preview, ambient MCP/runtime object, ambient SSH configuration or mutation-capable read route is a blocker. The manifest is canonical-hashed, mode/owner checked, absolute-path-only and contains no shell fragments/PATH lookup. OCI uses the shared complete Streamable HTTP lifecycle for server `oci-admin`, tool `oci_read`, and only `inventory.get`, `network.security_list`, `peering.drg_status`, `peering.inventory`; the Codex client label `oci_admin_http` is not an executable callback. Cloudflare performs exact direct REST GETs for the three records. SSH read calls use explicit user/host/port/identity/known-host fingerprints and `ssh -n -F /dev/null`. Immutable supply uses metadata/range-zero digest reads without download/cache writes.
- **D-19:** Every production observation/receipt is closed-schema and value-free: one unique `observation_id` identifies the collection and every receipt has a distinct unique `receipt_id`; each binds started/completed/expiry timestamps, execution-source commit/tree, route/tool/provider operation ID, revision/ETag, payload and semantic digests, locally derived preview from prestate/desired/ordered operations, and exact safe flags. Capacity binds exactly six ordered samples, one exact common capacity-policy SHA-256, raw bytes/inodes/image/backups/log-reservation counters and the independently derived policy result. Missing/duplicate/reordered IDs, policy mismatch, raw stdout/stderr/payload, secret material, missing provenance and unknown fields fail closed. The 05D2H receipt uses the same provenance discipline.
- **D-20:** D implements `collect-and-plan`, `validate-generation` and `promote-generation` plus tests but does not execute them. W may only execute a separately hash-bound continuity-route OperationPlan after a future exact owner approval and must produce ordered readback/rollback plus a value-free current observation. E Task 1 generates and validates only in private non-repo storage. Its closed branch table is: rc0 only for current observation plus W `STRICT_EQUIVALENCE_PROVEN` and a complete six-file bundle whose OperationPlan is last; rc3 only after a fresh valid current observation that remains mismatch/unproven, producing exactly a non-authorizing attestation plus blocked preflight marker; every other rc produces zero authority artifacts. Route unavailable, frozen-only input or missing/malformed/stale current observation never maps to rc3. E Task 2 is a read-only hash-bound checkpoint only for rc0. E Task 3 is the sole canonical writer: it preserves rc3 under `set -e`, revalidates source/W/H and fresh prestates through the governed launcher, uses exclusive no-replace promotion, cleans only invocation-created paths on failure, and writes the exact branch summary. F accepts only strict W and starts in a new launcher process, recollecting all current surfaces before import/factory/journal. Any drift requires a new OperationPlan and new approval.
- **D-21:** Before R, Q creates `validate-phase53-dirty-baseline.py`, its dedicated test, and one canonical value-free baseline for exactly the seven dirty D2D paths. The validator derives tracked/untracked via `git ls-files`, captures exact porcelain-v1 `-z` XY, and uses `lstat` plus O_NOFOLLOW streaming SHA-256 in 1 MiB chunks over regular files, with a double pass that rejects TOCTOU. The closed duplicate-key-rejecting schema binds exact path set, type/mode/size, RFC3339 `captured_at`, captured HEAD and a self digest. Creation is create-only mode 0600 with fsync/no-replace and never records payload/diff/stdout/stderr. The only legal sequence is capture H, run `exact` while HEAD=H, commit exactly validator+test+baseline as one-parent S with parent(S)=H, validate source-only `ancestor`, commit only the summary as one-parent C with parent(C)=S, then validate summary-form `ancestor`; `exact` is never run after S exists. `ancestor` recomputes every dirty-path field without requiring current HEAD=H, requires S/C ancestry to current HEAD, and pairs summary commit/path arguments. D first validates `ancestor` before editing the seven paths. No stash, revert or clean is permitted.
- **D-22:** Credential FDs are created inside the governed scope. The actual process chain is `omni` → `systemd-run` → `/usr/bin/flock` → launcher → `execve(target)`: flock remains the immediate parent/lock holder, while target retains the launcher PID and shares `omni-builds.slice` with flock. The standalone literal smoke invokes the wrapper exactly once; governed pytest never recursively reacquires the capacity-1 semaphore. The launcher hydrates only approved Vault profiles/variable names in memory, creates/seals memfd/pipe or opened-then-unlinked known-host FDs, makes only exact descriptors inheritable, closes every other non-stdio FD and execves the final absolute target with no secret env/log persistence. No governor change or no-fork flock option is allowed. A shared source-sealed MCP client implements initialize, session ID, initialized notification, tools/list allowlist, tool call, structured response validation and close for both read and apply paths. Host/Apache/runtime apply uses a source-sealed stdin-only one-shot worker sent every invocation to fixed `/usr/bin/sudo -n /usr/bin/python3 -I -`; no scp/helper install or arbitrary shell fragment is allowed.
- **D-23:** Vault identity continuity never follows from `current_version=1` plus a historical fingerprint alone. R exposes only a generic launcher/reader interface and does not claim the Phase 53 Vault route exists. V source-only defines true metadata endpoints plus distinct server-side `data-read-derived-output` for current fingerprint/pair-validity, reusing only the Phase 52 approved public key/fingerprint. It forbids key generation/import/replacement/rotation and AppRole/token/ACL creation. The authorized_keys change is only the exact Phase 52 forced-command prefix to the Phase 53 prefix, preserving suffix and unrelated bytes; every other prestate is NO_GO. The forced dispatcher accepts zero argv, empty stdin and only protocols `phase53-vault-continuity-metadata-v1` and `phase53-vault-continuity-derived-v1`, uses exact sudo dispatch, delegates legacy commands to Phase 52 and rejects malformed input with 64. W owns live prestate, plan, approval, install ordering, readback, authorized_keys-first reverse if-current rollback and evidence. W's decision is only `STRICT_EQUIVALENCE_PROVEN` or `NO_GO`; no override branch exists.
- **D-24:** Cloudflare prestate selects the exact owner-approved branch per hostname before OperationPlan: absent uses POST/create, binds the returned record ID and exact readback, then rollback delete-if-current; present uses revision/ETag CAS update, exact readback and rollback restore-if-current. Duplicate names, mixed identity or revision drift block. W has its own continuity-route OperationPlan and never reuses an edge approval. Housekeeping runs only after W authorizes continuity and records scoped truth: provider_mutation=false, network_mutation=false, live_runtime_mutation=false, housekeeping_filesystem_mutation=true and recoverable=true. If W is NO-GO, H/E/F/06 are structurally ineligible.

### the agent's Discretion

- Internal implementation language/framework of the small operational API, provided the plan prefers existing repo patterns, produces reproducible ARM64 artifacts without uncontrolled host builds, and satisfies authentication/redaction tests.
- Exact split of the combined CPU/RAM ceiling between `hbbs`, `hbbr` and the operational API, provided the server pair remains within its contract and aggregate host accounting is explicit.
- Exact external secondary probe provider and evidence encoding, provided it is genuinely outside the primary host and contains no secrets.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements

- `.planning/workstreams/rustdesk-fleet/ROADMAP.md` — Phase 53 goal, risks, five success criteria and Phase 54 boundary.
- `.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md` — `SRV-02`, `SRV-03`, `SRV-04`, `SRV-06` and `OPS-01` contracts.
- `.planning/workstreams/rustdesk-fleet/STATE.md` — current workstream position and selected-primary truth.

### Placement and topology

- `.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-PHASE53-TOPOLOGY-REVIEW.md` — current PASS/READY decision, selected Horistic and Windows boundary.
- `.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-HORISTIC-TOPOLOGY-IMPACT-REVIEW.md` — mandatory server/client isolation and co-location consequences.
- `.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-07-VERIFICATION.md` — independently verified Phase 52 prerequisite state.

### Supply, identity and recovery

- `.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-RESEARCH.md` — official image digest, Quadlet restrictions, ports and identity-handling research.
- `modules/rustdesk-fleet/contracts/supply-chain.json` — immutable server image identity.
- `modules/rustdesk-fleet/contracts/secret-roles.json` — approved Vault authority and public/private boundary.
- `modules/rustdesk-fleet/contracts/phase53-edge.json` — single machine-readable authority for the three DNS-only hostnames, reserved public address, translated external ports, internal native listeners and exhaustive public negatives.
- `modules/rustdesk-fleet/evidence/phase52/full-gate-summary.json` — selected-candidate stage vector and mutation accounting.
- `modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json` — value-free exact create-only transaction proof.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `modules/rustdesk-fleet/tools/phase52_recovery.py`: pinned hbbs command construction, bounded process execution, liveness wait, SQLite normalization and listener inspection.
- `modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py`: Horistic SSH/runtime patterns, mutation accounting, rollback terminality and redacted evidence schemas.
- `modules/rustdesk-fleet/tools/rustdesk-vault-provider`: bounded value-free provider surface for identity hydration.
- `modules/fleet-backup/scripts/*phase52*`: verified state-only backup/fetch and retained rollback artifacts.

### Established Patterns

- Managed runtime uses Podman plus user systemd/Quadlets, exact digest pins, transactional installers and explicit rollback manifests.
- Validators emit strict JSON schemas with stable check IDs, fail on extra fields or stored-verdict drift, and keep secret scans in the phase gate.
- CPU-heavy validation/build work runs through `omni srv1-ops resources run builds -- ...`; the primary runtime itself must have explicit systemd/container limits.

### Integration Points

- New production server contracts, installers, validators and evidence live under `modules/rustdesk-fleet/`.
- DNS/Cloudflare credentials are hydrated only from the Vault `cloudflare` profile; live edge changes must preserve previous records for rollback and consume `phase53-edge.json` instead of maintaining a second port/hostname authority.
- External Windows probes use the existing private-first SSH route and record only connectivity outcomes/timestamps.

</code_context>

<specifics>
## Specific Ideas

- Keep the operational API intentionally small and read-only; it exists because Giovanni approved central ATIUS endpoints while accepting the missing RustDesk OSS native API.
- Treat the Horistic reboot as a deliberate production primary outage now and, in Phase 54, as a joint server/client outage with separate recovery evidence.

</specifics>

<deferred>
## Deferred Ideas

- RustDesk client installation on Horistic and Windows, UAC/LightDM, direct-first and forced-relay canary proof — Phase 54.
- RustDesk client installation on `atius-srv-2`, `atius-srv-3`, then `atius-srv-1` — Phase 55.
- Full 20+5 connection matrix and authoritative transport correlation — Phase 56.
- Independent standby/failover topology — Phase 57.

</deferred>

---

*Phase: 53-primary-relay-and-public-edge*
*Context gathered: 2026-07-22*
