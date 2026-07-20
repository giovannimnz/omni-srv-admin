# Feature Research

**Domain:** Managed self-hosted remote access for the Atius five-host fleet
**Researched:** 2026-07-19
**Confidence:** HIGH for scope and acceptance requirements; MEDIUM for LightDM unattended control until canary proof

## Evidence Boundaries

### Official product facts

- OSS provides self-hosted `hbbs` ID/rendezvous/signaling and `hbbr` relay.
- RustDesk attempts direct hole punching before using the relay.
- Clients accept a self-hosted ID server and server public key; the relay address can be set explicitly or inferred in the standard same-host layout.
- Web console, API, OIDC/LDAP, 2FA, centralized device management, policy, and audit capabilities belong to RustDesk Server Pro.

### Local requirements and inferences

- Completion means the client is installed, configured, controlled, controlling, reboot-persistent, relay-capable, rollback-capable, and evidenced on every included host.
- The included targets are `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, and `GIOVANNI-W11-PC`. WSL and `GIOVANNI-S23` are explicitly excluded.
- The required connection matrix is 20 normal directed pairs plus five forced-relay target tests.
- Existing RustGuac, XRDP, AnyDesk, and NoMachine are retained; RustDesk is not authorized to remove or replace them.

## Feature Landscape

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Self-hosted ID and relay | Keeps registration and relay under Atius control | MEDIUM | `hbbs` + `hbbr` on conditional `srv-2` primary |
| Direct-first sessions | Avoids unnecessary relay bandwidth and matches normal RustDesk routing | MEDIUM | Must be observed across all 20 ordered host pairs |
| Relay fallback | Direct connectivity is not guaranteed across every network path | MEDIUM | Force one relay session into each of five targets |
| Linux ARM64 client | Four managed Linux hosts are ARM64 | MEDIUM | Pin `1.4.9` AArch64 `.deb` and verify checksum |
| Windows AMD64 client/service | W11 must work locked, elevated, and after reboot | MEDIUM | Pin `1.4.9` MSI; verify service, UAC, and pre-login |
| Unattended access | Remote recovery must not depend on a local click | HIGH | Unique permanent password per target; LightDM is an empirical gate |
| Deterministic configuration | Manual GUI drift cannot be the deployment mechanism | MEDIUM | CLI-managed ID, relay, public key, password, and option verification |
| Artifact and config integrity | A mutable or unverified binary invalidates the fleet claim | LOW | Verify version, SHA-256, image manifest digest, and effective options |
| Vault-managed secrets | Remote-access credentials are high-impact secrets | MEDIUM | One server private key and five unique target passwords |
| Regression-safe coexistence | Existing access paths are required during canary and rollback | HIGH | Test RustGuac, XRDP, AnyDesk, and NoMachine after each relevant phase |
| Real rollback | Installation success without recovery proof is incomplete | HIGH | Roll back server image/state and at least one Linux and Windows client |
| Upgrade rehearsal | Version pinning must have a tested forward path | MEDIUM | Backup, upgrade, smoke, rollback, and re-upgrade in a controlled window |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Requirement-to-evidence ledger | Prevents broad PASS claims from narrow service checks | MEDIUM | One current artifact per host, direction, transport, negative, and recovery gate |
| Full ordered-pair verification | Proves controller and controlled roles across every fleet combination | HIGH | 20 normal sessions, excluding self-pairs |
| Per-target forced relay | Proves every controlled client reaches the fallback path | MEDIUM | Five additional positive sessions |
| Cold standby restore | Recovers server identity without active-active SQLite risk | HIGH | `srv-3` only after backup/restore/failover proof |
| Zero desktop-manager churn | Protects the known-good XRDP/LXDE environment | MEDIUM | Empirical LightDM gate; no GDM migration |
| Layered break-glass access | Avoids a single remote-access monoculture | MEDIUM | Preserve existing tools throughout rollout |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Pro claims on OSS | Central management sounds implicit in self-hosting | OSS has no Pro console/API/OIDC/RBAC/audit contract | Record OSS risk acceptance or select Pro before production |
| Always-relay production | Appears simpler to reason about | Consumes relay bandwidth and hides direct-path defects | Direct-first plus explicit forced-relay test lane |
| Active-active OSS server | Sounds like high availability | Shared identity/state consistency is not established for this baseline | Primary on `srv-2`, cold standby on `srv-3` after restore drill |
| Display-manager replacement | GDM is named in official headless guidance | Replacing LightDM risks XRDP and existing desktops | Prove LightDM empirically or retain attended-only RustDesk plus fallback |
| Remove legacy tools at launch | Reduces apparent duplication | Eliminates recovery paths before RustDesk is proven | Retain RustGuac/XRDP/AnyDesk/NoMachine |
| One fleet password | Simplifies deployment | One disclosure compromises all targets | Unique password per target from Vault |

## Feature Dependencies

```text
[20 normal directed sessions]
    └──requires──> [five installed and configured clients]
                       └──requires──> [healthy hbbs + public key]
                                          └──requires──> [srv-2 capacity and ingress gates]

