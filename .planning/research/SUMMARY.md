# Research Summary: Atius Domain Infrastructure

**Domain:** Linux domain controller (FreeIPA + Keycloak + Samba on Ubuntu Server 24.04)
**Researched:** 2026-04-19
**Overall confidence:** MEDIUM-HIGH (critical findings verified with official sources, some Ubuntu-specific details rely on community reports)

## Executive Summary

This research maps the standard 2026 stack for building a FreeIPA-based Linux domain infrastructure on Ubuntu Server 24.04 ARM64 (Oracle Cloud). The most critical finding is that **`freeipa-server` is NOT available as an apt package on Ubuntu 24.04** — Launchpad Bug #1875114 has been "Triaged" since 2020 with no maintainer assigned. The only viable approach is running FreeIPA in a Docker container (`freeipa/freeipa-server:almalinux-9`), which introduces an ARM64 challenge: no official arm64 container image exists, requiring a manual build from the `freeipa/freeipa-container` repository.

Keycloak 26.5.x (latest as of February 2026) runs natively on Ubuntu with OpenJDK 21, federating users from FreeIPA via LDAP. Samba integrates with FreeIPA through Kerberos keytab authentication and SSSD-based ID mapping. The existing Apache2 installation (60+ vhosts on ports 80/443) must be migrated to 8080/8443 before FreeIPA can be installed, as FreeIPA requires ports 80/443 for its embedded web server.

The architecture places all services on a single server (10.1.1.1): FreeIPA in Docker, Keycloak as a systemd service, Samba natively, WireGuard migrated from 10.1.1.2, and Apache2 coexisting on alternate ports. WireGuard and FreeIPA have no port conflicts if WireGuard uses its default port 51820 — the critical warning is that WireGuard must NOT run on port 53, which FreeIPA DNS requires.

## Key Findings

**Stack:** FreeIPA (Docker container, AlmaLinux 9 base) + Keycloak 26.5.x (native, Java 21) + Samba 4.19+ (native, Kerberos auth) + WireGuard (native, port 51820)
**Architecture:** Single-server deployment with Docker for FreeIPA only, all other services native. ARM64 container build required.
**Critical pitfall:** `freeipa-server` doesn't exist in Ubuntu 24.04 repos. Docker container is mandatory. ARM64 image must be built from source.
**Secondary pitfall:** Apache2 must move off 80/443 BEFORE FreeIPA install. Port conflicts will block installation.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Apache2 Port Migration** — Free up ports 80/443
   - Addresses: COEX-01 (Apache2 coexistence), port availability for FreeIPA
   - Avoids: FreeIPA install failure due to port conflicts
   - Risk: Medium — 60+ vhosts need careful batch migration and testing
   - Cloudflare origin rules must be updated

2. **Phase 2: FreeIPA Server Container** — Core identity service
   - Addresses: FIPA-01 (FreeIPA installed), FIPA-04 (DNS integration)
   - Avoids: None — this IS the foundation everything else builds on
   - Risk: HIGH — ARM64 image build from source is untested; potential container build failures
   - **Likely needs deeper research** — ARM64 build process, Docker volume setup, post-install verification

3. **Phase 3: FreeIPA Client Enrollment** — Validate identity pipeline
   - Addresses: FIPA-02 (Linux machines join domain), FIPA-03 (user management)
   - Avoids: Rolling out to all machines before validating enrollment works
   - Risk: Low — once server works, client enrollment is straightforward
   - Start with enrolling 10.1.1.1 itself (host into its own domain)

4. **Phase 4: Samba Integration** — File sharing with domain auth
   - Addresses: SAM-01 (Samba with FreeIPA auth), SAM-02 (file shares accessible)
   - Avoids: Samba auth failures by establishing Kerberos integration first
   - Risk: Medium — `ipa-adtrust-install` must run in container; keytab setup is error-prone
   - **Likely needs deeper research** — trust-ad packages in container, keytab workflow

5. **Phase 5: WireGuard Migration** — Move from 10.1.1.2 to 10.1.1.1
   - Addresses: MIG-01 (WireGuard migrated)
   - Avoids: Network disruption during identity setup
   - Risk: Low — WireGuard config migration is straightforward; no port conflicts with FreeIPA

6. **Phase 6: Keycloak Installation & LDAP Federation** — Web SSO
   - Addresses: KEY-01 (Keycloak installed), KEY-02 (SSO via OIDC)
   - Avoids: SSO complexity before identity foundation is stable
   - Risk: Medium — LDAP federation TLS/NPE issues with FreeIPA
   - **Likely needs deeper research** — Java truststore CA import, FreeIPA LDAP attribute mapping

7. **Phase 7: Coexistence & DNS** — CoreDNS forwarding, Cloudflare updates
   - Addresses: COEX-02 (both SSO systems coexist), DNS integration
   - Avoids: DNS resolution failures for internal services
   - Risk: Low — forwarding config is simple; Cloudflare updates are mechanical

**Phase ordering rationale:**
- Apache2 migration MUST come first (ports 80/443 must be free)
- FreeIPA server MUST come second (everything else depends on it)
- Client enrollment validates FreeIPA before building on it
- Samba needs FreeIPA to be functional (Kerberos keytab dependency)
- WireGuard migration is independent but should happen before Keycloak (network stability)
- Keycloak is last major component (depends on FreeIPA LDAP being stable)
- Coexistence/DNS wraps up integration

**Research flags for phases:**
- Phase 2 (FreeIPA Server): HIGH research need — ARM64 container build is uncharted territory. May need to experiment with `freeipa-container` Dockerfile for arm64.
- Phase 4 (Samba): MEDIUM research need — `ipa-adtrust-install` in container, AD trust package availability in AlmaLinux 9 container image.
- Phase 6 (Keycloak): MEDIUM research need — LDAP federation TLS configuration, FreeIPA CA import into Java truststore, attribute mapping quirks.
- Phase 1 (Apache2): LOW research need — standard port migration, but 60+ vhosts volume requires careful testing.
- Phase 7 (Coexistence): LOW research need — Cloudflare origin rule updates are mechanical but numerous.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official FreeIPA docs, Keycloak releases, Samba docs, Launchpad bug tracker all verified |
| Features | HIGH | Standard FreeIPA/Keycloak/Samba feature set, well-documented |
| Architecture | MEDIUM-HIGH | Architecture is standard, but ARM64 container specifics are less tested |
| Pitfalls | MEDIUM | Critical pitfalls (missing package, port conflicts) verified. Some TLS/NPE issues from community reports only |

## Gaps to Address

- **ARM64 FreeIPA container build**: The `freeipa/freeipa-container` repo's ARM64 build process needs hands-on testing. GitHub issue #596 suggests someone built it successfully, but no official image exists.
- **AD Trust packages in AlmaLinux 9 container**: Whether `freeipa-server-trust-ad` is included in the official container image needs verification. If not, the container must be customized.
- **Keycloak LDAP federation with FreeIPA specifically**: General LDAP federation is documented, but FreeIPA's 389-DS backend has quirks (StartTLS behavior, attribute naming) that need testing.
- **Cloudflare origin port mapping for 60+ vhosts**: The exact Cloudflare API or bulk method for updating origin ports needs investigation to avoid manual updates.
- **FreeIPA DNS + CoreDNS coexistence**: Whether to keep CoreDNS or replace it entirely with FreeIPA DNS needs a decision based on existing DNS routing requirements.
