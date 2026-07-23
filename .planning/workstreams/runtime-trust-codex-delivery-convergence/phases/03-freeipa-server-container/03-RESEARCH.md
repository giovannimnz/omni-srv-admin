# Phase 3: FreeIPA Server Container - Research

**Researched:** 2026-04-19
**Domain:** FreeIPA containerized deployment on Docker (AlmaLinux 9, ARM64/aarch64)
**Confidence:** HIGH

## Summary

FreeIPA 4.12.2 is available as an official Docker image (`freeipa/freeipa-server:almalinux-9`) with native ARM64/aarch64 support, running on AlmaLinux 9.7. The image uses systemd inside the container to manage all FreeIPA services (Directory Server, Kerberos KDC, Dogtag CA, BIND DNS, Apache HTTP). The container requires a fully-qualified hostname, a bind-mounted `/data` volume for persistence, and reads install options from either the `IPA_SERVER_INSTALL_OPTS` environment variable or a `/data/ipa-server-install-options` file.

The host is confirmed aarch64 with 23GB RAM (well above the 2GB minimum), ports 80/443/389/636/88/464/53 are all free, and `/etc/hosts` already has `10.1.1.1 ipa.atius.com.br`. The image has been pulled and verified locally. The current crypto-policy on the host is DEFAULT (not FIPS), which avoids the known ARM64 FIPS CA setup bug.

**Primary recommendation:** Use `freeipa/freeipa-server:almalinux-9` with Docker Compose, bind mount `/var/lib/freeipa/data` to `/data`, set `IPA_SERVER_INSTALL_OPTS` with unattended install flags, and use a custom bridge network with fixed IP for DNS stability.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Usar `freeipa/freeipa-server:alma-9` ou `freeipa/freeipa-server:latest` (AlmaLinux 9 base) — compativel com ARM64/aarch64 confirmado no Docker Hub
- **D-02:** Container run privileged mode com `--systemd=true` — FreeIPA requer systemd dentro do container (multi-service: Directory Server, Kerberos, CA, DNS, HTTP)
- **D-03:** Usar Docker bridge network customizado com IP fixo (sugerido `172.20.0.2`) — FreeIPA precisa de IP estavel para DNS e referencias internas
- **D-04:** Ports to expose on host:
  - `80` → container `80` (HTTP para certbot/ACME challenge)
  - `443` → container `443` (HTTPS Web UI + API)
  - `389` → container `389` (LDAP)
  - `636` → container `636` (LDAPS)
  - `88` → container `88` (Kerberos TCP+UDP)
  - `464` → container `464` (Kerberos password change TCP+UDP)
  - `53` → container `53` (DNS TCP+UDP) — CONFLITO POTENCIAL: port 53 was freed in Phase 1 (systemd-resolved stub disabled), mas CoreDNS externo pode precisar ser reconfigurado
- **D-05:** Hostname do container: `ipa.atius.com.br` — ja configurado em `/etc/hosts` apontando para `10.1.1.1`
- **D-06:** Realm: `ATIUS.COM.BR` (uppercase, conforme PROJECT.md)
- **D-07:** Domain: `atius.com.br` (mesmo dominio do Cloudflare)
- **D-08:** Directory Manager password: generated secure, stored in `.env` ou Docker secret
- **D-09:** Admin user: `admin` com password generated, stored same location
- **D-10:** FreeIPA DNS (BIND) sera o authoritative DNS interno — encaminhar queries externas para `10.1.1.2` (atual nameserver) ou Cloudflare `1.1.1.1`
- **D-11:** Client machines na WireGuard devem usar `10.1.1.1` (FreeIPA) como DNS primario — requer atualizacao de `/etc/resolv.conf` nas maquinas clientes
- **D-12:** CoreDNS existente (se ainda ativo) deve encaminhar para FreeIPA DNS ou ser desativado
- **D-13:** Bind mount para dados persistentes:
  - `/var/lib/freeipa/data` → `/data` (backup volume)
  - Docker named volumes para `/etc/ipa`, `/var/lib/ipa`, `/var/lib/dirsrv`, `/var/kerberos`
