---
phase: 45
task: 45-02
status: completed
completed_at: 2026-07-10
requirements:
  - DNS-01
  - DNS-02
  - DNS-07
  - DNS-08
---

# 45-02 Summary - OCI Admin Dependency Gate

## Completed

- Validated the OCI-side dependency gate from `C:\Users\muniz\Documents\GitHub\oci-admin`
  without mixing new edits into that dirty worktree.
- Confirmed the canonical OCI-primary address map:
  - `atius-srv-1` -> `10.11.1.11`
  - `atius-srv-2` -> `10.12.1.12`
  - `atius-srv-3` -> `10.13.1.13`
  - `horistic-srv` -> `10.21.1.21`
- Confirmed the `oci-admin` CLI surface still exposes `peering drg-status`
  in preview/read-only mode and that the live command returns
  `recommended_architecture=upgraded_drg`, `ready_for_operation_plans=true`,
  `blockers=[]`, and `broad_admin_ingress_blocked=true`.
- Confirmed `oci-admin/docs/oci-primary-vpn-evidence.md` already captures:
  route proof on OCI-private interfaces, service-path proof for DNS/PgBouncer/
  Obsidian/Vault/TEI, W11 edge bridge proof through `wg100`, and the narrowed
  S23 handset-side route-scope blocker.
- Revalidated W11 on the live edge address `10.100.100.8`:
  `hostname` answered on `.8`, `ipconfig` reported `.8`, and internal DNS/TCP
  checks from W11 resolved `atius-srv-1` to `10.11.1.11` and reached
  `10.11.1.11:6432`, `10.13.1.13:8202`, and `10.21.1.21:3115`.
- Classified W11 as an edge client using the approved `wg100` bridge/fallback
  path, not as a native OCI/DRG host.
- Classified S23 as live on `10.100.100.9/32`; handshake, ICMP and TCP `8022`
  are green, but final closeout remains blocked by client route scope inside
  the handset profile.

## Validation

```powershell
Set-Location C:\Users\muniz\Documents\GitHub\oci-admin
uv run oci-admin --json context profiles
uv run oci-admin --json peering drg-status --profile atius1
```

Key result:

- DRG central target exists as `Brasil - Sao Paulo`
- `blockers=[]`
- `ready_for_operation_plans=true`
- `recommended_architecture=upgraded_drg`
- security guidance keeps broad admin ingress closed

```powershell
ssh muniz@10.100.100.8 hostname
ssh muniz@10.100.100.8 "cmd /c ipconfig | findstr /C:10.100.100.8"
ssh muniz@10.100.100.8 "powershell -NoProfile -Command 'Resolve-DnsName -Name atius-srv-1. -Server 10.11.1.11'"
ssh muniz@10.100.100.8 "powershell -NoProfile -Command 'Resolve-DnsName -Name horistic-srv. -Server 10.11.1.11'"
ssh muniz@10.100.100.8 "powershell -NoProfile -Command 'Test-NetConnection 10.11.1.11 -Port 6432'"
ssh muniz@10.100.100.8 "powershell -NoProfile -Command 'Test-NetConnection 10.13.1.13 -Port 8202'"
ssh muniz@10.100.100.8 "powershell -NoProfile -Command 'Test-NetConnection 10.21.1.21 -Port 3115'"
ssh ubuntu@10.100.100.1 "dig +short @10.11.1.11 atius-srv-1 A; dig +short @10.11.1.11 atius-srv-2 A; dig +short @10.11.1.11 atius-srv-3 A; dig +short @10.11.1.11 horistic-srv A"
```

Observed:

- W11 live identity on `10.100.100.8` confirmed.
- W11 DNS from the edge path resolves `atius-srv-1 -> 10.11.1.11` and
  `horistic-srv -> 10.21.1.21`.
- W11 TCP to DRG targets `10.11.1.11:6432`, `10.13.1.13:8202`, and
  `10.21.1.21:3115` passed.
- `dig @10.11.1.11` on SRV-1 returned the canonical OCI-primary IPs for the
  four Linux hosts.

## Remaining Blocker

`45-03` is still required before Phase 45 can advance: the resolver cutover and
host-by-host hostname validation must be captured in `omni-srv-admin`.

S23 is no longer blocked by VPN-down/auth-only ambiguity. The remaining blocker
is handset route scope: the profile still needs the OCI-private CIDRs in its
effective `AllowedIPs` so outbound TCP from inside Termux can reach the DRG
service plane.
