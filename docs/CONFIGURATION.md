# Configuration Guide - atius-srv

## Overview

This document describes all configuration options for the atius-srv server provisioning system, including setup.sh variables, firewall rules, domain infrastructure settings, and environment variables.

---

## 1. setup.sh Variables

**Location:** `/home/ubuntu/GitHub/atius-srv/setup.sh`

### Stage Selection Variable

| Variable | Description |
|----------|-------------|
| `STAGE_SELECTION` | User input (1 or 2) to choose setup stage |

### Stage 1 Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBIAN_FRONTEND` | `noninteractive` | Disables apt interactive prompts |
| `APT_OPTS` | `-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold` | Silent installation options for dpkg |
| `SWAP_SIZE` | `10G` | Swap file size (fallocate) |

**Commented out (previously used):**
```bash
# USER_PASS="bkfigt54"  # System password (now requires manual setting)
```

### Stage 2 Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBIAN_FRONTEND` | `noninteractive` | Disables apt interactive prompts |
| `APT_OPTS` | `-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold` | Silent installation options |
| `INSTALL_SCRIPT` | `./dark-theme-ubuntu/install.sh` | Path to dark theme installer |

### Installed Packages

**Stage 1:**
- `nano` - Text editor
- `postgresql-18`, `postgresql-client-18` - Database
- `lxde`, `xrdp` - Desktop environment and remote desktop
- `iptables`, `iptables-persistent` - Firewall

**Stage 2:**
- `trickle`, `chromium-browser` - Browser with bandwidth limiting
- `copyq` - Clipboard manager (replaces `parcellite`)

### Bandwidth Limiting (Chromium)

```bash
trickle -d 31250 -u 18750 chromium-browser %U
```
- Download limit: 31250 KB/s (~31 MB/s)
- Upload limit: 18750 KB/s (~18 MB/s)

---

## 2. iptables Firewall Rules

**Location:** `/home/ubuntu/GitHub/atius-srv/iptables/`

### Files

| File | Description |
|------|-------------|
| `iptables-backup-v4.conf` | IPv4 firewall rules |
| `iptables-backup-v6.conf` | IPv6 firewall rules |

### IPv4 Accepted Ports (INPUT chain)

| Port | Protocol | Service |
|------|----------|---------|
| 3389 | TCP/UDP | Microsoft RDP (RDP) |
| 3399 | TCP/UDP | RDP alternative |
| 80 | TCP | HTTP |
| 443 | TCP | HTTPS |
| 5000 | TCP | Application port |
| 5050 | TCP | Application port |
| 8000 | TCP | Application port |
| 8080 | TCP | HTTP proxy/alt |
| 8745 | TCP | PostgreSQL |
| 27813 | TCP | Application port |
| 28497 | TCP | Application port |

### IPv4 Accepted UDP Ports

| Port | Protocol | Service |
|------|----------|---------|
| 4449 | UDP | Application |
| 51820 | UDP | WireGuard VPN |
| 56000 | UDP | Application |
| 56100 | UDP | Application |

### Special Rules

**Private Networks (FORWARD):**
```bash
-A FORWARD -s 10.182.0.0/24 -j ACCEPT
-A FORWARD -d 10.182.0.0/24 -j ACCEPT
```

**NAT/Masquerading:**
```bash
# Docker networks
-A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE
-A POSTROUTING -s 172.19.0.0/16 ! -o br-f42fdcf25341 -j MASQUERADE

# MYST redirect (10.182.0.0/24)
-A POSTROUTING -s 10.182.0.0/24 ! -d 10.182.0.0/24 -j SNAT --to-source 10.0.0.65
```

**DNS Redirect (MYST chain):**
```bash
-A MYST -d 10.182.0.1/32 -p tcp -m tcp --dport 53 -j REDIRECT --to-ports 11253
-A MYST -d 10.182.0.1/32 -p udp -m udp --dport 53 -j REDIRECT --to-ports 11253
```

### Docker Rules

| Chain | Purpose |
|-------|---------|
| `DOCKER` | Docker port forwarding |
| `DOCKER-ISOLATION-STAGE-1/2` | Container isolation |
| `DOCKER-USER` | User-defined Docker rules |

### Applying Rules Manually

```bash
sudo iptables-restore < iptables/iptables-backup-v4.conf
sudo ip6tables-restore < iptables/iptables-backup-v6.conf
sudo netfilter-persistent save
```

---

## 3. Domain Infrastructure Configuration

**Location:** `/home/ubuntu/GitHub/atius-srv/domain-infrastructure/`

### Directory Structure

```
domain-infrastructure/
├── CLAUDE.md       # Full architecture documentation
├── configs/        # Service configurations (FreeIPA, Keycloak, Samba)
├── docker/         # Dockerfiles and compose files
└── scripts/        # Provisioning scripts
```

### Components

