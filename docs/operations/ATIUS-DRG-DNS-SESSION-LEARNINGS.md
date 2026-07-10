---
scope: session
date: 2026-07-10
counts:
  decisions: 5
  lessons: 5
  patterns: 5
  surprises: 5
sources:
  - 019f42bb-e564-7ca3-87b2-8573f3eb516e
  - docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md
  - docs/operations/drg-wireguard-readdress-plan.md
  - live validation 2026-07-10
---

# DRG / DNS Session Learnings

## Decisions

### OCI Private Plane Is Canonical
The canonical machine-to-machine service plane is now the OCI/DRG private map `10.11.1.11`, `10.12.1.12`, `10.13.1.13`, `10.21.1.21`.

**Rationale:** Live listeners, routes and K3s INTERNAL-IP already exist there.
**Source:** thread `019f42bb-e564-7ca3-87b2-8573f3eb516e`, live validation 2026-07-10

### `wg100` Must Be Reserve Only
`10.100.100.0/24` is not the canonical service plane anymore; it is reserve/fallback only.

**Rationale:** The DRG plane is faster, cheaper, and already carries the primary Linux inter-host paths.
**Source:** user requirement + live validation 2026-07-10

### Cloudflare Owns Public DNS, Not Machine Identity
Cloudflare remains authoritative for `atius.com.br` public records, but it must not be the source of truth for machine hostnames or internal routing.

**Rationale:** Public edge and private host discovery are different systems with different safety and latency requirements.
**Source:** `docs/CLOUDFLARE.md`, `AGENTS.md`

### Inventory Must Prefer `oci_private_ip`
Tooling should prefer `access.oci_private_ip` before `access.vpn_ip`.

**Rationale:** If the repo keeps preferring `vpn_ip`, the old plane keeps being reintroduced indirectly.
**Source:** `cli/omni/fleet.py`, `cli/omni/remote_ops.py`

### `atius.internal` Should Be The Private Naming Contract
Short names like `atius-srv-1` should resolve via an internal zone contract, not via public names or ad-hoc `/etc/hosts` only.

**Rationale:** This is the only durable path to “ping atius-srv-1” working consistently everywhere.
**Source:** current host naming pattern + user objective

## Lessons

### Live Infra Can Be Ahead Of Repo Semantics
Multiple services were already bound on OCI private IPs while docs and helper logic still described `wg100` as primary.

**Context:** PgBouncer, Obsidian REST, Vault and TEI were already live on DRG/OCI paths.
**Source:** live validation 2026-07-10

### Resolver Drift Matters More Than Listener Drift
Even after listeners were corrected, Linux hosts still consumed stale DNS sources like `10.1.1.2` or `10.100.100.1`.

**Context:** Service plane and consumer plane can diverge silently.
**Source:** `resolvectl` / `/etc/resolv.conf` checks on `srv-1`, `srv-2`, `srv-3`, `horistic`

### K3s Migration Was Already Further Than The Docs Said
The cluster was already reporting OCI-private INTERNAL-IP for all Linux nodes, while repo notes still described wg100 as canonical.

**Context:** The actual cluster status disproved part of the written assumptions.
**Source:** `k3s kubectl get nodes -o wide`

### Windows Must Be Treated As Its Own Validation Surface
Linux-to-Linux DRG success is not enough to declare the whole fleet canonical.

**Context:** W11 still lacked proven direct DRG reachability in this pass.
**Source:** local W11 probing attempts + inventory exception handling

### Obsidian/GBrain Closeout Prevents Re-Discovery Work
The most reusable part of the session was not one code patch but the captured contract of what is primary, what is reserve, and what is still drifting.

**Context:** Without durable notes, future sessions would repeat the same topology audit.
**Source:** vault/GBrain logging in this session

## Patterns

### Prefer Live Validation Over Repo Narratives
Check listeners, routes, resolver state, and node INTERNAL-IP before trusting repo docs.

**When to use:** Any IP-plane, DNS, or cross-host service migration.
**Source:** live validation 2026-07-10

### Split Public DNS And Internal DNS By Responsibility
Use Cloudflare for public `atius.com.br` edge records and an internal resolver for machine names.

**When to use:** Any fleet with both public services and private service mesh requirements.
**Source:** `docs/CLOUDFLARE.md`, session design outcome

### Use Inventory As Generator Input
Drive internal DNS, PKI SANs, and service endpoint docs from `inventory/hosts/*.yaml`.

**When to use:** Any place where host identity, naming, and endpoint addresses must stay aligned.
**Source:** `cli/omni/fleet.py`, inventory updates in this session

### Dual-Bind Then Demote
Keep reserve listeners during transition, move consumers first, then demote the reserve plane in docs and tooling.

**When to use:** Zero-downtime service-plane migrations.
**Source:** PgBouncer / Obsidian / Vault / TEI migration pattern in this session

### Record Exceptions Explicitly
Keep exceptions like W11 reserve-path use explicit in inventory and docs.

**When to use:** Any incomplete canonicalization where one platform lags the rest.
**Source:** `inventory/hosts/giovanni-w11-pc.yaml`

## Surprises

### `srv-1` Still Consumed `10.1.1.2`
The same host that was serving canonical answers on DRG/OCI was still consuming the retired resolver path.

**Impact:** Canonicalization was incomplete even though outward validation looked strong.
**Source:** `srv-1` `resolvectl` / `resolved.conf` / `/etc/resolv.conf`

### `srv-2` And `srv-3` Were Already Reaching OCI Targets Fine
The Linux peers could already reach PgBouncer, Obsidian, Vault, and TEI over DRG/OCI even while local config drift remained.

**Impact:** The remaining work is more about consumer config and governance than transport availability.
**Source:** remote probes from `srv-1`

### Horistic TEI Was Already Right On OCI While Docs Lagged
The working TEI path had already become `10.21.1.21:3115`, but repo artifacts still repeated `10.100.100.4:3115`.

**Impact:** Tooling that copied docs verbatim would have kept using the reserve path.
**Source:** live listener + inventory comparison

### `gbrain sync --full --no-embed` Is The Reliable Capture Path
Direct `gbrain capture/put` can fail in embedding-dependent environments, but source-vault sync without embed still preserves the note.

**Impact:** Durable note capture stayed available even with embedding provider issues.
**Source:** session note synchronization behavior

### `.planning` Removal Changes Delivery Strategy
The current worktree has `.planning` marked as removed, so a normal GSD phase-plan write would conflict with user-owned repo state.

**Impact:** Session planning had to be delivered as phase-style docs under `docs/operations/` instead of recreating `.planning/`.
**Source:** current worktree state
