# Phase 3: FreeIPA Server Container - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 03-freeipa-server-container
**Areas discussed:** Container Base Image, Container Networking, Domain Configuration, DNS Integration, Volume Persistence, CA Configuration, Security, Backup Strategy

---

## Container Base Image

| Option | Description | Selected |
|--------|-------------|----------|
| freeipa/freeipa-server:alma-9 | AlmaLinux 9 base, ARM64 support confirmed | ✓ |
| freeipa/freeipa-server:latest | Latest stable, typically AlmaLinux 9 | |
| Build from source | Custom Dockerfile, more control | |

**User's choice:** alma-9 (auto-selected recommended)
**Notes:** ARM64/aarch64 support confirmed on Docker Hub. AlmaLinux 9 is the current stable base for FreeIPA 4.10+.

## Container Networking

| Option | Description | Selected |
|--------|-------------|----------|
| Host network | Direct host networking, simplest | |
| Bridge network with fixed IP | Custom network, stable IP for DNS/Kerberos refs | ✓ |
| Macvlan | Direct L2 access, more complex | |

**User's choice:** Bridge network with fixed IP (auto-selected recommended)
**Notes:** FreeIPA requires stable IP for DNS and Kerberos references. Host network would conflict with existing services.

## Domain Configuration

| Option | Description | Selected | Selected |
|--------|-------------|----------|----------|
| Realm ATIUS.COM.BR, Domain atius.com.br | Match existing Cloudflare domain | ✓ | |
| Separate realm/domain | Different internal domain | | |

**User's choice:** Match existing domain (auto-selected recommended)
**Notes:** Simplifies DNS integration. Hostname ipa.atius.com.br already in /etc/hosts.

## DNS Integration

| Option | Description | Selected |
|--------|-------------|----------|
| FreeIPA DNS as primary | Authoritative internal DNS, forward external queries | ✓ |
| Keep CoreDNS as primary | CoreDNS forwards to FreeIPA | |
| Dual DNS | Clients choose based on network | |

**User's choice:** FreeIPA DNS as primary (auto-selected recommended)
**Notes:** FreeIPA BIND is the natural authoritative DNS for the domain. Clients on WireGuard should use 10.1.1.1 as primary DNS.

## Volume Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Docker named volumes | Managed by Docker, simpler | |
| Bind mounts to host | Direct host access, easier backup | ✓ |
| Hybrid | Critical dirs as bind mounts, others as volumes | |

**User's choice:** Bind mounts for data + Docker volumes for internal dirs (auto-selected recommended)
**Notes:** Backup volume MUST be bind mount for ipa-backup files accessible on host.

## CA Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| FreeIPA embedded CA (Dogtag) | Self-signed, managed by FreeIPA | ✓ |
| External CA | Use existing PKI or Let's Encrypt | |
| No CA | Skip certificate services | |

**User's choice:** Embedded CA (auto-selected recommended)
**Notes:** Self-signed for internal use. Known ARM64 FIPS bug may require workaround.

## Security

| Option | Description | Selected |
|--------|-------------|----------|
| Container as root (privileged) | Required for FreeIPA services | ✓ |
| Rootless container | More secure, may not work | |

**User's choice:** Privileged (auto-selected required)
**Notes:** FreeIPA requires root for Directory Server, Kerberos, CA, DNS. OCI security groups must open ports for WireGuard network.

## Backup Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| ipa-backup via docker exec | Native FreeIPA backup to mounted volume | ✓ |
| Docker volume backup | Stop container, backup volume | |
| External backup script | Custom script with database dumps | |

**User's choice:** ipa-backup via docker exec (auto-selected recommended)
**Notes:** Native FreeIPA backup includes LDAP, Kerberos, CA, DNS data. Volume mount makes files accessible on host.

---

## Claude's Discretion

- Exact Docker Compose vs docker run command structure
- Password generation approach
- Specific FreeIPA server-install options (DNS forwarder choice, NTP source)
- Container healthcheck implementation
- Exact backup script location and naming

## Deferred Ideas

- Keycloak federation com FreeIPA LDAP — Phase 6
- Client machine enrollment (ipa-client-install) — Phase 7
- Samba AD Trust config — Phase 4
- FreeIPA replica para HA — v2 (HA-01)
- CoreDNS decommission ou reconfiguracao — Phase 5 (WireGuard migration)