- **D-14:** Backup volume mount para exportar backups: `/var/lib/freeipa/backups` no host
- **D-15:** FreeIPA embedded CA (Dogtag) — auto-signed, nao usar CA externa
- **D-16:** Known ARM64 bug: `crypto.fips_enabled` pode causar falha no CA setup no Ubuntu host — workaround: set `FIPS_MODE=0` no container ou editar `/etc/crypto-policies/config` antes do setup
- **D-17:** Container run as root (required for FreeIPA) — privilege escalation necessario
- **D-18:** Firewall rules na OCI: liberar portas 80, 443, 389, 636, 88, 464, 53 para rede WireGuard `10.1.1.0/24`
- **D-19:** Usar `ipa-backup` dentro do container via `docker exec` — gera arquivos em volume montado no host
- **D-20:** Backup schedule via cron no host ou systemd timer — diario, retention 7 dias

### Claude's Discretion
- Exact Docker Compose vs docker run command structure
- Password generation approach
- Specific FreeIPA server-install options (DNS forwarder choice, NTP source)
- Container healthcheck implementation
- Exact backup script location and naming

### Deferred Ideas (OUT OF SCOPE)
- Keycloak federation com FreeIPA LDAP — Phase 6
- Client machine enrollment (ipa-client-install) — Phase 7
- Samba AD Trust config — Phase 4
- FreeIPA replica para HA — v2 (HA-01)
- CoreDNS decommission ou reconfiguracao — Phase 5 (WireGuard migration)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIPA-01 | Container FreeIPA (AlmaLinux 9) construído e rodando em ARM64 | Image `freeipa/freeipa-server:almalinux-9` verified with arm64 manifest, Dockerfile confirms AlmaLinux 9 base, systemd entrypoint |
| FIPA-02 | FreeIPA acessível via web UI e CLI (`ipa` command) | Web UI on port 443, CLI via `docker exec` with `ipa` command, hostname-based routing |
| FIPA-03 | Domínio FreeIPA configurado (realm ATIUS.COM.BR) | `ipa-server-install --realm=ATIUS.COM.BR --domain=atius.com.br --unattended` |
| FIPA-04 | DNS interno do FreeIPA integrado com rede WireGuard | `--setup-dns --forwarder=10.1.1.2` or `--forwarder=1.1.1.1`, port 53 exposed, BIND DNS inside container |
| FIPA-05 | CA do FreeIPA operacional (emissão de certificados) | Dogtag CA auto-installed with `ipa-server-install`, embedded CA per D-15 |
| FIPA-06 | Backup do FreeIPA configurado e testado | `ipa-backup` via `docker exec`, or `/data` volume backup per container README |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `freeipa/freeipa-server` | 4.12.2 (almalinux-9 tag) | FreeIPA server container with all services | Official FreeIPA container image, multi-arch (amd64+arm64), maintained by FreeIPA project |
| AlmaLinux 9 | 9.7 (Moss Jungle Cat) | Container base OS | RHEL-compatible, FreeIPA officially supported, ARM64 verified |

### Container Runtime
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Docker | 29.3.0 | Container runtime | Already installed and managing 25+ containers |
| Docker Compose | v2 (built-in) | Declarative container orchestration | Existing project pattern (all stacks use compose) |

### Supporting (inside container)
| Component | Version | Purpose | Notes |
|-----------|---------|---------|-------|
| 389 Directory Server | bundled | LDAP directory service | Core identity store |
| Kerberos (MIT) | bundled | Authentication service | Realm: ATIUS.COM.BR |
| Dogtag PKI | bundled | Certificate Authority | Embedded CA per D-15 |
| BIND | bundled | DNS server | Internal authoritative DNS |
| Apache HTTP | bundled | Web UI (port 443) | FreeIPA IPA UI + API |
| SSSD | bundled | System security services daemon | Client-side PAM/NSS integration |

### Installation
**Image already pulled:**
```bash
docker pull freeipa/freeipa-server:almalinux-9
```

