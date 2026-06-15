---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-14
status: fallback-review-complete
branch: docs/m005-gate-review-20260614
mode: read-only-host-network-assessment
---

# Phase 13 PTP / Direct-IP Fallback Review

## Scope

This note is read-only evidence for the remaining M005 fallback gate.

Question answered here:

1. What direct-IP paths already exist today?
2. What breaks if `wg0` is down?
3. Is public-IP fallback viable?
4. Should the cluster move to an API HA endpoint/VIP/LB, or should this gate be waived explicitly?

## Current direct-IP paths observed

### Path A: WireGuard API path in use today

- SRV-2 and SRV-3 both use `server: "https://10.1.1.1:6443"`.
- SRV-1, SRV-2 and SRV-3 all use:
  - `node-ip` on `10.1.1.x`
  - `advertise-address` on `10.1.1.x`
  - `flannel-iface: "wg0"`
- SRV-1 `iptables` currently allows `6443/2379/2380/10250/10257/10259` from:
  - `10.1.1.0/24` on `wg0`
  - `10.42.0.0/16`
  - `lo`
- SRV-1 drops those ports for other sources.

Result: the only validated bootstrap/control-plane path in service today is the WireGuard path to `10.1.1.1:6443`.

### Path B: OCI private-IP path exists at L3, but not as a working K3s fallback

Observed host private IPs:

- SRV-1: `10.0.0.38`
- SRV-2: `10.0.0.197`
- SRV-3: `10.0.0.154`

Observed evidence:

- SRV-1 listens on `*:6443`.
- From SRV-1 itself, `10.0.0.38:6443` opens.
- From SRV-2 and SRV-3, `ip route get 10.0.0.38` resolves via `enp0s6`.
- From SRV-2 and SRV-3, TCP open to `10.0.0.38:6443` fails.
- This matches the SRV-1 firewall posture: K3s control-plane ports are not allowed from the `10.0.0.0/24` side.

Result: the OCI private network is present, but it is not a functioning fallback path for the current K3s API.

### Path C: Public-IP path is not available for K3s API

Observed public IPs:

- SRV-1: `137.131.190.161`
- SRV-2: `129.148.47.32`
- SRV-3: `136.248.126.12`

Observed evidence:

- `6443` is closed on all three public IPs.
- From SRV-1 local checks, `137.131.190.161:6443` is closed.
- From SRV-2 and SRV-3, `137.131.190.161:6443` is also closed.
- SRV-1 `tls-san` includes only:
  - `10.1.1.1`
  - `10.1.1.2`
  - `10.1.1.7`
  - `atius-srv-1`
  - `atius-srv-2`
  - `atius-srv-3`

Result: public-IP fallback is not viable today for both reachability and certificate identity reasons.

## What fails if `wg0` is down

If `wg0` drops on any control-plane node, the cluster loses more than just the join URL.

### Immediate failures

1. SRV-2 and SRV-3 bootstrap/reconnect path to `https://10.1.1.1:6443` fails.
2. Etcd peer traffic breaks in practice because peer listeners are on `10.1.1.x:2379` and `10.1.1.x:2380`.
3. Flannel overlay breaks because `flannel-iface` is pinned to `wg0`.
4. Node advertised addresses remain `10.1.1.x`, so control-plane/node reachability assumptions stay tied to WireGuard.

### Operational consequence

Even if `server:` on SRV-2/SRV-3 were changed tomorrow from `10.1.1.1` to another endpoint, the cluster would still not be WireGuard-independent, because:

- control-plane identity is on `10.1.1.x`
- etcd peer traffic is on `10.1.1.x`
- overlay networking is on `wg0`

Result: this gate is not just an "API endpoint alias" issue. It is a deeper transport dependency issue.

## Viability assessment

### Private-IP fallback to SRV-1 `10.0.0.38`

Current state: not viable.

Why:

- routing exists
- listener exists
- firewall policy blocks the path
- current certificate SAN does not include `10.0.0.38`
- current K3s node identity and overlay still depend on WireGuard anyway

