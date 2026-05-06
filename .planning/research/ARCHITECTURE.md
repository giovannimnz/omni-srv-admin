# Architecture Patterns

**Domain:** Linux domain infrastructure (FreeIPA + Keycloak + Samba)
**Researched:** 2026-04-19

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVER 10.1.1.1 (Ubuntu 22.04)                   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    FreeIPA Server                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────┐ ┌───────────┐ │   │
│  │  │ 389-DS   │ │ MIT      │ │ BIND │ │Dogtag│ │ Apache    │ │   │
│  │  │ (LDAP)   │ │ Kerberos │ │ DNS  │ │ PKI  │ │ httpd     │ │   │
│  │  │ :389,:636│ │ :88,:464 │ │ :53  │ │      │ │ :80,:443  │ │   │
│  │  └────┬─────┘ └────┬─────┘ └──┬───┘ └──┬───┘ └─────┬─────┘ │   │
│  │       │             │          │        │           │       │   │
│  │  ┌────┴─────────────┴──────────┴────────┴───────────┴─────┐ │   │
│  │  │              ipa-otpd (OTP daemon)                      │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    SSSD (local cache)                        │   │
│  │  services: nss, pam, sudo, ssh, ifp (D-Bus info pipe)       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                        │                    │            │
│  ┌──────┴──────┐          ┌──────┴──────┐    ┌────────┴────────┐  │
│  │   Keycloak  │          │    Samba    │    │  Linux Clients  │  │
│  │  (OIDC/SSO) │          │  (File Srv) │    │  (ipa-client)   │  │
│  │  :8443,*    │          │  :445,:139  │    │  :SSSD          │  │
│  └─────────────┘          └─────────────┘    └─────────────────┘  │
│         │                        │                    │            │
│  ┌──────┴────────────────────────┴────────────────────┴─────────┐  │
│  │              Apache2 (existing, moved to :8080/:8443)         │  │
│  │              60+ vhosts → proxy to PM2 apps + Docker          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Existing Infrastructure                        │   │
│  │  PM2 apps (API:8015, Web:3015, etc.) + 25 Docker containers │   │
│  │  PostgreSQL 17 + MongoDB                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

External clients connect via WireGuard 10.1.1.0/24
```

### Topology: Single Server with Domain Member Samba

**Recommended: FreeIPA server + Samba domain member on the same machine (10.1.1.1).**

FreeIPA is designed as an integrated server — all components (LDAP, Kerberos, DNS, CA, httpd) run together. Samba should be configured as a **domain member** on the same enrolled system using `ipa-client-samba`. This is the officially supported pattern since FreeIPA 4.8.0+.

**Why not ipasam backend?** The `ipasam` passdb backend approach is deprecated and error-prone. The domain member approach with `idmap_sss` is the current best practice — Samba delegates SID-to-POSIX mapping to SSSD, keeping identity resolution synchronized with the directory.

**Why not split across machines?** With 4-10 Linux clients in a WireGuard network, a single-server deployment is appropriate. Multi-master replication is only needed for HA at larger scale. The existing infrastructure (PM2, Docker, databases) already runs on 10.1.1.1.

## Component Boundaries

| Component | Responsibility | Communicates With | Ports |
|-----------|---------------|-------------------|-------|
| **389-DS (Directory Server)** | LDAP identity store — users, groups, hosts, policies | FreeIPA httpd, SSSD, Keycloak LDAP | TCP 389 (LDAP), TCP 636 (LDAPS) |
| **MIT Kerberos KDC** | Ticket granting, authentication, SSO | SSSD, Samba, Keycloak (Kerberos auth), clients | TCP/UDP 88 (Kerberos), TCP/UDP 464 (kpasswd) |
| **BIND DNS** | Internal DNS resolution, dynamic updates | FreeIPA clients, all network services | TCP/UDP 53 |
| **Dogtag PKI (CA)** | Certificate issuance, renewal, CRL | FreeIPA httpd, Kerberos (TLS), clients | Managed internally via 389-DS |
| **Apache httpd (FreeIPA)** | Web UI (ipa), KDC proxy, cert renewal | 389-DS, Kerberos, clients (browser) | TCP 80, TCP 443 |
| **ipa-otpd** | OTP verification daemon | Kerberos KDC, SSSD (idp pre-auth) | Unix socket (internal) |
| **SSSD** | Local identity cache, auth bridge, D-Bus info pipe | FreeIPA (LDAP/Kerberos), Keycloak (D-Bus), Samba (idmap), PAM | D-Bus (internal) |
| **Keycloak** | OIDC/OAuth2 SSO for web apps | FreeIPA LDAP (via SSSD D-Bus or direct LDAP), web apps (OIDC) | TCP 8443 (HTTPS), TCP 8080 (HTTP admin) |
| **Samba** | SMB/CIFS file shares | FreeIPA (Kerberos keytab), SSSD (idmap_sss), Windows/Linux SMB clients | TCP 445 (SMB), TCP 139 (NetBIOS) |
| **Apache2 (existing)** | Reverse proxy for 60+ vhosts | PM2 apps, Docker containers | TCP 8080, TCP 8443 (moved from 80/443) |

## Data Flow

### 1. Linux Client Login Flow (Machine Authentication)

```
Client Machine
     │
     ▼
