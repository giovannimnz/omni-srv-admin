# Feature Landscape

**Domain:** Linux domain infrastructure (FreeIPA + Keycloak + Samba)
**Researched:** 2026-04-19

## Table Stakes

Features users expect from a Linux domain infrastructure. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Centralized user authentication** (FreeIPA LDAP + Kerberos) | Core purpose of domain controller | Medium | `ipa-server-install` in Docker container. Provides LDAP (389-DS), Kerberos KDC, integrated CA. |
| **Linux machine login via domain credentials** | Users expect single credential for all machines | Low | `ipa-client-install --mkhomedir` on each client. SSSD handles PAM/NSS. |
| **User/group management via web UI** | Admins need to create/manage users without CLI | Low | FreeIPA web UI on `https://ipa.atius.com.br/ipa/ui`. Built-in. |
| **DNS resolution for internal hosts** | Machines need to find each other by name | Low | FreeIPA integrated DNS (BIND). Must configure zone for `atius.com.br`. |
| **File sharing via SMB/CIFS** | Users expect network drives accessible from Linux | Medium | Samba with Kerberos auth via FreeIPA keytab. Requires `ipa-adtrust-install`. |
| **Web SSO for applications** | Modern apps expect OIDC/OAuth2 login | Medium | Keycloak as OIDC provider, federated to FreeIPA LDAP. |
| **Home directory auto-creation** | Users expect their home dir on first login | Low | `oddjob-mkhomedir` + `ipa-client-install --mkhomedir`. |
| **Password policy enforcement** | Security requirement — expiry, complexity, lockout | Low | Built into FreeIPA. Configurable via web UI. |
| **Host enrollment** | Machines must register as domain members | Low | `ipa-client-install` + DNS A record + host principal in Kerberos. |
| **Sudo rule management** | Admins need centralized sudo policy | Low | FreeIPA sudo rules + `authselect enable-feature with-sudo` on clients. |
| **TLS certificates for services** | Services need valid certs for secure communication | Medium | FreeIPA integrated IPA CA. `ipa-getcert` for certificate requests. |
| **Time synchronization** | Kerberos requires synchronized clocks | Low | NTP/chrony. FreeIPA installer can configure or skip (`--no-ntp`). |

## Differentiators

Features that set this product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **WireGuard VPN integration** | Secure remote access to all domain services | Low | WireGuard on same host. No port conflicts with FreeIPA if using port 51820. |
| **Coexistence with existing Apache2 SSO** | Zero-downtime migration — legacy apps keep working | Medium | Apache2 on 8080/8443, Keycloak on 8180/8843. Both SSO systems run simultaneously. |
| **Cloudflare edge integration** | External apps get FreeIPA-backed auth via Cloudflare | Medium | Cloudflare terminates SSL, proxies to internal services. Requires origin rule updates after Apache2 migration. |
| **CoreDNS split-horizon DNS** | Internal queries → FreeIPA, external → public DNS | Low | CoreDNS forward zones. Delegates `*.atius.com.br` to FreeIPA DNS. |
| **Docker-native FreeIPA on ARM64** | Runs on Oracle Cloud ARM instances without x86 hardware | High | Requires building ARM64 container image from source. No official arm64 image. |
| **Keycloak + FreeIPA live federation** | User changes in FreeIPA immediately reflected in Keycloak | Medium | Keycloak "FEDERATED" sync mode with short cache eviction. |
| **Certificate management via FreeIPA CA** | Auto-issue TLS certs for internal services | Medium | `ipa-getcert request` for Apache2, Keycloak, and other services. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **FreeIPA ↔ Active Directory trust** | No Windows/Mac machines in environment (out of scope) | Don't install `ipa-server-trust-ad` unless Windows support is needed later. Skip AD trust configuration to reduce complexity. |
| **Replacing Apache2 SSO immediately** | 60+ vhosts would need simultaneous migration — too risky | Keep Apache2 JWT SSO running. Migrate apps to Keycloak one at a time over subsequent phases. |
| **Docker for Keycloak** | Project constraint forbids it; also complicates LDAP connectivity | Use native systemd service with Java 21. |
| **FreeIPA as external DNS for all queries** | FreeIPA DNS is for internal zone only; external resolution needs public resolvers | Use CoreDNS split-horizon: internal → FreeIPA, external → 8.8.8.8. |
| **Samba standalone user management** | Samba should NOT manage its own users — FreeIPA is the identity source | All user management through FreeIPA. Samba authenticates via Kerberos keytab. |
| **Running FreeIPA server natively on Ubuntu** | Package doesn't exist in Ubuntu 24.04 repos | Use Docker container (`freeipa/freeipa-server:almalinux-9`). |
| **WireGuard on port 53** | Conflicts with FreeIPA DNS | Use port 51820 for WireGuard. |
| **Horistic integration** | Explicitly out of scope — separate project with own domain | Horistic stays on 10.1.1.3. Handle in separate project. |

## Feature Dependencies

```
FreeIPA Server (Docker) → FreeIPA Client enrollment (all Linux machines)
FreeIPA Server → Samba Kerberos authentication
FreeIPA Server → Keycloak LDAP federation
FreeIPA DNS → CoreDNS forward zone
Apache2 port migration → FreeIPA installation (ports 80/443 must be free)
FreeIPA Server → ipa-adtrust-install → Samba AD trust support
FreeIPA Client enrollment → SSSD → Samba user/group resolution
WireGuard migration → All internal networking functional
Keycloak installation → LDAP federation configuration → Web SSO
```

## MVP Recommendation

Prioritize:
1. **FreeIPA Server container** — Without identity, nothing else works. Install first, configure DNS, create admin user.
2. **FreeIPA Client enrollment** (on 10.1.1.1 itself) — Validate the identity pipeline before rolling out to other machines.
3. **Samba + FreeIPA integration** — Core value proposition: file sharing with domain auth.
4. **Keycloak + LDAP federation** — Web SSO for applications, coexisting with Apache2.

Defer:
- **Client enrollment on other machines** — Get it working on the server first, then roll out to 4-10 machines.
- **Apache2 SSO migration to Keycloak** — Coexistence is sufficient for MVP. Migrate apps incrementally later.
- **CoreDNS reconfiguration** — Can use FreeIPA DNS directly as the nameserver for all clients. CoreDNS forwarding is a nice-to-have.
- **Certificate management via FreeIPA CA** — Cloudflare origin certs are sufficient for now. Add FreeIPA CA for internal services later.
- **Sudo rule management** — Useful but not critical for MVP. Add after basic auth is working.

## Sources

- [FreeIPA Documentation](https://www.freeipa.org/page/Documentation) — HIGH confidence
- [Keycloak LDAP Federation Guide](https://www.keycloak.org/docs/latest/server_admin/index.html#_ldap_mappers) — HIGH confidence
- [FreeIPA Samba Integration](https://www.freeipa.org/page/Howto/Integrating_a_Samba_File_Server_With_IPA) — HIGH confidence
- Project context from `.planning/PROJECT.md` — requirements and constraints
