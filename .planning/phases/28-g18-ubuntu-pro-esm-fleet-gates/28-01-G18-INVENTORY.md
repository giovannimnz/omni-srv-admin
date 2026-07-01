# Phase 28 Plan 01: G18 Ubuntu Pro/ESM Inventory

**Generated:** 2026-06-24T22:09:50Z
**Requirements:** G18-01, G18-02
**Mode:** read-only/prep only

No live mutation executed. This report was generated with SSH read-only probes only; it did not run apt upgrade/full-upgrade/autoremove/install/remove, package cache refresh, XRDP/RDP restart, PM2 restart, Landscape mutation, Ubuntu Pro attach/detach/refresh/enable, or webhook POST.

## Fleet targets

| Host | SSH target | VPN IP | Public IP | Inventory file |
| --- | --- | --- | --- | --- |
| atius-srv-1 | ubuntu@10.1.1.1 | 10.1.1.1 | 137.131.190.161 | inventory/hosts/atius-srv-1.yaml |
| atius-srv-2 | ubuntu@10.1.1.2 | 10.1.1.2 | 129.148.47.32 | inventory/hosts/atius-srv-2.yaml |
| atius-srv-3 | ubuntu@10.1.1.3 | 10.1.1.3 | 136.248.126.12 | inventory/hosts/atius-srv-3.yaml |

## Command classes used

| Category | Command |
| --- | --- |
| host identity | `hostnamectl --static 2>/dev/null || hostname` |
| host identity | `if [ -r /etc/os-release ]; then . /etc/os-release; printf "%s\n" "${PRETTY_NAME:-unknown}"; else lsb_release -ds 2>/dev/null || uname -s; fi` |
| host identity | `uname -r` |
| ubuntu pro package | `dpkg-query -W -f='${Version}\n' ubuntu-pro-client 2>/dev/null || true` |
| ubuntu pro status | `pro status --format json 2>&1` |
| token file metadata only | `for p in /home/ubuntu/secrets/ubuntu-pro-token.txt /home/ubuntu/ubuntu-pro-token.txt; do if [ -e "$p" ]; then stat -c "%n|%U|%G|%a|%s|%F" "$p"; else printf "%s|missing|-|-|0|missing\n" "$p"; fi; done` |
| apt source metadata only | `for p in /etc/apt/sources.list /etc/apt/sources.list.d/*; do [ -f "$p" ] || continue; case "$p" in *.list|*.sources|*.list.distUpgrade|*.sources.distUpgrade) stat -c "%n|%U|%G|%a|%s" "$p";; esac; done` |
| apt cached upgradable list | `apt list --upgradable 2>/dev/null || true` |
| apt held packages | `apt-mark showhold 2>/dev/null || true` |
| reboot marker | `[ -f /var/run/reboot-required ] && printf "yes\n" || printf "no\n"` |
| disk capacity | `for p in / /boot /var; do df -P -B1 "$p" 2>/dev/null | awk -v p="$p" 'NR==2 {print p "|" $1 "|" $2 "|" $3 "|" $4 "|" $5 "|" $6}'; done` |
| sensitive service state | `for s in landscape-client xrdp xrdp-sesman pm2-ubuntu k3s; do a="$(systemctl is-active "$s" 2>/dev/null || true)"; e="$(systemctl is-enabled "$s" 2>/dev/null || true)"; printf "%s|%s|%s\n" "$s" "${a:-unknown}" "${e:-unknown}"; done` |
| landscape read-only registration check | `if command -v landscape-config >/dev/null 2>&1; then landscape-config --is-registered >/dev/null 2>&1; printf "registered_exit=%s\n" "$?"; else printf "landscape-config=missing\n"; fi; if command -v landscape-client >/dev/null 2>&1; then landscape-client --version 2>&1 | head -n 1; fi` |

## Redaction policy

- Ubuntu Pro account emails, account IDs, contract IDs, and token-like values are redacted before Markdown output.
- Ubuntu Pro token files are audited with `stat` metadata only: path, presence, owner, group, mode, byte size, and file type.
- Token contents are never read, hashed, copied, or printed.
- Apt source contents are not copied; only filename, inferred format, owner, group, mode, and byte size are reported.

## Phase 29 gate inputs

