# Phase 53: Primary Relay and Public Edge - Research

**Researched:** 2026-07-22
**Workstream:** `rustdesk-fleet`
**Primary:** `horistic-srv`
**Requirements:** `SRV-02`, `SRV-03`, `SRV-04`, `SRV-06`, `OPS-01`
**Status:** Ready for planning
**Unresolved blockers:** 0
**Authority update (2026-07-25):** public native values `21115-21117`
and the single-hostname edge described in the historical research below are
superseded by CONTEXT D-05/D-06. Current external authority is
`34099/TCP`, `34100/TCP+UDP`, `34101/TCP` across the three DNS-only A records
`rustdesk.atius.com.br`, `rustdesk-id.atius.com.br` and
`rustdesk-relay.atius.com.br`; internal native listeners remain unchanged.
Downstream execution must use `53-CONTEXT.md`, `REQUIREMENTS.md` and, after
53-05D, `modules/rustdesk-fleet/contracts/phase53-edge.json`.

## Executive result

Phase 53 is implementable with the official RustDesk Server OSS `1.1.15`
ARM64 image already pinned by Phase 52. The primary must run `hbbs` and
`hbbr` as rootless Podman Quadlets on `horistic-srv`, while root-owned host
firewall, OCI ingress, Apache HTTPS and boot-linger changes remain separate,
transactional scopes.

The three-round independent review converged on one important normalization:
the pinned upstream opens local TCP `21118` and `21119` even when the web
client is not published. The phase contract regulates the public native edge,
not the existence of those expected upstream sockets. The plans must therefore
prove both the exact local socket set and a narrower externally reachable set.

## Sources and verified facts

### Official upstream

- RustDesk Server OSS `1.1.15` is the current pinned release used by the
  Phase 52 supply-chain contract:
  <https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.15>.
- The official deployment guide requires TCP `21115-21117` and UDP `21116`;
  TCP `21118/21119` are websocket ports that need not be exposed when the web
  client is unused:
  <https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/>.
- In the pinned source, `hbbs` derives NAT TCP as `port - 1` and websocket TCP
  as `port + 2`; `hbbr` derives websocket TCP as `port + 2`:
  <https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/rendezvous_server.rs>
  and
  <https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/relay_server.rs>.
- Podman Quadlet supports rootless user units, `Network=host`, standard
  systemd `[Service]` directives and cgroup-v2 enforcement:
  <https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html>.
- Cloudflare DNS-only records return the origin address and do not proxy the
  non-HTTP RustDesk traffic:
  <https://developers.cloudflare.com/dns/proxy-status/>.
- OCI effective ingress is the union of applicable Security Lists and NSGs; a
  new narrow NSG does not cancel an older broad allow:
  <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm>.

### Live read-only preflight

The live probe used `horistic@10.21.1.21`; the legacy alias that selects user
`ubuntu` is not valid for this operation.

| Fact | Current value |
|---|---|
| Host/arch | `horistic-srv`, `aarch64` |
| Podman | `4.9.3`, rootless, cgroup v2, systemd cgroup manager |
| User manager | running |
| Linger | `no` |
| Root filesystem | 59% used at preflight |
| RustDesk listeners | none on `21114-21119` |
| Current public address | `163.176.232.119` |
| `rustdesk.atius.com.br` | no A/AAAA record |
| Apache | active on TCP 80/443 with existing vhosts |
| Host firewall frontend | UFW installed but inactive; do not rely on it |

`Linger=no` is a boot-gate issue, not a design blocker. The installer must
snapshot it, enable linger transactionally, prove rootless user services start
after a real reboot without interactive login, and disable it on rollback only
when the transaction changed the prior state.

## Normative transport contract

> **Superseded public-edge note (2026-07-25):** this section preserves the
> upstream/local-listener research and the historical public-edge conclusion.
> CONTEXT D-05/D-06 now govern execution: external `34099/34100/34101`,
> three DNS-only hostnames and unchanged internal native listeners. After
> 53-05D, `phase53-edge.json` is the sole machine-readable authority.