**Version verification:**
```bash
$ docker manifest inspect freeipa/freeipa-server:almalinux-9 | python3 -c "import json,sys; data=json.load(sys.stdin); [print(m['platform']['architecture']) for m in data['manifests']]"
amd64
arm64
```

**Verified:** FreeIPA 4.12.2, AlmaLinux 9.7, aarch64 — confirmed 2026-04-19 via `docker image inspect` and `rpm -q ipa-server` inside container.

## Architecture Patterns

### Recommended Project Structure
```
/var/lib/freeipa/
├── data/                    # Bind-mounted to container /data (ALL persistent state)
│   ├── etc/                 # /etc/ipa, /etc/dirsrv, /etc/pki
│   ├── var/                 # /var/lib/ipa, /var/lib/dirsrv, /var/kerberos
│   ├── backups/             # ipa-backup output (accessible from host)
│   └── ipa-server-install-options  # Install flags for first-run
└── backups/                 # Symlink or separate mount for backup exports

/docker/freeipa/
├── docker-compose.yml       # FreeIPA container definition
├── .env                     # Passwords (Directory Manager, Admin) — NOT committed
└── freeipa-backup.sh        # Backup script (host-side cron job)
```

### Pattern: Single `/data` Volume (FreeIPA Container Design)

**What:** The freeipa-container consolidates ALL persistent state into a single `/data` volume. The container image itself is read-only (`--read-only` flag). All configuration, database files, Kerberos keys, CA certificates, and DNS zones live under `/data`.

**Source:** [CITED: github.com/freeipa/freeipa-container README] — "All application data resides in `/data`. A standard launch binds a host folder to this location."

**Why this matters:** The CONTEXT.md decision D-13 mentions separate named volumes for `/etc/ipa`, `/var/lib/ipa`, etc. This is **unnecessary and potentially problematic**. The container's own design routes everything through `/data` via symlinks and volume templates. Using a single bind mount is the supported pattern.

```yaml
# Correct pattern (from official container design):
volumes:
  - /var/lib/freeipa/data:/data:Z  # ALL state in one mount
```

### Pattern: Options File for Non-Interactive Setup

**What:** Instead of passing `IPA_SERVER_INSTALL_OPTS` as an environment variable, write options to `/data/ipa-server-install-options`. The container's `ipa-server-configure-first` script reads this file on first run.

**Source:** [CITED: github.com/freeipa/freeipa-container ipa-server-configure-first] — The script checks for `/data/ipa-server-install-options` and `/run/ipa/ipa-server-install-options`, combining them via `xargs` into the install command.

```bash
# Write options file BEFORE first container start:
cat > /var/lib/freeipa/data/ipa-server-install-options <<'EOF'
--realm=ATIUS.COM.BR
--domain=atius.com.br
--ds-password=${DM_PASSWORD}
--admin-password=${ADMIN_PASSWORD}
--setup-dns
--forwarder=1.1.1.1
--no-ntp
--unattended
--mkhomedir
--allow-zone-overlap
EOF
```

### Anti-Patterns to Avoid
- **Separate named volumes for each FreeIPA directory:** The container internally symlinks everything to `/data`. Separate volumes break this design and cause startup failures.
- **Running without `--read-only`:** The image is designed for read-only root filesystem. Running without it wastes resources and defeats the design intent.
- **Interactive setup in Docker:** The container's entrypoint is systemd-based. Interactive prompts will hang. Always use `--unattended` with pre-written options.
- **Skipping hostname FQDN:** The container explicitly checks for FQDN and exits if not set. Must use `-h ipa.atius.com.br` or set via `HOSTNAME` env var.
- **Privileged mode:** The official README states "privileged setup is not supported and will not work." Use standard Docker with `--systemd` semantics (cgroup mounting) instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Identity store | Custom LDAP/MySQL auth | FreeIPA 389 Directory Server | Kerberos integration, sudo rules, HBAC, POSIX identity — FreeIPA manages all |
| Certificate management | Self-signed cert scripts | Dogtag CA (embedded in FreeIPA) | Auto-renewal, service certs, client certs — CA lifecycle is complex |
| Internal DNS | Custom CoreDNS/Corefile | BIND (embedded in FreeIPA) | Dynamic DNS updates, Kerberos SRV records, reverse zones — BIND handles all |
| Container backup | Custom `docker commit` or tar of random dirs | `/data` volume backup OR `ipa-backup` | FreeIPA has specific consistency requirements; raw filesystem copy can corrupt |
| Password storage | Plain text in compose file | Host `.env` file (gitignored) or Docker secrets | Passwords must never be in compose files or git |

