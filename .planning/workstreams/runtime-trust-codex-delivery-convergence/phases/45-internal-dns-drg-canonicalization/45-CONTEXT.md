---
phase: 45
name: Internal DNS and DRG Canonicalization
status: planned
created: 2026-07-10
requirements: [DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06, DNS-07, DNS-08]
---

# Phase 45 Context

## Operator Decisions

- `.planning` is the canonical surface for phase planning. Operational docs may
  remain as runbooks/evidence, but execution order, gates and validation belong
  in this directory.
- OCI/DRG private IPs are the canonical service plane whenever reachable:
  - `atius-srv-1` -> `10.11.1.11`
  - `atius-srv-2` -> `10.12.1.12`
  - `atius-srv-3` -> `10.13.1.13`
  - `horistic-srv` -> `10.21.1.21`
- `wg100` / `10.100.100.0/24` is reserve fallback only.
- `10.1.1.0/24` is retired and must not be used as active resolver, service path, validation path or rollback target.
- `GIOVANNI-W11-PC` is an edge client: it may reach DRG targets through the
  approved `wg100` bridge/fallback path, but that does not make `wg100` the
  canonical server-to-server plane.
- `GIOVANNI-S23` is already live on `10.100.100.9/32`, but remains blocked for
  final edge validation until outbound proof is captured from inside the
  handset/Termux session.
- Public `atius.com.br` records are Cloudflare-managed; internal hostnames and private IP identity are managed by internal DNS/inventory.

## Current Evidence

- Five Codex sessions were reviewed and summarized in `45-SESSION-INTAKE.md`.
- `45-CROSS-PROJECT-DEPENDENCIES.md` maps what must be proved by `oci-admin`
  before DNS cutover can be called complete.
- `45-REVIEWS.md` records the manual convergence pass and the actionable
  findings absorbed into this replan.
- K3s node InternalIP already moved to OCI/DRG private IPs during prior validation.
- PgBouncer, Obsidian REST/MCP, Vault and TEI docs/configs are being canonicalized to `10.11.1.11`, `10.13.1.13`, and `10.21.1.21`.
- W11 WireGuard is now live on `10.100.100.8/32`; SSH and local interface proof
  were revalidated from the new IP.
- S23 WireGuard is now live on `10.100.100.9/32`; handshake, ICMP and TCP 8022
  are green from the bridge path, while authenticated handset-side outbound
  proof remains pending.
- The remote `atius-srv-1` checkout has uncommitted home-proxy/PPTP docs and
  inventory changes; they are valid planning input but not yet a pullable Git
  source of truth.
- Wayland on `atius-srv-3` is being corrected so GSD appears as skills/commands,
  not runtime agents. That is a parallel operator-runtime dependency, not a DNS
  blocker.
- The main resolver drift identified at replan time was executed in wave `45-03`:
  - SRV-1 and SRV-2 now use `systemd-resolved` global DNS `10.11.1.11 1.1.1.1`.
  - SRV-3 had the stale `wg0` DNS line removed from `/etc/wireguard/wg0.conf`.
  - Horistic now uses `/etc/resolv.conf` with `10.11.1.11` primary.
  - W11 now uses tunnel DNS `10.11.1.11` with reserve `10.100.100.1` and
    suffix search `atius.internal`.
  - Remaining blocker is closeout drift, not live hostname resolution.

## Source Of Truth

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-PLAN.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-VALIDATION.md`
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/45-internal-dns-drg-canonicalization/45-CROSS-PROJECT-DEPENDENCIES.md`
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
- Do not model home-proxy/PPTP residential LAN IPs as OCI/DRG or internal DNS
  authority.
- Do not store secret values from any session in Git, `.planning`, Obsidian,
  GBrain, logs or shell history.
