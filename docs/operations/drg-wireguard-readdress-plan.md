# DRG and WireGuard Readdress Plan

**Status:** replan required before OCI writes
**Updated:** 2026-07-06
**Primary execution owner:** `oci-admin`
**Runtime inventory owner:** `omni-srv-admin`

## Why This Exists

The fleet is moving toward an OCI DRG topology managed from `oci-admin` on
`GIOVANNI-W11-PC`:

`C:\Users\muniz\Documents\GitHub\oci-admin`

The network migration source thread verified for this replan is:

`019f33f6-1aac-7a41-baae-f80f494a60e8`

The W11 Codex thread reported as coordination context is:

`019f2ba1-1982-7c03-a17d-3ce28c589ac1`

At verification time, `019f33f6-1aac-7a41-baae-f80f494a60e8` was the
`oci-admin` Phase 9 network migration thread. The W11 thread
`019f2ba1-1982-7c03-a17d-3ce28c589ac1` was active on unrelated
`omni-srv-admin`/Wayland work, so this document treats the Phase 9 thread as the
technical source for DRG/WireGuard state and uses `019f2ba1` only as
coordination context.

## Current Live Address Map

| Host | OCI NIC today | `wg0` today | `wg100` today | K3s InternalIP |
|---|---:|---:|---:|---:|
| `atius-srv-1` | `10.0.0.38/24` | `10.1.1.1/32` | `10.100.100.1/24` | `10.100.100.1` |
| `atius-srv-2` | `10.0.0.197/24` | `10.1.1.2/24` | `10.100.100.2/32` | `10.100.100.2` |
| `atius-srv-3` | `10.0.0.154/24` | `10.1.1.3/32`, `10.1.1.7/32` | `10.100.100.3/32` | `10.100.100.3` |
| `horistic-srv` | `10.0.0.65/24` | `10.1.1.4/32` | `10.100.100.4/32` | `10.100.100.4` |

Current client reservations:

| Endpoint | Legacy address | `wg100` target | Status |
|---|---:|---:|---|
| `GIOVANNI-W11-PC` | `10.1.1.5` | `10.100.100.5` | direct SRV-1 handshake validated |
| `GIOVANNI-S23` | `10.1.1.6` | `10.100.100.6` | direct SRV-1 handshake validated |
| `peer11` | - | `10.100.100.11` | config generated; import/handshake pending |
| `peer12` | - | `10.100.100.12` | config generated; import/handshake pending |
| `peer13` | - | `10.100.100.13` | config generated; import/handshake pending |
| `peer14` | - | `10.100.100.14` | config generated; import/handshake pending |
| `peer15` | - | `10.100.100.15` | config generated; import/handshake pending |
| `peer16` | `10.1.1.16` | `10.100.100.16` | generated; likely MT5 class, verify before activation |
| `peer17` | `10.1.1.17` | `10.100.100.17` | generated; likely MT5 class, verify before activation |

Current non-WireGuard ranges:

| Purpose | CIDR |
|---|---:|
| K3s pods | `10.42.0.0/16` |
| K3s services | `10.43.0.0/16` |
| FreeIPA Podman network | `10.89.53.0/24` |
| SRV-3 LXD bridge | `10.65.172.0/24` |
| Docker default on Horistic | `172.17.0.0/16` |
| Tailscale | `100.64.0.0/10` |

Do not use these blocks for new OCI VCN/subnet/route planning:

| Block | Reason |
|---|---|
| `10.0.0.0/16` | Current overlapping OCI VCN/subnet space |
| `10.42.0.0/16` | K3s pod CIDR |
| `10.43.0.0/16` | K3s service CIDR |
| `10.65.172.0/24` | SRV-3 LXD bridge |
| `10.89.53.0/24` | FreeIPA Podman network |
| `10.100.0.0/16` | Reserved for WireGuard target space |
| `10.1.0.0/16` | Contains the still-live legacy WireGuard `10.1.1.0/24` |
| `100.64.0.0/10` | Tailscale CGNAT space |

## DRG Planning Constraint

Do not build the DRG route plan while the attached VCNs all overlap on
`10.0.0.0/16` with server subnets in `10.0.0.0/24`. DRG does not remove that
overlap blocker by itself. `oci-admin` owns the OCI-side address-plane and must
produce OperationPlan previews before any live write.

Previous `oci-admin` Phase 9 target address plane:

| Scope | Target VCN CIDR | Target server subnet | Stable target host IP |
|---|---:|---:|---:|
| `atius1` / SRV-1 | `10.1.0.0/16` | `10.1.1.0/24` | `10.1.1.11` |
| `atius2` / SRV-2 | `10.2.0.0/16` | `10.2.1.0/24` | `10.2.1.12` |
| `atius3` / SRV-3 | `10.3.0.0/16` | `10.3.1.0/24` | `10.3.1.13` |
| `horistic` | `10.21.0.0/16` | `10.21.1.0/24` | `10.21.1.21` |

Reservations from the same plan:

- `10.4.0.0/16` through `10.20.0.0/16`: future ATIUS networks.
- `10.21.0.0/16+`: Horistic and non-ATIUS networks.
- W11 future reservation: `10.22.0.0/16`, host `10.22.1.22`.
- S23 future reservation: `10.23.0.0/16`, host `10.23.1.23`.

This plan is rejected for the current migration because `10.1.0.0/16` contains
the live legacy WireGuard range `10.1.1.0/24`. That legacy range is still used
as rollback/compatibility and appears in broad repo scans. Reusing the same
space for a DRG-routed VCN would create ambiguous routing and make rollback
harder.

Replanned DRG address plane:

| Scope | Target VCN CIDR | Target server subnet | Stable target host IP |
|---|---:|---:|---:|
| `atius1` / SRV-1 | `10.51.0.0/16` | `10.51.1.0/24` | `10.51.1.11` |
| `atius2` / SRV-2 | `10.52.0.0/16` | `10.52.1.0/24` | `10.52.1.12` |
| `atius3` / SRV-3 | `10.53.0.0/16` | `10.53.1.0/24` | `10.53.1.13` |
| `horistic` | `10.71.0.0/16` | `10.71.1.0/24` | `10.71.1.21` |

Reservations after the replan:

- `10.54.0.0/16` through `10.70.0.0/16`: future ATIUS OCI networks.
- `10.72.0.0/16+`: future non-ATIUS/Horistic or edge-site networks.
- W11 and S23 remain WireGuard clients for now, not OCI VCNs. If either becomes
  a routed site later, reserve W11 as `10.72.0.0/16` and S23 as
  `10.73.0.0/16`.
- Do not allocate OCI VCN/subnet space from `10.100.0.0/16`; it remains the
  WireGuard control-plane family.

## Target WireGuard Range

| Purpose | CIDR | Notes |
|---|---:|---|
| Fleet WireGuard control plane | `10.100.100.0/24` | Live target range from `oci-admin` Phase 9 |
| Legacy rollback/compatibility | `10.1.1.0/24` | Keep until `active_blocker=0` and compatibility aliases are closed |

Live and pending host assignments:

| Host | WireGuard target | Status |
|---|---:|---|
| `atius-srv-1` | `10.100.100.1` | live hub |
| `atius-srv-2` | `10.100.100.2` | live |
| `atius-srv-3` | `10.100.100.3` | live |
| `horistic-srv` | `10.100.100.4` | live |
| `GIOVANNI-W11-PC` | `10.100.100.5` | live handshake to SRV-1 |
| `GIOVANNI-S23` | `10.100.100.6` | live handshake to SRV-1 |
| `peer11`-`peer17` | `10.100.100.11`-`10.100.100.17` | generated, pending device import |

`10.100.100.0/24` is already live for K3s node InternalIPs on the four Linux
hosts. SRV-1 is the active hub for the new `wg100` path, `vpn.atius.com.br`
now points at the SRV-1 endpoint on UDP `51821`, and W11/S23 handshakes have
been validated directly against SRV-1. The remaining `oci-admin` WireGuard work
is to activate and validate `peer11` through `peer17`, then keep both old and
new ranges online until service references are closed.

## Migration Waves

### Wave 0 - Freeze and Backups

- Snapshot or confirm rollback for every OCI instance/block volume.
- Take an etcd snapshot before touching K3s node IPs or peer URLs.
- Backup `/etc/wireguard`, `/etc/rancher/k3s/config.yaml`,
  `/home/ubuntu/GitHub/vpn-atius/coredns`, `/etc/hosts`, Apache vhosts and
  host firewall scripts.
- Export current evidence: `ip -br -4 addr`, `ip route`, `wg show`,
  `sudo k3s kubectl get nodes -o wide`, CoreDNS forward and reverse queries.

### Wave 1 - DRG Replan Gate

- Confirm each OCI account, VCN, subnet, route table, NSG and security list.
- Replace the previous `10.1.0.0/16`, `10.2.0.0/16`, `10.3.0.0/16` and
  `10.21.0.0/16` plan with `10.51.0.0/16`, `10.52.0.0/16`,
  `10.53.0.0/16` and `10.71.0.0/16`.