SSSD (on client)
     │
     ├──► DNS resolution → FreeIPA BIND (:53)
     │
     ├──► Kerberos pre-auth → MIT KDC (:88)
     │         │
     │         ▼
     │    TGT issued → cached locally
     │
     └──► LDAP lookup → 389-DS (:389)
               │
               ▼
          User record, groups, SSH keys returned
```

**Result:** User logs into Linux machine with FreeIPA credentials, home directory auto-created, Kerberos ticket cached.

### 2. SSSD → Keycloak SSO Flow (Web Authentication)

```
Browser
  │
  ▼
Keycloak (:8443)
  │
  ├──► SSSD D-Bus InfoPipe (read-only)
  │         │
  │         ├──► Get user attributes (mail, givenname, sn)
  │         └──► Get user groups
  │
  ├──► PAM authentication → pam_sss.so
  │         │
  │         └──► SSSD → FreeIPA (LDAP bind + Kerberos)
  │
  └──► OIDC token issued → Browser
            │
            ▼
       App validates token → Keycloak
```

**Key detail:** Keycloak communicates with FreeIPA through SSSD's D-Bus interface (`org.freedesktop.sssd.infopipe`), NOT direct LDAP. This is read-only — user creation/modification must happen through FreeIPA's admin interface or `ipa` CLI.

### 3. Samba File Access Flow (Kerberos SSO)

```
SMB Client (Linux/Windows)
  │
  ├──► Kerberos TGT request → FreeIPA KDC (:88)
  │         │
  │         ▼
  │    TGT for cifs/10.1.1.1@REALM
  │
  ▼
Samba (10.1.1.1 :445)
  │
  ├──► Kerberos validation → dedicated keytab (/etc/samba/samba.keytab)
  │         │
  │         └──► AES-256 + RC4-HMAC encryption
  │
  ├──► SID→UID/GID mapping → idmap_sss → SSSD
  │         │
  │         └──► POSIX identity from FreeIPA directory
  │
  └──► File access granted (POSIX permissions)
```

### 4. Existing App Auth Coexistence Flow

```
Client
  │
  ├──► auth.atius.com.br → Apache2 (:8080/:8443) → Existing JWT SSO → PM2 apps
  │
  └──► auth-new.atius.com.br → FreeIPA httpd (:80/:443) → Keycloak (:8443) → OIDC → future apps
