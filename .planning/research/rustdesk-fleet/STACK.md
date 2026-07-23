# Stack Research

**Domain:** Self-hosted RustDesk remote-access fleet on Ubuntu ARM64 and Windows 11 AMD64
**Researched:** 2026-07-19
**Confidence:** HIGH for published RustDesk capabilities and release artifacts; MEDIUM for unattended LightDM behavior pending live proof

## Evidence Boundaries

### Official facts

- RustDesk client `1.4.9` is the current GitHub release marked `Latest`; the release publishes Linux AArch64 and Windows x86-64 artifacts.
- RustDesk Server OSS `1.1.15` is the current GitHub release marked `Latest`; it publishes ARM64 and AMD64 server artifacts.
- RustDesk Server OSS consists of `hbbs` for ID/rendezvous/signaling and `hbbr` for relay fallback.
- The minimum native server surface is TCP `21115`, TCP+UDP `21116`, and TCP `21117`. TCP `21118`/`21119` are WebSocket ports and TCP `21114` is the Pro console/API surface.
- The official container documentation includes Docker Compose and Podman Quadlet examples with host networking and persistent data.
- RustDesk Server OSS and the RustDesk client are AGPL-3.0 projects. RustDesk Server Pro is a separately licensed product.

### Local live evidence and policy

- `atius-srv-2` was observed as `aarch64`, 4 CPU, 23 GiB RAM, and root filesystem `194G total / 163G used / 32G available / 84%`.
- `atius-srv-3` was observed as `aarch64` and root filesystem `194G total / 161G used / 34G available / 83%`; it also carries more security-sensitive workloads.
- The resource watchdog becomes critical at 85%. RustDesk placement therefore has a stricter local gate: `srv-2` must be at or below 78% before deployment and at or below 80% after deployment.
- `atius-srv-1`, `atius-srv-2`, and `atius-srv-3` currently use LightDM. Official RustDesk headless guidance names GDM, so LightDM behavior is an empirical acceptance gate rather than an assumed capability.
- Existing RustGuac, XRDP, AnyDesk, and NoMachine paths are recovery and regression surfaces; this project adds RustDesk without removing them.
- The flat planning surface was migrated transactionally on 2026-07-19 after a full external snapshot and an orphan-lock audit. Phase 48 now remains intact in `runtime-trust-codex-delivery-convergence`; every RustDesk command must explicitly target the isolated `rustdesk-fleet` workstream.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| RustDesk Server OSS | `1.1.15` pinned by image digest | Run `hbbs` and `hbbr` on the primary relay host | Provides the required self-hosted rendezvous and relay path without introducing Pro-only claims |
| RustDesk Client | `1.4.9` pinned artifacts | Remote-control client/service on all five targets | Official release supplies Linux AArch64 and Windows x86-64 packages |
| Podman Quadlet | Host-supported version | Manage `hbbs` and `hbbr` as rootless user-systemd containers | Matches the local Podman + user-systemd operating standard and the official Quadlet deployment shape |
| systemd user services | Host version | Restart, ordering, resource limits, and boot persistence | Makes container lifecycle inspectable and compatible with local operational controls |
| HashiCorp Vault | Existing Atius service | Authoritative secret storage | Required local source of truth for the server private key and five per-target permanent passwords |
| Cloudflare DNS | Existing Atius DNS authority | Publish `rustdesk.atius.com.br` | DNS-only A record preserves native TCP/UDP connectivity; no HTTP proxy is inserted into the native data path |

### Supporting Components

| Component | Version / Contract | Purpose | When to Use |
|-----------|--------------------|---------|-------------|
| `hbbs` | Server `1.1.15` | Registration, heartbeat, ID lookup, NAT test, and signaling | Always on the primary server |
| `hbbr` | Server `1.1.15` | Relay when direct hole punching is unavailable or a relay test is forced | Always available; not forced in normal production operation |
| Linux DE + Xorg | Existing LXDE/X11 | Supply a controllable graphical session | Required for Linux inbound visual control; prove LightDM behavior per host |
| Windows RustDesk service | Client `1.4.9` | Unattended service, locked-screen and UAC path | `GIOVANNI-W11-PC` |
| OCI ingress + host firewall | Existing infrastructure | Allow only the minimum RustDesk native ports | Primary `srv-2` placement |
| Existing remote-access stack | Existing versions | Break-glass and regression fallback | Preserve RustGuac, XRDP, AnyDesk, and NoMachine throughout rollout |

### Artifact Integrity

| Artifact | SHA-256 |
|----------|---------|
| `rustdesk-1.4.9-aarch64.deb` | `ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0` |
| `rustdesk-1.4.9-x86_64.msi` | `c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa` |
| `rustdesk-1.4.9-x86_64.exe` | `eaedeb0088e687bf46f7c46a9c6ea5493ce51f3134dfd6acbedb47b5b9136274` |
| `rustdesk-server-hbbs_1.1.15_arm64.deb` | `33c325cf20cd1df76cf5a7ffe4edb1eaae6c1bd61065c54ab6531946e12cbdcc` |
| `rustdesk-server-hbbr_1.1.15_arm64.deb` | `23aacbc6ec399f4d5211392243fd4da87e624e9c7b2dd16d20da67cf505951b9` |

The production container must additionally be pinned to the resolved ARM64 manifest digest and recorded at deployment time. Do not infer that a mutable tag still resolves to the researched image.

## Deployment Profile

### Primary server profile

