# G18 Ubuntu Pro/ESM Inventory

This runbook defines the read-only inventory used by Phase 28 Plan 01.
It prepares G18-01 and the G18-02 mutation gate without changing SRV-1,
SRV-2, or SRV-3.

## Command

```bash
python3 scripts/g18-pro-esm-inventory.py \
  --hosts atius-srv-1,atius-srv-2,atius-srv-3,atius-srv-4,horistic-srv \
  --output .planning/phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md
```

Safety checks:

```bash
python3 -m py_compile scripts/g18-pro-esm-inventory.py
python3 scripts/g18-pro-esm-inventory.py --self-test
python3 scripts/g18-pro-esm-inventory.py --dry-run-commands
```

## Scope

Allowed hosts are hard-coded to:

| Host | Inventory |
|---|---|
| atius-srv-1 | `inventory/hosts/atius-srv-1.yaml` |
| atius-srv-2 | `inventory/hosts/atius-srv-2.yaml` |
| atius-srv-3 | `inventory/hosts/atius-srv-3.yaml` |

The collector loads `access.ssh`, `access.vpn_ip`, `access.public_ip`,
`backup.gdrive_base`, and `oci.*` from those files. Other hosts are rejected.

## Collected Fields

| Field group | Source | Notes |
|---|---|---|
| Host identity | `hostnamectl`, `/etc/os-release`, `uname -r` | Read-only OS and kernel snapshot. |
| Ubuntu Pro client | `dpkg-query -W ubuntu-pro-client` | Package version only. |
| Pro status | `pro status --format json` | Account email, account ID, contract ID, and token-like values are redacted. |
| Token files | `stat` on approved token paths | Path, presence, owner, group, mode, byte size, and file type only. |
| Apt sources | `stat` on `.list` and `.sources` files | Infers one-line vs DEB822 from filename; source contents are not copied. |
| Upgradable packages | `apt list --upgradable` | Uses existing local apt cache; no `apt update` or upgrade. |
| Held packages | `apt-mark showhold` | Read-only package hold list. |
| Reboot marker | `/var/run/reboot-required` existence check | Does not reboot or change state. |
| Disk capacity | `df -P -B1 / /boot /var` | Marks >=80 percent as warning and >=90 percent as blocker. |
| Services | `systemctl is-active/is-enabled` | Checks Landscape, XRDP, PM2, and K3s without restart. |
| Landscape | `landscape-config --is-registered` | Registration check only; no `landscape-config --silent`. |
| Backup manifest | repo inventory | OCI snapshot metadata and GDrive backup base. |

## Redaction Policy

- Never write Ubuntu Pro token contents, hashes, API keys, Cloudflare tokens,
  Landscape credentials, webhook secrets, account IDs, contract IDs, or account
  email values to reports.
- Token files are never read. The collector uses `stat` metadata only.
- Account/contract presence is reported as `present/redacted`.
- OCI snapshot values from repo inventory may be shortened for readability, but
  they are not used as credentials.
- Remote command stderr/stdout that can contain identifiers is passed through
  the same redaction filter before Markdown output.

## Explicitly Forbidden in Phase 28

The collector self-test rejects command strings containing these mutation
classes:

| Class | Examples rejected |
|---|---|
| apt mutation | `apt update`, `apt upgrade`, `apt full-upgrade`, install/remove/purge/autoremove |
| Ubuntu Pro mutation | `pro attach`, `pro detach`, `pro refresh`, `pro enable`, `pro disable` |
| Service mutation | `systemctl start/stop/restart/reload/enable/disable` |
| Landscape mutation | `landscape-config --silent` and other non-registration config actions |
| PM2 mutation | `pm2 restart`, `pm2 kill`, `pm2 save`, `pm2 resurrect` |
| Webhook POST | `curl -X POST`, `http ... POST`, `wget --post*` |

## Phase 29 Gate Use

Before any live upgrade in Phase 29, the operator should confirm:

1. All five managed hosts are reachable by SSH.
2. Ubuntu Pro is attached and `esm-apps` / `esm-infra` are enabled.
3. Account and contract identity are present, with exact values kept out of
   docs and logs.
4. Approved token file metadata exists if a detach/attach fallback is needed.
5. Apt source format is known, including DEB822 vs one-line source files.
6. Upgradable counts, held packages, reboot-required state, disk thresholds,
   Landscape state, XRDP state, PM2 state, and K3s state are reviewed.
7. OCI snapshot metadata and GDrive backup base are available or explicitly
   blocked before mutation.

Phase 28 does not run live apt upgrade, full-upgrade, autoremove, package
install/remove, XRDP/RDP restart, PM2 restart, Landscape mutation, or webhook
POST.

## Scope addendum - 2026-06-24

`atius-srv-4` and `horistic-srv` are allowed G18 managed hosts. Use the five-host list for Phase 29 refreshes:

```bash
python3 scripts/g18-pro-esm-inventory.py \
  --hosts atius-srv-1,atius-srv-2,atius-srv-3,atius-srv-4,horistic-srv \
  --output .planning/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-01-G18-FRESH-INVENTORY.md
```