### Exact local runtime sockets

The validator must classify these as the only expected socket delta owned by
the pinned containers:

| Process | TCP | UDP | Classification |
|---|---|---|---|
| `hbbs` | `21115`, `21116`, `21118` | `21116` | expected upstream |
| `hbbr` | `21117`, `21119` | none | expected upstream |

- TCP `21114` must have no RustDesk listener.
- Any additional Phase-53-created socket, wrong owner, wrong digest or socket
  outside the expected set is blocking.
- A dual-stack bind does not authorize IPv6 reachability.

### Exact public edge

| Family | Allowed | Forbidden |
|---|---|---|
| IPv4/TCP | `21115-21117` | `21114`, `21118`, `21119`, every other Phase 53 exposure |
| IPv4/UDP | `21116` | every other Phase 53 exposure |
| IPv6 | none | all RustDesk ports |

`21118/21119` are therefore `expected-upstream-nonpublished`: present locally,
absent from every public allowlist and externally `not-open`. This preserves
`Network=host`, the immutable official image and the user-approved minimal
public surface.

## Runtime architecture

### Paths and isolation

Use an explicit server domain that a future Horistic client cannot share:

- Quadlets: `~/.config/containers/systemd/atius-rustdesk-server-*.container`
- Persistent non-secret state:
  `~/.local/share/atius-rustdesk/server/state`
- Runtime identity hydration:
  `/run/user/<uid>/atius-rustdesk/server-identity`
- Bounded logs: `~/.local/state/atius-rustdesk/server/logs`
- Transaction rollback:
  `~/.local/share/atius-rustdesk/server/rollback/<transaction-id>`

The private server identity is hydrated from the approved Vault reference into
tmpfs through the bounded provider. No private key, password or reusable token
may appear in argv, environment dumps, evidence, journal output or docs. Only
the public fingerprint and value-free metadata are durable evidence.

Quadlets must use the immutable ARM64 reference from
`modules/rustdesk-fleet/contracts/supply-chain.json`, `Pull=never`,
`Network=host`, read-only rootfs where compatible, `NoNewPrivileges=true`,
`DropCapability=all`, bounded PIDs and explicit writable mounts only.

### Resource budget

Apply the safer aggregate interpretation: all new Phase 53 backend processes
fit in one parent slice capped at `CPUQuota=80%` and `MemoryMax=1G`.

| Service | CPU ceiling | RAM ceiling |
|---|---:|---:|
| `hbbs` | `35%` | `448 MiB` |
| `hbbr` | `35%` | `384 MiB` |
| ops API backend | `10%` | `192 MiB` |
| aggregate | `80%` | `1024 MiB` |

The server pair remains at `70%` and `832 MiB`, inside `SRV-02`. Apache is a
pre-existing shared service outside the slice, but its resource and restart
delta must be measured during API probes. Validate declared and effective
limits through generated units, `podman inspect`, `systemctl show`, `cpu.max`
and `memory.max`.

Logs across the new Phase 53 services share the approved `128 MiB/day`,
30-day, approximately 4 GiB reserve. RustDesk internal files and container
stderr can duplicate output; plans must choose one bounded authoritative log
path and prove actual rotation/size rather than relying only on global
journald settings.

## Edge and publication transaction

> **Superseded transaction constants (2026-07-25):** steps below mentioning one
> hostname or public native `21115-21117` are historical research, not current
> executor inputs. Apply/probe tooling must derive the three-hostname translated
> edge from CONTEXT D-05/D-06, REQUIREMENTS and `phase53-edge.json` after 05D.

The order is fail-closed and must not be reordered:

1. Revalidate Phase 52 `11/11 PASS`, selected Horistic, image digest, public
   fingerprint, capacity and retained backups.
2. Require equality among OCI VNIC public IPv4, Horistic egress IPv4 and the A
   record of `ssh-horistic-srv.atius.com.br`. A mismatch blocks before writes.
