---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-13
status: read-only-baseline
branch: codex/k3s-portainer-oci-plan
validated_at: 2026-06-13 14:31 BRT
source: ip/route/wg/ping/ss/podman/docker read-only snapshot across SRV-1/SRV-2/SRV-3
---

# Phase 13 Network, VPN, Port and Podman Map

## Result

Read-only baseline captured before starting any K3s, Portainer, firewall, PTP
or OCI network mutation.

- WireGuard `wg0` is active on all three nodes.
- Pings between `10.1.1.1`, `10.1.1.2` and `10.1.1.7` passed with `0%` packet loss from every node.
- K3s candidate ports are not listening yet: TCP `6443`, `2379`, `2380`, `10250`; UDP `8472`.
- Docker is not installed/available on the three hosts in this snapshot.
- Podman rootless is active on SRV-1 and SRV-2; SRV-3 has an empty reserved Podman network.
- PgBouncer remains the Fleet/Future-node DB endpoint: `10.1.1.1:6432`.
- Direct PostgreSQL remains on SRV-1 `8745`; clients from SRV-2/SRV-3 must not use it directly.

This file is a required read-before-change artifact for M005. Any new port,
route, tunnel, K3s CIDR, PTP interface, firewall rule or OCI ingress rule must
be checked against this baseline and the vault reference:

- `30-RECURSOS/atius/port-mapping-fleet-2026-06-13.md`

## Host Identity

| Host | Public IP | OCI private IP | WireGuard IP | WireGuard UDP | OS/kernel | K3s role target |
|---|---:|---:|---:|---:|---|---|
| `ATIUS-SRV-1` | `137.131.190.161` | `10.0.0.38/24` | `10.1.1.1/32` | `51820` | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | server+worker+etcd |
| `ATIUS-SRV-2` | `129.148.47.32` | `10.0.0.197/24` | `10.1.1.2/24` | `51820` | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | server+worker+etcd |
| `ATIUS-SRV-3` | `136.248.126.12` | `10.0.0.154/24` | `10.1.1.7/32` | `44420` | Ubuntu 24.04.4 LTS / `6.17.0-1016-oracle` | server+worker+etcd |

OCI note: the three servers are in different OCI accounts/tenancies. There is
no shared VCN/NSG assumption. Treat `10.0.0.x` as per-account underlay and
`10.1.1.x` as the canonical private node identity for M005.

## VPN Health

| From | To `10.1.1.1` | To `10.1.1.2` | To `10.1.1.7` |
|---|---|---|---|
| SRV-1 | `0%` loss, local | `0%` loss | `0%` loss |
| SRV-2 | `0%` loss | `0%` loss, local | `0%` loss |
| SRV-3 | `0%` loss | `0%` loss | `0%` loss, local |

Current WireGuard topology is not a full mesh:

- SRV-2 has direct peers for SRV-1 and SRV-3.
- SRV-1 has a peer to SRV-2 with `AllowedIPs=10.1.1.0/24`.
- SRV-3 has a peer to SRV-2 with `AllowedIPs=10.1.1.0/24`.

Implication: M005 may bootstrap K3s over canonical `wg0` after gates, but the
requested PTP fallback must be designed as a separate full-mesh fallback plan.
Do not assume WireGuard is already full mesh.

## Reserved/Occupied Network Ranges

| Range | Owner | Notes |
|---|---|---|
| `10.0.0.0/24` | OCI private underlay per account | Same-looking range exists per account; do not assume L2/L3 shared fabric. |
| `10.1.1.0/24` | WireGuard node/admin network | Canonical K3s node identity for M005. |
| `10.10.1.0/24` | SRV-1 rootless Podman `srv1-podman` | Active containers. |
| `10.10.2.0/24` | SRV-2 rootless Podman `srv2-podman` | Active mailcow/new-api containers. |
| `10.10.3.0/24` | SRV-3 rootless Podman `srv3-podman` | Reserved, no active containers. |
| `10.10.200.0/24` | SRV-2 rootless Podman default `podman` | Exists even outside `srv2-podman`. |
| `10.89.0.0/24` | SRV-1 rootless Podman default `podman` | Exists in SRV-1 rootless user namespace. |
| `10.88.0.0/16` | Rootful Podman default on all hosts | No rootful containers running in this snapshot. |

