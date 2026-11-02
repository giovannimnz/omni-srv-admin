#!/usr/bin/env bash
# omni::fleet-auto-upgrades-configure v1.0.0
# Canonical ATIUS fleet unattended automatic security updates with strict <=20% CPU containment.
set -euo pipefail

printf 'host=%s\n' "$(hostname)"
printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

export DEBIAN_FRONTEND=noninteractive

# 1. Ensure packages installed
if ! dpkg -s unattended-upgrades >/dev/null 2>&1; then
  echo "Installing unattended-upgrades..."
  apt-get update -qq
  apt-get install -y -qq unattended-upgrades
fi

# 2. Configure 20auto-upgrades
cat <<'EOF' > /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
EOF

# 3. Configure 50unattended-upgrades
cat <<'EOF' > /etc/apt/apt.conf.d/50unattended-upgrades
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Package-Blacklist {
    // Hold packages if needed
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::SyslogEnable "true";
Unattended-Upgrade::SyslogFacility "daemon";
EOF

# 4. Enforce ATIUS CPU Guardrail (<=20% CPU quota, nice 19, idle IO) via systemd drop-in
mkdir -p /etc/systemd/system/apt-daily-upgrade.service.d
cat <<'EOF' > /etc/systemd/system/apt-daily-upgrade.service.d/override.conf
[Service]
Nice=19
CPUQuota=20%
IOSchedulingClass=idle
EOF

mkdir -p /etc/systemd/system/unattended-upgrades.service.d
cat <<'EOF' > /etc/systemd/system/unattended-upgrades.service.d/override.conf
[Service]
Nice=19
CPUQuota=20%
IOSchedulingClass=idle
EOF

systemctl daemon-reload
systemctl enable unattended-upgrades
systemctl restart unattended-upgrades

echo "status=configured_and_active"
echo "cpu_quota=20%"
echo "automatic_reboot=false"
echo "unattended_upgrades_service=$(systemctl is-active unattended-upgrades)"
