# Aardvark-dns rootless bug (podman 4.9.3 + netavark 1.4.0 + aardvark 1.4.0)

## The bug

On rootless podman with the netavark network backend, aardvark-dns
binds on the bridge gateway IP (e.g. `10.10.1.1:53`) inside its own
netns, but containers in the same network are in a **different netns**
(rootlesskit + slirp4netns). The bridge is shared (`cni-podman2` style),
but the aardvark process is not directly reachable from container
netns.

**Observable symptom (varies by network config):**

| `dns_enabled` in network | aardvark PID | self-lookup from container | external lookup |
|--------------------------|---------------|----------------------------|------------------|
| `false` (default CNI)    | not running   | NXDOMAIN (aardvark not even up) | NXDOMAIN |
| `true` but no systemd-resolved | running | resolves to IP (10.10.X.X) | TIMEOUT (no forwarder) |
| `true` with systemd-resolved active | running | resolves to IP | resolves to real IP (via systemd-resolved stub) |

The "TIMEOUT" row is the dangerous one: container starts, gateway
responds to ICMP, aardvark process exists and has the config, but UDP
queries to `10.10.N.1:53` hang because aardvark has no upstream
forwarder configured. The container appears to work for ping/IP but
fails every DNS-dependent operation (apt update, curl, healthcheck).

## Root cause

`aardvark-dns` is invoked by the netavark-managed network with only
the network's internal name table. It has no concept of upstream
forwarders unless:

1. The network was created with `--dns=IP[,IP]` (e.g. `--dns=1.1.1.1,8.8.8.8`)
2. Or `/etc/resolv.conf` from the host is bind-mounted into aardvark's
   config (the `systemd-resolved` stub at 127.0.0.53:53 typically)

In rootless mode, the host's `/etc/resolv.conf` is NOT bind-mounted.
Aardvark only forwards if option (1) was used at network creation.

## Why the bug bit us on SRV-2

SRV-2's `srv2-podman` was created 2026-06-13 with `dns_enabled=true`
but **no `--dns` flag**. Aardvark started when mailcow was alive but
returned NXDOMAIN for all external queries. This was masked for 45 days
because mailcow only does internal DNS (mysql ↔ php-fpm, dovecot ↔
postfix) — no external resolution needed.

Then a `systemd-resolved` upgrade was attempted, which removed
`/run/systemd/resolve/` (the stub listener at 127.0.0.53:53). All
containers that bind-mount `/run/systemd` (which podman does by
default for the rootless netns) started failing at container create
time with:

```
ERRO[0000] mounting /run/systemd/resolve to /proc/<pid>/ns/... at ...
  mount: mounting systemd-namespace on /proc/<pid>/ns/...: ENOENT
```

This is what caused mailcow to be **Exited for 45h** on SRV-2 — not
the upgrade itself, but the fact that the upgrade killed
`systemd-resolved` permanently on that host.

## Fix: install systemd-resolved (or alternative)

`/run/systemd/resolve/` must be a directory on the host with the
resolver sockets inside. The reliable way to get this is to install
`systemd-resolved` itself:

```bash
sudo apt-get install -y systemd-resolved
sudo systemctl enable --now systemd-resolved
ls -la /run/systemd/resolve/  # must show stub-resolv.conf + io.systemd.Resolve*
```

This satisfies podman's bind-mount requirement AND gives aardvark a
working forwarder (via the host's `/etc/resolv.conf` written by
systemd-resolved).

**Alternative** (lighter): use `systemd-tmpfiles` to create the
directory at boot, but this still needs a forwarder for external
DNS, which aardvark doesn't have without `--dns`. Don't use this
unless you can guarantee the network was created with `--dns=`.

## Validation

After install, the smoke test from `SKILL.md` should show:

```
$ podman exec test-dns nslookup test-dns
Server:    10.10.<N>.1
Address:   10.10.<N>.1:53
Non-authoritative answer:
Name:    test-dns.dns.podman
Address: 10.10.<N>.<X>

$ podman exec test-dns nslookup google.com
Server:    10.10.<N>.1
Address:   10.10.<N>.1:53
Non-authoritative answer:
Name:    google.com
Address: 142.250.<X>.<Y>
```

Both must resolve. If self-lookup works but external doesn't, the
fix was incomplete — check `systemctl is-active systemd-resolved`
and that `/run/systemd/resolve/stub-resolv.conf` exists.

## Why this isn't going to be fixed upstream soon

- Tracked as [containers/podman#22714](https://github.com/containers/podman/issues/22714)
  (aardvark external resolution requires explicit `--dns`)
- Workaround proposed: aardvark auto-detect systemd-resolved
  stub and use it as forwarder. Not yet implemented as of
  aardvark 1.4.0 (2026-05).
- Mitigation in fleet standard: require `systemd-resolved` as a
  pre-flight, document the bind-mount ENOENT symptom prominently.
