# Project Research Summary

**Project:** Omni Srv Admin — RustDesk Fleet
**Domain:** Managed self-hosted remote access for a mixed Ubuntu ARM64 and Windows 11 AMD64 fleet
**Researched:** 2026-07-19
**Confidence:** MEDIUM-HIGH

## Executive Summary

The recommended baseline is RustDesk Server OSS 1.1.15 on a conditional primary
at atius-srv-2, with RustDesk client 1.4.9 on atius-srv-1, atius-srv-2,
atius-srv-3, horistic-srv, and GIOVANNI-W11-PC. The server should run as two
rootless, hardened Podman Quadlets: hbbs for identity, rendezvous, and signaling,
and hbbr for relay fallback. Normal operation remains direct-first; relay use is
proved explicitly rather than forced globally. The public endpoint should be a
DNS-only rustdesk.atius.com.br record exposing only TCP 21115-21117 and UDP
21116. Existing RustGuac, XRDP, AnyDesk, and NoMachine paths remain installed as
independent recovery channels.

This is not yet deployable on atius-srv-2: the observed root filesystem use was
84%, one point below the 85% watchdog critical threshold. Deployment is a NO-GO
until exact byte-level evidence shows no more than 78% use before deployment, no
more than 80% projected and measured afterward, and at least 20 GiB available
after accounting for images, state, bounded logs, rollback artifacts, and
snapshots. atius-srv-3 is not an automatic fallback; it becomes a cold standby
only after the same server identity is restored and a real failover drill
passes.

The largest functional uncertainty is unattended Linux access. Official
RustDesk headless guidance names GDM, while the fleet uses LightDM/LXDE/X11. The
rollout must preserve LightDM and prove active-session, lock, logout, reboot,
and pre-login control on every Linux target. Production acceptance also
requires all 20 ordered non-self host pairs, five per-target forced-relay tests,
negative authentication/key tests, soaks, and executed rollback/upgrade. OSS is
acceptable only with an explicit risk acceptance for the absence of Pro web
console, API, OIDC/LDAP, RBAC, centralized policy/device management, and
human-attributed audit; if any of those controls is mandatory, Pro must be
selected before production.

## Key Findings

Detailed evidence is in [STACK.md](./STACK.md), [FEATURES.md](./FEATURES.md), [ARCHITECTURE.md](./ARCHITECTURE.md), and [PITFALLS.md](./PITFALLS.md).

### Recommended Stack

Use pinned RustDesk releases, local Podman/user-systemd conventions, Vault-backed secret handling, and a minimum native network surface. Mutable tags, manual GUI-only configuration, shared fleet passwords, active-active OSS state, and display-manager replacement are outside the baseline.

**Core technologies:**

- **RustDesk Server OSS 1.1.15:** hbbs and hbbr — sufficient for native self-hosted ID, signaling, direct negotiation, and relay when enterprise control-plane features are not required.
- **RustDesk client 1.4.9:** pinned Linux AArch64 DEB and Windows x86-64 MSI — matches the included host architectures and supports managed CLI/service configuration.
- **Rootless Podman Quadlet plus user systemd:** deterministic server lifecycle — aligns with the repo's managed runtime standard and official RustDesk Quadlet examples.
- **HashiCorp Vault:** authoritative server private key and five unique per-target passwords — keeps high-impact credentials out of the repo, logs, evidence, Obsidian, and GBrain.
- **Cloudflare DNS plus OCI/host firewall:** DNS-only name and minimum public ingress — preserves native TCP/UDP connectivity without an HTTP proxy.
- **RustDesk Server Pro 1.8.5, conditional alternative:** required if SSO/OIDC, RBAC, API, centralized device management, policy, or human-attributed audit becomes mandatory.

### Expected Features

**Must have:**

- Self-hosted hbbs/hbbr with direct-first connectivity and relay fallback.
- Pinned and checksum-verified ARM64 Linux and AMD64 Windows artifacts.
- Deterministic client ID server, relay, public-key, password, and service configuration.
- One server keypair, shared public key, protected private key, and one unique Vault password per target.
- Unattended reboot/pre-login behavior proved on every included host.
- Full 20-pair normal matrix, five per-target forced-relay tests, five wrong-password rejections, and wrong-key rejection on disposable Linux and Windows contexts.
- Thirty-minute sessions for every target and a two-hour representative soak.
- Executed server, Linux-client, and Windows-client rollback plus forward upgrade rehearsal.
- Regression proof for RustGuac, XRDP, AnyDesk, and NoMachine.

**Should have after primary validation:**

- Requirement-to-evidence ledger tying every acceptance claim to current, redacted proof.
- Restored and tested cold standby on atius-srv-3 with preserved server identity.
- Bounded metrics/log evidence and a safe periodic relay smoke.
- Managed artifact mirror if GitHub availability becomes an accepted operational risk.

