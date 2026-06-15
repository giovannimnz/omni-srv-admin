# fleet-network-watchdog

Idempotent network sanity check + Tailscale DNS hijack recovery for the ATIUS fleet (SRV-1, SRV-2, SRV-3).

## What it does

1. Detects infrastructure: tailscale, systemd-resolved, xrdp, WireGuard peer
2. Disables Tailscale `--accept-dns` (which otherwise hijacks `/etc/resolv.conf` to point to `100.100.100.100`, breaking DNS if your tailnet has no global DNS config)
3. Sets `tailscale --operator=<user>` (so future `tailscale set` calls don't need sudo)
4. If systemd-resolved is present:
   - Ensures `DNSStubListener=yes` (Ubuntu default = no, breaks 127.0.0.53:53 binding)
   - Rewrites `/etc/resolv.conf` to `127.0.0.53` (stub) + WireGuard peer + `1.1.1.1` (Cloudflare fallback)
   - Restarts `systemd-resolved` only if DNSStub changed
5. xrdp key read check:
   - If snakeoil cert: ensures xrdp user is in `ssl-cert` group (Ubuntu default)
   - If custom cert: ensures xrdp user is in the right group OR key is readable
6. Verifies DNS resolution works (`getent hosts google.com`)

## System support matrix

| Host | systemd-resolved | Strategy | Timer |
|---|---|---|---|
| SRV-1 (10.1.1.1) | ✓ present | full fix: DNSStub + rewrite + restart | active (2min+10min) |
| SRV-2 (10.1.1.2) | ✗ absent (BIND/dnsmasq local) | tailscale disable + xrdp perm only | not installed |
| SRV-3 (10.1.1.7) | ✓ present | full fix: DNSStub + rewrite + restart | active (2min+10min) |

## Install per host

### Hosts with systemd-resolved (SRV-1, SRV-3)

```bash
sudo cp modules/fleet-network-watchdog/fleet-network-watchdog.sh /home/ubuntu/scripts/
sudo cp modules/fleet-network-watchdog/srv1-fix-network.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now srv1-fix-network.timer
```

### Hosts without systemd-resolved (SRV-2)

```bash
sudo cp modules/fleet-network-watchdog/fleet-network-watchdog.sh /home/ubuntu/scripts/
# no timer needed — DNS is handled by local BIND/dnsmasq
```

## Run manually

```bash
sudo bash /home/ubuntu/scripts/fleet-network-watchdog.sh           # full cycle
sudo bash /home/ubuntu/scripts/fleet-network-watchdog.sh --no-restart  # skip restart
```

## Idempotency

Safe to run N times. Converges to a working state. Skips steps that are already correct.

## Files in this module

- `fleet-network-watchdog.sh` — the main script (deploy to `/home/ubuntu/scripts/`)
- `srv1-fix-network.sh` — original SRV-1-only version (kept for compatibility)
- `srv1-fix-network.service` — oneshot service (deploy to `/etc/systemd/system/`)
- `srv1-fix-network.timer` — periodic timer (deploy to `/etc/systemd/system/`)
- `README.md` — this file

The unit files keep the `srv1-fix-network.*` name to avoid breaking existing installations
on SRV-1. New hosts can use the same name without conflict.

## See also

- `61-Incidents/2026-06-15-srv1-xrdp-dns-hermes-blackout.md` (Obsidian vault)
- `61-Incidents/2026-06-15-fleet-tailscale-dns-recovery.md` (Obsidian vault)
- `60-LOGS/Sessoes/2026-06-15-fleet-tailscale-dns-recovery.md` (Obsidian vault)

## Background

On 2026-06-15, after SRV-1 reboot, the tailnet had MagicDNS enabled globally but no
`dns.config.nameservers` set in the tailnet admin panel. Result: `tailscale --accept-dns=true`
caused `/etc/resolv.conf` to point at `100.100.100.100`, which returned SERVFAIL for
every query. WireGuard (10.1.1.x) doesn't depend on DNS, which masked the issue.

The same bug existed on SRV-3 (latent — would have manifested on next reboot). SRV-2
uses a different DNS stack and is more resilient.
