# Pitfalls Research

**Domain:** Production rollout of self-hosted RustDesk across the Atius fleet
**Researched:** 2026-07-19
**Confidence:** HIGH for identified safety and verification risks; MEDIUM for LightDM recovery behavior pending canary execution

## Evidence Boundaries

- Claims about RustDesk roles, ports, packages, client configuration, headless requirements, and Pro-only capabilities come from official RustDesk documentation and repositories.
- Disk thresholds, host placement, Vault rules, CPU limits, fleet test counts, legacy-tool preservation, and GSD workstream constraints are local requirements or live evidence.
- No result in this document is implementation evidence. Every runtime claim remains pending until the corresponding phase executes its gate.

## Critical Pitfalls

### Pitfall 1: Deploying at the disk watchdog boundary

**What goes wrong:**
Pulling images, retaining rollback artifacts, or allowing logs to grow pushes `srv-2` from the observed 84% to the 85% critical threshold.

**Why it happens:**
The absolute 32 GiB available looks sufficient, while the governed threshold leaves only about one percentage point of operational margin.

**How to avoid:**
Require `<=78%` before deployment, calculate image/state/log/rollback reservations in bytes, and require projected plus measured post-deploy use `<=80%` with at least 20 GiB available.

**Warning signs:**
Rounded `df -h` used as the only capacity evidence; no log cap; rollback image stored outside the formula; deployment proposed while root remains at 84%.

**Phase to address:**
Phase 2 — Capacity, network, and rollback preflight.

---

### Pitfall 2: Assuming LightDM is supported headless because X11 exists

**What goes wrong:**
RustDesk works inside a logged-in LXDE session but cannot control the LightDM greeter after logout or reboot.

**Why it happens:**
Official headless guidance requires a desktop environment, Xorg, and GDM. The local fleet uses LightDM, an undocumented combination for this behavior.

**How to avoid:**
Keep LightDM unchanged and run empirical tests for active session, lock, logout, reboot, pre-login, and reconnect on every Linux host. Preserve XRDP/RustGuac.

**Warning signs:**
Acceptance based only on service state, generated ID, or a test made after a human has already logged in.

**Phase to address:**
Phases 4 and 5 — Canaries and serialized Linux rollout.

---

### Pitfall 3: Confusing server keys with per-target credentials

**What goes wrong:**
The server private key is copied to clients, a new keypair is generated during restore, or all hosts receive the same permanent password.

**Why it happens:**
The UI labels the public key as `Key`, while Pro license keys, server identity, client identity, and access passwords are different concepts.

**How to avoid:**
Use one server keypair for `hbbs`/`hbbr`; distribute only the shared public key; keep the private key in Vault/runtime backup; use five distinct Vault passwords.

**Warning signs:**
Private key in a config template; key mismatch after restart; identical password references across inventory; secret values in command logs.

**Phase to address:**
Phases 1-3 — Contract, preflight, and server deployment.

---

### Pitfall 4: Proving only the shared relay, not every target

**What goes wrong:**
One relay session passes, but another client cannot reach or sustain the relay path.

**Why it happens:**
There is one shared `hbbr`, so a shared-path test appears sufficient even though endpoint networks, OS services, and permissions differ.

**How to avoid:**
Run 20 normal ordered pairs plus one forced-relay inbound session for each of the five targets.

**Warning signs:**
Evidence contains fewer than 25 positive sessions or does not name controller, controlled target, transport, start/end time, and result.

**Phase to address:**
Phase 6 — Directed fleet verification.

---

### Pitfall 5: Leaking permanent passwords through automation

**What goes wrong:**
Passwords appear in shell history, process logs, CI output, Markdown, Obsidian, GBrain, or support bundles.

**Why it happens:**
The official CLI accepts `--password` as an argument, making careless wrappers easy to log.

**How to avoid:**
Hydrate per-target passwords only for the short-lived local command, disable tracing, avoid echo, redact process/log evidence, and validate the negative/positive behavior rather than recording the value.

**Warning signs:**
`set -x`, verbose PowerShell transcription, command echo, persisted environment variables, or screenshots containing credentials.