**Defer:**

- Server Pro unless enterprise identity, policy, API, or audit controls are mandatory.
- Web client and WebSocket ports 21118/21119 until a separate WSS/TLS/browser threat model exists.
- Additional relay geography until measured latency or bandwidth justifies it.
- Removal of any legacy access tool until a separate decommission milestone proves independent recovery.

### Architecture Approach

All five clients register with hbbs through rustdesk.atius.com.br and attempt
direct peer connectivity first. hbbr relays only when direct negotiation fails
or a controlled test forces relay. hbbs and hbbr share one persistent server
identity boundary on atius-srv-2, while Vault is the recovery authority for
private material. The server containers remain separately managed, rootless,
host-networked, digest-pinned, log-bounded, and jointly capped at 0.8 CPU.
Client rollout is serialized after one Linux and one Windows canary, and
atius-srv-3 stays inactive until an isolated restore and controlled DNS/ingress
failover succeed.

**Major components:**

1. **hbbs primary service** — client registration, heartbeat, ID lookup, rendezvous, signaling, and NAT coordination.
2. **hbbr primary service** — encrypted relay fallback on TCP 21117.
3. **Four Linux ARM64 clients** — both controlling and controlled roles, with LightDM/LXDE/X11 acceptance proved empirically.
4. **One Windows 11 AMD64 client** — service, lock-screen, reboot, pre-login, and UAC/elevation acceptance.
5. **Vault secret boundary** — server private-key recovery and five target-specific unattended passwords.
6. **DNS, OCI ingress, and host firewall** — externally validated minimum native surface.
7. **Evidence ledger and legacy access stack** — requirement-level proof plus independent break-glass paths.

The GSD planning surface was transactionally migrated on 2026-07-19 after a full external snapshot and orphan-lock audit. Phase 48 remains intact under runtime-trust-codex-delivery-convergence. Every RustDesk lifecycle command must explicitly target the isolated rustdesk-fleet workstream, while writers for shared PROJECT, MILESTONES, and Graphify state remain serialized.

### Critical Pitfalls

1. **Deploying at the disk watchdog boundary** — reclaim or govern storage first; require pre-deploy use at or below 78%, projected and measured post-deploy use at or below 80%, and at least 20 GiB available.
2. **Assuming LightDM unattended support** — preserve the display manager and require visual lock/logout/reboot/pre-login proof on every Linux host; otherwise classify RustDesk as attended-only and retain fallbacks.
3. **Confusing server identity with access credentials** — distribute only the server public key, keep the private key in Vault/runtime recovery scope, and use five distinct target passwords.
4. **Accepting partial connectivity evidence** — require 20 normal ordered pairs, five per-target relay tests, negative authentication/key tests, reboot/UAC checks, and soaks.
5. **Treating rootless host networking as isolation** — pin the digest, minimize privileges and writable paths, bound CPU/logs, and validate public listeners from outside the host.
6. **Claiming rollback without executing it** — restore prior image, state, key, and client versions and prove registration, direct, relay, and legacy access afterward.
7. **Claiming Pro controls on OSS** — record explicit OSS risk acceptance or stop and select Pro before rollout.
8. **Mutating the wrong GSD workstream** — use explicit rustdesk-fleet scope, one shared-file writer, Phase 48 integrity checks, and fresh Graphify checkpoints.

## Implications for Roadmap

The research supports eight gated phases. Each phase should include its own narrow tests and evidence; no later phase may reinterpret an earlier NO-GO as a warning.

### Phase 1: Contract and Workstream Guardrails

**Rationale:** Licensing, security controls, scope, and planning ownership determine whether the OSS design is valid before infrastructure changes begin.

**Delivers:** Included/excluded host contract; explicit OSS risk acceptance or Pro selection; threat model; requirement-to-evidence ledger; explicit rustdesk-fleet lifecycle command contract; Phase 48 integrity baseline.

**Addresses:** OSS/Pro boundary, five-host scope, secret roles, legacy-tool preservation, and test counts.

**Avoids:** Pro claims on OSS, shared credentials, wrong-workstream mutation, and hidden decommission scope.

### Phase 2: Capacity, Network, Vault, and Recovery Preflight

**Rationale:** The preferred server is currently a hard capacity NO-GO, and public ingress or secret design errors would invalidate every later test.

**Delivers:** Exact byte-level capacity calculation; approved reclamation or governed storage decision; DNS/port collision scan; external ingress plan; Vault paths and access model; backup, restore, upgrade, and rollback design.

**Uses:** Vault, Cloudflare DNS, OCI controls, and host inventory.

**Gate:** atius-srv-2 at or below 78% before deployment, projected post-deploy at or below 80%, and at least 20 GiB available. If it cannot pass, stop for an explicit placement decision; do not silently promote atius-srv-3.