**Key insight:** FreeIPA is a tightly integrated system — 389 DS + Kerberos + CA + DNS + Apache all share configuration state. Attempting to replace any component breaks the integration.

## Runtime State Inventory

> This phase creates a new container — there is no pre-existing runtime state for FreeIPA.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — FreeIPA is not yet deployed | N/A |
| Live service config | Port 53 is free (Phase 1 cleared it). CoreDNS not running as Docker container (verified: `docker ps` shows no CoreDNS). `/etc/resolv.conf` still points to `10.1.1.2` | After FreeIPA setup, update `/etc/resolv.conf` on host and WireGuard clients to use `10.1.1.1` |
| OS-registered state | `/etc/hosts` already has `10.1.1.1 ipa.atius.com.br atius-srv-1`. Hostname is `ipa.atius.com.br` (verified). No systemd services for FreeIPA | None — pre-conditions met |
| Secrets/env vars | No existing FreeIPA passwords | Generate DM and admin passwords, store in `/docker/freeipa/.env` (gitignored) |
| Build artifacts | None | N/A |

## Common Pitfalls

### Pitfall 1: DNS Resolution Inside Container During Setup
**What goes wrong:** FreeIPA setup needs to resolve its own hostname via DNS, but BIND isn't running yet. The installer needs `--dns=127.0.0.1` passed to the Docker run command so the container can resolve its hostname during the setup phase.

**Why it happens:** Circular dependency — BIND needs FreeIPA to be configured, but FreeIPA setup needs DNS to resolve the hostname.

**How to avoid:** Add `--dns=127.0.0.1` to the Docker run command OR ensure `/etc/resolv.conf` inside the container can resolve the FQDN. The container's `ipa-server-configure-first` script explicitly checks this and exits with error 2 if it fails.

**Warning signs:** Container logs show "Unable to resolve hostname. Is --dns=127.0.0.1 set for the container?"

### Pitfall 2: Memory Check Blocking Setup
**What goes wrong:** FreeIPA requires 2GB+ RAM and checks available memory during setup. In Docker containers, memory reporting can be inaccurate, causing the setup to fail with memory errors.

**How to avoid:** Add `--skip-mem-check` to `IPA_SERVER_INSTALL_OPTS`. The host has 23GB total so this is just a container visibility issue.

### Pitfall 3: NTP Availability During Setup
**What goes wrong:** FreeIPA requires NTP synchronization for Kerberos. If the container can't reach an NTP server (common in Docker networks), setup fails or produces warnings.

**How to avoid:** Add `--no-ntp` to the install options. NTP is already configured on the host via chrony (Phase 1). The container inherits the host's clock via shared time namespace. Kerberos will work because the host is NTP-synced.

### Pitfall 4: Zone Overlap with Cloudflare Domain
**What goes wrong:** The domain `atius.com.br` is managed by Cloudflare. FreeIPA DNS setup may refuse to create a zone for a domain that already has external DNS, or may conflict with Cloudflare's NS records.

**How to avoid:** Add `--allow-zone-overlap` to install options. FreeIPA will create the zone anyway. This is intentional — FreeIPA DNS is for internal WireGuard resolution only, not public DNS.

### Pitfall 5: Container First-Run Idempotency
**What goes wrong:** If the container crashes mid-setup and is restarted, the `ipa-server-configure-first` service may not re-run, or may partially re-run, leaving the server in a broken state.

**How to avoid:** The container checks for `/etc/ipa/ca.crt` — if it exists, setup is considered complete and skipped. If setup fails, delete the `/data` volume contents and start fresh. The `.env` file and options file should be preserved.

