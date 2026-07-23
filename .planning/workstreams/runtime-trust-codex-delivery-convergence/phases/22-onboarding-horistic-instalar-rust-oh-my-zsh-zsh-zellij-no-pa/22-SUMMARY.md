---
phase: 22
plan: 22-PLAN.md
status: complete
completed_by: hermes-agent
completed_at: 2026-06-17
---

# Phase 22 — SUMMARY

## Status: ✅ COMPLETE

## Host

| Hostname | WireGuard IP | Public IP | Platform | Role |
|---|---|---|---|---|
| `horistic-srv` (was `horistic-srv-1`) | 10.1.1.4 | 163.176.232.119 | Ubuntu 24.04 aarch64 | Apache2 proxy for *.horistic.com |

## Accomplishments

- **Host rename:** `horistic-srv-1` → `horistic-srv` applied without reboot
- **WireGuard:** key/PSK/IP preserved; `/etc/wireguard/wg0.conf` not touched
- **Tailscale:** rename applied
- **Toolchain:** rustup 1.96.0, cargo-binstall 1.20.0, zellij 0.44.3 (fleet standard)
- **Monitoramento:** prometheus-node-exporter active on :9100
- **Inventário omni:** `inventory/hosts/horistic-srv-1.yaml` → `horistic-srv.yaml`
- **DB:** `horistic-srv` upserted in `TbHosts/TbNodes/TbNodeTelemetry`; `horistic-srv-1` removed
- **VPN/CoreDNS:** alias lowercase canonical; `/etc/hosts` updated on SRV-1/2/3/Horistic
- **Vault:** gbrain sync (no embed, MiniMax 1 RPM)
- **Docs:** network map v1.4.0 (repo + vault mirror)
- **IP remapping:** Apache2 now at 10.1.1.4 (was 10.1.1.3); SRV-3 canonical is now 10.1.1.3

## Pending (operational — not blocking)

- Apache vhost config on horistic-srv still references `remote.horistic-srv-1.atius.com.br` (working, low priority)
- GDrive folder still named `horistic-srv-1` (operational)

## Validation

- `hostname` returns `horistic-srv`
- `getent hosts horistic-srv` resolves correctly
- `rustc --version` = 1.96.0, `cargo-binstall --version` = 1.20.0, `zellij --version` = 0.44.3
- `omni fleet show horistic-srv` returns YAML
- `omni fleet monitor hosts --json` shows horistic-srv with source=database
