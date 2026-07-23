# ATIUS Internal DNS And Cloudflare Manual

## Purpose

Define the canonical DNS model for ATIUS after the DRG/OCI promotion.

This manual separates:

- public DNS for `atius.com.br`
- internal DNS for host and service resolution
- reserve/fallback addressing through `wg100`

## Canonical Model

### Public DNS

- Public authoritative zone: `atius.com.br`
- Public DNS provider: Cloudflare
- Public edge purpose:
  - internet-facing hostnames
  - proxy/CDN/WAF/TLS termination
  - public service routing to Apache, router, Landscape, Portainer, etc.

Cloudflare is **not** the source of truth for machine-to-machine private routing.

### Internal DNS

- Canonical internal host resolver endpoint: `10.11.1.11:53`
- Canonical private machine/service plane:
  - `atius-srv-1` -> `10.11.1.11`
  - `atius-srv-2` -> `10.12.1.12`
  - `atius-srv-3` -> `10.13.1.13`
  - `horistic-srv` -> `10.21.1.21`
- Reserve/fallback plane only:
  - `wg100` / `10.100.100.0/24`

### Internal Naming

The target contract is:

- short hostname:
  - `atius-srv-1`
  - `atius-srv-2`
  - `atius-srv-3`
  - `horistic-srv`
- internal FQDN:
  - `atius-srv-1.atius.internal`
  - `atius-srv-2.atius.internal`
  - `atius-srv-3.atius.internal`
  - `horistic-srv.atius.internal`

Short names must resolve to the OCI private IP by default. `ping atius-srv-1`
must choose `10.11.1.11`, not `10.100.100.1`.

### Wayland Owner Identity Contract

Phase 48 owner-local development uses one explicit identity shape for every
server. `local` describes the absence of a network hop; it does not make the
srv-3 user implicit or anonymous.

| Host ID | FQDN | OCI/DRG address | Login user | Owner workspace | Mode from srv-3 |
|---|---|---|---|---|---|
| `atius-srv-1` | `atius-srv-1.atius.internal` | `10.11.1.11` | `ubuntu` | `/home/ubuntu/GitHub` | `ssh` |
| `atius-srv-2` | `atius-srv-2.atius.internal` | `10.12.1.12` | `ubuntu` | `/home/ubuntu/GitHub` | `ssh` |
| `atius-srv-3` | `atius-srv-3.atius.internal` | `10.13.1.13` | `ubuntu` | `/home/ubuntu/GitHub` | `local` |
| `horistic-srv` | `horistic-srv.atius.internal` | `10.21.1.21` | `horistic` | `/home/horistic/GitHub` | `ssh` |

Only the three `ssh` rows receive dedicated `wayland-owner-*` aliases. The
srv-3 row must still be validated as `id -un=ubuntu`, but it must not open a
loopback SSH connection.

### Address Preference Order

For all Linux machine-to-machine operations, prefer:

1. `access.oci_private_ip`
2. `access.vpn_ip` (`wg100`, reserve only)
3. `access.public_ip` only for break-glass or explicit public probes

For Windows and mobile clients:

- DRG/OCI direct path is the target
- `wg100` remains acceptable only while DRG direct reachability is not proven

Home edge exception:

- `casa.atius.com.br` and `dns-casa.atius.com.br` belong to the residential
  `home-proxy` edge and are not internal machine identity records.
- Residential reservations `192.168.1.8`/`.9`/`.10` are local BE3 LAN
  bindings for W11/S20/S23, not `access.oci_private_ip` or internal DNS
  targets.

## Source Of Truth

### Repo

Primary machine inventory:

- `inventory/hosts/*.yaml`

Canonical host fields:

- `access.oci_private_ip`
- `access.vpn_ip`
- `access.public_ip`
- `access.ssh`

Rule:

- `oci_private_ip` is the canonical service/routing address
- `vpn_ip` is reserve/fallback only
- public IP must never be preferred for internal service routing

The Phase 48 Wayland owner transport is a narrower contract stored additively
in `inventory/remotes/wayland-github-*.yaml` under `owner_transport`. Its
allowlisted fields are `mode`, `fqdn`, `oci_private_ip`, `user`,
`workspace_root`, and, only for `mode: ssh`, `alias`. Do not derive this path
from legacy `access.ssh`, which may intentionally continue to describe a
reserve or break-glass route used by other fleet tooling.

### Public Zone

Public records for `atius.com.br` stay documented and managed through:

- [docs/CLOUDFLARE.md](/C:/Users/muniz/Documents/GitHub/omni-srv-admin/docs/CLOUDFLARE.md)

Management path:

- Cloudflare API
- secrets loaded from Vault profile `cloudflare`
- no secrets in repo/docs/chat

### Internal Zone

Target authoritative behavior:

- `10.11.1.11:53` returns A records for all host short names and internal FQDNs
- PTRs exist for the OCI private addresses
- `wg100` names, if kept, must be explicit aliases only, never the canonical answer

Recommended implementation path:

- keep the resolver endpoint on `srv-1`
- generate host records from `inventory/hosts/*.yaml`
- distribute resolver/search-domain configuration to all machines

## Machine Naming Policy

### Keep

- short canonical machine names:
  - `atius-srv-1`
  - `atius-srv-2`
  - `atius-srv-3`
  - `horistic-srv`
- optional reserve aliases:
  - `atius-srv-1-wg`
  - `atius-srv-2-wg`
  - `atius-srv-3-wg`
  - `horistic-srv-wg`