3. Snapshot DNS record-set, OCI VNIC/NSG/Security Lists, nft/iptables/UFW,
   listeners, Apache, linger and legacy-access smokes.
4. Install/start server and ops backend while public ingress remains closed.
5. Install a root-owned ATIUS nftables table/chain atomically after `nft -c`.
   Never flush the global ruleset or edit k3s/CNI-owned chains.
6. Audit the effective union of OCI Security Lists and all attached NSGs, then
   apply the exact dedicated ingress. Any broad pre-existing allow that covers
   forbidden ports is blocking.
7. Probe by public IP from Windows and a second independent source.
8. Create one DNS-only A record
   `rustdesk.atius.com.br -> <revalidated Horistic IPv4>` with
   `proxied=false`; create no AAAA or concurrent CNAME.
9. Repeat positive/negative probes by hostname through independent resolvers.
10. Run legacy regressions, restart/boot gates and only then promote evidence.

The root-owned firewall policy needs an ownership marker and contract digest.
Quadlets should refuse readiness when the root-owned edge-policy proof is
missing. The plan must preserve k3s, RustGuac, XRDP, AnyDesk, NoMachine and
noVNC before and after every edge transition.

## External proof

Use `GIOVANNI-W11-PC` over private SSH first, with a second public-origin host.
For TCP, both origins prove `21115-21117` reachable and
`21114/21118/21119` not-open by IP and hostname.

An isolated UDP scan reporting `open|filtered` is insufficient. For each
origin, correlate a disposable non-secret nonce sent to UDP `21116` with:

- nft rule counter delta;
- metadata-only capture tuple/timestamp, without persisted payload;
- socket ownership by the pinned `hbbs` container;
- distinct attempt/timestamp evidence.

This proves network delivery to the server socket. A real RustDesk handshake
and session remain Phase 54.

## ATIUS operational API

`rustdesk-ops.atius.com.br` is a separate authenticated HTTPS service. Reuse
the existing Apache 443 edge and proxy to a backend bound only to loopback or
a private Unix socket. Do not configure the RustDesk client `API Server` field
and do not open TCP `21114`.

Expose only versioned read-only endpoints:

- `GET /v1/health`
- `GET /v1/readiness`
- `GET /v1/status`
- `GET /v1/metrics/summary`

Health is process-local. Readiness is derived from the exact current digest,
socket ownership, public fingerprint continuity, edge policy, resource caps,
disk/log bounds and bounded restart counters. Direct/relay byte counters are
observability inputs only and cannot claim transport until Phases 54/56
correlate client UI/log evidence and relay deltas.

Authentication must be enforced by the backend even when Apache also protects
the route. Unauthorized/missing/malformed credentials return a uniform denial.
No bearer value, password, key, client ID, request authorization header or
reusable material may enter access logs or API responses.

Before Apache reload, require `apachectl configtest`; after reload, probe all
existing vhosts. Rollback removes only the Phase 53 vhost/backend and restores
the exact prior Apache state.

## Restart, boot and rollback gates

Capture a baseline, then perform three controlled restarts and one real host
reboot. Each cycle must preserve:

- public fingerprint and hydrated identity provenance;
- SQLite integrity and state digest;
- exact local socket and public-edge contracts;
- effective cgroup limits;
- bounded logs/disk growth;
- API readiness and authentication;
- legacy access paths.

Rollback triggers include address mismatch, DNS proxy/AAAA/concurrent record,
effective OCI broad allow, nft enforcement loss, extra socket, forbidden port
reachability, UDP correlation failure, fingerprint/data drift, resource/log
breach, API redaction/auth failure or legacy regression.

Rollback ordering is containment first:

1. close/restore OCI and host ingress;
2. remove the newly created A record or restore the prior record-set;
3. stop/remove only Phase 53 server and API domains;
4. restore Apache, nft/OCI attachments and linger conditionally;
5. prove RustDesk public ports closed and all fallbacks intact.

Do not delete retained Phase 52 backups and do not touch future client paths.

## Candidate implementation artifacts

The planner should decompose around these cohesive surfaces:

