# Development Guide - omni-srv-admin

Repository for provisioning and maintaining the Atius server (10.1.1.1 Oracle Cloud).

## Repository Overview

```
/home/ubuntu/GitHub/omni-srv-admin/
├── setup.sh                    # Two-stage server setup script
├── iptables/                   # Firewall rules backup (IPv4/IPv6)
├── domain-infrastructure/       # Linux domain services (FreeIPA, Keycloak, Samba)
│   ├── CLAUDE.md              # Detailed domain infrastructure docs
│   ├── configs/               # Service configurations (gitkeep - pending)
│   ├── docker/                # FreeIPA container definitions (gitkeep - pending)
│   └── scripts/               # Setup/migration scripts (gitkeep - pending)
├── antivirus/                  # ClamAV monitoring and scanning scripts
├── dark-theme-ubuntu/          # LXDE dark theme customization
├── .planning/                  # Phase planning and requirements tracking
├── docs/                       # Documentation
└── vscode-profile/            # VSCode configuration
```

## How to Modify Configurations

### Core Setup Script (setup.sh)

The `setup.sh` is a two-stage automated provisioning script.

**Stage 1 - System Preparation** (requires reboot after):
- Updates system packages
- Installs PostgreSQL 18, nano, LXDE, XRDP
- Configures 10GB swap file
- Sets up iptables firewall with persistent rules

**Stage 2 - Applications** (run after reboot):
- Installs Chromium with bandwidth limiter (trickle: 31250 down / 18750 up KB/s)
- Installs CopyQ clipboard manager
- Creates desktop shortcut for Chromium
- Applies dark theme

**Modifying setup.sh:**
1. Review the stage structure - Stage 1 runs before reboot, Stage 2 after
2. The script uses `DEBIAN_FRONTEND=noninteractive` for silent apt operations
3. Firewall rules in `iptables/` are auto-applied during Stage 1
4. Test changes incrementally - modify one stage at a time

### Firewall Rules (iptables/)

**Files:**
- `iptables/iptables-backup-v4.conf` - IPv4 rules
- `iptables/iptables-backup-v6.conf` - IPv6 rules

**Applying rules manually:**
```bash
sudo iptables-restore < iptables/iptables-backup-v4.conf
sudo ip6tables-restore < iptables/iptables-backup-v6.conf
sudo netfilter-persistent save
```

**Modifying firewall rules:**
1. Edit the `.conf` files directly (iptables syntax)
2. Test with `sudo iptables-restore < file` before committing
3. Verify with `sudo iptables -L -n` and `sudo ip6tables -L -n`

### Domain Infrastructure (domain-infrastructure/)

This module is under active development (Phase 3 in ROADMAP.md).

**Current status:** Phases 1-2 completed, Phase 3 (FreeIPA) pending.

**Structure:**
- `configs/` - Will contain FreeIPA, Keycloak, Samba configs (empty, gitkeep)
- `docker/` - Will contain FreeIPA container definitions (empty, gitkeep)
- `scripts/` - Will contain provisioning scripts (empty, gitkeep)

**To add configurations:**
1. Create config files in the appropriate subdirectory
2. Document the purpose in `CLAUDE.md`
3. Add validation steps to the corresponding phase plan

**Key constraints:**
- FreeIPA runs in Docker AlmaLinux 9 (no native Ubuntu package)
- Apache2 moved to ports 9080/9444 to free 80/443 for FreeIPA
- FQDN required: `omni-srv-admin-1.atius.com.br`
- Existing Apache2 SSO must not be affected

### Antivirus Scripts (antivirus/)

**monitor.sh** - Continuous CPU monitoring and suspicious process detection
```bash
./monitor.sh  # Output saved to antivirus/monitor.log
```

**scan.sh** - Full system scan using ClamAV, rkhunter, chkrootkit
```bash
sudo ./scan.sh  # Requires sudo for full system access
```

### Dark Theme (dark-theme-ubuntu/)

**Scripts:**
- `install.sh` - Apply dark theme
- `repair.sh` - Repair theme if broken
- `uninstall.sh` - Restore original theme

**Components:**
- `themes/` - LXDE/Openbox theme files
- `fonts/` - Apple and Microsoft fonts
- `config_files/` - System configuration files

**Theme backup:** Automatic backup to `lxde-theme-backup-YYYYMMDD_HHMMSS/` before changes.

## Testing Changes - Manual Validation

This repository contains server provisioning scripts and configurations. Automated tests are limited - validation is primarily manual.

### Pre-Deployment Validation Checklist

**Before running setup.sh Stage 1:**
- [ ] Verify Ubuntu 22.04 ARM64 environment
- [ ] Confirm sudo access
- [ ] Check current port usage: `ss -tlnp | grep -E ':(80|443|8080)'`
- [ ] Note current hostname: `hostname` and `hostname -f`

**After setup.sh Stage 1 (post-reboot):**
- [ ] Verify swap: `free -h` shows ~10GB swap
- [ ] Check PostgreSQL: `pg_isready -p 5432` or configured port
- [ ] Verify firewall: `sudo iptables -L -n | head -20`
- [ ] Test XRDP: Connect via RDP client
- [ ] Confirm LXDE: `ps aux | grep lxsession`