K3s default `cluster-cidr=10.42.0.0/16` and `service-cidr=10.43.0.0/16` do not
collide with the observed Podman or WireGuard ranges. Do not choose K3s/PTP
CIDRs inside `10.0.0.0/24`, `10.1.1.0/24`, `10.10.0.0/16`, `10.88.0.0/16` or
`10.89.0.0/24`.

## SRV-1 Host Ports

Stable TCP listeners observed:

```text
*:80 apache2
*:443 apache2
*:8081 apache2
*:8084 apache2
*:8443 apache2
*:9080 apache2
*:9444 apache2
*:29443 apache2
*:3000 rootlessport
*:3001 rootlessport
*:3300 rootlessport
*:3389 xrdp
*:50000 rootlessport
*:6889 qbittorrent-nox
*:8085 rootlessport
*:8978 rootlessport
*:9090 systemd
0.0.0.0:22 sshd
0.0.0.0:111 rpcbind
0.0.0.0:10000 miniserv.pl
0.0.0.0:25809 electron
0.0.0.0:3015 next-server
0.0.0.0:3050 next-server
0.0.0.0:6080 websockify
0.0.0.0:7070 anydesk
0.0.0.0:8015 node
0.0.0.0:8050 node
0.0.0.0:8099 node
0.0.0.0:8199 node
0.0.0.0:8310 python3
0.0.0.0:8745 postgres
10.1.1.1:6432 pgbouncer
127.0.0.1:6432 pgbouncer
127.0.0.1:13483 electron
127.0.0.1:18080 node
127.0.0.1:3003 next-server
127.0.0.1:5173 MainThread
127.0.0.1:5175 python3
127.0.0.1:631 cupsd
127.0.0.1:8091 python
127.0.0.1:8092 python
127.0.0.1:9222 chromium
127.0.0.1:9230 electron
```

Stable UDP listeners observed:

```text
0.0.0.0:111 rpcbind
0.0.0.0:10000 miniserv.pl
0.0.0.0:50001 anydesk
0.0.0.0:50848 avahi-daemon
0.0.0.0:51820 wireguard
0.0.0.0:5353 avahi-daemon
0.0.0.0:6771 qbittorrent-nox
127.0.0.1:323 chronyd
```

Port implications:

- Apache already owns `80/443`; K3s must keep Traefik and ServiceLB disabled.
- `10.1.1.1:6432` is the DB client endpoint; use PgBouncer.
- `0.0.0.0:8745` is direct PostgreSQL; do not point SRV-2/SRV-3 clients there.
- No K3s listener exists yet on `6443`, `2379`, `2380`, `8472` or `10250`.

## SRV-1 Podman

Rootless networks:

| Network | CIDR | Gateway | Interface |
|---|---:|---:|---|
| `podman` | `10.89.0.0/24` | `10.89.0.1` | `cni-podman1` |
| `srv1-podman` | `10.10.1.0/24` | `10.10.1.1` | `cni-podman2` |

Rootless containers:

| Container | Internal IP | Published ports |
|---|---:|---|
| `9ffed7fe58c8-infra` | `10.10.1.4` | `*:3000-3001->3000-3001/tcp`, `*:3300->3001/tcp` |
| `model-detailed` | `10.10.1.4` | via pod ports |
| `redis` | `10.10.1.4` | via pod ports |
| `postgres` | `10.10.1.4` | via pod ports |
| `router-ai-atius` | `10.10.1.4` | via pod ports |
| `jenkins` | `10.10.1.5` | `*:8085->8080/tcp`, `*:50000->50000/tcp` |
| `cloudbeaver` | `10.10.1.6` | `*:8978->8978/tcp` |

