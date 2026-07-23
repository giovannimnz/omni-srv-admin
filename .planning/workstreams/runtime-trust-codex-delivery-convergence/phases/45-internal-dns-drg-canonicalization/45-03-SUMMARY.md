---
phase: 45
task: 45-03
status: completed
completed_at: 2026-07-10
requirements:
  - DNS-03
  - DNS-04
  - DNS-05
  - DNS-07
---

# 45-03 Summary - Internal DNS Resolver Cutover

## Completed

- Revalidated SRV-1 authoritative DNS on `10.11.1.11:53`; direct `dig` returns
  `atius-srv-1/2/3/horistic-srv -> 10.11.1.11/10.12.1.12/10.13.1.13/10.21.1.21`.
- Converged Linux resolver state on the four managed hosts:
  - `srv-1`: `systemd-resolved` global DNS changed from legacy `10.1.1.2` to
    `10.11.1.11 1.1.1.1`.
  - `srv-2`: `systemd-resolved` global DNS changed from legacy `10.1.1.2` to
    `10.11.1.11 1.1.1.1`.
  - `srv-3`: `systemd-resolved` global DNS changed to `10.11.1.11 1.1.1.1`,
    and the stale `DNS = 10.1.1.2` line was removed from `/etc/wireguard/wg0.conf`.
  - `horistic-srv`: `/etc/resolv.conf` was rewritten to use `10.11.1.11`
    primary and `1.1.1.1` fallback.
- Deployed the corrected `modules/fleet-network-watchdog/fleet-network-watchdog.sh`
  to `srv-1`, `srv-2`, and `srv-3`, after backing up the live resolver files.
- Promoted W11 to DRG-first DNS on the tunnel path:
  - `GIOVANNI-W11-PC-wg` now uses `10.11.1.11` primary and `10.100.100.1` reserve.
  - Windows global `SuffixSearchList` now contains `atius.internal`.
  - Short-name resolution now expands through the internal DNS path and the
    tunnel reaches the OCI-primary service endpoints.

## Validation

```bash
ssh ubuntu@10.100.100.1 "resolvectl dns; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv; ping -c 1 atius-srv-1"
ssh ubuntu@10.100.100.2 "resolvectl dns; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv; ping -c 1 atius-srv-1"
ssh ubuntu@10.100.100.3 "resolvectl dns; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv; ping -c 1 atius-srv-1"
ssh horistic@10.100.100.4 "cat /etc/resolv.conf; getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv; ping -c 1 atius-srv-1"
ssh ubuntu@10.100.100.1 "dig +short @10.11.1.11 atius-srv-1 A; dig +short @10.11.1.11 atius-srv-2 A; dig +short @10.11.1.11 atius-srv-3 A; dig +short @10.11.1.11 horistic-srv A"
```

Observed:

- All four Linux hosts now resolve the canonical hostnames to the OCI-primary
  addresses through their active resolver path.
- `ping atius-srv-1` by hostname passed on all four Linux hosts.
- `srv-3` no longer advertises `10.1.1.2` under `resolvectl status`.

```powershell
Resolve-DnsName -Name atius-srv-1.
Resolve-DnsName -Name atius-srv-2.
Resolve-DnsName -Name atius-srv-3.
Resolve-DnsName -Name horistic-srv.
ping atius-srv-1 -n 1
ping horistic-srv -n 1
Test-NetConnection atius-srv-1.atius.internal -Port 6432
Test-NetConnection atius-srv-3.atius.internal -Port 8202
Test-NetConnection horistic-srv.atius.internal -Port 3115
Get-DnsClientServerAddress -InterfaceAlias GIOVANNI-W11-PC-wg -AddressFamily IPv4
Get-DnsClientGlobalSetting
```

Observed:

- W11 resolves the four canonical names to `10.11.1.11`, `10.12.1.12`,
  `10.13.1.13`, and `10.21.1.21`.
- `ping atius-srv-1` and `ping horistic-srv` expand to
  `atius-srv-1.atius.internal` / `horistic-srv.atius.internal` and pass.
- W11 reaches `10.11.1.11:6432`, `10.13.1.13:8202`, and `10.21.1.21:3115`
  through the tunnel.

## Backups

- `srv-1`: `/etc/systemd/resolved.conf.*.bak`, `/etc/resolv.conf.*.bak`
- `srv-2`: `/etc/systemd/resolved.conf.*.bak`, `/etc/resolv.conf.*.bak`
- `srv-3`: `/etc/systemd/resolved.conf.*.bak`, `/etc/resolv.conf.*.bak`,
  `/etc/wireguard/wg0.conf.*.bak`
- `horistic-srv`: `/etc/resolv.conf.*.bak`

## Remaining Gate

`45-04` remains open. The live resolver path is now converged, but repo/runtime
drift still needs cleanup so no docs, watchdogs, service configs, or planning
artifacts can accidentally promote `wg100` as primary or revive `10.1.1.0/24`
as an active path.
