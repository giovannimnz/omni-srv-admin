# Getting Started with omni-srv-admin

## Prerequisites

- A clean Ubuntu 22.04 installation (or compatible Debian-based Linux)
- Internet connection
- User with sudo privileges

---

## Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/giovannimnz/omni-srv-admin.git
cd omni-srv-admin

# 2. Make setup script executable
chmod +x setup.sh

# 3. Run the setup script
sudo ./setup.sh
```

The `setup.sh` is a two-stage automated setup script:

- **Stage 1**: System preparation (Swap, LXDE, XRDP, firewall). Requires reboot after completion.
- **Stage 2**: Applications and theme installation (Chromium, CopyQ, Dark Theme). Run after Stage 1 and reboot.

---

## Per-Module Instructions

### 1. antivirus/

Anti-malware and monitoring scripts for system security.

**scan.sh** - Full system virus/malware scan (ClamAV, rkhunter, chkrootkit)
```bash
cd antivirus
chmod +x scan.sh
sudo ./scan.sh
```
Logs are saved to `antivirus/` directory.

**monitor.sh** - CPU usage monitoring and suspicious process detection
```bash
cd antivirus
chmod +x monitor.sh
./monitor.sh
```
Output saved to `antivirus/monitor.log`.

---

### 2. dark-theme-ubuntu/

Complete dark theme package for Ubuntu LXDE (Sublime Text, Apple fonts, Zsh, LXDE/Openbox dark styling).

**install.sh** - Apply dark theme to the system
```bash
cd dark-theme-ubuntu
chmod +x install.sh
./install.sh
```

**uninstall.sh** - Restore original theme
```bash
cd dark-theme-ubuntu
chmod +x uninstall.sh
sudo ./uninstall.sh
```

**repair.sh** - Repair theme if something breaks
```bash
cd dark-theme-ubuntu
chmod +x repair.sh
sudo ./repair.sh
```

---

### 3. domain-infrastructure/

Centralized Linux domain architecture with FreeIPA (Docker-based), Keycloak SSO, and Samba file sharing.

Refer to `domain-infrastructure/CLAUDE.md` for full architecture details and implementation guide.

---

### 4. iptables/

Firewall backup and restore rules for IPv4 and IPv6.

**Files:**
- `iptables-backup-v4.conf` - IPv4 firewall rules
- `iptables-backup-v6.conf` - IPv6 firewall rules

Rules are automatically applied during Stage 1 of `setup.sh` if this directory exists.

To manually restore rules:
```bash
sudo iptables-restore < iptables/iptables-backup-v4.conf
sudo ip6tables-restore < iptables/iptables-backup-v6.conf
sudo netfilter-persistent save
```

---

### 5. vscode-profile/

VS Code configuration profiles and extensions for development.

**Extensions folder:** `vscode-profile/Extensions/` - Pre-configured VS Code extensions

**Workspace files:** `.code-workspace` files for multi-folder workspace setups

To use a profile:
1. Open VS Code
2. File > Open Workspace from File
3. Select desired `.code-workspace` file

---

## Notes

- Run `setup.sh` Stage 1 first, reboot, then run Stage 2
- Some operations require sudo password — ensure you have sudo access
- Stage 2 requires running after reboot and connecting via RDP or SSH
- The dark theme installer may prompt for sudo password automatically if needed
