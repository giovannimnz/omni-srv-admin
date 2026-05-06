# Manual Testing Guide — atius-srv

This repository is a server configuration repo with no automated test suite.
All validation is performed manually. This document describes the procedures
for verifying each major component after provisioning or changes.

---

## 1. `setup.sh` Dry-Run Validation

`setup.sh` is a two-stage provisioning script. Dry-run validation confirms the
script's logic is sound without executing privileged operations.

### 1.1 Syntax Check

```bash
bash -n /home/ubuntu/GitHub/atius-srv/setup.sh
```

Expected: no output (exit code 0). Any syntax error is printed to stderr.

### 1.2 Stage Logic Review

Inspect the case statement at the top of the script. Confirm:

- **Stage 1** (option `1`): updates apt, installs `nano`, `postgresql-18`,
  configures swap, installs `lxde` + `xrdp`, installs `iptables` +
  `iptables-persistent`, and calls `iptables-restore`.
- **Stage 2** (option `2`): installs `chromium-browser` + `trickle`,
  installs `copyq`, writes a desktop entry file, runs
  `dark-theme-ubuntu/install.sh`.
- **Invalid input** exits with code 1 and an error message.

### 1.3 Path and Dependency Checks (Stage 1)

Before running, verify the following files and directories exist relative to
the repo root:

| Path | Expected |
|------|----------|
| `iptables/iptables-backup-v4.conf` | readable file |
| `iptables/iptables-backup-v6.conf` | readable file |
| `iptables/` | must be a directory (script does `cd iptables`) |

```bash
# Verify from the repo root
cd /home/ubuntu/GitHub/atius-srv
[ -d iptables ]          && echo "iptables/ dir: OK"  || echo "iptables/ dir: MISSING"
[ -f iptables/iptables-backup-v4.conf ] && echo "v4 rules: OK"  || echo "v4 rules: MISSING"
[ -f iptables/iptables-backup-v6.conf ] && echo "v6 rules: OK"  || echo "v6 rules: MISSING"
```

### 1.4 Stage 2 Dependency Check

```bash
cd /home/ubuntu/GitHub/atius-srv
[ -f dark-theme-ubuntu/install.sh ] && echo "theme install.sh: OK" || echo "theme install.sh: MISSING"
```

### 1.5 Dry-Run Simulation (read-only)

To simulate Stage 1 without running any privileged commands, use:

```bash
# Preview the apt commands that would run (print-only simulation)
grep -E "^[[:space:]]+sudo apt-get" /home/ubuntu/GitHub/atius-srv/setup.sh
```

Review the output — confirm no unexpected packages and that all `apt-get`
calls use the `$APT_OPTS` silent flags.

---

## 2. iptables Rules Validation

Rules are stored in `iptables/iptables-backup-v4.conf` (IPv4) and
`iptables/iptables-backup-v6.conf` (IPv6). These are applied by `setup.sh`
and persisted with `netfilter-persistent`.

### 2.1 File Existence and Format

```bash
# Confirm files are non-empty and valid iptables-save format
wc -l /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf
wc -l /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v6.conf
grep -c "^COMMIT$" /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf
grep -c "^\\*filter$" /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf
```

Expected: both files have lines, v4 contains `*filter` and `COMMIT` markers.

### 2.2 Required INPUT Rules (IPv4)

The following ports must appear as `ACCEPT` in the `*filter` table's INPUT
chain. Validate with:

```bash
PATTERNS=(
  "-p tcp --dport 3389"
  "-p tcp --dport 3399"
  "-p tcp --dport 80"
  "-p tcp --dport 443"
  "-p tcp --dport 5000"
  "-p tcp --dport 5050"
  "-p tcp --dport 8000"
  "-p tcp --dport 8745"
  "-p tcp --dport 8080"
  "-p tcp --dport 27813"
  "-p tcp --dport 28497"
  "-p udp --dport 4449"
  "-p udp --dport 56000"
  "-p udp --dport 51820"
)

for p in "${PATTERNS[@]}"; do
  if grep -q "$p" /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf; then
    echo "FOUND: $p"
  else
    echo "MISSING: $p"
  fi
done
```

All should report `FOUND`. Missing entries indicate a port that would not be
opened after `setup.sh` runs.

### 2.3 Live Comparison (on a running system)

If running on the actual server, compare the saved rules against the live
running rules:

```bash
# Show live iptables rules (filter table, INPUT chain)
sudo iptables -L INPUT -n --line-numbers

# Show saved rules for the same
grep -A 100 "^\*filter" /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf \
  | grep -A 100 ":INPUT"

# Diff live vs saved (simplified)
sudo iptables-save > /tmp/live-iptables.conf
diff /tmp/live-iptables.conf /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v4.conf
```

Differences in counters (`[123:45678]`) are expected and harmless. Focus on
rule order and policy changes.

### 2.4 IPv6 Sanity

```bash
# Confirm v6 file has DROP or ACCEPT policy for INPUT
grep -E "^:INPUT" /home/ubuntu/GitHub/atius-srv/iptables/iptables-backup-v6.conf
```

---

## 3. Domain Infrastructure Configuration Validation

The `domain-infrastructure/` directory contains FreeIPA (Docker), Keycloak,
and Samba configuration. As of the current layout, `configs/` and `scripts/`
are empty (`.gitkeep`). Validation focuses on the Docker and documentation
files that exist.