**Phase to address:**
Phases 2, 4, and 5.

---

### Pitfall 6: Treating host networking as hardening

**What goes wrong:**
Rootless containers run correctly but expose extra ports, inherit unnecessary capabilities, or bypass expected firewall assumptions.

**Why it happens:**
Rootless reduces privilege; it does not make `Network=host` private.

**How to avoid:**
Pin the image digest, minimize capabilities, apply no-new-privileges where supported, isolate writable state, cap CPU/logs, and validate OCI plus host firewall exposure externally.

**Warning signs:**
TCP `21114`, `21118`, or `21119` open in OSS baseline; listener checks only on localhost; container is rootful without an exception record.

**Phase to address:**
Phase 3 — Server deployment.

---

### Pitfall 7: Calling rollback complete without executing it

**What goes wrong:**
An upgrade changes state or identity and the old version cannot resume service.

**Why it happens:**
Teams preserve a previous tag or write a runbook but never restore the old image, state, key, and client connectivity.

**How to avoid:**
Execute server rollback, one Linux client rollback, and one Windows client rollback; prove stable ID/key, registration, direct path, relay path, and existing-tool fallback afterward.

**Warning signs:**
Rollback evidence is a command list, not timestamped runtime output; old artifact hash or state snapshot is missing.

**Phase to address:**
Phase 7 — Resilience, upgrade, and rollback.

---

### Pitfall 8: Replacing the existing recovery stack too early

**What goes wrong:**
A RustDesk regression removes all practical access to a host.

**Why it happens:**
The new tool is treated as a replacement instead of an additional access path during validation.

**How to avoid:**
Keep RustGuac, XRDP, AnyDesk, and NoMachine installed and verify their critical paths after RustDesk changes.

**Warning signs:**
Uninstall/disable commands in the RustDesk plan; port reassignment without port-map validation; rollback depends on RustDesk itself.

**Phase to address:**
All execution phases; final regression in Phase 8.

---

### Pitfall 9: Claiming OSS has Pro control-plane capabilities

**What goes wrong:**
Production is approved under the assumption that OSS supplies SSO, RBAC, API, web console, policy sync, or human-attributed audit.

**Why it happens:**
Self-hosting is conflated with centralized enterprise management.

**How to avoid:**
Record explicit OSS risk acceptance. If any control-plane capability is mandatory, stop and select/license Pro before production.

**Warning signs:**
Requirements mention Atius SSO or audit attribution but the architecture still has no Pro server/API.

**Phase to address:**
Phase 1 — Contract and licensing decision.

---

### Pitfall 10: Mutating the wrong GSD workstream after migration

**What goes wrong:**
An unscoped command writes STATE, ROADMAP, REQUIREMENTS, phases, PROJECT, MILESTONES, or graph state for the wrong delivery lane.

**Why it happens:**
The operator assumes the active-workstream marker is sufficient and omits an explicit `--ws rustdesk-fleet` scope or overlaps a shared-file writer.

**How to avoid:**
Use explicit RustDesk workstream scoping, serialize shared PROJECT/MILESTONES/Graphify integration, and verify both workstreams after every lifecycle mutation. The completed migration snapshot remains the rollback source for the namespace conversion.

**Warning signs:**
Commands without RustDesk workstream scope, shared-file changes by more than one writer, a stale Graphify graph, or Phase 48 artifacts appearing under the RustDesk lane.