**After setup.sh Stage 2:**
- [ ] Chromium launches: Check desktop shortcut or `which chromium-browser`
- [ ] CopyQ running: `ps aux | grep copyq`
- [ ] Dark theme applied: `ls -la ~/Desktop/chromium-browser.desktop`

**Domain Infrastructure validation (per phase):**

Phase 1-2 (Apache2 migration):
- [ ] Apache2 on alternative ports: `ss -tlnp | grep -E ':(9080|9444)'`
- [ ] Vhosts functional: `curl -I http://localhost:9080/<vhost>`
- [ ] Cloudflare Origin Rules configured for port 9444

Phase 3 (FreeIPA):
- [ ] Container running: `docker ps | grep freeipa`
- [ ] CLI accessible: `docker exec <container> ipa user-find --all`
- [ ] Web UI: Access `https://<fqdn>/ipa/ui`
- [ ] DNS functional: `dig @localhost SRV _ldap._tcp.atius.com.br`

Phase 4 (Samba):
- [ ] Kerberos ticket: `kinit` with FreeIPA user
- [ ] Share listing: `smbclient -L //localhost -k`
- [ ] Share access: Mount and read/write test

Phase 5 (WireGuard):
- [ ] Interface up: `wg show`
- [ ] Peer connectivity: `ping -c 3 <peer-ip>`

Phase 6 (Keycloak):
- [ ] Service running: `systemctl status keycloak`
- [ ] Admin console: Access `auth.atius.com.br`
- [ ] LDAP federation: User sync from FreeIPA

### Configuration Validation Commands

**Iptables:**
```bash
# List current rules
sudo iptables -L -n -v
sudo ip6tables -L -n -v

# Count rules
sudo iptables -L -n | wc -l

# Test specific port
sudo iptables -L INPUT -n | grep 80
```

**Docker containers:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs <container> --tail 50
```

**Services:**
```bash
systemctl list-units --type=service --state=running
ss -tlnp | grep LISTEN
```

## How to Contribute

### Repository Structure

This is a **server configuration repository** - changes affect production infrastructure. All modifications follow a structured process.

### Contribution Workflow

1. **Understand the current phase** - Check `.planning/ROADMAP.md` for active development phase
2. **Review constraints** - Key constraints in `.planning/PROJECT.md` (FreeIPA in Docker, Apache2 coexistence, FQDN requirement)
3. **Create a planning document** - For significant changes, add a plan in `.planning/phases/<phase>/`
4. **Test locally** - Validate changes manually before committing
5. **Commit with context** - Use descriptive commit messages referencing requirements/phase

### Phase Planning

Development is organized into phases (see `.planning/ROADMAP.md`):

- Each phase has its own directory under `.planning/phases/`
- Phase plans follow naming: `XX-YY-PLAN.md` (e.g., `03-02-PLAN.md`)
- Plans include context, steps, success criteria, and verification

**Creating a new phase plan:**
1. Create directory: `.planning/phases/XX-<phase-name>/`
2. Create `XX-CONTEXT.md` - Background and constraints
3. Create `XX-YY-PLAN.md` - Specific implementation plan
4. Create `XX-PLAN-CHECK.md` - Verification checklist
5. Update `.planning/ROADMAP.md` - Add new phase

### Git Conventions

**Branch naming:**
- `main` - Production-ready state
- `phase/X/<description>` - Phase-specific work

**Commit messages:**
```
Phase X: Brief description

- Change 1
- Change 2
- References: REQ-XXX, FIPA-XXX
```

**File changes:**
- Config files: Document purpose in CLAUDE.md or module readme
- Scripts: Add header comment with purpose and usage
- Firewall rules: Comment non-obvious rules

### Adding New Modules

To add a new module to the repository:

1. Create module directory at root level
2. Add `README.md` or header comment documenting purpose
3. Update main `README.md` to include module description
4. If applicable, add to setup.sh or create standalone script
5. Document in this DEVELOPMENT.md

### Key Files for Reference

| File | Purpose |
|------|---------|
| `setup.sh` | Main provisioning script |
| `.planning/ROADMAP.md` | Phase timeline and milestones |
| `.planning/PROJECT.md` | Requirements and constraints |
| `domain-infrastructure/CLAUDE.md` | Detailed domain architecture |
| `docs/ARCHITECTURE.md` | System architecture overview |
| `docs/GETTING-STARTED.md` | Initial setup guide |

### Important Constraints

- **FreeIPA in Docker**: Native package unavailable on Ubuntu 22.04 (bug #1875114)
- **Port allocation**: Apache2 uses 9080/9444, FreeIPA uses 80/443
- **Hostname**: Must be FQDN (`omni-srv-admin-1.atius.com.br`) for FreeIPA
- **Coexistence**: Apache2 SSO in ~/GitHub/atius must not be affected
- **ARM64**: Oracle Cloud Infrastructure uses ARM64/aarch64

### Getting Help

- Architecture details: `docs/ARCHITECTURE.md`
- Domain infrastructure: `domain-infrastructure/CLAUDE.md`
- Current phase status: `.planning/ROADMAP.md`
- Requirements tracking: `.planning/PROJECT.md`