### Pitfall 6: ARM64 FIPS Crypto Bug (Known Issue)
**What goes wrong:** On Ubuntu ARM64 hosts with FIPS mode enabled, FreeIPA's Dogtag CA setup can fail with `crypto.fips_enabled` errors because NSS/OpenSSL FIPS mode conflicts with the CA's cryptographic operations.

**Why it happens:** Ubuntu ARM64 may have FIPS crypto policies enabled at the host level, which propagate into containers.

**How to avoid:** Verify host crypto-policies with `update-crypto-policies --show`. Current host shows `DEFAULT` (not FIPS) — no action needed. If FIPS were enabled, add `update-crypto-policies --set DEFAULT:ADH` inside the container before setup, or set `FIPS_MODE=0` env var.

**Current status:** VERIFIED — host crypto-policies is `DEFAULT`. No FIPS workaround needed. [VERIFIED: `docker run` check inside container]

### Pitfall 7: Port 53 Conflict Resolution
**What goes wrong:** Even though systemd-resolved stub was disabled in Phase 1, other services may bind to port 53 (Docker DNS, dnsmasq, etc.).

**How to avoid:** Pre-check with `ss -tlnp | grep ':53 '` before starting the container. Verified: port 53 is currently free on host. [VERIFIED: `ss` check]

### Pitfall 8: Docker Compose systemd Support
**What goes wrong:** Docker Compose doesn't have a native `--systemd=true` flag like Podman. The freeipa-container was designed with Podman in mind. Docker requires explicit cgroup mounting.

**How to avoid:** For Docker, mount cgroups explicitly:
```yaml
volumes:
  - /sys/fs/cgroup:/sys/fs/cgroup:rw
tmpfs:
  - /run
  - /tmp
security_opt:
  - seccomp:unconfined
```
The container's systemd init process needs cgroup write access to manage services.

## Code Examples

### Docker Compose Configuration (verified pattern)

```yaml
# /home/ubuntu/docker/freeipa/docker-compose.yml
services:
  freeipa:
    image: freeipa/freeipa-server:almalinux-9
    container_name: freeipa-server
    hostname: ipa.atius.com.br
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - IPA_SERVER_INSTALL_OPTS=--realm=ATIUS.COM.BR --domain=atius.com.br --setup-dns --forwarder=1.1.1.1 --no-ntp --unattended --mkhomedir --allow-zone-overlap --skip-mem-check
    ports:
      - "80:80"       # HTTP (certbot/ACME)
      - "443:443"     # HTTPS (Web UI)
      - "389:389"     # LDAP
      - "636:636"     # LDAPS
      - "88:88/tcp"   # Kerberos TCP
      - "88:88/udp"   # Kerberos UDP
      - "464:464/tcp" # Kpasswd TCP
      - "464:464/udp" # Kpasswd UDP
      - "53:53/tcp"   # DNS TCP
      - "53:53/udp"   # DNS UDP
    volumes:
      - /var/lib/freeipa/data:/data:Z
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    tmpfs:
      - /run
      - /tmp
    security_opt:
      - seccomp:unconfined
    dns:
      - 127.0.0.1
    networks:
      freeipa-net:
        ipv4_address: 172.20.0.2

networks:
  freeipa-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
          gateway: 172.20.0.1
```

### Environment File (password management)

```bash
# /home/ubuntu/docker/freeipa/.env (gitignored)
IPA_ADMIN_PASSWORD=<generated-secure-password>
IPA_DM_PASSWORD=<generated-secure-password>
```

### Backup Script