**Phase to address:**
Phase 1 and every lifecycle transition.

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `latest` image/client discovery | Less version bookkeeping | Non-reproducible upgrades and rollback | Never in production |
| Configure clients by GUI only | Fast canary | Unverifiable drift across five hosts | Canary exploration only; replace before rollout |
| One forced-relay test total | Shorter QA | Misses endpoint-specific relay failures | Never for final acceptance |
| Skip 20 ordered pairs | Faster completion | Does not satisfy the final explicit fleet matrix | Never for this milestone |
| Keep passwords outside Vault | Easier scripting | Secret sprawl and unrecoverable authority | Never |
| Run rootful containers | Avoid rootless troubleshooting | Larger blast radius | Only with a documented blocker and separate approval |
| Omit cold-standby drill | Saves time | Backup may be unusable during outage | Never for final completion |
| Remove legacy tools | Reduces visible duplication | Loses break-glass paths | Only in a later decommission milestone |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Cloudflare DNS | Proxy the hostname as an HTTP site | DNS-only A record for native TCP/UDP RustDesk ports |
| OCI ingress | Open the full TCP 21114-21119 range | Open TCP 21115-21117 and UDP 21116 only for OSS baseline |
| Vault | Store public and private material as indistinguishable secrets | Private key/passwords secret; public key distributable and fingerprinted |
| Podman host network | Trust rootless status as network isolation | Enforce external OCI/host firewall checks and minimum listeners |
| LightDM/XRDP | Change display manager to match RustDesk docs | Preserve LightDM; use empirical gate and existing fallbacks |
| GSD workstreams | Create a workstream during Phase 48 | Wait for clean checkpoint and fresh Graphify |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Relay forced permanently | Rising bandwidth and latency on `srv-2` | Direct-first production; force relay only for tests or approved policy | When direct-capable sessions unnecessarily traverse `hbbr` |
| Unbounded logs | Disk crosses 80/85% gates | Journald/container log caps and capacity formula | Potentially after any repeated auth/session error storm |
| Rollback copies on root omitted from capacity | Deployment passes preflight then crosses watchdog | Reserve current and rollback images/snapshots in byte formula | At the first real upgrade |
| All tests started concurrently | CPU/network spike obscures attribution | Serialize target rollout and cap soak concurrency | During 20-pair verification if unmanaged |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Copy server private key to clients | Fleet-wide server impersonation risk | Distribute only `id_ed25519.pub`; private key stays in server/Vault boundary |
| Shared permanent password | One credential compromises all targets | Unique Vault password per host |
| Accept server without public key | Trust-on-first-use/MITM exposure | Set and verify the expected shared public key |
| Open unused ports | Expanded public attack surface | Minimum OSS ports only |
| Enable unnecessary permissions | File transfer, terminal, tunnel, restart, or clipboard abuse | Explicit policy and negative permission tests on Linux and Windows |
| Store session evidence unredacted | Secret and personal-data leakage | Redact IDs only where required and never store passwords/private key |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Host works only after local login | Operator believes unattended recovery exists when it does not | Label attended-only until pre-login test passes |
| Ambiguous host IDs | Wrong machine selected during support | Record hostname-to-RustDesk-ID mapping without credentials |
| Relay/direct path not visible in evidence | Performance failures are hard to diagnose | Record transport path and timestamps for each session |
| Existing tools silently changed | Operators lose familiar recovery paths | Explicit regression checklist and no decommission in scope |

## "Looks Done But Isn't" Checklist