- Reject direct DRG routing if any routed CIDR overlaps current OCI, WireGuard,
  K3s, LXD, Podman or Tailscale ranges.
- Produce `oci-admin` OperationPlan previews and diffs before every live OCI
  write.
- Keep public edge and WireGuard working during DRG testing; DRG is underlay,
  not an immediate replacement for encrypted management.

### Wave 2 - Finish WireGuard Target Path

- Continue using `10.100.100.0/24` as the WireGuard target.
- Keep `10.1.1.0/24` live during compatibility and rollback.
- Treat SRV-1 hub, `vpn.atius.com.br` on SRV-1, W11 `10.100.100.5` and S23
  `10.100.100.6` as already live.
- Import and validate `peer11` through `peer17` on their target devices.
- Update firewall guards to allow both old and new WireGuard ranges.
- Add CoreDNS records and PTRs for the new addresses with low TTL.
- Validate host-to-host ping and TCP probes over both old and new ranges.

### Wave 3 - Service Endpoint Migration

Move service dependencies one class at a time:

- Fleet inventory and `/etc/hosts`
- CoreDNS `custom_hosts` and reverse zones
- PgBouncer endpoint currently documented as `10.1.1.1:6432`
- Vault endpoint currently documented as `10.1.1.3:8202`
- FreeIPA/CoreDNS forwarding currently using `10.1.1.3`
- Samba, Keycloak LDAP, Landscape, Obsidian/GBrain MCP, Jenkins JNLP
- Router/TEI references currently using `10.1.1.4:3115`
- Apache/vhost upstreams and monitoring scrape targets

Move clients to `10.100.100.x` service targets first. Do not move a service
dependency directly to the future DRG underlay until the DRG preview has passed
and WireGuard rollback remains available. Each move needs a same-day rollback
alias while old `10.1.1.x` stays available.

### Wave 4 - K3s Maintenance Window

K3s already uses `wg100` / `10.100.100.0/24` live and should not be moved to a
different WireGuard range for this DRG work. Treat K3s as a protected consumer
of the `10.100.100.0/24` target:

- Keep K3s node IPs on `10.100.100.1` through `10.100.100.4`.
- Verify `/readyz`, etcd quorum and node InternalIPs after any hub/DNS/firewall
  change.
- Do not retire old `10.1.1.x` service aliases until all K3s-adjacent service
  references are scanned and closed.

### Wave 5 - DRG Cutover

- Route OCI private underlay traffic over DRG only after the replan CIDRs are
  present in `oci-admin` and non-overlap is proven by OperationPlan preview.
- Prefer WireGuard over the DRG underlay for management and K3s-sensitive
  traffic unless a replacement encryption model is explicitly approved.
- Validate that public Cloudflare/Apache exposure did not bypass Access/VPN
  gates.

### Wave 6 - Old Range Retirement

Only retire old ranges after at least one stable observation window:

- Confirm repo/vault reference scan is zero or every remaining reference has a
  documented legacy exception.
- Remove stale `10.1.1.x` CoreDNS/PTR records.
- Remove old `AllowedIPs` and firewall accepts.
- Remove `10.1.1.7` SRV-3 compatibility alias after K3s/etcd no longer needs
  it.
- Update inventory, network map, GBrain/Obsidian notes, and runbooks.

## No-Go Conditions

- Any DRG-attached VCN still overlaps as `10.0.0.0/24`.
- Any new DRG VCN/subnet uses `10.1.0.0/16` while `10.1.1.0/24` remains live.
- No fresh etcd snapshot before K3s node-IP changes.
- K3s `/readyz` or etcd quorum is degraded.
- CoreDNS cannot answer both forward and reverse records for old and new ranges.
- `peer11`-`peer17` client configs are not imported but old client routes are
  removed.
- `10.1.1.0/24` reference scan has `active_blocker=unknown` or
  `active_blocker>0`; the 2026-07-06 `git grep` scan still found 201 tracked
  files with `10.1.1.` references.
- Public edge starts reaching private services directly without Access/VPN gate.

## Immediate Repo Follow-Ups

- Keep stale `10.1.1.x` references visible until each is migrated or marked as
  an intentional rollback/compatibility alias.
- Update `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` with this DRG
  transition note.
- Update `oci-admin` Phase 9 constants/docs to the `10.51/10.52/10.53/10.71`
  address plane before any live DRG writes.
- Treat `oci-admin` Phase 9 as the execution owner for OCI/DRG/WireGuard hub
  changes; `omni-srv-admin` remains the runtime inventory/smoke/runbook source.
