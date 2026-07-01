# FreeIPA Foundation and Host Prep

**Date:** 2026-06-25  
**Scope:** Phase 33 host prep for FreeIPA foundation, before any live launch.

## Decision

Do not install FreeIPA directly on any of the four Ubuntu hosts.

Use an isolated container/VM path for FreeIPA because all current hosts already own important ports or workloads:

| Host | Preflight result | Risk |
|---|---|---|
| `atius-srv-1` | Apache owns `80/443`; root disk `87%`; systemd-resolved owns local DNS | Bad target for FreeIPA direct host install |
| `atius-srv-2` | Apache owns `80/443`; CoreDNS owns `10.1.1.2:53`; root disk `87%` | DNS conflict with current fleet resolver |
| `atius-srv-3` | LXD owns public proxy `80/443`; LXD dnsmasq owns bridge DNS; root disk `65%` | Best infrastructure host, but FreeIPA needs isolated IP/port plan |
| `horistic-srv` | Apache owns `80/443`; Docker/LXC present; root disk `38%` used | Possible fallback, but not ideal for Atius domain core |

Recommended target path:

1. `atius-srv-3` as infrastructure host.
2. FreeIPA in a dedicated LXD container or VM, not on the host namespace.
3. Dedicated internal FQDN, for example `ipa.atius.internal` or `ipa.atius.com.br`, chosen before install.
4. Dedicated reachable IP plan for LDAP/Kerberos/DNS. Do not bind over existing SRV3 Landscape ports.
5. CoreDNS/WireGuard integration after FreeIPA is stable, not before.

## FreeIPA Requirements That Matter Here

FreeIPA/Kerberos depends on:

- Static hostname.
- Fully qualified hostname.
- Hostname resolvable forward and reverse before install.
- Working time sync.
- DNS design that is correct before client enrollment.
- Sufficient memory. FreeIPA upstream quick start says at least 1.2 GB with CA and recommends 2 GB for test/demo.
- Ports for LDAP/Kerberos/HTTP(S)/DNS/NTP depending on enabled features.

## Port Classes

| Purpose | Ports |
|---|---|
| DNS | TCP/UDP `53` |
| Kerberos | TCP/UDP `88`, TCP/UDP `464` |
| LDAP | TCP `389` |
| LDAPS | TCP `636` |
| Web UI / enrollment | TCP `80`, TCP `443` |
| NTP if IPA manages it | UDP `123` |

## Live Preflight Evidence

Read-only preflight on 2026-06-25:

- All four hosts have NTP synchronized.
- All four hosts have about 24 GB RAM.
- SRV1/SRV2 root disks are high at `87%`.
- SRV3 root disk is acceptable at `65%`.
- Horistic root disk is acceptable at `38%`.
- SRV1/SRV2/Horistic Apache owns public `80/443`.
- SRV3 LXD owns public `80/443` for the Landscape proxy path.
- SRV2 CoreDNS owns `10.1.1.2:53`.
- SRV3 LXD dnsmasq owns `10.65.172.1:53` and bridge IPv6 DNS.

## Required Gate Before Launch

Do not run `ipa-server-install`, pull a FreeIPA image or publish any FreeIPA port until these are decided:

1. FQDN: `ipa.atius.internal` vs `ipa.atius.com.br`.
2. Realm: likely `ATIUS.COM.BR`, but must be confirmed.
3. FreeIPA network model: LXD routed IP, VM IP, K3s LoadBalancer or dedicated host.
4. DNS authority model: FreeIPA authoritative zone vs CoreDNS forwarding.
5. Backup target for `/data` or VM disk.
6. Admin secret handling path, root-only and never in repo/docs/chat.
7. Rollback path for DNS/client enrollment.

## Candidate Launch Pattern

For the next gated plan, prefer:

- Build/deploy a FreeIPA container from the official FreeIPA container project or a distro package path inside an AlmaLinux/RHEL-family container/VM.
- Persist server data on a dedicated volume.
- Keep initial access private over WireGuard/VPN.
- Do not expose FreeIPA web UI to the public internet.
- Integrate clients one at a time after a successful read-only smoke.

## Live Bootstrap Baseline

Applied on 2026-06-25 after explicit operator continuation.

| Item | Value |
|---|---|
| Host | `atius-srv-3` |
| Engine | rootful Podman |
| Container | `freeipa-atius` |
| Image | `docker.io/freeipa/freeipa-server:almalinux-9` |
| FQDN | `ipa.atius.internal` |
| Domain | `atius.internal` |
| Realm | `ATIUS.INTERNAL` |
| Podman network | `freeipa-atius-net` |
| Container IP | `10.89.53.10` |
| Persistent data | `/srv/freeipa-atius/data` |
| Secret file | `/root/freeipa-atius/bootstrap.env` root-only; do not copy to docs or chat |
| Initial backup | `/root/freeipa-atius/backups/freeipa-atius-bootstrap-20260625T203235Z.tgz` root-only |
| Systemd unit | `/etc/systemd/system/container-freeipa-atius.service` |

No FreeIPA ports were published on SRV3 public interfaces. Access is private to the host/Podman network until Phase 34 defines DNS/routing/client enrollment.

Smoke result:

- `ipactl status`: Directory Service, KDC, kadmin, named, httpd, custodia, pki-tomcatd, ipa-otpd and ipa-dnskeysyncd running.
- `https://ipa.atius.internal/ipa/ui/` from inside the container returned `200`.
- `dig ipa.atius.internal @127.0.0.1` returned `10.89.53.10`.
- `kinit admin` succeeded for `admin@ATIUS.INTERNAL`.

## References

- FreeIPA Quick Start Guide: `https://www.freeipa.org/page/Quick_Start_Guide`
- FreeIPA Docker/container guidance: `https://www.freeipa.org/page/Docker`
- FreeIPA container project: `https://github.com/freeipa/freeipa-container`