### Public-IP fallback to SRV-1 `137.131.190.161`

Current state: not viable.

Why:

- port `6443` is closed publicly
- certificate SAN does not include the public IP
- exposing K3s API publicly would materially widen attack surface
- it still would not solve the `flannel-iface=wg0` and etcd peer dependency

## Recommended decision for M005

Do **not** implement public-IP fallback.

2026-06-15 user decision: add Tailscale as a second management plane across
SRV-1/SRV-2/SRV-3.

Tailscale closes a narrower M005 fallback gate:

- SSH/admin access;
- Fleet/PgBouncer/debugging path;
- emergency access if WireGuard is unavailable.

It does **not** make K3s independent from WireGuard in M005.

## Tailscale evidence - 2026-06-15

Observed self IPs:

| Host | Tailscale IPv4 | Status |
|---|---|---|
| SRV-1 | `100.76.56.62` | online |
| SRV-2 | `100.93.43.113` | online |
| SRV-3 | `100.72.102.57` | online |

Bidirectional `tailscale ping` checks passed:

- SRV-1 -> SRV-2 and SRV-3
- SRV-2 -> SRV-1 and SRV-3
- SRV-3 -> SRV-1 and SRV-2

Remaining gate item:

- record/review ACLs to ensure only Giovanni/admin identity plus the 3 nodes can
  use the management fallback.

Minimum ACL intent for M005:

- source identities: Giovanni/admin operator identity only, plus the three
  tagged server nodes when node-to-node access is required;
- destination nodes: SRV-1, SRV-2, SRV-3 Tailscale IPs only;
- allowed ports: `22/tcp`, `6432/tcp` when PgBouncer checks are explicitly
  needed, and narrowly scoped Fleet diagnostics;
- excluded: wildcard `*:*`, broad public/user access, and any use of Tailscale
  as flannel/etcd/K3s transport in this milestone.

Do **not** treat "change `server:` from `10.1.1.1` to a new value" as sufficient closure for the WireGuard-down gate.

For this milestone, the technically honest options are:

1. **Preferred long-term fix:** redesign control-plane transport around an internal HA endpoint on OCI private networking.
2. **Preferred short-term release choice:** validate Tailscale as management fallback and document WireGuard as a required cluster dependency for K3s.

## Precise long-term fix

If the requirement is true control-plane resilience without WireGuard, the next implementation should be:

1. Create an internal OCI VIP or private LB for Kubernetes API on the `10.0.0.0/24` network.
2. Add that VIP/DNS name to K3s server certificate SANs.
3. Allow `6443` from the OCI private subnet to the control-plane nodes.
4. Repoint SRV-2/SRV-3 `server:` to that private HA endpoint.
5. Rework node identity and overlay away from mandatory `wg0` dependence, or accept that only bootstrap becomes HA while east-west cluster traffic still depends on WireGuard.

Important: steps 1-4 alone improve API bootstrap HA, but they do **not** fully satisfy the current "WireGuard down" fallback concern unless step 5 is also addressed.

## Precise waiver text

If M005 needs a release decision now, the recommended waiver is:

> WireGuard is an intentional K3s transport dependency for M005. The current K3s control-plane, etcd peer traffic and flannel overlay are all bound to `10.1.1.x` / `wg0`. Tailscale is accepted as a secondary management-plane fallback for SSH/Fleet/PgBouncer/debugging between SRV-1/SRV-2/SRV-3, but it is not used as the K3s/flannel/etcd transport in this milestone. If WireGuard fails, the accepted recovery path is to use Tailscale for access and restore `wg0` before control-plane restart, rejoin or disaster recovery actions. API HA endpoint/VIP/LB work is deferred to the next infra phase.

## Bottom line

- Existing validated path: `10.1.1.1:6443` over WireGuard only.
- OCI private IP path: present but blocked and not certificate-ready.
- Public IP path: not viable and not recommended.
- Best immediate decision: explicit waiver.
- Best next engineering step: private OCI API VIP/LB, followed by a separate decision on whether the entire cluster should stop depending on `wg0`.
