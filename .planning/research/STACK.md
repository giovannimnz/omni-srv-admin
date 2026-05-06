# Technology Stack

**Project:** Atius Domain Infrastructure — FreeIPA + Keycloak + Samba on Ubuntu Server 24.04
**Researched:** 2026-04-19

## Recommended Stack

### Core Identity — FreeIPA (4.11+ via Docker container)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| freeipa/freeipa-server | 4.11.x (container: rocky-8/almalinux-9 base) | Centralized LDAP + Kerberos + CA + DNS | FreeIPA server packages are **NOT available** in Ubuntu 24.04 repositories (Launchpad Bug #1875114 — "Triaged" since 2020, still unresolved). Container is the only viable option on Ubuntu. |
| freeipa-client | 4.11.1 (apt) | Client enrollment on Linux machines | Available via `apt install freeipa-client` on Ubuntu 24.04. Package exists for clients, not server. |
| sssd | 3.x (apt) | System Security Services Daemon on clients | Provides PAM/NSS integration with FreeIPA LDAP/Kerberos. Installed automatically with freeipa-client. |
| oddjob-mkhomedir | (apt) | Auto-create home directories on first login | Required for `--mkhomedir` flag during client enrollment. |

**Why Docker for FreeIPA Server (not native):**
- `freeipa-server` package does NOT exist in Ubuntu 24.04 Noble repositories — confirmed via Launchpad Bug #1875114
- Manual compilation from source fails at `configure: exit 1` due to missing PKI dependencies (`python3-pki-base`, `pki-base`) not available in Noble
- The official `freeipa/freeipa-server` Docker image uses Rocky Linux 8 / AlmaLinux 9 base — runs on any Linux host with Docker
- ARM64/aarch64 Docker image support is limited (GitHub issue #596 closed but no official arm64 image published; manual build required)
- **This server is ARM64 (Oracle Cloud aarch64)** — must build the FreeIPA container image from source for arm64, or use x86_64 emulation (slow, not recommended)

**FreeIPA Server Container Requirements:**
```bash
docker run --name freeipa-server \
  --hostname ipa.atius.com.br \
  --volume /var/lib/ipa-data:/data:Z \
  --cap-add SYS_TIME \
  --cap-add NET_ADMIN \
  --sysctl net.ipv6.conf.all.disable_ipv6=0 \
  --publish 80:80 --publish 443:443 \
  --publish 389:389 --publish 636:636 \
  --publish 88:88/tcp --publish 88:88/udp \
  --publish 464:464/tcp --publish 464:464/udp \
  --publish 53:53/tcp --publish 53:53/udp \
  --publish 123:123/udp \
  freeipa/freeipa-server:almalinux-9 \
  ipa-server-install --realm=ATIUS.COM.BR --domain=atius.com.br --admin-password=XXX --ds-password=XXX --no-ntp -U
```

### SSO — Keycloak (26.5.x standalone)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Keycloak | 26.5.4+ (Quarkus-based) | Web SSO / OIDC provider | Latest stable, Java 21 runtime, production-ready. OpenJDK 17/21/25 supported — use Java 21 for FIPS compatibility. |
| OpenJDK | 21 LTS | Keycloak JVM runtime | Keycloak 26.x ships with Java 21 as default. Recommended for production. |
| `apt install fontconfig` | — | Font rendering | Required by JVM on headless Ubuntu servers to avoid startup warnings. |

**Installation method (NOT Docker per project constraints):**
```bash
# 1. Install Java 21
sudo apt install -y openjdk-21-jdk-headless

# 2. Download Keycloak (Quarkus distribution)
# Use the tar.gz distribution from keycloak.org/downloads
wget https://github.com/keycloak/keycloak/releases/download/26.5.4/keycloak-26.5.4.tar.gz
sudo tar -xzf keycloak-26.5.4.tar.gz -C /opt/
sudo ln -s /opt/keycloak-26.5.4 /opt/keycloak

# 3. Create systemd service (port 8443 to avoid conflict with FreeIPA on 443)
sudo tee /etc/systemd/system/keycloak.service << 'EOF'
[Unit]
Description=Keycloak Identity Server
After=network-online.target

[Service]
Type=notify
User=keycloak
Group=keycloak
ExecStart=/opt/keycloak/bin/kc.sh start \
  --http-port=8443 \
  --https-port=8843 \
  --hostname=auth.atius.com.br \
  --hostname-strict=true \
  --proxy=edge \
  --features=preview
Restart=on-failure
RestartSec=10
Environment=KC_BOOTSTRAP_ADMIN_USERNAME=admin
Environment=KC_BOOTSTRAP_ADMIN_PASSWORD=changeme
Environment=JAVA_OPTS="-Xms512m -Xmx2g -XX:+UseG1GC"

[Install]
WantedBy=multi-user.target
EOF

sudo useradd -r -s /bin/false keycloak
sudo chown -R keycloak:keycloak /opt/keycloak-26.5.4
sudo systemctl daemon-reload
sudo systemctl enable --now keycloak
```

**Keycloak ↔ FreeIPA Integration (LDAP Federation):**
- Keycloak User Storage Provider → LDAP type
- Connection URL: `ldap://ipa.atius.com.br:389` (or `ldaps://ipa.atius.com.br:636` for TLS)
- Users DN: `cn=users,cn=accounts,dc=atius,dc=com,dc=br`
- Bind DN: `uid=admin,cn=users,cn=accounts,dc=atius,dc=com,dc=br`
- User Object Classes: `inetOrgPerson, organizationalPerson`
- Username LDAP attribute: `uid`
- **Gotcha:** FreeIPA LDAP may reject simple bind without StartTLS. Use `ldaps://` (port 636) or configure StartTLS in Keycloak. Known NPE issues with TLS in some Keycloak versions — test thoroughly.
- Sync Mode: `IMPORT` (one-time import) or `FEDERATED` (live lookups)

### File Sharing — Samba (4.x)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Samba | 4.19+ (Ubuntu 24.04 repos) | SMB/CIFS file sharing | Native apt packages. Integrates with FreeIPA via Kerberos keytab. |
| sssd-libwbclient | (apt) | Winbind bridge to SSSD | Required for FreeIPA user/group resolution in Samba. |
| samba | (apt) | Core Samba packages | `apt install samba samba-common samba-client` |

**Since FreeIPA server runs in Docker on this same host, Samba runs natively on Ubuntu and connects to FreeIPA as a client:**
```bash
# Install Samba + FreeIPA client integration
sudo apt install -y samba sssd-libwbclient freeipa-client oddjob-mkhomedir

# Enroll in FreeIPA domain
sudo ipa-client-install --mkhomedir --no-ntp

# On the FreeIPA server (inside Docker container), run:
# ipa-adtrust-install --netbios-name=ATIUS -a admin_password

# Register CIFS service principal on FreeIPA server
ipa service-add cifs/10.1.1.1

# On the Samba host, fetch keytab
ipa-getkeytab -s ipa.atius.com.br -p cifs/10.1.1.1@ATIUS.COM.BR -k /etc/samba/samba.keytab

# Samba config (/etc/samba/smb.conf)
[global]
    workgroup = ATIUS
    realm = ATIUS.COM.BR
    security = ads
    kerberos method = secrets and keytab
    idmap config * : backend = tdb
    idmap config * : range = 3000-7999
    idmap config ATIUS : backend = sss
    idmap config ATIUS : range = 10000-999999
    winbind use default domain = yes
    winbind enum users = yes
    winbind enum groups = yes
    winbind refresh tickets = yes
    template shell = /bin/bash
    template homedir = /home/%U

[shared]
    path = /srv/samba/shared
    read only = no
    valid users = "@ATIUS\Domain Users"
```

### DNS — CoreDNS → FreeIPA forwarding
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| CoreDNS | 1.12+ (existing) | External DNS resolver | Already running on 10.1.1.2 (to be migrated to 10.1.1.1) |
| FreeIPA DNS | Built-in (BIND + KDC) | Internal zone authority | FreeIPA runs its own DNS for the realm. CoreDNS forwards internal queries to it. |

**CoreDNS Corefile configuration:**
```
atius.com.br:53 {
    forward . 172.17.0.2  # FreeIPA container IP (or host-gateway)
    cache 30
    reload
}

.:53 {
    forward . 8.8.8.8 1.1.1.1
    cache 300
    reload
}
```

**Gotcha:** FreeIPA DNS runs inside the Docker container. CoreDNS needs to forward to the container's IP address (not `localhost`). Use `--dns` flag when starting the container, or configure Docker bridge networking so CoreDNS can reach the FreeIPA container IP. Alternative: use FreeIPA's DNS exclusively and remove CoreDNS entirely (simpler, recommended).

### VPN — WireGuard
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| WireGuard | linux-modules-extra (kernel module) | VPN tunnel | Already running on 10.1.1.2 (to be migrated to 10.1.1.1). No conflicts with FreeIPA — WireGuard uses UDP 51820, FreeIPA uses different ports. |
| wireguard-tools | (apt) | wg command-line tools | `apt install wireguard-tools` |

**Port analysis — NO conflicts between WireGuard and FreeIPA:**
| Service | Ports | Protocol |
|---------|-------|----------|
| WireGuard | 51820 | UDP |
| FreeIPA HTTP | 80, 443 | TCP |
| FreeIPA LDAP/LDAPS | 389, 636 | TCP |
| FreeIPA Kerberos | 88, 464 | TCP + UDP |
| FreeIPA DNS | 53 | TCP + UDP |
| FreeIPA NTP | 123 | UDP |
| Keycloak HTTP | 8443 | TCP |
| Keycloak HTTPS | 8843 | TCP |

### Apache2 Migration (80/443 → 8080/8443)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Apache2 | 2.4.58+ (Ubuntu 24.04) | Existing reverse proxy | Must be moved to free ports 8080/8443 for FreeIPA to use 80/443. |

**Migration steps for 60+ vhosts:**
```bash
# 1. Change Apache Listen directives
sudo sed -i 's/^Listen 80$/Listen 8080/' /etc/apache2/ports.conf
sudo sed -i 's/^Listen 443$/Listen 8443/' /etc/apache2/ports.conf

# 2. Update all VirtualHost declarations
sudo find /etc/apache2/sites-enabled -name '*.conf' -exec sed -i \
  's/<VirtualHost \*:80>/<VirtualHost *:8080>/g; s/<VirtualHost \*:443>/<VirtualHost *:8443>/g' {} +

# 3. Update any ProxyPass/ProxyPassReverse directives that reference port 80/443
sudo grep -rl 'proxy.*:80[^0-9]' /etc/apache2/sites-enabled/ | xargs sed -i \
  's/:80\([^0-9]\)/:8080\1/g; s/:443\([^0-9]\)/:8443\1/g'

# 4. Update any hardcoded redirects or ServerName references
# (review manually — automated replacement is risky)

# 5. Verify configuration
sudo apache2ctl configtest

# 6. Restart Apache
sudo systemctl restart apache2

# 7. Verify all vhosts respond on new ports
# curl -I http://localhost:8080 -H "Host: api.atius.com.br"
```

**Critical warnings:**
- Cloudflare proxy currently terminates SSL at `443` → forwards to origin. After migration, Cloudflare must point to `8080` (non-SSL) or `8443` (SSL). Update Cloudflare origin rules accordingly.
- Any hardcoded URLs in app configs referencing port 80/443 must be updated.
- PM2 apps, Docker containers, or other services that proxy to Apache must be updated to point to `8080`/`8443`.
- Test each vhost after migration. The `sed` approach handles the bulk change but edge cases (custom ports, inline port references in rewrite rules) need manual review.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Identity Server | FreeIPA (Docker container) | FreeIPA (native apt) | `freeipa-server` package **does not exist** in Ubuntu 24.04 repos. Launchpad Bug #1875114 — unresolved since 2020. Compilation fails due to missing PKI deps. |
| Identity Server | FreeIPA | OpenLDAP + Kerberos manually | FreeIPA bundles LDAP + Kerberos + CA + DNS + Web UI + client tooling. Manual setup is error-prone and harder to maintain. |
| Identity Server | FreeIPA | Authentik / Authentik | Authentik is more modern, Docker-native, ARM64 supported. But project explicitly requires FreeIPA for Linux machine login (PAM/SSSD integration is native). Authentik lacks native Linux PAM integration. |
| SSO | Keycloak (standalone) | Keycloak (Docker) | Project constraint: no Docker for Keycloak. Also, standalone simplifies systemd integration with existing server management. |
| SSO | Keycloak | Authelia / OAuth2 Proxy | Keycloak provides full IdP with LDAP federation, user management, OIDC/OAuth2/SAML. Authelia is simpler but lacks LDAP federation depth and admin console. |
| DNS | CoreDNS + FreeIPA DNS forwarding | FreeIPA DNS only | Simpler to let FreeIPA be the sole DNS authority. But if CoreDNS is needed for other routing rules, forwarding works. Recommendation: use FreeIPA DNS as primary, drop CoreDNS if possible. |
| Samba Auth | Samba + FreeIPA Kerberos keytab | Samba standalone AD | FreeIPA is the identity source of truth. Samba should delegate auth, not manage its own users. |
| FreeIPA ARM64 | Build container from source | x86_64 emulation (QEMU) | ARM64 native container is ~10x faster. QEMU emulation for FreeIPA (heavy PKI/DB operations) would be unacceptably slow. |

## Installation Order

```
1. Apache2 port migration (80/443 → 8080/8443)  — Free up ports FIRST
2. Docker Engine (if not installed)                — FreeIPA container dependency
3. FreeIPA Server container                        — Core identity service (needs 80/443)
4. FreeIPA DNS configuration                       — Internal DNS zones
5. WireGuard migration (10.1.1.2 → 10.1.1.1)      — Network layer
6. CoreDNS reconfiguration                         — Forward to FreeIPA DNS
7. Samba installation + FreeIPA client enrollment  — File sharing
8. ipa-adtrust-install (inside FreeIPA container)  — AD trust for Samba
9. Keycloak installation (Java 21 + standalone)    — Web SSO
10. Keycloak LDAP federation → FreeIPA             — Connect SSO to identity
```

## Port Summary

| Service | Port(s) | Protocol | Notes |
|---------|---------|----------|-------|
| FreeIPA HTTP | 80 | TCP | Required by FreeIPA installer |
| FreeIPA HTTPS | 443 | TCP | Required by FreeIPA installer |
| FreeIPA LDAP | 389 | TCP | Directory service |
| FreeIPA LDAPS | 636 | TCP | Secure directory |
| FreeIPA Kerberos | 88 | TCP/UDP | Authentication |
| FreeIPA Kerberos | 464 | TCP/UDP | Password change |
| FreeIPA DNS | 53 | TCP/UDP | Internal zone |
| FreeIPA NTP | 123 | UDP | Time sync |
| Apache2 HTTP | 8080 | TCP | Migrated from 80 |
| Apache2 HTTPS | 8443 | TCP | Migrated from 443 |
| Keycloak HTTP | 8443 | TCP | **CONFLICT with Apache2 HTTPS** — use 8180 instead |
| Keycloak HTTPS | 8843 | TCP | Alternative HTTPS port |
| WireGuard | 51820 | UDP | VPN tunnel |
| WireGuard | 53 | UDP | **POSSIBLE CONFLICT** if WG runs on port 53 (not recommended) |
| PostgreSQL 17 | 8745 | TCP | Existing |
| MongoDB | 27017 | TCP | Existing |
| PM2 Web | 3000 | TCP | Existing |
| Portainer | 9443 | TCP | Existing |
| Jenkins | 8085 | TCP | Existing |
| Open WebUI | 3001 | TCP | Existing |
| n8n | 5678 | TCP | Existing |
| CloudBeaver | 8000 | TCP | Existing |

**CRITICAL PORT CONFLICT: Apache2 HTTPS → 8443 conflicts with Keycloak HTTP → 8443**
- Apache2 HTTPS should use **8443**
- Keycloak HTTP should use **8180** (not 8443)
- Keycloak HTTPS should use **8843**

**WireGuard on port 53 warning:** Some setups run WireGuard on UDP 53 to bypass firewalls. This **will conflict** with FreeIPA DNS on port 53. WireGuard MUST use port 51820 (or another non-53 port) when coexisting with FreeIPA DNS.

## Ubuntu-Specific Gotchas

### FreeIPA Server on Ubuntu — THE Critical Issue
- `freeipa-server` is **NOT packaged** for Ubuntu 24.04 Noble
- Launchpad Bug #1875114 filed in 2020, still "Triaged" — no maintainer assigned
- Ubuntu 22.04 had partial server packages; 24.04 has none
- `freeipa-client` IS available on 24.04 (v4.11.1)
- Docker container (`freeipa/freeipa-server:almalinux-9`) is the only viable server option
- ARM64 container image NOT officially published — must build from source (`freeipa-container` repo)

### FreeIPA Client on Ubuntu — Known Issues
- SSL certificate hostname mismatch during enrollment (reported on Ubuntu 24.04): `"certificate verify failed: Hostname mismatch"`
- Fix: ensure FreeIPA server hostname matches the certificate CN/SAN exactly
- DNS auto-discovery fails if FreeIPA DNS isn't configured first — use `--server` and `--domain` flags explicitly
- `ipa-client-install --no-ntp` required if chrony/ntp is already managed externally

### FreeIPA Installer Assumptions
- Assumes a "clean" system — will overwrite existing configs
- Requires FQDN in `/etc/hosts` BEFORE the localhost line
- Requires reverse DNS to resolve correctly
- Will NOT coexist with pre-existing LDAP/Kerberos instances

### Keycloak on Ubuntu — Gotchas
- `fontconfig` package needed for JVM on headless servers (avoid `java.lang.NullPointerException` in font rendering)
- Keycloak 26.x requires `--hostname` and `--hostname-strict` for production mode
- Without a reverse proxy, Keycloak's `proxy=edge` mode is needed if Cloudflare terminates SSL
- Java 21 recommended (Java 25 supported but Java 21 has FIPS mode support)

### Samba + FreeIPA — Gotchas
- `ipa-adtrust-install` must run on the FreeIPA SERVER (inside the Docker container), not on the Samba client
- AD Trust support requires `freeipa-server-trust-ad` package (available in RHEL/Fedora, not in Ubuntu)
- The container image should include trust-ad packages — verify before deployment
- Samba on FreeIPA CLIENT uses `ipa-client-samba` package (available on Ubuntu 24.04)
- Kerberos keytab must be fetched via `ipa-getkeytab` — cannot be manually created
- SELinux booleans don't apply on Ubuntu (no SELinux by default) — skip that step

## Sources

- [FreeIPA Install & Deploy Guide](https://www.freeipa.org/page/InstallAndDeploy) — HIGH confidence (official)
- [FreeIPA 4.13.0 Release Notes](https://www.freeipa.org/release-notes/4-13-0.html) — HIGH confidence (official, fixes Ubuntu client cert issue)
- [FreeIPA Docker Container](https://hub.docker.com/r/freeipa/freeipa-server/) — HIGH confidence (official)
- [FreeIPA Container ARM64 Issue #596](https://github.com/freeipa/freeipa-container/issues/596) — HIGH confidence (official GitHub)
- [Launchpad Bug #1875114 — freeipa-server missing from Ubuntu 2x.04](https://bugs.launchpad.net/ubuntu/+source/freeipa/+bug/1875114) — HIGH confidence (official Ubuntu bug tracker)
- [Keycloak 26.5.4 Release](https://www.keycloak.org/2026/02/keycloak-2654-released) — HIGH confidence (official)
- [Keycloak Supported Configurations](https://github.com/keycloak/keycloak/blob/main/docs/guides/server/supported-configurations.adoc) — HIGH confidence (official)
- [FreeIPA + Samba Integration Howto](https://www.freeipa.org/page/Howto/Integrating_a_Samba_File_Server_With_IPA) — HIGH confidence (official)
- [Keycloak + FreeIPA LDAP Federation Discussion](https://lists.fedorahosted.org/archives/list/freeipa-users@lists.fedorahosted.org/thread/GRLTGFJC3LFGR2P6EZRMMZX6XAG2REF4/) — MEDIUM confidence (community)
- [FreeIPA Client on Ubuntu 24.04](https://kifarunix.com/install-and-configure-freeipa-client-on-ubuntu-24-04/) — MEDIUM confidence (community tutorial)
- [CoreDNS Forward Zones](https://oneuptime.com/blog/post/2026-02-09-coredns-forward-zones-split-horizon-dns/view) — MEDIUM confidence (community)
- [Ubuntu 24.04 SSL enrollment bug report](https://lists.fedorahosted.org/archives/list/freeipa-users@lists.fedorahosted.org/thread/U5IE2MX7H67JHEJVC7TKZZ5MJ4DCKZ2J/) — MEDIUM confidence (community)