- Confirm each host has Ubuntu Pro attached, `esm-apps` enabled, and `esm-infra` enabled.
- Confirm account/contract identity is present but keep the exact values out of docs and logs.
- Confirm token file metadata is present at an approved path before any detach/attach fallback.
- Confirm OCI snapshot metadata and GDrive backup base exist before any live apt mutation.
- Resolve any disk, reboot-required, SSH, Pro, Landscape, XRDP, PM2, or K3s blocker listed per host.

## atius-srv-1

| Field | Value |
| --- | --- |
| inventory target | ubuntu@10.1.1.1 |
| vpn ip | 10.1.1.1 |
| public ip | 137.131.190.161 |
| remote hostname | atius-srv-1 |
| OS | Ubuntu 24.04.4 LTS |
| kernel | 6.17.0-1016-oracle |
| ubuntu-pro-client | 37.2ubuntu~24.04 |
| Ubuntu Pro attached | True |
| account identity | present/redacted |
| contract identity | present/redacted |
| esm-apps | enabled |
| esm-infra | enabled |
| Landscape registration | no |
| Landscape client | 24.02-0ubuntu5.7 |
| reboot required | no |

### Token file metadata

Token contents were not read, hashed, copied, or printed.

| Path | Present | Owner | Group | Mode | Bytes | Type |
| --- | --- | --- | --- | --- | --- | --- |
| /home/ubuntu/secrets/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |
| /home/ubuntu/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |

### Apt sources

| Path | Format | Owner | Group | Mode | Bytes |
| --- | --- | --- | --- | --- | --- |
| /etc/apt/sources.list | one-line | root | root | 644 | 3232 |
| /etc/apt/sources.list.d/ansible-ubuntu-ansible-jammy.list | one-line | root | root | 644 | 195 |
| /etc/apt/sources.list.d/ansible-ubuntu-ansible-jammy.list.distUpgrade | one-line | root | root | 644 | 195 |
| /etc/apt/sources.list.d/anydesk-stable.list | one-line | root | root | 644 | 88 |
| /etc/apt/sources.list.d/anydesk-stable.list.distUpgrade | one-line | root | root | 644 | 88 |
| /etc/apt/sources.list.d/backports.list | one-line | root | root | 644 | 93 |
| /etc/apt/sources.list.d/backports.list.distUpgrade | one-line | root | root | 644 | 93 |
| /etc/apt/sources.list.d/brave-browser-release.list | one-line | root | root | 644 | 141 |
| /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list | one-line | root | root | 644 | 145 |
| /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list.distUpgrade | one-line | root | root | 644 | 145 |
| /etc/apt/sources.list.d/docker.list.distUpgrade | one-line | root | root | 644 | 112 |
| /etc/apt/sources.list.d/foxinou-ubuntu-dvpn-node-manager-jammy.list | one-line | root | root | 644 | 215 |
| /etc/apt/sources.list.d/foxinou-ubuntu-dvpn-node-manager-jammy.list.distUpgrade | one-line | root | root | 644 | 215 |
| /etc/apt/sources.list.d/github-cli.list | one-line | root | root | 644 | 119 |
| /etc/apt/sources.list.d/github-cli.list.distUpgrade | one-line | root | root | 644 | 119 |
| /etc/apt/sources.list.d/mongodb-org-8.0.list | one-line | root | root | 644 | 141 |
| /etc/apt/sources.list.d/mongodb-org-8.0.list.distUpgrade | one-line | root | root | 644 | 141 |
| /etc/apt/sources.list.d/nodesource.sources | DEB822 | root | root | 644 | 155 |
| /etc/apt/sources.list.d/nodesource.sources.distUpgrade | DEB822 | root | root | 644 | 155 |
| /etc/apt/sources.list.d/pgdg.sources | DEB822 | root | root | 644 | 162 |
| /etc/apt/sources.list.d/pgdg.sources.distUpgrade | DEB822 | root | root | 644 | 162 |
| /etc/apt/sources.list.d/sublime-text.sources | DEB822 | root | root | 644 | 118 |
| /etc/apt/sources.list.d/sublime-text.sources.distUpgrade | DEB822 | root | root | 644 | 118 |
| /etc/apt/sources.list.d/tailscale.list | one-line | root | root | 644 | 156 |
| /etc/apt/sources.list.d/timescale_timescaledb.list | one-line | root | root | 644 | 402 |
| /etc/apt/sources.list.d/timescale_timescaledb.list.distUpgrade | one-line | root | root | 644 | 402 |
| /etc/apt/sources.list.d/ubuntu-esm-apps.list.distUpgrade | one-line | root | root | 644 | 266 |
| /etc/apt/sources.list.d/ubuntu-esm-apps.sources | DEB822 | root | root | 644 | 202 |
| /etc/apt/sources.list.d/ubuntu-esm-infra.list.distUpgrade | one-line | root | root | 644 | 274 |
| /etc/apt/sources.list.d/ubuntu-esm-infra.sources | DEB822 | root | root | 644 | 206 |
| /etc/apt/sources.list.d/vscode.sources.distUpgrade | DEB822 | root | root | 644 | 278 |
| /etc/apt/sources.list.d/webmin.list | one-line | root | root | 644 | 135 |
| /etc/apt/sources.list.d/webmin.list.distUpgrade | one-line | root | root | 644 | 135 |
| /etc/apt/sources.list.d/xtradeb-ubuntu-apps-jammy.list | one-line | root | root | 644 | 185 |
| /etc/apt/sources.list.d/xtradeb-ubuntu-apps-jammy.list.distUpgrade | one-line | root | root | 644 | 189 |

