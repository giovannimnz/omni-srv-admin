# Omni Srv Admin (omni-srv-admin) Architecture

## Overview

Repository for provisioning and maintaining the Atius server (10.1.1.1 Oracle Cloud). Contains setup scripts, firewall configurations, domain infrastructure (FreeIPA + Keycloak + Samba), antivirus, and desktop theme customization.

## Server Role

- **Hostname**: omni-srv-admin-1.atius.com.br
- **IP Address**: 10.1.1.1 (WireGuard VPN: 10.1.1.0/24)
- **Platform**: Oracle Cloud Infrastructure (ARM64/aarch64)
- **OS**: Ubuntu 22.04

## Directory Structure

```
/home/ubuntu/GitHub/omni-srv-admin/
├── setup.sh                    # Main two-stage setup script
├── iptables/                   # Firewall rules backup
│   ├── iptables-backup-v4.conf
│   └── iptables-backup-v6.conf
├── domain-infrastructure/      # Linux domain services
│   ├── CLAUDE.md              # Domain infra documentation
│   ├── configs/               # Service configurations
│   ├── docker/                # FreeIPA container (AlmaLinux 9)
│   └── scripts/              # Setup/migration scripts
├── antivirus/                  # ClamAV scripts
│   ├── monitor.sh
│   └── scan.sh
├── dark-theme-ubuntu/         # LXDE dark theme
│   ├── install.sh
│   ├── repair.sh
│   ├── uninstall.sh
│   ├── config_files/
│   ├── fonts/
│   └── themes/
├── .planning/                  # Project planning
│   └── PROJECT.md
├── vscode-profile/
├── AGENTS.md
├── RECOVERY_LOG.md
└── readme.md
```

## Modules

### 1. Setup Module (setup.sh)

Two-stage automated provisioning script:

**Stage 1 - System Preparation**:
- Updates repositories and system packages
- Installs PostgreSQL 18, nano, LXDE, XRDP
- Configures 10GB swap file
- Sets up iptables firewall with persistent rules
- Requires reboot after completion

**Stage 2 - Applications**:
- Installs Chromium browser with bandwidth limiter (trickle: 31250 down / 18750 up KB/s)
- Installs CopyQ clipboard manager (replaces parcellite)
- Creates desktop shortcut for Chromium
- Applies dark theme via dark-theme-ubuntu/install.sh

### 2. Iptables Module (iptables/)

Firewall configuration with IPv4 and IPv6 backup files:
- `iptables-backup-v4.conf` - IPv4 rules
- `iptables-backup-v6.conf` - IPv6 rules

Applied during Stage 1 setup via:
```
sudo iptables-restore < iptables-backup-v4.conf
sudo ip6tables-restore < iptables-backup-v6.conf
sudo netfilter-persistent save
```

### 3. Domain Infrastructure Module (domain-infrastructure/)

Linux domain centralization providing Active Directory-like functionality:

**Components**:
- **FreeIPA** (Docker AlmaLinux 9 container): LDAP + Kerberos + CA for machine login and central authentication
- **Keycloak** (native OS, Java 21): Web SSO via OIDC, federated to FreeIPA LDAP
- **Samba**: File shares with FreeIPA/Kerberos authentication
- **WireGuard**: VPN (migrated from 10.1.1.2)

**Constraints**:
- FreeIPA runs in Docker because `freeipa-server` unavailable on Ubuntu (bug #1875114)
- Apache2 moved to ports 9080/9444 to free 80/443 for FreeIPA
- FQDN required: `omni-srv-admin-1.atius.com.br`
- Coexistence with existing Apache2 SSO (~/GitHub/atius) mandatory

### 4. Antivirus Module (antivirus/)

ClamAV-based virus protection:
- `monitor.sh` - Continuous monitoring script
- `scan.sh` - On-demand scanning script

### 5. Dark Theme Ubuntu Module (dark-theme-ubuntu/)

LXDE desktop dark theme customization:
- `install.sh` - Main installation script
- `repair.sh` - Theme repair utility
- `uninstall.sh` - Theme removal script
- `config_files/` - Theme configuration
- `fonts/` - Custom fonts
- `themes/` - GTK/icon themes
- `lxde-theme-backup-YYYYMMDD_HHMMSS/` - Automatic backup before changes

## Technology Stack

### Operating System
- Ubuntu 22.04 (Oracle Cloud Infrastructure, ARM64)

### Runtime Environments
- Node.js v24.13.1 (via NVM 0.39.7)
- Python 3.10.12 (system) / 3.11 (via uv)
- npm 11.8.0

### Application Stack
- **API**: Fastify v5.7.1 (port 8015)
- **Frontend**: Next.js v14.2.29 (port 3015)
- **Process Manager**: PM2 v6.0.14
- **Reverse Proxy**: Apache 2.4.52

### Databases
- PostgreSQL 17 (port 8745)
- MongoDB (port 27017)

### Container Infrastructure
- Docker + containerd
- ~25 Docker containers running (Portainer, Plane, Jenkins, Open WebUI, Paperclip, n8n, etc.)

### Identity & Security
- FreeIPA (Docker AlmaLinux 9) - LDAP + Kerberos
- Keycloak (native OS) - OIDC SSO
- WireGuard VPN (10.1.1.0/24)
- iptables firewall

### Development Tools
- Jest v30.0.5 - Backend testing
- Playwright v1.58.2 - E2E testing
- Jenkins - CI/CD

## Network Configuration

| Service | Port | Notes |
|---------|------|-------|
| Atius API | 8015 | Fastify |
| Atius Web | 3015 | Next.js |
| PostgreSQL | 8745 | System cluster |
| MongoDB | 27017 | For PM2 web replica |
| Apache2 | 9080/9444 | Moved from 80/443 |
| FreeIPA | 80/443 | Docker container |

## Related Servers

| IP | Role |
|----|------|
| 10.1.1.1 | This server (Atius apps, Docker, PM2, PostgreSQL, Apache2) |
| 10.1.1.2 | WireGuard VPN + CoreDNS + Samba (to be migrated) |
| 10.1.1.3 | Apache2 for Horistic |

## Domain

- Domain: atius.com.br (Cloudflare)
- DNS: Internal nameserver at 10.1.1.2 (Oracle VCN)
- SSL: Cloudflare origin certs at /etc/ssl/cloudflare/
