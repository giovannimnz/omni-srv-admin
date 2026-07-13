---
phase: 45
task: 45-04
status: completed
completed_at: 2026-07-10
requirements: [DNS-01, DNS-02, DNS-03, DNS-06, DNS-07, DNS-08]
---

# 45-04 Summary - Fallback Boundaries And Closeout

## Completed

- Added the offline `M004-OFF-08` gate for the OCI/DRG host map, W11/S23
  edge addresses, W11 PgBouncer endpoint, Horistic K3s identity, and retired
  overlay drift in active network scripts/configs.
- Promoted the Windows fleet DB env and inventory to `10.11.1.11:6432`; the
  prior file is backed up as `fleet-db.env.20260710-081954.bak`.
- Updated active Podman, Rust/Zellij, K3s, Jenkins, backup, Tailscale, SSO,
  Landscape, SMB and edge references to OCI/DRG.
- Aligned K3s examples and Horistic inventory with the live OCI node IPs.
- Classified both MT5 KVM hosts as `blocked-network-readdress`; planned
  `wg100` `.16/.17` addresses are explicitly not live.
- Kept remaining `10.1.1.x` strings only as historical evidence, regression
  detectors, legacy fields, or explicit blocked cleanup notes.
- Recorded the remote `atius-srv-1` dirty worktree as a separate merge queue.
- Wrote Obsidian `60-LOGS/2026-07-10-phase45-dns-drg-closeout.md` and GBrain
  `ops/phase45-dns-drg-closeout-2026-07-10`.

## Validation

- M004 validator: 8 PASS, overall PASS.
- Focused pytest: 1 passed, 16 deselected.
- Inventory: `valid=true`, 11 hosts.
- W11 DB heartbeat: healthy through `10.11.1.11:6432`.
- Bash syntax and `git diff --check`: PASS.
- DNS short/FQDN answers and Linux short-name ping: PASS.
- Windows DNS returns all four OCI/DRG targets.

## Follow-Ups Outside Phase 45

- S23 needs OCI CIDRs in handset `AllowedIPs` for final Termux outbound proof.
- Phase 44 must replace Obsidian/Vault self-signed listener certificates with
  issued ATIUS service leaf/chains before Windows HTTPS passes without `-k`.
- MT5 KVM recovery/readdress requires console or restored public access.
