# Phase 53 Research Debate

**Date:** 2026-07-22
**Mode:** three-round, independent, read-only
**Scope:** runtime, public edge, operations API and recovery
**Final result:** `unresolved_blocker_count=0`

## Participants

- Runtime researcher: rootless Quadlets, identity, cgroups, logs, boot and rollback.
- Edge researcher: DNS, host/OCI ingress, external TCP/UDP proof and containment.
- Orchestrator: operational API, contract interpretation and cross-surface integration.

No participant mutated Vault, DNS, OCI, firewall, Apache, packages, services or clients.

## Round 1 — Arguments

### Runtime

The pinned RustDesk OSS `1.1.15` source always derives websocket listeners at
`port + 2`: `hbbs` opens TCP `21118`, and `hbbr` opens TCP `21119`. With the
approved `Network=host`, these sockets are visible locally. The live Horistic
preflight otherwise passed Podman rootless/cgroup-v2 prerequisites, but found
`Linger=no`, which must be changed transactionally and proved over a real boot.

### Edge

The edge must be DNS-last and fail-closed. UFW is currently inactive, so a
root-owned ATIUS nftables scope is required. OCI enforcement must evaluate the
union of all Security Lists and attached NSGs; a dedicated narrow NSG is not
sufficient if another attachment broadly permits the same ports. UDP `21116`
requires nonce/counter/capture/socket-owner correlation from two external
origins rather than interpreting `open|filtered` as proof.

### Operations API

The API must remain separate from RustDesk Pro semantics: Apache HTTPS on
`rustdesk-ops.atius.com.br`, backend on loopback or Unix socket, versioned
read-only endpoints, backend authentication and redaction, and no TCP `21114`
or client `API Server` field. Its new backend belongs in the Phase 53 aggregate
resource/log budget; the pre-existing Apache process is regression measured.

## Round 2 — Replies

Both independent researchers initially classified local `21118/21119` versus
the minimal port contract as a planning blocker. They rejected two apparent
workarounds:

- rootless bridge plus selected `PublishPort` would violate the approved
  `Network=host` contract;
- a custom RustDesk build would violate the official immutable digest and
  no-host-build supply-chain contract.

They agreed that firewall and OCI can prevent public exposure even though
`ss` still shows the upstream sockets. They also converged on:

- an exact local listener delta with container/digest ownership;
- explicit forbidden-public rules for TCP `21114/21118/21119` in IPv4/IPv6;
- DNS A-only, `proxied=false`, no AAAA;
- a parent slice covering `hbbs`, `hbbr` and the ops backend;
- conditional linger rollback and Apache/k3s/legacy regressions.

## Round 3 — Rejoinders

The orchestrator challenged the blocker classification using the governing
text: the Phase Boundary says “publishes only”, `SRV-03` says “expõe somente”,
and D-05/D-06 define the native-edge allowlist. That language regulates public
reachability; it does not require removing documented, unavoidable upstream
sockets from the host.

Both researchers accepted this layered reading without a context amendment.
The normalized contract is:

```yaml
local_runtime_required:
  hbbs: {tcp: [21115, 21116, 21118], udp: [21116]}
  hbbr: {tcp: [21117, 21119]}
local_runtime_forbidden:
  tcp: [21114]
  unexpected_delta: any_socket_outside_pinned_upstream_set
public_ipv4_allowed:
  tcp: [21115, 21116, 21117]
  udp: [21116]
public_forbidden:
  tcp: [21114, 21118, 21119]
  ipv6: all_rustdesk_ports
```

The final resource recommendation is:

| Service | CPU | RAM |
|---|---:|---:|
| `hbbs` | `35%` | `448 MiB` |
| `hbbr` | `35%` | `384 MiB` |
| ops backend | `10%` | `192 MiB` |
| aggregate | `80%` | `1 GiB` |

## Converged gates

1. Exact local socket set and ownership.
2. Effective nftables plus OCI public allowlist.
3. Two-source TCP positives and forbidden-port negatives.
4. Correlated UDP `21116` proof.
5. DNS-only A created last, with no AAAA.
6. Authenticated/redacted operational API and no TCP `21114`.
7. Three restarts, one reboot and terminal rollback.
8. Server/client domains and all legacy recovery paths preserved.

No secret values were read or written into this artifact.
