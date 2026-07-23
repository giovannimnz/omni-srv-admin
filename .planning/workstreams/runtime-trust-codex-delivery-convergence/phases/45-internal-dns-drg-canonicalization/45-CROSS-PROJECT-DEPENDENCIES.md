---
phase: 45
artifact: cross-project-dependencies
created: 2026-07-10
status: current
---

# 45 Cross-Project Dependencies

Phase 45 is owned by `omni-srv-admin`, but the DNS cutover cannot be treated as
complete unless the OCI-side facts are proved by `oci-admin`.

## Responsibility Split

| Area | Owner repo | Required proof before closeout |
|---|---|---|
| DRG topology and route tables | `C:\Users\muniz\Documents\GitHub\oci-admin` | Route tables, VCN/subnet placements, and peering/DRG status prove server-to-server paths for the four private IPs. |
| Security lists / NSGs | `C:\Users\muniz\Documents\GitHub\oci-admin` | OCI rules permit DNS `53`, PgBouncer `6432`, Obsidian `27124`, Vault `8202`, and TEI `3115` only where intended. |
| Private IP attachment evidence | `C:\Users\muniz\Documents\GitHub\oci-admin` | `atius-srv-1=10.11.1.11`, `atius-srv-2=10.12.1.12`, `atius-srv-3=10.13.1.13`, `horistic-srv=10.21.1.21` are attached, reachable, and documented. |
| Internal DNS records and resolver behavior | `omni-srv-admin` | `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, and `*.atius.internal` resolve to DRG/OCI private IPs. |
| W11/S23 edge fallback | `oci-admin` plus `home-proxy` | W11 bridge/reachability is proven; S23 still needs handset-side outbound proof. Residential PPTP remains separate from service DNS. |
| Runtime skills / Wayland | `wayland` on `atius-srv-3` | `$gsd-*` skills are commands/skills, not runtime `acp.customAgents`; this stays parallel to DNS. |

## `oci-admin` Preflight Required For Phase 45

Run or produce equivalent evidence from `C:\Users\muniz\Documents\GitHub\oci-admin`
before executing live resolver cutover:

```powershell
uv run oci-admin --json context profiles
uv run oci-admin --json context regions --profile atius1
uv run oci-admin --json inventory instances --profile atius1 --region sa-saopaulo-1 --compartment <COMPARTMENT_OCID>
uv run oci-admin --json peering drg-status --profile atius1 --region sa-saopaulo-1
```

If the current CLI command names differ, the evidence must still cover:

- DRG attachment and route status for all four managed hosts.
- OCI security rules for `10.11.1.11:53`, `10.11.1.11:6432`,
  `10.11.1.11:27124`, `10.13.1.13:8202`, and `10.21.1.21:3115`.
- W11 reachability to the DRG targets through the approved bridge path.
- S23 fresh handshake plus outbound proof from inside Termux, not just
  bridge-side ping/TCP evidence.

## Merge / Dirty Worktree Rule

Do not treat the remote `atius-srv-1` `omni-srv-admin` dirty worktree as source
of truth until its changes are either committed/pushed or manually merged into
the Windows checkout with a reviewed diff. The session evidence is valid input
for planning, but Git still needs an explicit integration step.