#### FreeIPA (Docker-based)
- **Container Base:** AlmaLinux 9
- **Reason:** `freeipa-server` unavailable in Ubuntu 22.04 (bug #1875114)
- **Ports:** 80/443 (requires Apache2 moved to 8080/8443)
- **Services:** LDAP + Kerberos + CA

#### Keycloak (Native OS)
- **Federation:** LDAP from FreeIPA
- **Purpose:** Web SSO via OIDC
- **Domain:** `auth.atius.com.br`

#### Samba
- **Authentication:** FreeIPA/Kerberos
- **Purpose:** File shares for domain machines

#### WireGuard
- **Network:** 10.1.1.0/24
- **Migration:** From 10.1.1.2 to 10.1.1.1

### Configuration Files (configs/)

Currently empty (`.gitkeep`). Future configurations:
- FreeIPA realm settings
- Keycloak realm exports
- Samba shares definitions

### Docker Files (docker/)

Currently empty (`.gitkeep`). Will contain:
- `Dockerfile` for FreeIPA container
- `docker-compose.yml` for domain services

### Scripts (scripts/)

Currently empty (`.gitkeep`). Will contain:
- FreeIPA setup scripts
- Keycloak initialization
- Samba configuration

### Constraints

| Constraint | Details |
|------------|---------|
| **Hostname** | Must be FQDN: `atius-srv-1.atius.com.br` |
| **Apache2** | Moved to 9080/9444 to free 80/443 |
| **DNS** | CoreDNS coexistence with FreeIPA BIND |
| **SSO** | Existing Apache2 SSO at `~/GitHub/atius` must not be affected |

---

## 4. Environment Variables

### System-Level Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `DEBIAN_FRONTEND` | `noninteractive` | Disables apt prompts |
| `APT_OPTS` | (see above) | dpkg silent options |

### Application Environment (atius apps)

Refer to `GitHub/atius/config/.env` for the main application configuration (~58 variables).

**Critical Variables:**
| Variable | Example | Description |
|----------|---------|-------------|
| `JWT_SECRET` | (required) | JWT signing secret |
| `API_PORT` | `8015` | Fastify API port |
| `FRONTEND_PORT` | `3015` | Next.js frontend port |
| `DATABASE_URL` | (postgres) | PostgreSQL connection |
| `NODE_ENV` | `production` | Environment |

### PM2 Environment

**PM2 Home:** `~/.pm2`

Managed via `ecosystem.config.js` with helper functions:
- `withNodeEnv()` - Node.js environment variables
- `withUvEnv()` - Python/uv environment variables

### SSL Certificates

**Location:** `/etc/ssl/cloudflare/`
- Cloudflare origin certificates for `*.atius.com.br` and `*.horistic.com`

### Cloudflare Configuration

**Full documentation:** `docs/CLOUDFLARE.md`
- Global API Key, zones, DNS records, API endpoints, permissions
- Aliases para API (cf-zones, cf-dns-atius, cf-verify, cf-user-tokens)

---

## 5. Network Configuration

### Server Information

| Property | Value |
|----------|-------|
| **Hostname** | `atius-srv-1.atius.com.br` |
| **Primary IP** | `10.1.1.1` |
| **WireGuard VPN** | `10.1.1.0/24` |
| **Platform** | Oracle Cloud Infrastructure (ARM64) |

### Service Ports

| Service | Port | Notes |
|---------|------|-------|
| Atius API | 8015 | Fastify |
| Atius Web | 3015 | Next.js |
| PostgreSQL | 8745 | System cluster |
| MongoDB | 27017 | PM2 web replica set |
| Apache2 | 9080/9444 | Moved from 80/443 |
| FreeIPA | 80/443 | Docker container |

### Related Servers

| IP | Role |
|----|------|
| 10.1.1.1 | This server (Atius apps, Docker, PM2, PostgreSQL, Apache2) |
| 10.1.1.2 | WireGuard VPN + CoreDNS + Samba (to be migrated) |
| 10.1.1.3 | Apache2 for Horistic |

### DNS

- **Internal Nameserver:** `10.1.1.2` (Oracle VCN)
- **Domain:** `atius.com.br` via Cloudflare

---

## 6. Dark Theme Configuration

**Location:** `/home/ubuntu/GitHub/atius-srv/dark-theme-ubuntu/`

### Scripts

| Script | Purpose |
|--------|---------|
| `install.sh` | Apply dark theme |
| `repair.sh` | Repair broken theme |
| `uninstall.sh` | Restore original theme |

### Bandwidth Limiter (trickle)

```bash
trickle -d 31250 -u 18750 chromium-browser
```

### Components Installed

- Sublime Text ARM64
- Apple fonts (SF Pro, SF Mono)
- Microsoft Core Fonts
- LXDE/Openbox dark theme
- Oh My Zsh with syntax highlighting

---

## 7. Antivirus Configuration

**Location:** `/home/ubuntu/GitHub/atius-srv/antivirus/`

### Scripts

| Script | Purpose |
|--------|---------|
| `monitor.sh` | Continuous monitoring, CPU usage, suspicious processes |
| `scan.sh` | Full system scan (ClamAV, rkhunter, chkrootkit) |

### Log Output

- `antivirus/monitor.log` - Monitoring output

---

## 8. Quick Reference

### Applying Firewall Rules

```bash
cd /home/ubuntu/GitHub/atius-srv
sudo ./setup.sh
# Select stage 1 for firewall restoration
```

### Manual Firewall Restore

```bash
sudo iptables-restore < iptables/iptables-backup-v4.conf
sudo ip6tables-restore < iptables/iptables-backup-v6.conf
sudo netfilter-persistent save
```

### Environment File Location

```
GitHub/atius/config/.env  # Main application environment (~58 variables)
```

### Key Paths

| Path | Description |
|------|-------------|
| `/home/ubuntu/GitHub/atius-srv/` | Repository root |
| `/home/ubuntu/GitHub/atius/` | Application code |
| `~/.pm2/` | PM2 process manager home |
| `/etc/ssl/cloudflare/` | SSL certificates |
| `/etc/apache2/sites-enabled/` | Apache vhosts (~60+) |