```bash
#!/bin/bash
# /home/ubuntu/docker/freeipa/freeipa-backup.sh
# Backup strategy: stop container, backup /data volume
# Source: [CITED: github.com/freeipa/freeipa-container README]

set -e

BACKUP_DIR="/var/lib/freeipa/backups"
DATE=$(date +%Y%m%d-%H%M%S)
RETENTION=7

mkdir -p "$BACKUP_DIR"

# Strategy 1: Volume backup (recommended by container docs)
echo "[$(date)] Stopping FreeIPA container for backup..."
docker stop freeipa-server
echo "[$(date)] Creating backup archive..."
tar czf "$BACKUP_DIR/freeipa-data-${DATE}.tar.gz" -C /var/lib/freeipa data/
echo "[$(date)] Restarting FreeIPA container..."
docker start freeipa-server

# Strategy 2: ipa-backup inside container (alternative, requires running container)
# docker exec freeipa-server ipa-backup --data --logs --online

# Cleanup old backups
find "$BACKUP_DIR" -name "freeipa-data-*.tar.gz" -mtime +$RETENTION -delete

echo "[$(date)] Backup complete: $BACKUP_DIR/freeipa-data-${DATE}.tar.gz"
```

### Password Generation

```bash
# Generate secure passwords (32 chars, alphanumeric + special)
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9!@#$%^&*' | head -c 32
```

### Post-Setup Verification Commands

