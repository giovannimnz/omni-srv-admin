# Architecture Research

**Domain:** Self-hosted RustDesk control and relay architecture for the Atius fleet
**Researched:** 2026-07-19
**Confidence:** HIGH for server/network topology; MEDIUM for LightDM pre-login behavior pending per-host validation

## Evidence Boundaries

### Official architecture facts

- `hbbs` owns ID registration, rendezvous, signaling, and NAT traversal coordination.
- `hbbr` carries relay traffic only when a direct connection cannot be used or relay use is deliberately forced.
- Clients need the ID server and the server public key. In the same-host default topology, relay configuration can be explicit or inferred.
- OSS has no Pro web console/API/OIDC/RBAC/audit contract.

### Local architecture decisions and live evidence

- `srv-2` is the preferred primary because the user selected it and it has fewer security workloads than `srv-3`; placement remains blocked at the observed 84% disk use.
- The public name is `rustdesk.atius.com.br` as a DNS-only record. This is a local inference required to preserve native TCP/UDP reachability, not an official Cloudflare topology prescription.
- The primary runs two rootless hardened Podman Quadlets with host networking and a shared persistent state boundary.
- `srv-3` is a cold standby only after a real backup/restore/failover drill.
- Existing remote-access systems remain installed and tested.
- The planning surface was safely migrated into two workstreams after snapshot and lock-owner checks; Phase 48 remains in `runtime-trust-codex-delivery-convergence`, while RustDesk lifecycle artifacts belong only to `rustdesk-fleet`.

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                    Managed clients — RustDesk 1.4.9                 │
│                                                                      │
│  srv-1 ARM64  srv-2 ARM64  srv-3 ARM64  Horistic ARM64  W11 AMD64 │
│       │            │            │             │            │         │
└───────┴────────────┴────────────┴─────────────┴────────────┴─────────┘
                               │
                   rustdesk.atius.com.br
                    DNS-only A -> srv-2
                               │
┌──────────────────────────────┴───────────────────────────────────────┐
│                 atius-srv-2 — conditional primary                   │
│                                                                      │
│  rootless Podman/user-systemd, host network, combined CPU <= 0.8    │
│                                                                      │
│  ┌──────────────────────────┐    ┌──────────────────────────┐        │
│  │ hbbs 1.1.15             │    │ hbbr 1.1.15             │        │
│  │ TCP 21115, 21116        │    │ TCP 21117               │        │
│  │ UDP 21116               │    │ relay fallback          │        │
│  └────────────┬─────────────┘    └────────────┬─────────────┘        │
│               └──────────┬────────────────────┘                      │
│                    persistent state                                 │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ backup/restore, never active-active
┌─────────────────────────┴────────────────────────────────────────────┐
│               atius-srv-3 — future cold standby                     │
└──────────────────────────────────────────────────────────────────────┘

Vault: server private key + five per-target passwords
Repo/config: shared server public key + non-secret desired state
Fallbacks preserved: RustGuac, XRDP, AnyDesk, NoMachine
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `hbbs` | Register client IDs, receive heartbeats, coordinate rendezvous and direct connection attempts | Rootless Quadlet, pinned `rustdesk-server:1.1.15` image |
| `hbbr` | Relay encrypted session traffic when the direct path is unavailable or forced | Separate rootless Quadlet sharing server identity state |
| RustDesk Linux clients | Controlled and controlling roles on four ARM64 Ubuntu hosts | Pinned AArch64 `.deb`, system service, CLI-managed options |
| RustDesk Windows client | Controlled and controlling roles on W11 | Pinned x86-64 MSI, Windows service, elevated CLI management |
| Vault | Authoritative secret lifecycle and recovery | One server private key plus five target-specific passwords |
| DNS/OCI/firewall | Resolve and expose the minimum native surface | DNS-only record; TCP 21115-21117 and UDP 21116 |
| Evidence ledger | Bind requirements to current runtime proof | Session matrix, negative tests, soak, reboot, upgrade, rollback artifacts |
| Existing access stack | Recovery path and regression baseline | RustGuac, XRDP, AnyDesk, NoMachine retained |

## Recommended Project Structure

This is the intended later implementation shape, not files authorized by this research task:

```text
modules/rustdesk-fleet/
├── quadlet/                 # hbbs/hbbr unit templates and hardening
├── scripts/                 # preflight, deploy, configure, verify, rollback
├── tests/                   # offline, remote, negative, and evidence validators
└── README.md                # module contract without secrets

inventory/hosts/
└── <existing host>.yaml     # non-secret version/status/evidence only

docs/operations/
└── rustdesk-fleet.md        # operator runbook and recovery contract

.planning/phases/<future>/
└── evidence/                # redacted current test outputs
```

### Structure Rationale

