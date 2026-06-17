---
phase: 21
plan: 21-PLAN.md
status: complete
completed_by: hermes-agent
completed_at: 2026-06-17
---

# Phase 21 — SUMMARY

## Status: ✅ COMPLETE

## Hosts

| Hostname | WireGuard IP | Public IP | Platform | Notes |
|---|---|---|---|---|
| `atius-mt5-kvm-1` | 10.1.1.16 | Oracle OCI | Ubuntu 24.04 aarch64 | port 9001 preserved |
| `atius-mt5-kvm-2` | 10.1.1.17 | Oracle OCI | Ubuntu 24.04 aarch64 | port 9002 preserved |

## Accomplishments

- **Inventário:** `inventory/hosts/atius-mt5-kvm-1.yaml` + `atius-mt5-kvm-2.yaml` (lowercase, oracle-oci-kvm, amd64, no K3s, ports 9001/9002 + 9100)
- **DB:** `TbHosts` + `TbNodes` + `TbPrograms` + `TbNodeTelemetry` populated for both KVMs
- **VPN/CoreDNS:** `atius-mt5-kvm-1` e `atius-mt5-kvm-2` published in `vpn-atius/coredns/custom_hosts` (lowercase canonical + uppercase aliases); `peer_aliases.json` updated; `wg-quick strip wg0` validates OK
- **Docs:** `vpn-atius/README.md` updated; `mt5-arm` docs renamed from `ATIUS-MT5-KVM-*` to `atius-mt5-kvm-*` across all docs
- **Shell runtime:** zsh default, Oh My Zsh + zsh-syntax-highlighting, Rust 1.96.0 via rustup, cargo-binstall 1.20.0, zellij 0.44.3 with interactive auto-start
- **Monitoramento:** prometheus-node-exporter active on both KVMs (:9100)
- **omni fleet:** `validate-inventory` 11 hosts OK; `list` shows both KVMs; `programs --host atius-mt5-kvm-1` returns 7; `monitor hosts --json` source=database healthy
- **Graphify:** fresh, 5248 nodes / 5934 edges, stale=false
- **Vault:** `ideaverse/60-LOGS/2026-06-17-mt5-kvm-fleet-onboarding.md` + network map mirror + daily note updated

## Out of Scope (intentional)

- K3s ingress
- WireGuard key rotation
- MT5/EA runtime changes
- Mandatory reboot

## Validation

- KVM-1: `hostname=atius-mt5-kvm-1`, `zsh` default, `rustc 1.96.0`, `cargo-binstall 1.20.0`, `zellij 0.44.3`, `node-exporter active`, port 9001 + 9100
- KVM-2: idem, port 9002 + 9100
- VPN: `getent hosts atius-mt5-kvm-1 = 10.1.1.16`, `getent hosts atius-mt5-kvm-2 = 10.1.1.17`
- DB: 2 rows TbHosts + 2 TbNodes + 10 TbPrograms + 2 telemetry