```

Both SSO systems coexist: the existing Apache2 JWT SSO continues serving current apps on alt ports, while Keycloak serves new apps via OIDC through FreeIPA's httpd on standard ports.

## Port Mapping and Conflict Resolution

### Current State (Before Changes)

| Port | Current Service | Status |
|------|----------------|--------|
| TCP 80 | Apache2 (60+ vhosts) | **CONFLICT** — needed by FreeIPA |
| TCP 443 | Apache2 (60+ vhosts) | **CONFLICT** — needed by FreeIPA |
| TCP 8080 | Unknown (listening on 0.0.0.0) | Available for Apache2 move |
| TCP 389 | Not in use | Available for FreeIPA |
| TCP 636 | Not in use | Available for FreeIPA |
| TCP/UDP 88 | Not in use | Available for Kerberos |
| TCP/UDP 464 | Not in use | Available for kpasswd |
| TCP/UDP 53 | systemd-resolved (127.0.0.53) | **CONFLICT** — needs resolution |
| TCP 445 | Not in use | Available for Samba |
| TCP 139 | Not in use | Available for Samba (NetBIOS) |

### Target State (After Changes)

| Port | Service | Notes |
|------|---------|-------|
| TCP 80 | FreeIPA httpd | Primary — ipa web UI, KDC proxy |
| TCP 443 | FreeIPA httpd + SSL | Primary — ipa web UI, Keycloak proxy |
| TCP 389 | 389-DS (LDAP) | FreeIPA directory |
| TCP 636 | 389-DS (LDAPS) | FreeIPA directory (TLS) |
| TCP/UDP 88 | MIT Kerberos KDC | Authentication |
| TCP/UDP 464 | Kerberos kpasswd | Password changes |
| TCP/UDP 53 | BIND DNS | FreeIPA DNS — requires systemd-resolved stub disabled |
| TCP 445 | Samba | SMB file shares |
| TCP 139 | Samba | NetBIOS (may be disabled if SMB-only) |
| TCP 749 | Kerberos admin | Administrative channel |
| TCP 8080 | Apache2 (existing) | **Moved** — all 60+ vhosts on alt port |
| TCP 8443 | Apache2 (existing, alt HTTPS) + Keycloak | **Shared or separate** — see below |
| UDP 123 | NTP (chrony/ntpd) | Time sync — Kerberos requires <5min drift |

### Port Conflict Resolution Strategy

1. **Apache2 → Alt ports:** Change `/etc/apache2/ports.conf` from `Listen 80`/`Listen 443` to `Listen 8080`/`Listen 8443`. Update all 60+ vhost configs (change `<VirtualHost *:80>` → `<VirtualHost *:8080>`, same for 443). All existing URLs require DNS or reverse proxy adjustment.

2. **systemd-resolved stub:** BIND needs port 53. Disable `systemd-resolved` stub listener (`StubListener=no` in `/etc/systemd/resolved.conf`) or configure BIND to listen on the WireGuard interface IP only. FreeIPA installer may handle this automatically.

3. **Keycloak port:** Keycloak defaults to 8080 (HTTP) and 8443 (HTTPS). Since Apache2 moves to these ports, configure Keycloak on **different ports** (e.g., 9080/9443) and use FreeIPA's httpd as a reverse proxy to Keycloak, OR run Keycloak on 8443 and move Apache2 HTTPS to 9443. **Recommendation: Keycloak on 9443, Apache2 on 8443.**

## Patterns to Follow

### Pattern 1: Domain Member Samba (not ipasam)

**What:** Configure Samba as a domain member using `ipa-client-samba` + `idmap_sss` backend.

**When:** Always — this is the supported approach since FreeIPA 4.8.0.

**Why:** The `ipasam` passdb backend is deprecated, causes backtrace errors, and requires manual LDAP schema extensions. The domain member approach uses SSSD for identity mapping, which is already configured by FreeIPA enrollment.

**Implementation:**
```bash
# On the FreeIPA-enrolled server
sudo ipa-client-samba          # Creates CIFS service, keytab, generates smb.conf
sudo systemctl enable --now smb nmb
```

**Generated smb.conf structure:**
```ini
[global]
    server role = member server
    realm = ATIUS.COM.BR
    dedicated keytab file = FILE:/etc/samba/samba.keytab
    kerberos method = dedicated keytab
    idmap config * : backend = tdb
    idmap config * : range = 0-0
    idmap config ATIUS : backend = sss
    idmap config ATIUS : range = 1000000-9999999
    template shell = /bin/bash
    template homedir = /home/%u
    load printers = no
    disable spoolss = yes