- [ ] **Server running:** `hbbs`/`hbbr` active is insufficient — verify public TCP/UDP ingress, key persistence, direct, relay, restart, and rollback.
- [ ] **Client installed:** Package presence is insufficient — verify ID, effective options, positive/negative authentication, visual control, and reboot.
- [ ] **All hosts tested:** Five host smokes are insufficient — verify all 20 directed normal pairs and five forced-relay targets.
- [ ] **Headless enabled:** Option state is insufficient — verify LightDM greeter before login on every Linux host.
- [ ] **Windows service active:** Service state is insufficient — verify locked screen, reboot, pre-login, and UAC/elevation.
- [ ] **Secrets migrated:** Vault path existence is insufficient — verify restore without exposing values and reject wrong credentials.
- [ ] **Backup created:** Archive existence is insufficient — restore it on isolated `srv-3` and prove matching server identity.
- [ ] **Rollback documented:** A runbook is insufficient — execute server, Linux, and Windows rollback.
- [ ] **No regression:** RustDesk success is insufficient — re-test RustGuac, XRDP, AnyDesk, and NoMachine.
- [ ] **GSD isolated:** Workstream creation is insufficient — verify Phase 48 remains intact and every RustDesk lifecycle command targets `rustdesk-fleet`.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Disk gate crossed | MEDIUM | Stop rollout, preserve access, prune only approved/recoverable data, move governed storage if designed, recalculate before resume |
| Server key mismatch | HIGH | Stop activation, restore authoritative private key from Vault/backup, verify public fingerprint, reconnect disposable clients first |
| LightDM pre-login failure | MEDIUM | Keep LightDM, classify RustDesk attended-only, restore XRDP/RustGuac path, open separate virtual-seat investigation |
| Client rollout regression | MEDIUM | Use preserved DEB/MSI/config backup, roll back one host, prove legacy access, then resume serially |
| Server upgrade failure | HIGH | Restore pinned prior digest and state snapshot, prove registration/direct/relay, then investigate offline |
| Planning migration conflict | HIGH | Stop writers, preserve current diffs, reconcile against last committed checkpoint, rebuild Graphify only after ownership is clear |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| OSS/Pro capability mismatch | Phase 1 | Signed requirement decision and explicit OSS risk acceptance or Pro selection |
| Disk/watchdog boundary | Phase 2 | Exact byte formula, pre `<=78%`, projected/measured post `<=80%` |
| Key/password misuse | Phases 2-3 | Vault path/fingerprint checks; no secret scan hits |
| Host-network exposure | Phase 3 | External listener/port scan and rootless hardening evidence |
| LightDM headless assumption | Phases 4-5 | Lock/logout/reboot/pre-login proof per Linux target |
| Incomplete connection coverage | Phase 6 | 20 normal + 5 forced relay + negative matrix complete |
| Performance/log growth | Phases 3, 6-7 | Resource metrics, 30-minute target runs, two-hour soak |
| Fake rollback | Phase 7 | Timestamped server/Linux/Windows rollback and re-upgrade evidence |
| Legacy access removal/regression | Phases 4-8 | RustGuac/XRDP/AnyDesk/NoMachine regression checklist |
| Wrong-workstream planning mutation | Phase 1 and transitions | Explicit RustDesk scope, single shared writer, Phase 48 integrity check, Graphify fresh |

## NO-GO Conditions

- `srv-2` remains above 78% pre-deploy or exceeds projected/measured 80% post-deploy.
- Rootless execution, host-network hardening, image digest, or combined CPU ceiling cannot be verified.
- The server private key or any target password appears outside Vault/runtime secret handling.
- SSO, RBAC, API, or human-attributed audit is mandatory while OSS remains selected.
- Any Linux target fails required pre-login unattended control and unattended remains a completion requirement.
- Any existing RustGuac, XRDP, AnyDesk, or NoMachine recovery path regresses.
- The 20 normal pairs, five forced-relay targets, five wrong-password negatives, or Linux/Windows wrong-key negatives are incomplete.
- The 30-minute per-target tests or two-hour representative soak do not pass.
- Server, Linux client, or Windows client rollback is not actually executed.
- `srv-3` is promoted without restore and failover evidence.
- A RustDesk command targets the wrong workstream, Phase 48 integrity cannot be proved after a lifecycle mutation, or Graphify is stale at a planning/execution checkpoint.

## Sources

- [RustDesk self-host architecture](https://rustdesk.com/docs/en/self-host/) — server roles, direct/relay behavior, and port definitions.
- [RustDesk Server OSS Docker/Podman](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/) — persistence, host network, ports, and relay forcing configuration.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — server public key and client server settings.
- [RustDesk advanced settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/) — headless prerequisites, password modes, and permission controls.
- [RustDesk Linux documentation](https://rustdesk.com/docs/en/manual/linux/) — experimental Wayland and login-screen limitation.
- [RustDesk Server Pro](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/) — Pro-only identity and management capabilities.
- [RustDesk Server Pro license](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/license/) — licensing boundary and server migration behavior.
- [RustDesk Server Pro upgrade FAQ](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/faq/#there-is-a-new-version-of-rustdesk-server-pro-out-how-can-i-upgrade) — backup-before-upgrade guidance.

---
*Pitfalls research for: RustDesk fleet remote access*
*Researched: 2026-07-19*