- **`modules/rustdesk-fleet/`:** keeps desired state, orchestration, and tests under one owned module boundary.
- **`quadlet/`:** separates server runtime declarations from orchestration code.
- **`scripts/`:** ensures secrets are hydrated at execution time and not embedded in manifests.
- **`tests/`:** separates offline safety checks from live remote-control evidence.
- **`evidence/`:** allows completion claims to point to per-host and per-path proof without storing credentials.

## Architectural Patterns

### Pattern 1: Direct-first with explicit relay verification

**What:** Let RustDesk attempt direct peer connectivity during normal operation, while maintaining `hbbr` as fallback.

**When to use:** Default production operation.

**Trade-offs:** Reduces relay bandwidth, but requires explicit tests to prove both direct and relay paths. The acceptance suite therefore includes all 20 normal directed pairs and five forced-relay target tests.

### Pattern 2: Rootless immutable runtime

**What:** Run `hbbs` and `hbbr` as separate rootless user-systemd Quadlets pinned to a version and manifest digest, with writable state isolated from an otherwise immutable container filesystem.

**When to use:** Primary production deployment on `srv-2`.

**Trade-offs:** Stronger containment and deterministic rollback; host networking still exposes the process directly and must be constrained by OCI and host firewall rules. Validate no added capability, no-new-privileges, writable-path scope, user namespace, and CPU/log limits against the installed Podman version.

### Pattern 3: Public-key distribution, private-key isolation

**What:** Generate or restore one server keypair, distribute only its public key to clients, and store the private key in the runtime state plus Vault recovery path.

**When to use:** Initial deployment, restore, failover, and client onboarding.

**Trade-offs:** Stable client trust and simple configuration; loss or accidental rotation of the private key causes key mismatch across the entire fleet.

### Pattern 4: Serialized fleet rollout

**What:** Deploy and validate one target at a time after the Horistic + W11 canaries.

**When to use:** All client installation and upgrade waves.

**Trade-offs:** Slower than blind parallel rollout, but preserves clear attribution and prevents a fleet-wide remote-access regression.

### Pattern 5: Primary plus cold standby

**What:** Keep only `srv-2` active. Prepare `srv-3` only after restore and failover are proven with the same server identity.

**When to use:** Recovery design for the OSS baseline.

**Trade-offs:** Recovery is not instantaneous; avoids unproven active-active state consistency.

## Data Flow

### Registration and direct session

```text
[Client B heartbeat]
        -> [hbbs TCP/UDP 21116: ID and reachable endpoint]

[Client A requests Client B]
        -> [hbbs rendezvous/signaling]
        -> [direct hole-punch attempt]
        -> [A <-> B direct session]
```

### Relay fallback

```text
[Direct path fails or test forces relay]
        -> [hbbs returns relay path]
        -> [Client A <-> hbbr TCP 21117 <-> Client B]
```

### Managed configuration

```text
[Versioned deployment script]
        -> [verify artifact SHA-256]
        -> [install DEB/MSI]
        -> [set ID host + relay host + shared public key]
        -> [hydrate unique target password from Vault]
        -> [query effective options + get ID + service check]
        -> [positive and negative connection proof]
```

### Recovery

```text
[Quiesced primary snapshot + Vault private key]
        -> [restore on isolated srv-3 standby]
        -> [validate key/state without simultaneous public activation]
        -> [controlled DNS/ingress cutover]
        -> [client registration + direct + relay smoke]
        -> [rollback to srv-2 or accept failover]
```

## State Management

| State | Authority | Persistence | Verification |
|-------|-----------|-------------|--------------|
| Server private key | Vault; hydrated runtime copy | Restricted persistent server directory | Public-key fingerprint matches expected value after restart/restore |
| Server public key | Non-secret desired state | Repo/config and client option | CLI option query and wrong-key negative test |
| Per-target password | Vault | RustDesk local protected config after CLI application | Correct password succeeds; wrong password fails 5/5 |
| Client ID | Client-generated local state | Host-local RustDesk config | `--get-id` stable through restart/upgrade/rollback |
| Server data/logs | Persistent server directory | Bounded filesystem/log retention | Snapshot, restore, disk and log-cap checks |
| Acceptance evidence | Planning phase evidence area | Redacted Markdown/JSON/log excerpts | Requirement-to-evidence validator |

## Network and Capacity Contract

| Item | Contract |
|------|----------|
| DNS | `rustdesk.atius.com.br` DNS-only to `srv-2` public IP |
| TCP ingress | `21115`, `21116`, `21117` only |
| UDP ingress | `21116` only |
| Explicitly closed | `21114`, `21118`, `21119` in OSS baseline |
| Runtime CPU | `hbbs` + `hbbr` combined at or below `0.8` CPU |
| Disk pre-gate | Root filesystem at or below 78% |
| Disk post-gate | Projected and measured root use at or below 80%, at least 20 GiB available |
| Routing | Direct-first; forced relay only in controlled tests or a separately approved policy |