### 3.1 Docker Configuration Review

```bash
ls -la /home/ubuntu/GitHub/atius-srv/domain-infrastructure/docker/
```

Expected: at minimum one Dockerfile or `docker-compose.yml`. If the directory
is empty (only `.gitkeep`), no Docker image has been defined yet — this is a
known gap and provisioning cannot proceed for FreeIPA.

If Docker files exist:

```bash
# Verify Dockerfile references a compatible base image (AlmaLinux 9)
grep -E "^FROM" /home/ubuntu/GitHub/atius-srv/domain-infrastructure/docker/Dockerfile

# Check docker-compose.yml has required services: freeipa, keycloak
grep -E "freeipa|keycloak" /home/ubuntu/GitHub/atius-srv/domain-infrastructure/docker/docker-compose.yml
```

### 3.2 FreeIPA Container Ports (from CLAUDE.md constraints)

The following ports must be exposed or mapped by the Docker compose file for
FreeIPA to be accessible on the host:

| Service | Port | Purpose |
|---------|------|---------|
| HTTP | 80 | FreeIPA web UI |
| HTTPS | 443 | FreeIPA web UI (TLS) |
| LDAP | 389 | LDAPS (startTLS) |
| LDAPS | 636 | LDAP over TLS |
| Kerberos | 88 | KDC |
| Kpasswd | 464 | Kerberos password change |

Validate these ports are declared in the Docker compose file:

```bash
grep -E "80|443|389|636|88|464" \
  /home/ubuntu/GitHub/atius-srv/domain-infrastructure/docker/docker-compose.yml
```

### 3.3 Keycloak Configuration Check

Keycloak runs native on the OS (not containerized) and federates to FreeIPA's
LDAP. Verify the expected realm/user federation settings are documented in
`domain-infrastructure/CLAUDE.md`:

```bash
# Look for Keycloak references
grep -i "keycloak" /home/ubuntu/GitHub/atius-srv/domain-infrastructure/CLAUDE.md | head -10
```

### 3.4 Network and DNS Constraints (CLAUDE.md)

According to `CLAUDE.md`:

- FreeIPA runs on container Docker AlmaLinux 9 base.
- Hostname must be FQDN: `atius-srv-1.atius.com.br`.
- Apache2 is moved to ports `9080/9443` to free `80/443` for FreeIPA.
- Port 8080 is already in use and needs investigation before FreeIPA can claim it.
- CoreDNS (on `10.1.1.2`) must coexist with FreeIPA's internal BIND.

Validate these constraints are noted:

```bash
grep -i "8080\|9080\|hostname\|FQDN\|coredns" \
  /home/ubuntu/GitHub/atius-srv/domain-infrastructure/CLAUDE.md
```

If deploying, confirm `hostname` on the target system before provisioning
FreeIPA:

```bash
hostname
hostname -f   # must return FQDN
```

### 3.5 Samba / WireGuard Migration Note

Per the README, WireGuard and Samba are being migrated from `10.1.1.2` to
`10.1.1.1`. No specific WireGuard or Samba config files exist yet in this
repo under `domain-infrastructure/`. When they are added, validate:

```bash
# After files are added, check for WireGuard config presence
find /home/ubuntu/GitHub/atius-srv/domain-infrastructure/ -name "*.conf" -o -name "wg0.conf"

# After files are added, check for Samba config
find /home/ubuntu/GitHub/atius-srv/domain-infrastructure/ -name "smb.conf"
```

---

## 4. Pre-Deployment Checklist

Before running `setup.sh` on a clean server, run through each section above:

```
[ ] setup.sh syntax check passed (bash -n)
[ ] iptables/ directory exists with v4 and v6 rule files
[ ] All required INPUT ports present in iptables-backup-v4.conf
[ ] dark-theme-ubuntu/install.sh exists (for Stage 2)
[ ] domain-infrastructure/docker/ has Dockerfile or compose file
[ ] Hostname is FQDN (atius-srv-1.atius.com.br) before FreeIPA install
[ ] Port 8080 conflict resolved before FreeIPA claims port 80/443
[ ] Apache2 moved to 9080/9443 (if FreeIPA will be deployed)
```

---

## 5. Post-Deployment Validation

After running `setup.sh` Stage 1 and rebooting:

```bash
# Verify swap is active
swapon --show

# Verify iptables-persistent loaded the saved rules
sudo iptables -L INPUT -n | grep -E "3389|3399|80|443|8745"

# Verify netfilter-persistent service is enabled
systemctl is-enabled netfilter-persistent

# Verify PostgreSQL is running (Stage 1 installs 18)
sudo systemctl status postgresql | grep Active

# After Stage 2: verify Chromium desktop entry
[ -f ~/Desktop/chromium-browser.desktop ] && echo "Chromium shortcut: OK"
```

---

## 6. Known Limitations

- **No automated test suite.** All checks above are manual.
- **domain-infrastructure/configs/ and scripts/ are empty.** Validation
  coverage for FreeIPA, Keycloak, and Samba is limited to Docker files and
  CLAUDE.md documentation until actual config files are committed.
- **iptables rules include Docker bridge and libvirt chains.** These are
  preserved from the original server snapshot and include private subnet
  references (`172.17.0.0/16`, `172.19.0.0/16`, `192.168.122.0/24`,
  `10.182.0.0/24`). Do not drop these unless the Docker/libvirt environment
  changes.