### Phase 3: Hardened Primary Server

**Rationale:** Clients need a stable, recoverable server identity and minimum reachable surface before onboarding.

**Delivers:** Digest-pinned rootless hbbs/hbbr Quadlets on atius-srv-2; persistent identity/state; bounded logs; combined CPU at or below 0.8; restart proof; externally verified TCP 21115-21117 and UDP 21116; unused ports closed.

**Implements:** Primary server, public-key distribution source, runtime hardening, and server observability.

**Avoids:** Mutable images, identity loss, excess ingress, rootful drift, and unbounded resource use.

### Phase 4: Linux and Windows Canaries

**Rationale:** One representative Linux target and GIOVANNI-W11-PC expose the two highest-risk platform behaviors before fleet-wide mutation.

**Delivers:** Pinned clients on horistic-srv and GIOVANNI-W11-PC; managed options; unique Vault passwords; direct and forced-relay sessions; Linux LightDM/LXDE pre-login evidence; Windows lock/reboot/pre-login/UAC evidence; legacy-tool regression results.

**Gate:** If required unattended behavior fails on either platform, stop and classify the limitation before installing the remaining clients.

### Phase 5: Serialized Fleet Rollout

**Rationale:** Per-host installation and verification preserve attribution and prevent a fleet-wide access regression.

**Delivers:** Managed RustDesk client on atius-srv-1, atius-srv-2, and atius-srv-3, one host at a time; stable IDs; effective configuration proof; reboot/pre-login tests; rollback package/config retained; fallback tools rechecked.

**Implements:** Complete five-client topology without removing existing remote access.

### Phase 6: Directed Fleet Verification

**Rationale:** Host-level smoke tests do not prove every controller-to-target route or endpoint-specific relay behavior.

**Delivers:** 20/20 normal ordered non-self sessions; 5/5 forced-relay inbound target sessions; 5/5 wrong-password rejections; wrong-key rejection in disposable Linux and Windows contexts; transport and timestamp evidence.

**Gate:** Any missing direction, target, transport, or negative result keeps the milestone incomplete.

### Phase 7: Resilience, Upgrade, Rollback, and Cold Restore

**Rationale:** Durability is established by exercised recovery, not installed packages or written runbooks.

**Delivers:** Thirty-minute session per target; two-hour representative Linux/Windows soak; server rollback and re-upgrade; one Linux and one Windows client rollback and re-upgrade; isolated atius-srv-3 restore with matching server identity; controlled failover and return path.

**Avoids:** Fake rollback, unusable backup, silent identity rotation, relay saturation, and premature standby promotion.

### Phase 8: Acceptance and Operational Closeout

**Rationale:** The milestone needs one auditable source of truth after all runtime gates pass.

**Delivers:** Requirement-by-requirement UAT; redacted evidence audit; final legacy-tool regression; operator and recovery runbooks; Obsidian and GBrain records; fresh Graphify; workstream and Phase 48 integrity check; explicit statement that no legacy tool was decommissioned.

**Gate:** Close only when every runtime, security, resilience, and planning-isolation requirement has current evidence.

### Phase Ordering Rationale

- Contract and OSS/Pro selection precede infrastructure because enterprise-control requirements can replace the server baseline.
- Capacity, network, Vault, backup, and rollback are preconditions to pulling images or creating public listeners.
- The stable server identity precedes client configuration because every client pins the same public key.
- Cross-platform canaries precede serialized rollout because LightDM and Windows UAC/pre-login behavior are the principal unknowns.
- The complete fleet precedes the 20-pair matrix, while rollback artifacts are retained from the first mutation rather than created afterward.
- Soak, upgrade, rollback, and standby restore follow functional proof but precede acceptance.
- Documentation, Obsidian, GBrain, Graphify, and shared GSD integration close the work only after runtime truth is stable.

### Research Flags

Phases needing deeper research or live discovery during planning:

- **Phase 1:** Confirm whether Atius security policy mandates SSO, RBAC, API, centralized device policy, or human-attributed audit; this decides OSS versus Pro.
- **Phase 2:** Refresh byte-level disk inventory, identify safe reclamation candidates, verify OCI/DNS ownership, and validate Vault helper availability without exposing values.
- **Phase 3:** Confirm exact hardening directives supported by the installed Podman/systemd versions and resolve the ARM64 image manifest digest at deployment time.
- **Phase 4:** Treat LightDM pre-login and Windows UAC/secure-desktop behavior as empirical research; official docs do not establish the local result.
- **Phase 7:** Define a safe isolated restore/failover rehearsal and quantify relay bandwidth/log growth during soaks.

Phases with established patterns after their gates are resolved:

