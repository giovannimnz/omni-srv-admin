# Phase 29 Task 01: G18 Fresh Inventory Go/No-Go

**Generated:** 2026-06-25T03:32:16Z
**Scope:** `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`
**Source:** `29-01-G18-FRESH-INVENTORY.md`, `29-02-LANDSCAPE-API-EVIDENCE.md`
**Mode:** read-only/prep only

No live mutation executed. This gate does not approve `apt upgrade`, `apt full-upgrade`, `autoremove`, package install/remove, XRDP/RDP restart, PM2 restart, Landscape mutation, Ubuntu Pro attach/detach/refresh/enable, reboot, or webhook POST.

## Decision

**Fleet decision:** BLOCK

No host is approved for live apt mutation yet. The previous 3-host checkpoint is superseded by this 4-host gate because `horistic-srv` is now part of the managed fleet.

## Landscape reconciliation

Landscape SaaS/API validation is **PASS** for all 4 managed hosts. The non-root local command `landscape-config --is-registered` is no longer treated as authoritative because `/etc/landscape/client.conf` is unreadable by the invoking user on every host.

| Host | SaaS/API | Local client.conf | Local registration probe |
| --- | --- | --- | --- |
| `atius-srv-1` | present/online | unreadable | permission-limited |
| `atius-srv-2` | present/online | unreadable | permission-limited |
| `atius-srv-3` | present/online | unreadable | permission-limited |
| `horistic-srv` | present/online | unreadable | permission-limited |

## Host status

| Host | Decision | Pro/ESM | Upgradable | Disk | Landscape | Runtime notes | Blocking reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `atius-srv-1` | BLOCK | attached; `esm-apps` enabled; `esm-infra` enabled | 45 total, 15 ESM apps, 0 ESM infra, 30 non-ESM | `/`, `/boot`, `/var` at 86% warning | SaaS/API PASS; local probe permission-limited | `landscape-client`, `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `k3s` active/enabled | Ubuntu Pro token file missing at approved paths; disk warning acceptance/remediation still needed before mutation |
| `atius-srv-2` | BLOCK | attached; `esm-apps` enabled; `esm-infra` enabled | 10 total, 3 ESM apps, 0 ESM infra, 7 non-ESM | `/`, `/boot`, `/var` at 86% warning | SaaS/API PASS; local probe permission-limited | `landscape-client`, `xrdp`, `xrdp-sesman`, `pm2-ubuntu`, `k3s` active/enabled | Ubuntu Pro token file missing at approved paths; disk warning acceptance/remediation still needed before mutation |
| `atius-srv-3` | BLOCK | attached; `esm-apps` enabled; `esm-infra` enabled | 22 total, 15 ESM apps, 0 ESM infra, 7 non-ESM | `/`, `/boot`, `/var` at 66% ok | SaaS/API PASS; local probe permission-limited | `landscape-client`, `xrdp`, `xrdp-sesman`, `k3s` active/enabled; `pm2-ubuntu` inactive/not-found | Ubuntu Pro token file missing at approved paths; confirm whether `pm2-ubuntu` is intentionally absent before mutation |
| `horistic-srv` | BLOCK | attached; `esm-apps` enabled; `esm-infra` enabled | 20 total, 3 ESM apps, 0 ESM infra, 17 non-ESM | `/`, `/boot`, `/var` at 37% ok | SaaS/API PASS; local probe permission-limited | `landscape-client`, `xrdp`, `xrdp-sesman` active/enabled; `pm2-ubuntu` inactive/not-found; `k3s` inactive/not-found | Ubuntu Pro token file missing at approved paths; confirm whether `pm2-ubuntu` and `k3s` are intentionally absent for this host role |

## Required approval payload before mutation

To approve any host, provide a per-host approval record with:

- Host name.
- Explicit approval for live apt mutation on that host.
- Accepted rollback/checkpoint evidence: OCI snapshot ID or signed no-OCI exception, plus GDrive backup/checkpoint path.
- Ubuntu Pro token path metadata or signed no-attach-fallback exception.
- Disk warning acceptance/remediation where applicable.
- Role-specific acceptance for missing `pm2-ubuntu` or `k3s` where applicable.
- Confirmation that no RDP/XRDP restart, PM2 repair, webhook POST, or reboot should be performed unless separately approved.

## Recommended host order if later approved

1. `horistic-srv` only if its role intentionally does not require `pm2-ubuntu`/`k3s`, because disk state is clean and it exercises the fourth-host path.
2. `atius-srv-3`, because disk state is clean but `pm2-ubuntu` needs role confirmation.
3. `atius-srv-2`, after disk warning acceptance or cleanup.
4. `atius-srv-1`, after disk warning acceptance or cleanup.

## Stop condition

Stop at this checkpoint. Do not run live apt mutation until the operator provides explicit per-host approval or remediation notes.