Capacity calculation:

```text
post% = 100 * (
    used
  + pulled_images
  + persistent_state_reservation
  + bounded_log_reservation
  + rollback_image_and_snapshot_reservation
) / filesystem_total
```

## Verification Topology

Five hosts produce `5 * 4 = 20` ordered non-self pairs. Every pair must pass a normal direct-first session. In addition:

- each target must pass one forced-relay inbound session: 5 tests;
- every target must reject a wrong permanent password: 5 tests;
- disposable Linux and Windows contexts must reject the wrong server public key;
- every target must sustain a 30-minute session;
- one representative W11/Linux path must sustain a two-hour soak;
- every Linux host must pass logout, locked session, reboot, and pre-login access;
- W11 must pass lock, reboot, pre-login, service, and UAC/elevation behavior;
- server and client rollback plus upgrade must be executed.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current five-host fleet | One `hbbs` + one `hbbr` on `srv-2`; direct-first; bounded cold standby |
| More Atius endpoints | Measure relay bandwidth, file descriptors, logs, and registration behavior before adding resources |
| Multiple sites or sustained relay load | Consider additional relays and evaluate whether Pro relay management is required |
| Mandatory central identity/audit | Replace OSS decision with Pro evaluation before expanding users |

### Scaling Priorities

1. **First bottleneck:** Disk safety and relay bandwidth, not CPU. Govern logs, preserve margin, and measure forced-relay throughput.
2. **Second bottleneck:** Manual OSS inventory and policy management. Promote Pro only when the management requirement is explicit.

## Anti-Patterns

### Blind active-active

**What people do:** Start the same OSS identity/state on two public hosts.

**Why it is wrong:** The baseline has no validated active-active data consistency or relay-selection contract.

**Do this instead:** Keep `srv-3` cold until restore/failover is proven.

### Treating service health as desktop health

**What people do:** Accept `systemctl active`, an open port, or a generated ID as completion.

**Why it is wrong:** None proves LightDM greeter capture, UAC, direct/relay behavior, or rollback.

**Do this instead:** Require the full per-host visual, authentication, reboot, soak, and recovery evidence.

### Mutating the wrong GSD workstream

**What people do:** Run lifecycle commands without explicit RustDesk workstream scope or overlap shared PROJECT/MILESTONES/Graphify writers.

**Why it is wrong:** State, roadmap, requirements, or shared context can be written into the wrong delivery lane even though the namespace migration itself already succeeded.

**Do this instead:** Target `rustdesk-fleet` explicitly, serialize shared-file integration, verify Phase 48 integrity, and require fresh Graphify at checkpoints.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GitHub RustDesk releases | Download pinned artifacts and verify published SHA-256/digest | No `latest` in production |
| Cloudflare DNS | DNS-only A record | Local topology inference; no orange-cloud HTTP proxy for native ports |
| OCI network controls | Explicit minimum TCP/UDP ingress | Validate externally, not only from localhost |
| HashiCorp Vault | Runtime hydration of private key and passwords | Never record secret values in repo or evidence |
| RustDesk Server Pro | Requirement-triggered alternative | Required if central SSO/RBAC/API/human audit is mandatory |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `hbbs` ↔ clients | TCP/UDP 21116 plus TCP 21115 | Registration, heartbeat, NAT and signaling |
| `hbbr` ↔ clients | TCP 21117 | Relay fallback |
| Deployment scripts ↔ Vault | Ephemeral secret hydration | No xtrace, echo, persistent environment, or Markdown values |
| RustDesk ↔ existing remote tools | Coexistence only | No removal or port takeover |
| RustDesk workstream ↔ Phase 48 workstream | Explicit GSD scope plus serialized shared-file integration | Phase 48 remains intact; RustDesk lifecycle files stay namespaced |

## Sources

- [RustDesk self-host architecture](https://rustdesk.com/docs/en/self-host/) — component roles, request flow, relay fallback, and ports.
- [RustDesk Server OSS Docker/Podman](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/) — host network, persistence, Compose, and Quadlet patterns.
- [RustDesk Kubernetes example](https://github.com/rustdesk/rustdesk-server/blob/master/kubernetes/example.yaml) — official single-replica `Recreate` example and RWO persistent state shape.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — ID, relay, public key, API distinction, and config import/export.
- [RustDesk client deployment](https://rustdesk.com/docs/en/self-host/client-deployment/) — managed Linux and Windows deployment patterns.
- [RustDesk Linux documentation](https://rustdesk.com/docs/en/manual/linux/) — X11/Wayland and login-screen limitations.
- [RustDesk advanced settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/) — headless, password, permission, and connection settings.

---
*Architecture research for: RustDesk fleet remote access*
*Researched: 2026-07-19*
