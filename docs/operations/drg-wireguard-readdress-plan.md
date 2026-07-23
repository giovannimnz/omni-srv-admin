# DRG and WireGuard Readdress Plan

**Status:** replan required before OCI writes
**Updated:** 2026-07-10
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
| `GIOVANNI-W11-PC` | `10.1.1.5` | `10.100.100.8` | live; direct SRV-1 handshake validated on 2026-07-10; previous `10.100.100.5` is historical/cleanup only |
| `GIOVANNI-S20` | - | `10.100.100.9` | configured on the hub on 2026-07-23; no handset handshake, endpoint or traffic yet |
| `GIOVANNI-S23` | `10.1.1.6` | `10.100.100.10` | configured on the hub on 2026-07-23; no handset handshake, endpoint or traffic yet; `.9` was the previous live assignment |
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
| `10.1.0.0/16` | Historical collision zone because it used to contain the retired WireGuard `10.1.1.0/24` |
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
the old WireGuard range `10.1.1.0/24`. Even aposentada, essa faixa segue sendo
um risco de ambiguidade em docs/artefatos históricos; não reutilizar esse espaço
para VCN roteada por DRG.

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
- `home-proxy` PPTP residencial (`GIOVANNI-W11-PC=192.168.1.8`,
  `GIOVANNI-S20=192.168.1.9`, `GIOVANNI-S23=192.168.1.10`) is a home-edge
  access path only. Do not advertise `192.168.1.0/24` into DRG/wg100 and do
  not model W11/S20/S23 as routed sites
  without a separate routed-site phase.
- Do not allocate OCI VCN/subnet space from `10.100.0.0/16`; it remains the
  WireGuard control-plane family.

## Target WireGuard Range

| Purpose | CIDR | Notes |
|---|---:|---|
| Fleet WireGuard reserve plane | `10.100.100.0/24` | Reserve/fallback only after DRG promotion |
| Retired historical range | `10.1.1.0/24` | Retired on 2026-07-08; keep only as historical evidence while old notes are cleaned up |

Live and pending host assignments:

| Host | WireGuard target | Status |
|---|---:|---|
| `atius-srv-1` | `10.100.100.1` | live hub |
| `atius-srv-2` | `10.100.100.2` | live |
| `atius-srv-3` | `10.100.100.3` | live |
| `horistic-srv` | `10.100.100.4` | live |
| `GIOVANNI-W11-PC` | `10.100.100.8` | live handshake to SRV-1 after the 2026-07-10 cutover; previous `.5` is historical/cleanup only |
| `GIOVANNI-S20` | `10.100.100.9` | configured on hub; handshake/endpoint/traffic still zero on 2026-07-23 |
| `GIOVANNI-S23` | `10.100.100.10` | configured on hub; handshake/endpoint/traffic still zero on 2026-07-23; `.9` was live before this cutover |
| `peer11`-`peer17` | `10.100.100.11`-`10.100.100.17` | generated, pending device import |

The OCI/DRG private plane is now the canonical service path:
- `atius-srv-1` -> `10.11.1.11`
- `atius-srv-2` -> `10.12.1.12`
- `atius-srv-3` -> `10.13.1.13`
- `horistic-srv` -> `10.21.1.21`

`wg100` remains available as reserve/fallback, mainly for W11/S23 and break-glass.

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

- Keep `10.100.100.0/24` as reserve path only.
- Do not reintroduce `10.1.1.0/24` as live compatibility or rollback path.
- Treat SRV-1 hub and `vpn.atius.com.br` on SRV-1 as live. W11
  `10.100.100.8` is proven; S20 `10.100.100.9` and S23 `10.100.100.10` are
  current hub assignments but remain pending handset handshake. Keep
  `10.100.100.5/.6` only as historical evidence or temporary cleanup scope.
- Expand the current S23 profile, historically named peer6, so handset-side
  traffic can reach the OCI-private CIDRs `10.11.0.0/16`, `10.12.0.0/16`,
  `10.13.0.0/16`, and `10.21.0.0/16`; the live profile still behaves like
  `AllowedIPs = 10.100.100.0/24`.
- Import and validate `peer11` through `peer17` on their target devices.
- Update firewall guards to allow OCI private peers as primary and `wg100` as reserve.
- Add CoreDNS records and PTRs for the new addresses with low TTL.
- Validate host-to-host ping and TCP probes over OCI-primary and `wg100`
  reserve paths.

### Wave 3 - Service Endpoint Migration

Move service dependencies one class at a time:

- Fleet inventory and `/etc/hosts`
- CoreDNS `custom_hosts` and reverse zones
- PgBouncer endpoint fixed on `10.11.1.11:6432`, with `10.100.100.1:6432` reserve.
- Vault endpoint fixed on `10.13.1.13:8202`, with `10.100.100.3` reserve.
- FreeIPA/CoreDNS forwarding must reference `10.13.1.13`
- Samba, Keycloak LDAP, Landscape, Obsidian/GBrain MCP, Jenkins JNLP
- Router/TEI references must use `10.21.1.21:3115`, with `10.100.100.4` reserve.
- Apache/vhost upstreams and monitoring scrape targets

Move clients to the OCI private targets first. Use `10.100.100.x` only as reserve path. Do not move a service
dependency directly to the future DRG underlay until the DRG preview has passed
and same-day validation evidence. Do not keep `10.1.1.x` aliases as active
service addresses after the retirement decision.

### Wave 4 - K3s Maintenance Window

K3s now reports OCI private INTERNAL-IP live on the four Linux hosts. Treat
OCI/DRG as the canonical cluster plane and keep `wg100` only as reserve dual-bind
while the last control-plane assumptions are removed:

- Keep K3s node IPs on `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.
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

Retirement closeout requirements for the old range:

- Confirm repo/vault/GBrain reference scan is zero or every remaining reference
  is clearly historical.
- Remove stale `10.1.1.x` CoreDNS/PTR records.
- Remove old `AllowedIPs` and firewall accepts.
- Update inventory, network map, GBrain/Obsidian notes, and runbooks.

## No-Go Conditions

- Any DRG-attached VCN still overlaps as `10.0.0.0/24`.
- Any new DRG VCN/subnet reuses `10.1.0.0/16` without a fresh explicit review
  of historical collision risk.
- No fresh etcd snapshot before K3s node-IP changes.
- K3s `/readyz` or etcd quorum is degraded.
- CoreDNS cannot answer forward and reverse records for OCI-primary names and
  their explicit `wg100` reserve aliases.
- `peer11`-`peer17` client configs are not imported but old client routes are
  removed.
- Historical `10.1.1.x` references still appear as if they were active source
  of truth.
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