```

### Pattern 2: Keycloak SSSD Federation (not direct LDAP)

**What:** Use Keycloak's SSSD user federation provider via D-Bus InfoPipe, with PAM for authentication.

**When:** When running Keycloak on the same host as FreeIPA/SSSD. Requires Keycloak 22.0+ (SSSD provider was broken in 20.x, fixed in 22.0).

**Why:** SSSD federation is the officially recommended FreeIPA integration path. Direct LDAP federation has object class mapping issues (FreeIPA uses `inetOrgPerson + posixAccount + ipaObject`, not standard LDAP). SSSD handles all the mapping transparently.

**Implementation:**
```bash
# Prerequisites
sudo apt install sssd-dbus libjna-java   # D-Bus bridge + Java native access

# Run Keycloak setup script (must be run as root, before starting Keycloak)
sudo $KEYCLOAK_HOME/bin/federation-sssd-setup.sh

# This modifies /etc/sssd/sssd.conf to add ifp service:
#   services = nss, sudo, pam, ssh, ifp
#   [ifp]
#   allowed_uids = root, keycloak_user
#   user_attributes = +mail, +givenname, +sn

# Creates /etc/pam.d/keycloak:
#   auth    required   pam_sss.so
#   account required   pam_sss.so
```

**Key limitation:** SSSD federation is **read-only**. User creation, password changes, and group management MUST go through FreeIPA's admin interface (`ipa` CLI or web UI).

### Pattern 3: Apache2 Coexistence via Port Migration

**What:** Move existing Apache2 from ports 80/443 to 8080/8443, freeing standard ports for FreeIPA.

**When:** Before FreeIPA installation — FreeIPA's installer configures httpd on 80/443 and will fail if ports are occupied.

**Implementation:**
```bash
# 1. Stop Apache2
sudo systemctl stop apache2

# 2. Edit /etc/apache2/ports.conf
#    Change: Listen 80 → Listen 8080
#    Change: Listen 443 → Listen 8443

# 3. Update all vhost configs
#    sed -i 's/<VirtualHost \*:80>/<VirtualHost *:8080>/g' /etc/apache2/sites-enabled/*
#    sed -i 's/<VirtualHost \*:443>/<VirtualHost *:8443>/g' /etc/apache2/sites-enabled/*

# 4. Restart Apache2
sudo systemctl start apache2

# 5. Verify all apps still work on new ports
#    (Update DNS or add reverse proxy entries as needed)
```

**Important:** All 60+ vhosts need their `VirtualHost` directives updated. Any hardcoded `:80` or `:443` in app configs, redirect rules, or Let's Encrypt challenges must be reviewed. Let's Encrypt certbot can handle alt-port challenges with `--http-01-port 8080`.

### Pattern 4: SSSD InfoPipe for Attribute Exposure

**What:** Configure SSSD's InfoPipe D-Bus responder to expose user attributes to Keycloak.

**When:** Required for Keycloak to read FreeIPA user attributes (email, name, groups) via D-Bus.

```ini
# /etc/sssd/sssd.conf — add to existing domain section
[domain/atius.com.br]
ldap_user_extra_attrs = mail:mail, sn:sn, givenname:givenname, telephoneNumber:telephoneNumber

# Add ifp service
[sssd]
services = nss, sudo, pam, ssh, ifp

# Configure InfoPipe access
[ifp]
allowed_uids = root, keycloak
user_attributes = +mail, +telephoneNumber, +givenname, +sn
```

**Verification:**
```bash
# Test D-Bus attribute query
dbus-send --print-reply --system \
  --dest=org.freedesktop.sssd.infopipe \
  /org/freedesktop/sssd/infopipe \
  org.freedesktop.sssd.infopipe.GetUserAttr \
  string:username array:string:mail,givenname,sn

