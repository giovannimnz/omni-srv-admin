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

### Address Preference Order

For all Linux machine-to-machine operations, prefer:

1. `access.oci_private_ip`
2. `access.vpn_ip` (`wg100`, reserve only)
3. `access.public_ip` only for break-glass or explicit public probes

For Windows and mobile clients:

- DRG/OCI direct path is the target
- `wg100` remains acceptable only while DRG direct reachability is not proven

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
  - `atius-srv-1-wg100`
  - `atius-srv-2-wg100`
  - `atius-srv-3-wg100`
  - `horistic-srv-wg100`

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
- `GIOVANNI-S23` is an edge client on `10.100.100.9`; final handset-side
  outbound reachability remains limited by the client `AllowedIPs` scope.
- `wg100` endpoints remain documented and tested only as reserve fallback.

See:

- [ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md](/C:/Users/muniz/Documents/GitHub/omni-srv-admin/docs/operations/ATIUS-INTERNAL-DNS-CANONICALIZATION-PLAN.md)
- [ATIUS-DRG-DNS-SESSION-LEARNINGS.md](/C:/Users/muniz/Documents/GitHub/omni-srv-admin/docs/operations/ATIUS-DRG-DNS-SESSION-LEARNINGS.md)