[five forced-relay target sessions]
    └──requires──> [healthy hbbr]
                       └──requires──> [TCP 21117 reachability]

[unattended Linux acceptance]
    └──requires──> [LightDM/LXDE/X11 empirical reboot and pre-login proof]

[cold standby]
    └──requires──> [server backup + preserved private key + DNS failover procedure]

[production completion]
    └──requires──> [rollback + upgrade + regression + soak evidence]

[SSO/RBAC/human audit mandatory] ──conflicts──> [OSS baseline]
```

### Dependency Notes

- **Connection testing requires capacity first:** pulling an image while `srv-2` is at 84% would cross the local disk safety boundary before functional validation begins.
- **Relay testing requires the shared path and each target:** one shared `hbbr` service exists, but five target-side relay tests prove each client can use it.
- **Unattended acceptance requires session-state proof:** `systemctl active` and a non-empty RustDesk ID do not prove that LightDM pre-login capture works.
- **Cold standby requires identity preservation:** clients trust the server public key, so failover must restore the matching private key.
- **OSS requires risk acceptance:** if SSO, RBAC, API, or human-attributed audit becomes mandatory, select Pro before production rollout.

## MVP Definition

### Launch With

- [ ] Server OSS `1.1.15` pinned on a capacity-compliant `srv-2`.
- [ ] DNS-only `rustdesk.atius.com.br` with minimum native ports only.
- [ ] Rootless hardened Quadlets for `hbbs` and `hbbr` with bounded CPU and logs.
- [ ] RustDesk client `1.4.9` on all five included hosts.
- [ ] One shared server public key and five unique Vault-managed passwords.
- [ ] 20/20 normal directed connections.
- [ ] 5/5 forced-relay target connections.
- [ ] 5/5 wrong-password rejection.
- [ ] Wrong-key rejection on disposable Linux and Windows test contexts.
- [ ] 30-minute session for every target and a two-hour representative soak.
- [ ] Linux reboot/logout/pre-login proof and Windows reboot/lock/UAC proof.
- [ ] Real server and client rollback plus upgrade rehearsal.
- [ ] RustGuac, XRDP, AnyDesk, and NoMachine regression checks.

### Add After Validation

- [ ] `srv-3` cold standby — only after backup, restore, and DNS/failover drill pass.
- [ ] Central operational dashboards — after stable metrics and log-retention contracts exist.
- [ ] Automated periodic relay smoke — after a safe disposable-session mechanism exists.
- [ ] Managed artifact mirror — if GitHub availability becomes an operational dependency concern.

### Future Consideration

- [ ] RustDesk Server Pro — trigger: mandatory SSO/OIDC, RBAC, API, device management, or human-attributed audit.
- [ ] Self-hosted web client — trigger: explicit browser-client requirement and separate WSS/TLS threat model.
- [ ] Additional relay geography — trigger: measured relay latency or bandwidth saturation.
- [ ] Replacement of legacy remote tools — only after an independent decommission milestone and recovery review.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Capacity-safe server placement | HIGH | MEDIUM | P1 |
| Direct and relay connectivity | HIGH | HIGH | P1 |
| Five-host managed client rollout | HIGH | HIGH | P1 |
| Vault secret model | HIGH | MEDIUM | P1 |
| Headless and pre-login proof | HIGH | HIGH | P1 |
| Full directed matrix and negatives | HIGH | HIGH | P1 |
| Rollback, upgrade, and soak | HIGH | HIGH | P1 |
| Cold standby | MEDIUM | HIGH | P2 |
| Pro management plane | MEDIUM | HIGH | P3 unless security policy promotes it |
| Atius custom ops API | HIGH | MEDIUM | P1 under OPS-01; separate from RustDesk native API |
| Web client | LOW | HIGH | P3 |

**Priority key:**

- P1: Must have for production acceptance.
- P2: Add after the primary path is proven.
- P3: Future or requirement-triggered scope.

## Solution Variant Analysis

| Capability | OSS Baseline | Pro Variant | Project Decision |
|------------|--------------|-------------|------------------|
| ID/signaling/relay | Included | Included | OSS is sufficient |
| Native desktop clients | Included | Included | OSS is sufficient |
| Web console/native API | Not part of OSS contract | Included | No baseline claim |
| Atius custom ops endpoints | External operational wrapper only | Independent of Pro | Implement under OPS-01 without client `API Server` or TCP 21114 |
| OIDC/LDAP/2FA | Not part of OSS contract | Included | Promote Pro if mandatory |
| RBAC/device policy/audit | Not part of OSS contract | Included | Explicit OSS risk acceptance required |
| Custom client generator | Pro feature | Included | Use managed CLI/config scripts in OSS |
| Multiple managed relays | Manual OSS architecture | Pro-managed capability | One primary relay in baseline |

## Acceptance Roadmap

| Phase | Deliverable | Gate |
|-------|-------------|------|
| 1. Contract | Scope, OSS/Pro decision, threat model, evidence ledger | OSS risk accepted or Pro selected |
| 2. Preflight | Capacity, DNS, ports, Vault paths, backup and rollback design | `srv-2 <=78%`, projected post `<=80%` |
| 3. Server | Hardened rootless `hbbs`/`hbbr` primary plus separate Atius ops endpoints | Ports, key persistence, CPU, logs, restart and API auth/redaction green |
| 4. Canaries | Horistic + W11 | Direct, relay, reboot, UAC/pre-login, fallbacks green |
| 5. Fleet rollout | Remaining Linux clients, serialized | Every target passes before next host |
| 6. Matrix | 20 direct + 5 relay + negatives | All evidence complete |
| 7. Resilience | Soaks, upgrade, rollback, cold restore | Recovery is executed, not described |
| 8. Closeout | Full UAT, docs, Obsidian, GBrain, Graphify | Requirement-by-requirement audit passes |

## Sources

- [RustDesk self-host architecture](https://rustdesk.com/docs/en/self-host/) — server roles, direct-first behavior, relay fallback, and native ports.
- [RustDesk Server OSS](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/) — OSS feature boundary.
- [RustDesk Server Pro](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/) — Pro identity, management, API, and audit features.
- [RustDesk Server Pro web console](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/console/) — console, token, device, policy, and log management.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — self-hosted client inputs and deployment choices.
- [RustDesk advanced settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/) — security, password, permission, relay, and Linux headless settings.
- [RustDesk client deployment](https://rustdesk.com/docs/en/self-host/client-deployment/) — scripted Linux/Windows deployment patterns.

---
*Feature research for: RustDesk fleet remote access*
*Researched: 2026-07-19*