| Setting | Decision | Status |
|---------|----------|--------|
| Host | `atius-srv-2` | Conditional on capacity gates |
| Runtime | Two rootless Podman Quadlets | Local architecture decision |
| Network | Host network | Supported by official examples; hardened locally |
| Public DNS | `rustdesk.atius.com.br`, DNS-only A record to `srv-2` | Local inference from native TCP/UDP requirements |
| Normal routing | Direct-first | Matches official hole-punch-then-relay behavior |
| Relay routing | `hbbr` on `srv-2`, forced only in controlled tests | Required fallback and test surface |
| Exposed ports | TCP `21115-21117`, UDP `21116` | Official minimum native surface |
| Closed ports | TCP `21114`, `21118`, `21119` | No Pro console/API or WebSocket client in baseline |
| CPU ceiling | Combined `hbbs` + `hbbr` at or below `0.8` CPU | Local 20%-of-host guardrail |
| State | Private persistent directory, bounded logs, restorable snapshot | Local durability requirement |

### Capacity formula and gates

Use byte-level values, not rounded `df -h` output:

```text
projected_post_used_bytes =
    current_used_bytes
  + image_bytes
  + state_reservation_bytes
  + log_reservation_bytes
  + rollback_reservation_bytes

projected_post_percent =
    100 * projected_post_used_bytes / filesystem_total_bytes
```

Hard gates:

1. `pre_deploy_percent <= 78`.
2. `projected_post_percent <= 80`.
3. `measured_post_deploy_percent <= 80`.
4. At least 20 GiB remains available after deployment.
5. Log retention and image rollback reservations are included in the calculation.

The observed 84% on `srv-2` is a NO-GO until space is reclaimed or container/state storage is moved to a separately governed filesystem. `srv-3` is not an automatic substitute.

## Managed Client Configuration

The baseline uses the installed client CLI, not a Pro console or API:

```text
rustdesk --option custom-rendezvous-server rustdesk.atius.com.br
rustdesk --option key <shared-server-public-key>
rustdesk --option relay-server rustdesk.atius.com.br
rustdesk --password <per-target-password-from-vault>
rustdesk --get-id
```

- The server has one keypair shared by `hbbs` and `hbbr`.
- The same server public key is distributed to all clients and is not secret.
- The server private key is secret and must be recoverable from Vault without appearing in logs or docs.
- Each controlled target has a distinct permanent password stored in Vault.
- Client configuration is verified by querying CLI options, checking service state, testing the correct password, and proving wrong-password rejection.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Server OSS `1.1.15` | RustDesk Server Pro `1.8.5` | Use Pro if SSO/OIDC, RBAC, API, web console, centralized device management, or human-attributed audit is mandatory |
| Rootless Podman Quadlets on `srv-2` | Docker Compose | Use Compose if local Podman/user-systemd standards are intentionally changed |
| Primary plus cold standby | Active-active | Do not use active-active for this OSS/SQLite baseline; reconsider only with a supported design and tested consistency model |
| Direct-first | Always relay | Force relay only when policy requires all traffic through the relay and bandwidth/capacity is accepted |
| Existing LightDM preserved | GDM replacement | No display-manager replacement in this project; a separate approved desktop architecture phase would be required |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Mutable `latest` tags | Upgrade and rollback cannot be reproduced | Version and manifest digest pinning |
| Cloudflare HTTP proxy for native RustDesk ports | Native TCP/UDP signaling and relay are not an HTTP-only site | DNS-only A record and direct ingress rules |
| TCP `21114`, `21118`, `21119` in OSS baseline | Adds unused Pro/WebSocket attack surface | Minimum TCP 21115-21117 + UDP 21116 |
| Shared permanent password | One disclosure compromises every target | Five unique Vault-managed passwords |
| Per-client copies of the server private key | Breaks the trust boundary and increases secret exposure | Shared public key on clients; private key only on server/backup path |
| Unscoped GSD mutation after workstream migration | Can write STATE/ROADMAP/REQUIREMENTS for the wrong delivery lane | Pass `--ws rustdesk-fleet`, serialize shared-file writers, and verify the active workstream before every mutation |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| RustDesk client `1.4.9` Linux AArch64 | Ubuntu 24.04 ARM64 fleet | Package exists; LightDM headless behavior still requires live proof |
| RustDesk client `1.4.9` Windows x86-64 | Windows 11 AMD64 | MSI/service path; verify UAC, lock screen, and pre-login after reboot |
| RustDesk Server OSS `1.1.15` ARM64 image | `atius-srv-2` AArch64 | Official release and container manifest include ARM64 |
| OSS server | Client ID/Relay/Key configuration | No API server is required for the native OSS baseline |
| Pro server | OIDC/RBAC/API/audit requirements | Commercial license and separate acceptance are required |

## Sources

- [RustDesk client 1.4.9 release](https://github.com/rustdesk/rustdesk/releases/tag/1.4.9) — versions, architectures, artifacts, and release hashes.
- [RustDesk Server OSS 1.1.15 release](https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.15) — server version, rootless-related release note, and server artifacts.
- [RustDesk self-host architecture](https://rustdesk.com/docs/en/self-host/) — `hbbs`, `hbbr`, direct/relay behavior, and port roles.
- [RustDesk Server OSS Docker and Podman](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/) — container, persistent volume, host network, and Quadlet examples.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — ID server, relay, server public key, and import/export choices.
- [RustDesk client documentation](https://rustdesk.com/docs/en/client/) — platforms, packages, service controls, and CLI operations.
- [RustDesk Server Pro](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/) — Pro-only management and identity capabilities.
- [RustDesk Server OSS license](https://github.com/rustdesk/rustdesk-server/blob/master/LICENSE) — AGPL-3.0.

---
*Stack research for: RustDesk fleet remote access*
*Researched: 2026-07-19*