# Test group query
dbus-send --print-reply --system \
  --dest=org.freedesktop.sssd.infopipe \
  /org/freedesktop/sssd/infopipe \
  org.freedesktop.sssd.infopipe.GetUserGroups \
  string:username
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Running Samba as a Standalone Server with FreeIPA

**What:** Configuring Samba with `security = user` and local user databases while FreeIPA runs.

**Why bad:** Defeats the purpose of centralized identity. Users need separate passwords for Samba vs. FreeIPA login. Kerberos SSO doesn't work.

**Instead:** Use `ipa-client-samba` to enroll Samba as a domain member. Samba uses FreeIPA Kerberos for auth and SSSD for identity mapping.

### Anti-Pattern 2: Direct LDAP Connection from Keycloak to FreeIPA

**What:** Configuring Keycloak's LDAP provider to connect directly to FreeIPA's 389-DS on `ldap://localhost:389`.

**Why bad:** FreeIPA's LDAP schema is non-standard — users have multiple object classes (`inetOrgPerson`, `posixAccount`, `ipaObject`, `krbPrincipalAux`). Attribute mappings are complex (40+ fields). User creation from Keycloak fails silently. Group sync filters break connections.

**Instead:** Use SSSD federation (D-Bus InfoPipe + PAM). SSSD handles all schema translation. Read-only is acceptable — manage users through FreeIPA.

### Anti-Pattern 3: FreeIPA Behind a Reverse Proxy

**What:** Putting FreeIPA's httpd behind Apache2 or nginx reverse proxy.

**Why bad:** FreeIPA's httpd handles Kerberos authentication, KDC proxy, and certificate renewal. These require direct access to specific paths and headers. Reverse proxying breaks GSSAPI/SPNEGO negotiation.

**Instead:** Move existing Apache2 to alt ports. Give FreeIPA direct access to 80/443. If external access is needed, use FreeIPA's built-in proxy capabilities.

### Anti-Pattern 4: Skipping Time Synchronization

**What:** Running FreeIPA without NTP/chrony configured.

**Why bad:** Kerberos authentication fails if clock drift exceeds 5 minutes. All clients (SSSD, Samba, Keycloak) depend on Kerberos. Time skew causes intermittent, hard-to-debug auth failures.

**Instead:** Configure chrony or ntpd on the FreeIPA server and all clients. The FreeIPA server should be the NTP reference for the domain.

### Anti-Pattern 5: Installing FreeIPA in a Container on This System

**What:** Running FreeIPA in Docker alongside existing services.

**Why bad:** FreeIPA requires systemd integration, host-level D-Bus access (for SSSD InfoPipe), direct port binding on 80/443/389/88, and modifies `/etc/krb5.conf`, `/etc/sssd/sssd.conf`, and NSS configuration. Container isolation breaks SSSD-Kerberos-D-Bus communication chain that Keycloak depends on.

**Instead:** Install FreeIPA directly on the host OS (Ubuntu 22.04). This is already the project decision in PROJECT.md.

## Build Order (Critical Dependencies)

```
Phase 1: Prepare Host
  └── Move Apache2 to alt ports (8080/8443)
  └── Disable systemd-resolved stub DNS (:53)
  └── Configure chrony/NTP
      │
Phase 2: Install FreeIPA Server
  └── ipa-server-install (--setup-dns, --mkhomedir)
  └── Configure DNS zone (atius.com.br)
  └── Create admin users, groups, HBAC rules
      │
Phase 3: Enroll Samba as Domain Member
  └── ipa-client-samba (on same host — already enrolled)
  └── Configure smb.conf shares
  └── Test Kerberos auth: smbclient -k //10.1.1.1/share
      │
Phase 4: Install Keycloak + SSSD Federation
  └── Install Keycloak (OS, not Docker)
  └── Configure SSSD ifp (InfoPipe D-Bus)
  └── Run federation-sssd-setup.sh
  └── Configure Keycloak realm + SSSD provider
  └── Test OIDC login with FreeIPA user
      │
Phase 5: Enroll Client Machines
  └── ipa-client-install on each Linux client
  └── Test login: ssh user@client → FreeIPA auth
  └── Test Samba access: smbclient -k //10.1.1.1/share
      │
Phase 6: Migrate WireGuard + CoreDNS
  └── Move WireGuard from 10.1.1.2 → 10.1.1.1
  └── Integrate CoreDNS with FreeIPA DNS
      │
Phase 7: Coexistence Validation
  └── Verify existing Apache2 apps work on alt ports
  └── Verify existing JWT SSO unaffected
  └── Verify new Keycloak OIDC works alongside
```