Rootful Podman network `podman` exists at `10.88.0.0/16`, but no rootful
containers are running. Docker CLI/service is absent.

## SRV-2 Host Ports

Stable TCP listeners observed:

```text
*:80 apache2
*:443 apache2
*:110 rootlessport
*:143 rootlessport
*:25 rootlessport
*:3301 rootlessport
*:3307 rootlessport
*:3389 xrdp
*:4190 rootlessport
*:465 rootlessport
*:587 rootlessport
*:8053 coredns
*:8080 rootlessport
*:8443 rootlessport
*:993 rootlessport
*:995 rootlessport
0.0.0.0:22 sshd
0.0.0.0:111 rpcbind
0.0.0.0:139 smbd
0.0.0.0:445 smbd
0.0.0.0:25809 electron
0.0.0.0:5173 MainThread
0.0.0.0:6080 websockify
0.0.0.0:8310 python3
10.1.1.2:53 coredns
127.0.0.1:53 coredns
127.0.0.1:5432 postgres
127.0.0.1:631 cupsd
127.0.0.1:7654 rootlessport
127.0.0.1:18053 electron
127.0.0.1:19991 rootlessport
127.0.0.1:9230 electron
```

Stable UDP listeners observed:

```text
0.0.0.0:111 rpcbind
0.0.0.0:137 nmbd
0.0.0.0:138 nmbd
0.0.0.0:14556 avahi-daemon
0.0.0.0:51820 wireguard
0.0.0.0:5353 avahi-daemon
10.1.1.2:53 coredns
127.0.0.1:53 coredns
```

Podman rootless `slirp4netns` also exposed many high UDP listeners during the
snapshot. They are operationally noisy and may change on restart; recapture
before tightening firewall rules. Observed examples included `11068`, `1642`,
`17613`, `19832`, `21347`, `23076`, `31471`, `35726`, `42708`, `51820`,
`59909`, `64312`, `65245`.

Port implications:

- Apache already owns `80/443`; K3s must keep Traefik and ServiceLB disabled.
- CoreDNS owns host/VPN DNS on `10.1.1.2:53` and `127.0.0.1:53`.
- Mailcow owns public mail ports through Podman rootless.
- No K3s listener exists yet on `6443`, `2379`, `2380`, `8472` or `10250`.

## SRV-2 Podman

Rootless networks:

| Network | CIDR | Gateway | Interface |
|---|---:|---:|---|
| `podman` | `10.10.200.0/24` | `10.10.200.1` | `podman0` |
| `srv2-podman` | `10.10.2.0/24` | `10.10.2.1` | `podman2` |

Rootless containers:

| Container | Internal IP | Published ports |
|---|---:|---|
| `new-api` | `10.10.2.200` | `*:3301->3000/tcp` |
| `mailcowdockerized-nginx-mailcow-1` | `10.10.2.10` | `*:8080->8080/tcp`, `*:8443->8443/tcp` |
| `mailcowdockerized-postfix-mailcow-1` | `10.10.2.253` | `*:25->25/tcp`, `*:465->465/tcp`, `*:587->587/tcp` |
| `mailcowdockerized-dovecot-mailcow-1` | `10.10.2.250` | `*:110->110/tcp`, `*:143->143/tcp`, `*:993->993/tcp`, `*:995->995/tcp`, `*:4190->4190/tcp`, `127.0.0.1:19991->12345/tcp` |
| `mailcowdockerized-mysql-mailcow-1` | `10.10.2.11` | `*:3307->3306/tcp` |
| `mailcowdockerized-redis-mailcow-1` | `10.10.2.249` | `127.0.0.1:7654->6379/tcp` |
| `mailcowdockerized-unbound-mailcow-1` | `10.10.2.254` | none |
| `mailcowdockerized-clamd-mailcow-1` | `10.10.2.3` | none |
| `mailcowdockerized-rspamd-mailcow-1` | `10.10.2.4` | none |
| `mailcowdockerized-php-fpm-mailcow-1` | `10.10.2.5` | none |
| `mailcowdockerized-memcached-mailcow-1` | `10.10.2.6` | none |
| `mailcowdockerized-acme-mailcow-1` | `10.10.2.7` | none |
| `mailcowdockerized-watchdog-mailcow-1` | `10.10.2.8` | none |
| `mailcowdockerized-dockerapi-mailcow-1` | `10.10.2.9` | none |
| `mailcowdockerized-olefy-mailcow-1` | `10.10.2.12` | none |
| `mailcowdockerized-ofelia-mailcow-1` | `10.10.2.13` | none |
| `mailcowdockerized-sogo-mailcow-1` | `10.10.2.248` | none |