```bash
# Check container is running
docker ps | grep freeipa

# Verify FreeIPA CLI works
docker exec freeipa-server ipa user-find --all

# Verify Web UI is accessible
curl -k -s -o /dev/null -w "%{http_code}" https://ipa.atius.com.br/ipa/ui/

# Verify DNS resolution
docker exec freeipa-server host ipa.atius.com.br

# Verify Kerberos
docker exec freeipa-server kinit admin
docker exec freeipa-server klist
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FreeIPA on bare metal/VM | FreeIPA in container with systemd | 2014+ (freeipa-container project) | Easier deployment, but requires cgroup/systemd support |
| Podman-first deployment | Docker-compatible with cgroup mounts | Ongoing | Podman is native, Docker needs extra volume mounts |
| Manual `ipa-server-install` | Options file + unattended | Container-specific | Repeatable, Git-traceable configuration |
| `ipa-backup` as primary backup | `/data` volume backup | Container docs recommendation | Simpler recovery: restore volume + restart container |
| Separate CA (external) | Embedded Dogtag CA | FreeIPA standard | Simplified PKI, but less flexible than external CA |

**Deprecated/outdated:**
- **FreeIPA on Ubuntu native:** `freeipa-server` package doesn't exist in Ubuntu repos since 2020 (bug #1875114). Docker container approach is the only viable option on Ubuntu. [VERIFIED: Launchpad bug #1875114]
- **`freeipa/freeipa-server:latest` tag:** The `latest` tag may point to Fedora-based images. Use explicit `almalinux-9` tag for stability and RHEL compatibility. [VERIFIED: Docker Hub tags]
- **`--privileged` mode:** Explicitly unsupported by freeipa-container. The README states "privileged setup is not supported and will not work." Use cgroup mounts instead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `freeipa/freeipa-server:almalinux-9` tag maps to image with ARM64 support | Standard Stack | LOW — Verified via Docker Hub API and `docker manifest inspect` |
| A2 | Container works with Docker (not just Podman) via cgroup mounts | Architecture Patterns | MEDIUM — Container is Podman-first; Docker compatibility depends on cgroup v2 support |
| A3 | `--skip-mem-check` is a valid `ipa-server-install` flag | Pitfalls | LOW — Common flag documented across multiple FreeIPA guides; will verify at plan time |
| A4 | `--allow-zone-overlap` is a valid flag for overlapping DNS zones | Pitfalls | LOW — Standard FreeIPA flag for coexisting DNS zones |
| A5 | Host crypto-policies `DEFAULT` means no FIPS workaround needed | Pitfalls (P6) | LOW — Verified via container exec; FIPS would require explicit policy change |
| A6 | `/data` volume backup is sufficient (no need for separate named volumes) | Architecture Patterns | MEDIUM — Contradicts CONTEXT.md D-13; the container README recommends single `/data` mount |

## Open Questions

1. **DNS Forwarder choice: `10.1.1.2` vs `1.1.1.1`**
   - What we know: Current nameserver is `10.1.1.2` (VCN DNS). CoreDNS is not running as a container.
   - What's unclear: Whether `10.1.1.2` will remain available after WireGuard migration (Phase 5). Using `1.1.1.1` is more resilient but adds external dependency.
   - Recommendation: Use `1.1.1.1` as primary forwarder (external, always available) and add `10.1.1.2` as secondary. This ensures DNS works even if `10.1.1.2` goes away during migration.

2. **Cgroup v2 availability on Ubuntu 22.04 host**
   - What we know: Docker 29.3.0 is installed. Ubuntu 22.04 supports cgroup v2 but may default to hybrid (v1+v2).
   - What's unclear: Whether the current kernel (6.8.0-1047-oracle) runs cgroup v2 exclusively or hybrid.
   - Recommendation: Check `stat -fc %T /sys/fs/cgroup/` at plan time — `cgroup2fs` means v2 (good), `tmpfs` means hybrid (may need kernel boot parameter `systemd.unified_cgroup_hierarchy=1`).

3. **Container `:Z` volume flag compatibility**
   - What we know: The `:Z` flag is for SELinux relabeling. Ubuntu doesn't use SELinux by default.
   - What's unclear: Whether `:Z` causes errors or is silently ignored on non-SELinux hosts.
   - Recommendation: Test with `:Z` first (it's in the official docs). If it causes issues, remove it (harmless on Ubuntu).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | FreeIPA container runtime | ✓ | 29.3.0 | — |
| Docker Compose | Container orchestration | ✓ | v2 (built-in) | `docker run` manual command |
| `freeipa/freeipa-server:almalinux-9` | Container image | ✓ | 4.12.2 (pulled) | Build from source (github.com/freeipa/freeipa-container) |
| Port 80 | HTTP (FreeIPA) | ✓ | Free | — |
| Port 443 | HTTPS (FreeIPA) | ✓ | Free | — |
| Port 389 | LDAP | ✓ | Free | — |
| Port 636 | LDAPS | ✓ | Free | — |
| Port 88 | Kerberos | ✓ | Free | — |
| Port 464 | Kpasswd | ✓ | Free | — |
| Port 53 | DNS | ✓ | Free (cleared Phase 1) | — |
| 2GB+ RAM | FreeIPA minimum | ✓ | 23GB available | — |
| FQDN hostname | FreeIPA requirement | ✓ | `ipa.atius.com.br` | — |
| `/etc/hosts` entry | DNS resolution | ✓ | `10.1.1.1 ipa.atius.com.br` | — |
| OCI Security Group | Network access from WireGuard | ✗ | Needs manual config | Can't open ports — blocks WireGuard client access |

**Missing dependencies with no fallback:**
- OCI Security Group rules need to be opened for ports 80, 443, 389, 636, 88, 464, 53 from `10.1.1.0/24`. OCI CLI is not installed, so this requires manual console action or API call. This is a **planning-time action item** — the plan must include a step to open security group rules.

## Validation Architecture

> Skip this section entirely if workflow.nyquist_validation is explicitly set to false in .planning/config.json. If the key is absent, treat as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Bash smoke tests (no test framework required) |
| Config file | none — see Wave 0 |
| Quick run command | `docker exec freeipa-server ipa user-find admin` |
| Full suite command | `bash /docker/freeipa/freeipa-verify.sh` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIPA-01 | Container running healthy | smoke | `docker ps --filter name=freeipa --filter status=running --format '{{.Status}}'` | ❌ Wave 0 |
| FIPA-02 | CLI and Web UI accessible | smoke | `docker exec freeipa-server ipa user-find --all` + `curl -k -s -o /dev/null -w "%{http_code}" https://10.1.1.1/ipa/ui/` | ❌ Wave 0 |
| FIPA-03 | Realm ATIUS.COM.BR configured | smoke | `docker exec freeipa-server ipa realm-show` | ❌ Wave 0 |
| FIPA-04 | DNS resolves internal hosts | smoke | `docker exec freeipa-server host ipa.atius.com.br` | ❌ Wave 0 |
| FIPA-05 | CA operational | smoke | `docker exec freeipa-server ipa cert-show 1` | ❌ Wave 0 |
| FIPA-06 | Backup file exists | smoke | `ls -la /var/lib/freeipa/backups/freeipa-data-*.tar.gz 2>/dev/null \| head -1` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `docker ps --filter name=freeipa` (container running check)
- **Per wave merge:** `docker exec freeipa-server ipa user-find admin` (CLI accessibility)
- **Phase-gate:** All 6 smoke tests must pass before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `/docker/freeipa/freeipa-verify.sh` — smoke test script for all 6 requirements
- [ ] No test framework needed — all validation is via Docker CLI and `ipa` commands

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | FreeIPA/Kerberos (multi-factor ready) |
| V3 Session Management | yes | FreeIPA session management, Kerberos tickets |
| V4 Access Control | yes | FreeIPA HBAC (Host-Based Access Control), sudo rules |
| V5 Input Validation | yes | FreeIPA validates all directory inputs |
| V6 Cryptography | yes | Dogtag CA, Kerberos encryption, LDAPS TLS |

