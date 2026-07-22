# Phase 53: Primary Relay and Public Edge - Context

**Gathered:** 2026-07-22
**Status:** Ready for planning
**Source:** Autonomous discussion after Phase 52 PASS and operator authorization to plan and execute

<domain>
## Phase Boundary

Phase 53 deploys the production RustDesk Server OSS primary on the selected `horistic-srv`, publishes only the approved native edge, proves persistence/resource/security behavior, and exposes a separate authenticated/redacted ATIUS operational API. It does not install either canary client; `horistic-srv` and `GIOVANNI-W11-PC` client installation remains Phase 54, while installation on the three Atius servers remains Phase 55.

</domain>

<decisions>
## Implementation Decisions

### Server and colocated-client separation

- **D-01:** Production `hbbs` and `hbbr` use rootless Podman Quadlets on `horistic-srv`, pinned to the Phase 52 ARM64 child digest. No tag-only or auto-update path is allowed.
- **D-02:** The Phase 53 server owns a dedicated state, service, resource, evidence and rollback domain. Future Phase 54 client assets on the same host must not share or mutate those paths.
- **D-03:** The two server containers share the approved combined ceiling of `0.8 CPU` and `1 GiB RAM`; every per-container allocation must sum within that ceiling. Logs are bounded and retained according to the approved Phase 52 budgets.
- **D-04:** Server identity is hydrated from the approved Vault reference through private bounded transport. Evidence records only the public fingerprint and value-free metadata.

### Native edge and external proof

- **D-05:** `rustdesk.atius.com.br` is the sole native client endpoint and remains Cloudflare DNS-only. It must resolve to the validated current public address of the selected Horistic edge; planning must revalidate the address instead of trusting an older inventory value.
- **D-06:** The allowlist is exactly TCP `21115-21117` plus UDP `21116`. TCP `21114`, `21118`, `21119`, other unexpected IPv4 listeners and any unintended IPv6 exposure fail closed.
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
- DNS/Cloudflare credentials are hydrated only from the Vault `cloudflare` profile; live edge changes must preserve previous records for rollback.
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