Rootful Podman network `podman` exists at `10.88.0.0/16`, but only stopped
legacy rootful containers were observed. `podman network ls` emitted a warning
for `/etc/cni/net.d/atius-shared.conflist`: missing CNI plugin `dnsname`.
Docker CLI/service is absent.

## SRV-3 Host Ports

Stable TCP listeners observed:

```text
*:3389 xrdp
0.0.0.0:22 sshd
0.0.0.0:25 postfix/master
0.0.0.0:111 rpcbind
0.0.0.0:8310 python3
127.0.0.1:631 cupsd
127.0.0.53:53 systemd-resolve
127.0.0.54:53 systemd-resolve
```

Stable UDP listeners observed:

```text
0.0.0.0:111 rpcbind
0.0.0.0:44420 wireguard
0.0.0.0:5353 avahi-daemon
0.0.0.0:55755 avahi-daemon
127.0.0.53:53 systemd-resolve
127.0.0.54:53 systemd-resolve
```

Port implications:

- SRV-3 is the cleanest host for K3s from a port-conflict perspective.
- No Apache listener is active on `80/443`.
- No K3s listener exists yet on `6443`, `2379`, `2380`, `8472` or `10250`.

## SRV-3 Podman

Rootless networks:

| Network | CIDR | Gateway | Interface |
|---|---:|---:|---|
| `srv3-podman` | `10.10.3.0/24` | `10.10.3.1` | `podman0` |

No rootless containers are running. Rootful Podman network `podman` exists at
`10.88.0.0/16`, but no rootful containers are running. Docker CLI/service is
absent.

## K3s Readiness Implications

Before Task 5 of `13-01-PLAN.md`, confirm again:

1. This map and the vault map were refreshed pre-change.
2. OCI snapshots/backups exist in each separate OCI account.
3. Public OCI ingress is closed for `6443`, `2379-2380`, `8472`, `10250`.
4. Host firewall allows K3s ports only between `10.1.1.x` peers on `wg0`.
5. Traefik and ServiceLB remain disabled in K3s config.
6. PTP fallback design does not reuse WireGuard/Podman/K3s CIDRs or active ports.
7. Fleet/PostgreSQL clients use `10.1.1.1:6432` PgBouncer, never SRV-1 `8745` directly.

## PTP Fallback Guardrails

Do not assign PTP ports or CIDRs until `13-02-PLAN.md` has a concrete design
table. The design must avoid:

- existing WireGuard ports `51820/udp` and `44420/udp`;
- Apache/public web ports `80/443/8080/8443/9080/9444/29443`;
- mail ports on SRV-2/SRV-3;
- Podman ranges `10.10.0.0/16`, `10.10.200.0/24`, `10.88.0.0/16`, `10.89.0.0/24`;
- K3s pod/service CIDRs `10.42.0.0/16` and `10.43.0.0/16`;
- public exposure of Kubernetes API/etcd/kubelet/Flannel.

If PTP is Admin/DR only, document it as non-transparent for K3s. If PTP becomes
transparent route fallback, it must preserve reachability to `10.1.1.x` without
changing K3s advertised addresses.