- **Phase 5:** Serialized package/config rollout follows the canary automation and evidence pattern.
- **Phase 6:** The directed-pair and negative-test matrix is fully specified.
- **Phase 8:** Evidence audit, runbook closeout, Obsidian/GBrain documentation, and Graphify freshness follow existing repo governance.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official releases, platform artifacts, roles, ports, licenses, and deployment examples are documented; production digest is resolved again at deployment. |
| Features | HIGH | Included hosts, exclusions, test matrix, rollback, coexistence, and acceptance criteria are explicit. |
| Architecture | MEDIUM-HIGH | Direct-first hbbs/hbbr topology is official and local runtime conventions are clear; capacity, LightDM, external ingress, and cold restore remain live gates. |
| Pitfalls | HIGH | Risks map directly to official limitations, live host evidence, and explicit local safety/governance rules. |

**Overall confidence:** MEDIUM-HIGH

The roadmap shape is well supported. Production readiness remains conditional because the primary host currently fails the disk gate and unattended LightDM behavior is not documented for this fleet.

### Gaps to Address

- **atius-srv-2 capacity:** Re-measure with byte-level data, reclaim approved space or select governed storage, and prove all pre/post reservations.
- **LightDM unattended behavior:** Execute lock, logout, reboot, greeter, and reconnect tests on every Linux host without changing the display manager.
- **horistic-srv management access:** Verify the authorized deployment/control path before selecting it as the Linux canary.
- **OCI and DNS reality:** Confirm public IP ownership, record conflicts, minimum ingress, and external TCP/UDP reachability live.
- **OSS versus Pro:** Obtain explicit risk acceptance or promote Pro before production if centralized identity, policy, API, or audit is required.
- **Podman hardening compatibility:** Validate rootless host-network, no-new-privileges, capability, writable-path, CPU, and log directives against installed versions.
- **Windows service behavior:** Prove reboot, lock screen, pre-login, UAC/elevation, service recovery, and rollback on the managed W11 host.
- **Recovery artifacts:** Confirm old client packages, prior server digest, state snapshot, key restore, and DNS/ingress rollback remain available through the exercise.
- **Workstream lifecycle:** Verify every mutation explicitly targets rustdesk-fleet, Phase 48 remains intact, and Graphify is fresh after shared-file integration.

## Sources

### Primary — HIGH confidence

- [RustDesk client 1.4.9 release](https://github.com/rustdesk/rustdesk/releases/tag/1.4.9) — current client version, architectures, artifacts, and hashes.
- [RustDesk Server OSS 1.1.15 release](https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.15) — current OSS server version and artifacts.
- [RustDesk Server Pro 1.8.5 release](https://github.com/rustdesk/rustdesk-server-pro/releases/tag/1.8.5) — current Pro version boundary.
- [RustDesk self-host architecture](https://rustdesk.com/docs/en/self-host/) — hbbs/hbbr roles, direct/relay behavior, and native ports.
- [RustDesk Server OSS documentation](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/) — OSS scope.
- [RustDesk Docker and Podman deployment](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/) — persistence, host networking, containers, and Quadlet examples.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — ID server, relay, public key, and import/export configuration.
- [RustDesk client deployment](https://rustdesk.com/docs/en/self-host/client-deployment/) — managed Linux and Windows deployment patterns.
- [RustDesk advanced settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/) — headless, password, permission, and relay settings.
- [RustDesk Linux documentation](https://rustdesk.com/docs/en/manual/linux/) — X11/Wayland and login-screen limitations.
- [RustDesk Server Pro documentation](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/) — enterprise management and identity features.
- [RustDesk Server Pro console](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/console/) — console, device, policy, token, and log features.
- [RustDesk Server Pro license](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/license/) — commercial licensing boundary.
- [RustDesk official Kubernetes example](https://github.com/rustdesk/rustdesk-server/blob/master/kubernetes/example.yaml) — single Recreate deployment and persistent-state shape.
- [RustDesk Server OSS license](https://github.com/rustdesk/rustdesk-server/blob/master/LICENSE) — AGPL-3.0 license.

### Local authoritative evidence

- Current host inventory and live filesystem/resource observations captured in the four detailed research reports.
- Repo CPU, k3s, Vault, Graphify, GSD, workstream, and secret-handling contracts.
- Completed 2026-07-19 transactional planning migration evidence: Phase 48 retained in runtime-trust-codex-delivery-convergence and RustDesk isolated to rustdesk-fleet.

### Secondary — MEDIUM confidence

- None relied upon. Local architecture inferences are identified as such and remain subject to live gates.

### Tertiary — LOW confidence

- None relied upon.

---
*Research completed: 2026-07-19*
*Ready for roadmap: yes — subject to the explicit Phase 1 and Phase 2 NO-GO gates*