- `modules/rustdesk-fleet/contracts/phase53-runtime.json` — normalized socket,
  resource, path, log and identity contract.
- `modules/rustdesk-fleet/contracts/phase53-edge.json` — DNS, nft, OCI,
  IPv4/IPv6 and external-probe contract.
- `modules/rustdesk-fleet/contracts/phase53-ops-api.json` — endpoint,
  authentication, redaction and readiness schema.
- `modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container`
  and `atius-rustdesk-server-hbbr.container`.
- `modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice` and bounded
  server/API/log units.
- `modules/rustdesk-fleet/tools/install-phase53-server.py` — transaction,
  pre-state, hydration, linger, Quadlet and rollback orchestration.
- `modules/rustdesk-fleet/tools/apply-phase53-edge.py` — root-owned nft/OCI/DNS
  orchestration with exact rollback manifest.
- `modules/rustdesk-fleet/tools/rustdesk-ops-api.py` — small read-only backend.
- `modules/rustdesk-fleet/tools/validate_phase53.py` — stored-verdict-free
  validator and report renderer.
- `modules/rustdesk-fleet/tests/test_phase53_primary_edge.py` — contract,
  fault-injection, redaction and evidence tests.
- `modules/rustdesk-fleet/evidence/phase53/` — redacted immutable projections.

Reuse bounded execution, identity hydration, SQLite normalization, listener
inspection and mutation accounting from `phase52_recovery.py` and
`phase52-horistic-live-drill.py`; do not fork those rules informally.

## Validation Architecture

### Fast contract layer

Run hermetic tests before any live change. They must cover:

- exact schema and no-extra-field validation;
- digest/arch/rootless/Quadlet and generated-unit assertions;
- aggregate and child resource math;
- local versus public socket classification;
- nft/OCI effective-policy fixtures, including broad-allow union failures;
- DNS A/proxy/AAAA/concurrent-record negatives;
- API auth/redaction/readiness and secret scanners;
- transactional failure at every mutation step with idempotent rollback;
- decision/requirement coverage and Phase 48 no-drift.

All broad tests run through `omni srv1-ops resources run builds -- ...`.

### Live gated layer

| Requirement | Required live proof |
|---|---|
| `SRV-02` | rootless pinned Quadlets, exact writable mounts/caps, parent and child cgroup readback |
| `SRV-03` | exact local socket owners plus forbidden public ports not-open in IPv4/IPv6 |
| `SRV-04` | revalidated public address, DNS-only A, effective OCI+nft and two-source TCP/UDP proof |
| `SRV-06` | fingerprint/SQLite/listener/resource/log invariants over three restarts and one reboot |
| `OPS-01` | HTTPS endpoints, auth negatives, redacted bodies/logs, derived readiness and no TCP 21114 |

### Evidence invariants

Each live artifact records schema version, source HEAD, transaction ID,
timestamps, input digests, selected host, expected/observed result, mutation
classes, rollback state and `secret_material_present=false`. It stores no
payload nonce, auth header, key, password or token. Canonical reports must be
derived from current raw evidence rather than trusting stored PASS fields.

### Advance gate

Phase 54 remains blocked until all five requirements pass, the rollback drill
is terminal, Graphify is fresh after the final commit and independent
verification finds zero unresolved blockers. Installing Windows or the
Horistic client is explicitly outside this phase.

## Recommended plan shape

1. Contracts, RED tests and validation skeleton.
2. Rootless server runtime, identity hydration, resource/log enforcement and
   transactional rollback.
3. Authenticated operational API plus Apache transaction and regression gate.
4. Root-owned nft/OCI edge policy and external probe harness.
5. Closed deploy, public-IP proof, DNS-last publication and hostname proof.
6. Restart/reboot/rollback drill, canonical report, ledger, docs and Graphify.

No design question remains open. Exact nft chain priority, API loopback port
versus Unix socket and certificate issuance mechanics are execution-time
choices that must pass the same pre-state/configtest/rollback gates.
