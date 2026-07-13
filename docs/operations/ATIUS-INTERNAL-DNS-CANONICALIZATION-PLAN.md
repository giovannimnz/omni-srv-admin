# ATIUS Internal DNS Canonicalization Plan

## Purpose

Create a practical plan to finish the DNS transition so the private OCI/DRG
plane is canonical end-to-end.

This is a phase-style plan artifact written outside `.planning/` on purpose:
the current worktree has the whole `.planning/` tree marked as removed, so
recreating it here would conflict with user-owned changes.

## Objective

Reach a state where:

- `ping atius-srv-1` resolves to `10.11.1.11`
- `ping atius-srv-2` resolves to `10.12.1.12`
- `ping atius-srv-3` resolves to `10.13.1.13`
- `ping horistic-srv` resolves to `10.21.1.21`
- public DNS remains in Cloudflare
- internal DNS is driven from inventory and prefers OCI private IPs
- `wg100` is reserve/fallback only

## Current State

Already true:

- K3s INTERNAL-IP is already on the OCI private plane
- PgBouncer binds on `10.11.1.11`
- Obsidian REST binds on `10.11.1.11`
- Vault binds on `10.13.1.13`
- TEI is reachable on `10.21.1.21:3115`
- repo contract is being moved to OCI-primary

Still drifting:

- `srv-1` consumes DNS through `10.1.1.2`
- `srv-2` still lists `10.1.1.2` in `resolved.conf`
- `srv-3` still shows `wg0 -> DNS 10.1.1.2`
- `horistic-srv` still uses `10.100.100.1` in `resolv.conf`
- W11 DRG direct reachability to `10.11.1.11` is not yet proven

## Planning Assumptions

1. Public zone `atius.com.br` remains Cloudflare-managed.
2. Internal hostnames should resolve through `10.11.1.11`.
3. `inventory/hosts/*.yaml` remains the source of truth for host identity.
4. `oci_private_ip` is the canonical service-plane field.
5. `vpn_ip` remains reserve/fallback.

## Target Architecture

### Public

- authoritative: Cloudflare
- zone: `atius.com.br`
- records: public services only

### Internal

- authoritative resolver endpoint: `10.11.1.11:53`
- internal zone: `atius.internal`
- canonical answers:
  - `atius-srv-1` -> `10.11.1.11`
  - `atius-srv-2` -> `10.12.1.12`
  - `atius-srv-3` -> `10.13.1.13`
  - `horistic-srv` -> `10.21.1.21`

## Execution Waves

### Wave 1 — Canonical Source Of Truth

Goal:

- finish repo semantics so tooling prefers `oci_private_ip`

Tasks:

1. inventory keeps both `oci_private_ip` and reserve `vpn_ip`
2. CLI/tools prefer `oci_private_ip`
3. docs explicitly split public Cloudflare DNS from internal DNS
4. skill/runbook references point to OCI-first commands

Done when:

- repo scanners show no active docs/scripts using `10.100.100.x` as primary service plane

### Wave 2 — Linux Resolver Cutover

Goal:

- all Linux hosts consume DNS primarily from `10.11.1.11`

Tasks:

1. `srv-1`:
   - replace `10.1.1.2` in `resolved.conf` / managed resolver path
   - update deployed watchdog scripts under `/home/ubuntu/scripts`
2. `srv-2`:
   - replace `DNS=127.0.0.1 10.1.1.2 1.1.1.1` with `DNS=10.11.1.11 1.1.1.1`
3. `srv-3`:
   - remove `wg0` DNS injection or override it with DRG-primary
4. `horistic-srv`:
   - replace `10.100.100.1` with `10.11.1.11`

Verification:

```bash
resolvectl dns
dig +short @10.11.1.11 atius-srv-1 A
getent hosts atius-srv-1 atius-srv-2 atius-srv-3 horistic-srv
```

Done when:

- all Linux nodes prefer `10.11.1.11` in resolver state

### Wave 3 — Internal DNS Authority Quality

Goal:

- make the DNS authority itself predictable and complete

Tasks:

1. ensure A records for short names and FQDNs
2. ensure PTR records for the OCI private addresses
3. explicitly keep reserve aliases separate if needed:
   - `atius-srv-1-wg`
   - `atius-srv-2-wg`
   - `atius-srv-3-wg`
   - `horistic-srv-wg`
4. remove any accidental canonical answer that points to reserve IP first

Done when:

- `dig` and `getent` agree on OCI-private canonical answers

### Wave 4 — Windows And Mobile Clients

Goal:

- validate whether W11 and S23 can move from reserve `wg100` to direct DRG

Tasks:

1. prove TCP reachability from W11 to:
   - `10.11.1.11:6432`
   - `10.11.1.11:27124`
2. if direct DRG works:
   - move Windows `fleet-db.env`
   - move Windows resolver target
3. if direct DRG does not work:
   - keep explicit reserve exception in docs and inventory

Done when:

- Windows either uses DRG directly or is clearly documented as the only reserve-path exception

### Wave 5 — Cloudflare Governance

Goal:

- keep public DNS clean and separate from internal host discovery

Tasks:

1. document public records that belong in Cloudflare
2. ban internal machine names from Cloudflare source-of-truth role
3. prefer API-driven inventory/audit of public records
4. define naming policy:
   - public service names in Cloudflare
   - machine names in internal DNS

Done when:

- `docs/CLOUDFLARE.md` and internal DNS manual no longer blur public/public-private responsibilities

### Wave 6 — Drift Detection And Automation

Goal:

- make regressions noisy

Tasks:

1. add a DNS drift check that flags:
   - resolver still pointing to `10.1.1.2`
   - primary service endpoint still pointing to `10.100.100.x`
2. add host validation commands to a reusable skill
3. record the fix path in Obsidian and GBrain

Done when:

- a future session can re-run the same checks without rediscovering the model

## Verification Matrix

### Internal DNS

```bash
dig +short @10.11.1.11 atius-srv-1 A
dig +short @10.11.1.11 atius-srv-2 A
dig +short @10.11.1.11 atius-srv-3 A
dig +short @10.11.1.11 horistic-srv A
```

### Service Reachability

```bash
nc -vz 10.11.1.11 6432
curl -k https://10.11.1.11:27124/
curl -k https://10.13.1.13:8202/v1/sys/health
curl http://10.21.1.21:3115/v1/models
```

### Repo Contract

```bash
pytest cli/omni/tests/test_fleet_pki.py -q
pytest modules/fleet-control-plane/tests/test_m004_contract.py -q -k "not offline_validation_harness"
```

## Risks

- `srv-1` is both the canonical resolver and a reserve-path bind host, so stale watchdog scripts can undo changes
- W11 may remain off-DRG longer than Linux peers
- FreeIPA/internal zone ownership needs to stay compatible with the `atius.internal` naming model

## Finish Criteria

- Linux resolvers prefer `10.11.1.11`
- short hostnames resolve to OCI private IPs everywhere
- public Cloudflare zone is clearly separated from internal host naming
- `wg100` appears only as reserve path
- repo, Obsidian, and GBrain all tell the same story