### Avoid

- using `atius.com.br` public hostnames for machine identity
- reusing public service names for host routing
- implicit dependence on `/etc/hosts` as canonical state

## Public Vs Internal Domain Roles

### `atius.com.br`

Use for:

- public applications
- public APIs
- Cloudflare-proxied edge names
- user-facing products and services

Do not use as the canonical zone for machine hostnames unless split-horizon is
explicitly designed and automated. Today the safer contract is:

- public zone: Cloudflare / `atius.com.br`
- private machine zone: `atius.internal`

### `atius.internal`

Use for:

- machine hostnames
- internal-only service aliases
- DNS search suffix
- PTR-backed private identity

## Perfect Internal DNS Target State

The system is only “perfect” when all of the following are true:

1. `ping atius-srv-1` resolves to `10.11.1.11` on every Linux host
2. `ping atius-srv-2` resolves to `10.12.1.12`
3. `ping atius-srv-3` resolves to `10.13.1.13`
4. `ping horistic-srv` resolves to `10.21.1.21`
5. PTR lookups match those names
6. resolver config on all Linux hosts points first to `10.11.1.11`
7. Windows resolver config prefers `10.11.1.11` once direct DRG reachability is validated
8. repo docs/configs/tools prefer `oci_private_ip`
9. `wg100` stays explicit reserve only
10. Cloudflare contains only public service records, not machine source-of-truth

## Validation Commands

### Linux

```bash
dig +short @10.11.1.11 atius-srv-1 A
dig +short @10.11.1.11 atius-srv-2 A
dig +short @10.11.1.11 atius-srv-3 A
dig +short @10.11.1.11 horistic-srv A

getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv
resolvectl status
ping -c 1 atius-srv-1
```

### Windows

```powershell
nslookup atius-srv-1 10.11.1.11
nslookup atius-srv-2 10.11.1.11
nslookup atius-srv-3 10.11.1.11
nslookup horistic-srv 10.11.1.11
Get-DnsClientServerAddress | Format-List
```

### Public Cloudflare Zone

```bash
curl -s "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ATIUS/dns_records?per_page=100"
```

Validate:

- public app records are present
- no machine hostname is being treated as public authoritative source of truth

## How To Add Or Change A Machine

1. Update `inventory/hosts/<host>.yaml`
2. Set or confirm:
   - `access.oci_private_ip`
   - `access.vpn_ip`
   - `access.public_ip`
   - canonical aliases
3. Regenerate internal DNS host map from inventory
4. Apply or sync resolver/search-domain config to clients
5. Validate:
   - `dig`
   - `getent`
   - `ping`
   - service TCP probes
6. Update public Cloudflare records only if the machine change affects a public service
7. Update Obsidian and GBrain

## Cloudflare Governance Rule

For `atius.com.br`, Cloudflare should manage:

- public A/CNAME records
- proxied edge names
- DNS-only records intentionally exposed
- cache/WAF/TLS/Access behavior

Cloudflare should **not** be the place where we manage:

- canonical machine names for host-to-host routing
- internal service discovery
- DRG private IP source of truth

## Current Edge Exceptions

As of `2026-07-10`:

- Linux service binds and host resolvers prefer the OCI/DRG private plane.
- `GIOVANNI-W11-PC` is an edge client on `10.100.100.8`, but its DNS and fleet
  service targets prefer the OCI/DRG addresses reached through the bridge.
- The hub configuration reserves `10.100.100.10/32` for `GIOVANNI-S23` and
  `10.100.100.9/32` for `GIOVANNI-S20`. Both peers had zero handshake,
  endpoint and traffic at the 2026-07-23 readback, so they are configured
  identities rather than proven handset sessions.
- `wg100` endpoints remain documented and tested only as reserve fallback.

Residential DNS incident 2026-07-23:

- BE3 WAN changed from `152.241.106.225` to `191.31.48.191`.
- BE3 clients received only `137.131.140.20` as DNS; raw Internet and direct
  DNS to `8.8.8.8` worked, while `137.131.140.20:53` timed out.
- AdGuard remained healthy locally, but the fail-closed `verified` nft set
  still authorized the old WAN. The watcher refused promotion because
  `verified_home_wan.healthcheck.status` was `unknown` and the planned
  healthcheck was not implemented. Restarting AdGuard does not repair this
  state; use the governed WAN promotion flow with backup and verification.
- Recovery completed through that governed flow: `verified` now contains
  `191.31.48.191`, its packet counter is increasing, and W11 successfully
  resolved `example.com` through `137.131.140.20`. The authenticated Stage2
  also promoted the Apache Casa origin to
  `HOME_ROUTER_BE3_ORIGIN=https://191.31.48.191:8888`, with
  candidate/provisional cleared. This closes the DNS outage, not the separate
  handset lifecycle and S20 SSH gates.
- A periodic healthcheck based only on timeout was evaluated and rejected:
  timeout does not prove that the verified WAN changed. The temporary timer
  and service were removed, and automatic WAN promotion remains `NO-GO`
  until an external probe can conclusively distinguish origin replacement
  from transient unreachability. Until then, use the backed-up governed
  manual flow and retain fail-closed state.

See:

- [ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md](/C:/Users/muniz/Documents/GitHub/omni-srv-admin/docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md)
- [ATIUS-DRG-DNS-SESSION-LEARNINGS.md](/C:/Users/muniz/Documents/GitHub/omni-srv-admin/docs/operations/ATIUS-DRG-DNS-SESSION-LEARNINGS.md)