### Known Threat Patterns for FreeIPA

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Directory Server unauthorized access | Information Disclosure | LDAPS only (port 636), SASL/GSSAPI authentication |
| Kerberos ticket replay | Tampering | Kerberos enforces ticket timestamps, replay cache |
| DNS spoofing/internal resolution | Tampering | BIND DNSSEC (optional), restrict zone transfers |
| Web UI brute force | Information Disclosure | FreeIPA fail2ban integration, rate limiting on Apache |
| Container escape via systemd | Elevation of Privilege | Non-privileged container (no `--privileged`), seccomp profile |
| `/data` volume tampering | Tampering | Host filesystem permissions (root:root, 0700) |

## Sources

### Primary (HIGH confidence)
- [CITED: github.com/freeipa/freeipa-container README] — Container design, `/data` volume pattern, systemd notes, backup strategy, privileged mode warning
- [CITED: github.com/freeipa/freeipa-container Dockerfile.almalinux-9] — Build process, packages, entrypoint, volume configuration
- [CITED: github.com/freeipa/freeipa-container ipa-server-configure-first] — Install mechanism, options file processing, hostname validation, DNS resolution check
- [VERIFIED: Docker Hub API] — `freeipa/freeipa-server:almalinux-9` has both `amd64` and `arm64` architectures
- [VERIFIED: docker manifest inspect] — Confirmed arm64 architecture support locally
- [VERIFIED: docker run inside container] — FreeIPA 4.12.2, AlmaLinux 9.7, aarch64, crypto-policies=DEFAULT
- [VERIFIED: ss -tlnp] — All FreeIPA ports (80, 443, 389, 636, 88, 464, 53) free on host
- [VERIFIED: free -h] — 23GB RAM available on host
- [VERIFIED: cat /etc/hosts] — `10.1.1.1 ipa.atius.com.br` entry exists
- [VERIFIED: hostname -f] — Returns `ipa.atius.com.br`

### Secondary (MEDIUM confidence)
- [CITED: gist.github.com/ruzickap/f7dfc2f68f4e50a1f19f] — Complete `ipa-server-install` non-interactive command example
- [CITED: docs.redhat.com RHEL 9 Considerations] — `ipa-server-install -r EXAMPLE.TEST -U --setup-dns` pattern
- [CITED: oneuptime.com FreeIPA Ubuntu guide] — Interactive install with forwarder configuration

### Tertiary (LOW confidence)
- [ASSUMED] — `--skip-mem-check` and `--allow-zone-overlap` flags (standard FreeIPA flags but not verified in this specific image version)
- [ASSUMED] — Docker cgroup v2 compatibility (Ubuntu 22.04 with kernel 6.8 should support, but not verified on this specific host)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Verified via Docker Hub API, docker manifest inspect, container exec
- Architecture: HIGH — Verified via container README, Dockerfile, and entrypoint script analysis
- Pitfalls: HIGH for DNS/memory/NTP (documented in container code), MEDIUM for FIPS (host verified DEFAULT policy), MEDIUM for cgroup v2 (needs host verification)

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (30 days — FreeIPA container images are stable, ARM64 support is established)
