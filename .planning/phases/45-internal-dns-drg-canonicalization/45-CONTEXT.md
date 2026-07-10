---
phase: 45
name: Internal DNS and DRG Canonicalization
status: planned
created: 2026-07-10
requirements: [DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06, DNS-07, DNS-08]
---

# Phase 45 Context

## Operator Decisions

- OCI/DRG private IPs are the canonical service plane whenever reachable:
  - `atius-srv-1` -> `10.11.1.11`
  - `atius-srv-2` -> `10.12.1.12`
  - `atius-srv-3` -> `10.13.1.13`
  - `horistic-srv` -> `10.21.1.21`
- `wg100` / `10.100.100.0/24` is reserve fallback only.
- `10.1.1.0/24` is retired and must not be used as active resolver, service path, validation path or rollback target.
- `GIOVANNI-W11-PC` may remain on reserve path until direct DRG reachability is proven from the Windows client.
- Public `atius.com.br` records are Cloudflare-managed; internal hostnames and private IP identity are managed by internal DNS/inventory.

## Current Evidence

- K3s node InternalIP already moved to OCI/DRG private IPs during prior validation.
- PgBouncer, Obsidian REST/MCP, Vault and TEI docs/configs are being canonicalized to `10.11.1.11`, `10.13.1.13`, and `10.21.1.21`.
- Live resolver drift remains the main blocker:
  - SRV-1 still had resolver references to `10.1.1.2`.
  - SRV-2 still had resolver references to `10.1.1.2`.
  - SRV-3 had `wg0` DNS pointing to `10.1.1.2`.
  - Horistic had resolver pointed to `10.100.100.1`.
  - Windows direct DRG reachability was not yet proven.

## Source Of Truth

- `inventory/hosts/*.yaml`
- `docs/operations/ATIUS-INTERNAL-DNS-AND-CLOUDFLARE-MANUAL.md`
- `docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md`
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md`
- `docs/CLOUDFLARE.md`
- `docs/fleet/control-plane.md`

## Non-Negotiables

- No secret values in Git, `.planning`, Obsidian, GBrain, logs or shell history.
- Do not make Cloudflare the source of internal machine identity.
- Do not make `10.100.100.x` look primary unless the file explicitly says reserve fallback.
- Do not keep `10.1.1.x` active in scripts, validators or resolver configs.
