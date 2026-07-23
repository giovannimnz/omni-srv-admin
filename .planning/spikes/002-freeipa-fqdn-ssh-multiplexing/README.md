---
spike: 002
name: freeipa-fqdn-ssh-multiplexing
type: standard
validates: "Canonical *.atius.internal owner-host execution can reach a 13-15 ms warm target through encrypted persistent SSH with fail-closed host-key trust"
verdict: PARTIAL
related: [48]
tags: [wayland, ssh, freeipa, drg, latency]
---

# Spike 002: FreeIPA FQDN SSH Multiplexing

## What This Validates

This spike tests whether the four lowercase FreeIPA-domain FQDNs are the right
canonical identities for Wayland owner-host execution and whether OpenSSH
multiplexing, rather than removal of encryption, is the path to roughly
13-15 ms warm command startup.

## Research

- OpenSSH `ControlMaster` shares multiple sessions over one network
  connection, while `ControlPersist` keeps the master available after the
  initiating session exits. `ControlPath` should include `%C` or user/host/port
  and live in a directory not writable by other users.
- FreeIPA can store user and host SSH public keys. DNS resolution and host-key
  trust remain distinct: an A record proves routing intent, not machine
  identity.
- SSSD 2.10 introduced `sss_ssh_knownhosts` for `KnownHostsCommand`; the live
  srv-3 client is SSSD 2.9.4 and still uses the distro-installed
  `sss_ssh_knownhostsproxy` integration.
- `VerifyHostKeyDNS=yes` is not an automatic trust shortcut unless SSHFP is
  validated securely through DNSSEC.

Primary references:

- https://man.openbsd.org/ssh_config
- https://freeipa.readthedocs.io/en/ipa-4-12/workshop/10-ssh-key-management.html
- https://sssd.io/release-notes/sssd-2.10.0.html
- https://sssd.io/release-notes/sssd-2.11.0.html

## Investigation Trail

- The canonical resolver `10.11.1.11` and Windows default resolution returned:

  | FQDN | OCI/DRG address |
  |---|---|
  | `atius-srv-1.atius.internal` | `10.11.1.11` |
  | `atius-srv-2.atius.internal` | `10.12.1.12` |
  | `atius-srv-3.atius.internal` | `10.13.1.13` |
  | `horistic-srv.atius.internal` | `10.21.1.21` |

- On srv-3, `getent ahostsv4` returned the same four OCI addresses. Effective
  `ssh -G` retained `ControlMaster=false`, `ControlPersist=no`,
  `GSSAPIAuthentication=yes`, `IdentitiesOnly=no`,
  `StrictHostKeyChecking=ask`, and
  `ProxyCommand=/usr/bin/sss_ssh_knownhostsproxy -p %p %h`.
- The effective user on srv-3 was `ubuntu` for every FQDN. That is correct for
  srv-1 through srv-3 and wrong for Horistic, whose owner is `horistic`.
- On Windows, raw FQDNs inherited local user `muniz`, no multiplexing, no
  single-identity restriction and no FQDN entries in `known_hosts`.
- A strict, non-mutating multiplexing attempt from srv-3 to srv-1, srv-2 and
  Horistic stopped before authentication with `Host key verification failed`.
  No key was accepted and no `known_hosts` file changed.
- The FreeIPA client on srv-3 is degraded: its enrolled identity is
  `atius-srv-3.atius.internal`, but `hostname -f` returns only `atius-srv-3` and
  the system resolver cannot currently resolve `ipa.atius.internal` even
  though a direct query to `10.11.1.11` returns `10.13.1.13`.
- Prior controlled direct-DRG measurements opened a master in 158-159 ms and
  then executed warm `true` commands in 14-18 ms. ChaCha20-Poly1305 and
  AES128-GCM both produced 13-14 ms samples. The artifact does not contain
  enough samples for honest mean/p50/p95 calculation.

## Results

Verdict: PARTIAL.

The FQDNs are the correct canonical identities and already route to OCI/DRG.
Encrypted multiplexing is also the correct performance mechanism. The live
fleet is not ready to activate those aliases because fail-closed host-key trust
fails, Horistic needs an explicit user, Windows FQDN aliases are absent, and
the srv-3 FreeIPA client/resolver is degraded.

The 13-15 ms warm range is plausible but not yet a demonstrated fleet average.
It must be treated as a stretch p50 target until a controlled sample set reports
mean and tail latency across all owner hosts.

Implementation prerequisites for the plan:

1. Repair `ipa.atius.internal` resolution and the srv-3 enrolled FQDN without
   weakening resolver fallback.
2. Enroll or reconcile every host record and publish/verify its SSH host keys
   in FreeIPA/SSSD; create trusted Windows FQDN entries through a verified
   channel rather than TOFU.
3. Add exact per-host users plus shared encrypted multiplexing settings,
   `IdentitiesOnly=yes`, a single managed identity, strict host-key checking,
   and a private control-socket directory.
4. Prewarm, check, reconnect and expire masters explicitly; fail closed if DNS
   leaves the OCI address set or host-key lookup fails.
5. Measure cold, warm no-op, interactive shell and real owner command with at
   least 30 samples per host and publish mean/p50/p95/p99 plus failures.

Do not set `ProxyCommand none` merely to reduce cold latency. The live SSSD
2.9.4 integration must remain until equivalent host-key verification is proven.