### Upgradable packages

| Total | ESM Apps | ESM Infra | Non-ESM |
| --- | --- | --- | --- |
| 44 | 15 | 0 | 29 |

Sample (first 20 cached entries, redacted):

- `anydesk/all 8.0.3 arm64 [upgradable from: 8.0.2]`
- `ffmpeg/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `gh/unknown 2.95.0 arm64 [upgradable from: 2.94.0]`
- `imagemagick-6-common/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 all [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `imagemagick-6.q16/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `imagemagick/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `kpartx/noble-updates 0.9.4-5ubuntu8.2 arm64 [upgradable from: 0.9.4-5ubuntu8.1]`
- `libavcodec60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavdevice60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavfilter9/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavformat60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavutil58/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libmagickcore-6.q16-7-extra/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libmagickcore-6.q16-7t64/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libmagickwand-6.q16-7t64/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libperl5.38t64/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `libpostproc57/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libswresample4/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libswscale7/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libvirt-clients/noble-updates 10.0.0-2ubuntu8.14 arm64 [upgradable from: 10.0.0-2ubuntu8.13]`

### Held packages

- none reported

### Disk capacity

| Path | Mount | Used | Available bytes | Status |
| --- | --- | --- | --- | --- |
| / | / | 86% | 30358339584 | warning |
| /boot | / | 86% | 30358339584 | warning |
| /var | / | 86% | 30358339584 | warning |

### Sensitive service state

| Service | Active | Enabled |
| --- | --- | --- |
| landscape-client | active | enabled |
| xrdp | active | enabled |
| xrdp-sesman | active | enabled |
| pm2-ubuntu | active | enabled |
| k3s | active | enabled |

### Backup and snapshot manifest

| Input | Value |
| --- | --- |
| OCI last snapshot | pending-250f...a298a94c |
| OCI last snapshot at | 2026-06-18T01:38:21Z |
| OCI routine schedule | weekly Sun 04:00 BRT |
| GDrive backup base | ATIUS-SRV/SRV-1/Backup |

### Blockers for Phase 29 mutation gate

- no Ubuntu Pro token file found at approved paths

## atius-srv-2

| Field | Value |
| --- | --- |
| inventory target | ubuntu@10.1.1.2 |
| vpn ip | 10.1.1.2 |
| public ip | 129.148.47.32 |
| remote hostname | atius-srv-2 |
| OS | Ubuntu 24.04.4 LTS |
| kernel | 6.17.0-1016-oracle |
| ubuntu-pro-client | 37.2ubuntu~24.04 |
| Ubuntu Pro attached | True |
| account identity | present/redacted |
| contract identity | present/redacted |
| esm-apps | enabled |
| esm-infra | enabled |
| Landscape registration | no |
| Landscape client | 24.02-0ubuntu5.7 |
| reboot required | no |

### Token file metadata

Token contents were not read, hashed, copied, or printed.

| Path | Present | Owner | Group | Mode | Bytes | Type |
| --- | --- | --- | --- | --- | --- | --- |
| /home/ubuntu/secrets/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |
| /home/ubuntu/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |

### Apt sources

| Path | Format | Owner | Group | Mode | Bytes |
| --- | --- | --- | --- | --- | --- |
| /etc/apt/sources.list | one-line | root | root | 644 | 3232 |
| /etc/apt/sources.list.d/brave-browser-release.list | one-line | root | root | 644 | 141 |
| /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-jammy.list | one-line | root | root | 644 | 193 |
| /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-jammy.list.distUpgrade | one-line | root | root | 644 | 148 |
| /etc/apt/sources.list.d/docker.list.distUpgrade | one-line | root | root | 644 | 116 |
| /etc/apt/sources.list.d/fex-emu-ubuntu-fex-noble.sources | DEB822 | root | root | 644 | 1781 |
| /etc/apt/sources.list.d/github-cli.list | one-line | root | root | 644 | 119 |
| /etc/apt/sources.list.d/github-cli.list.distUpgrade | one-line | root | root | 644 | 119 |
| /etc/apt/sources.list.d/pgdg.list | one-line | root | root | 644 | 105 |
| /etc/apt/sources.list.d/pgdg.list.distUpgrade | one-line | root | root | 644 | 60 |
| /etc/apt/sources.list.d/tailscale.list | one-line | root | root | 644 | 156 |
| /etc/apt/sources.list.d/ubuntu-esm-apps.list.distUpgrade | one-line | root | root | 644 | 266 |
| /etc/apt/sources.list.d/ubuntu-esm-apps.sources | DEB822 | root | root | 644 | 202 |
| /etc/apt/sources.list.d/ubuntu-esm-infra.list.distUpgrade | one-line | root | root | 644 | 274 |
| /etc/apt/sources.list.d/ubuntu-esm-infra.sources | DEB822 | root | root | 644 | 206 |
| /etc/apt/sources.list.d/vscode.sources | DEB822 | root | root | 644 | 278 |
| /etc/apt/sources.list.d/xtradeb-ubuntu-apps-jammy.list | one-line | root | root | 644 | 331 |

### Upgradable packages

| Total | ESM Apps | ESM Infra | Non-ESM |
| --- | --- | --- | --- |
| 10 | 3 | 0 | 7 |

Sample (first 20 cached entries, redacted):

- `code/stable 1.126.0-1782208023 arm64 [upgradable from: 1.124.2-1781225203]`
- `kpartx/noble-updates 0.9.4-5ubuntu8.2 arm64 [upgradable from: 0.9.4-5ubuntu8.1]`
- `libavcodec60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavutil58/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libperl5.38t64/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `libswresample4/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `multipath-tools/noble-updates 0.9.4-5ubuntu8.2 arm64 [upgradable from: 0.9.4-5ubuntu8.1]`
- `perl-base/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `perl-modules-5.38/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 all [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `perl/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`

### Held packages

- none reported

### Disk capacity

| Path | Mount | Used | Available bytes | Status |
| --- | --- | --- | --- | --- |
| / | / | 86% | 30238765056 | warning |
| /boot | / | 86% | 30238765056 | warning |
| /var | / | 86% | 30238765056 | warning |

### Sensitive service state

| Service | Active | Enabled |
| --- | --- | --- |
| landscape-client | active | enabled |
| xrdp | active | enabled |
| xrdp-sesman | active | enabled |
| pm2-ubuntu | active | enabled |
| k3s | active | enabled |

### Backup and snapshot manifest

| Input | Value |
| --- | --- |
| OCI last snapshot | pending-ef73...9692c21e |
| OCI last snapshot at | 2026-06-18T01:38:21Z |
| OCI routine schedule | weekly Sun 04:00 BRT |
| GDrive backup base | ATIUS-SRV/SRV-2/Backup |

### Blockers for Phase 29 mutation gate

- no Ubuntu Pro token file found at approved paths

## atius-srv-3

| Field | Value |
| --- | --- |
| inventory target | ubuntu@10.1.1.3 |
| vpn ip | 10.1.1.3 |
| public ip | 136.248.126.12 |
| remote hostname | atius-srv-3 |
| OS | Ubuntu 24.04.4 LTS |
| kernel | 6.17.0-1016-oracle |
| ubuntu-pro-client | 37.2ubuntu~24.04 |
| Ubuntu Pro attached | True |
| account identity | present/redacted |
| contract identity | present/redacted |
| esm-apps | enabled |
| esm-infra | enabled |
| Landscape registration | no |
| Landscape client | 24.02-0ubuntu5.7 |
| reboot required | no |

### Token file metadata

Token contents were not read, hashed, copied, or printed.

| Path | Present | Owner | Group | Mode | Bytes | Type |
| --- | --- | --- | --- | --- | --- | --- |
| /home/ubuntu/secrets/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |
| /home/ubuntu/ubuntu-pro-token.txt | no | - | - | - | 0 | missing |

### Apt sources

| Path | Format | Owner | Group | Mode | Bytes |
| --- | --- | --- | --- | --- | --- |
| /etc/apt/sources.list | one-line | root | root | 644 | 3232 |
| /etc/apt/sources.list.d/brave-browser-release.list | one-line | root | root | 644 | 141 |
| /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-jammy.list | one-line | root | root | 644 | 148 |
| /etc/apt/sources.list.d/fex-emu-ubuntu-fex-noble.sources | DEB822 | root | root | 644 | 1781 |
| /etc/apt/sources.list.d/github-cli.list | one-line | root | root | 644 | 119 |
| /etc/apt/sources.list.d/github_git-lfs.list | one-line | root | root | 644 | 367 |
| /etc/apt/sources.list.d/sublime-text.list | one-line | root | root | 644 | 50 |
| /etc/apt/sources.list.d/tailscale.list | one-line | root | root | 644 | 156 |
| /etc/apt/sources.list.d/ubuntu-esm-apps.sources | DEB822 | root | root | 644 | 202 |
| /etc/apt/sources.list.d/ubuntu-esm-infra.sources | DEB822 | root | root | 644 | 206 |
| /etc/apt/sources.list.d/winehq-noble.sources | DEB822 | root | root | 644 | 163 |
| /etc/apt/sources.list.d/xtradeb-ubuntu-apps-noble.sources | DEB822 | root | root | 644 | 1794 |

### Upgradable packages

| Total | ESM Apps | ESM Infra | Non-ESM |
| --- | --- | --- | --- |
| 21 | 15 | 0 | 6 |

Sample (first 20 cached entries, redacted):

- `ffmpeg/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `imagemagick-6-common/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 all [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `imagemagick-6.q16/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `imagemagick/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `kpartx/noble-updates 0.9.4-5ubuntu8.2 arm64 [upgradable from: 0.9.4-5ubuntu8.1]`
- `libavcodec60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavdevice60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavfilter9/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavformat60/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libavutil58/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libmagickcore-6.q16-7-extra/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libmagickcore-6.q16-7t64/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libmagickwand-6.q16-7t64/noble-apps-security 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm10 arm64 [upgradable from: 8:6.9.12.98+dfsg1-5.2ubuntu0.1~esm9]`
- `libperl5.38t64/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `libpostproc57/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libswresample4/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `libswscale7/noble-apps-security 7:6.1.1-3ubuntu5+esm10 arm64 [upgradable from: 7:6.1.1-3ubuntu5+esm8]`
- `multipath-tools/noble-updates 0.9.4-5ubuntu8.2 arm64 [upgradable from: 0.9.4-5ubuntu8.1]`
- `perl-base/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 arm64 [upgradable from: 5.38.2-3.2ubuntu0.2]`
- `perl-modules-5.38/noble-updates,noble-security 5.38.2-3.2ubuntu0.3 all [upgradable from: 5.38.2-3.2ubuntu0.2]`

### Held packages

- none reported

### Disk capacity

| Path | Mount | Used | Available bytes | Status |
| --- | --- | --- | --- | --- |
| / | / | 61% | 81297584128 | ok |
| /boot | / | 61% | 81297584128 | ok |
| /var | / | 61% | 81297584128 | ok |

### Sensitive service state

| Service | Active | Enabled |
| --- | --- | --- |
| landscape-client | active | enabled |
| xrdp | active | enabled |
| xrdp-sesman | active | enabled |
| pm2-ubuntu | inactive | not-found |
| k3s | active | enabled |

### Backup and snapshot manifest

| Input | Value |
| --- | --- |
| OCI last snapshot | pending-5c21...0e9d2d49 |
| OCI last snapshot at | 2026-06-18T01:38:21Z |
| OCI routine schedule | weekly Sun 04:00 BRT |
| GDrive backup base | ATIUS-SRV/SRV-3/Backup |

### Blockers for Phase 29 mutation gate

- no Ubuntu Pro token file found at approved paths