**Why this order:** Each phase produces prerequisites for the next. FreeIPA must exist before Samba can enroll. SSSD must be configured before Keycloak can federate. Client enrollment requires a working FreeIPA server. Apache2 port migration must happen BEFORE FreeIPA installation (ports 80/443 must be free).

## Scalability Considerations

| Concern | Current (4-10 clients, single server) | At 50+ clients | At 200+ clients |
|---------|---------------------------------------|-----------------|-----------------|
| **FreeIPA** | Single server sufficient | Add replica (multi-master) | Multiple replicas + load-balanced httpd |
| **SSSD** | Local caching handles load | Tune cache timeouts | Consider entry_cache_timeout tuning |
| **Samba** | Single file server | Add shares, consider DRBD | GlusterFS/Ceph for distributed storage |
| **Keycloak** | Single node OK | Cluster mode (HA) | Cluster + external DB (PostgreSQL) |
| **DNS** | BIND on FreeIPA server | Forwarders for external resolution | Split-horizon DNS, external resolver |
| **Ports** | All services on one host | Consider separate app servers | Load balancer + service segregation |

## How This Fits Into Existing Infrastructure

### Current Infrastructure on 10.1.1.1

- **PM2 apps:** API (8015), Web (3015), Webhooks (8199), Strategy Builder (8091), Bot Launcher, DIVAP indicators
- **Docker containers:** ~25 (Portainer, Plane, n8n, Open WebUI, Paperclip, Jenkins, etc.)
- **Databases:** PostgreSQL 17, MongoDB, MySQL (for trading)
- **Apache2:** 60+ vhosts with Let's Encrypt SSL, JWT SSO middleware
- **WireGuard:** Currently on 10.1.1.2, migrating to 10.1.1.1

### Integration Points

1. **FreeIPA DNS** will manage internal DNS for the WireGuard subnet (10.1.1.0/24). Existing CoreDNS on 10.1.1.2 should forward IPA zones to FreeIPA or be replaced.

2. **Keycloak** will eventually replace the Apache2 JWT SSO for apps. During coexistence, both systems run in parallel. Apps can migrate one-by-one from JWT to OIDC.

3. **Samba shares** will be accessible to all WireGuard clients. Existing Samba data on 10.1.1.2 needs migration to 10.1.1.1 with preserved permissions.

4. **Apache2 vhosts** continue serving all 60+ domains on alt ports. URLs change (e.g., `api.atius.com.br:8080`) unless a DNS-level or proxy-level redirect is added.

5. **Docker containers** can authenticate against FreeIPA if they need LDAP user lookups. Containers running on the host can use the host's SSSD via volume-mounted sockets.

## Sources

- FreeIPA documentation (freeipa.readthedocs.io) — HIGH confidence
- Keycloak documentation (keycloak.org/docs) — HIGH confidence
- Red Hat Keycloak Server Administration Guide — HIGH confidence
- FreeIPA release notes 4.8.0, 4.9.0 (freeipa.org) — HIGH confidence
- FreeIPA community mailing lists (lists.fedorahosted.org) — MEDIUM confidence
- Keycloak GitHub discussions/issues — MEDIUM confidence
- Samba team GitLab (gitlab.com/samba-team/samba) — HIGH confidence
- Community wikis and blogs (Leo's Notes, rockstable.it) — MEDIUM confidence
- Ubuntu manpages (manpages.ubuntu.com) — HIGH confidence
