# Podman networking standard — ATIUS fleet (SRV-1/2/3)

> Canonical one-page spec. Source of truth for `containers.conf`,
> `containers.conf.d/`, network `srv<N>-podman`, `systemd-resolved`,
> PATH, and `podman-compose` conventions. **Read this first.**
>
> Owner: omni-srv-admin
> Version: 1.0.0 (2026-06-16)
> Skill: `~/.hermes/skills/devops/podman-fleet-standardize/`

## Files per server (N ∈ {1, 2, 3})

### `~/.config/containers/containers.conf`

```ini
[network]
default_network = "srv<N>-podman"
default_subnet  = "10.10.<N>.0/24"
```

### `~/.config/containers/containers.conf.d/99-netavark.conf`

```ini
[network]
network_backend = "netavark"
```

### `~/.profile` (snipped to `templates/profile-path-fix.snippet`)

```bash
# Ensure ~/.local/bin is on PATH for non-interactive shells
case "$-" in
    *i*) ;;
    *) export PATH="$HOME/.local/bin:$PATH";;
esac
```

## Network `srv<N>-podman` (default, auto-created)

| Attribute       | Value                | Why                                  |
|-----------------|----------------------|--------------------------------------|
| driver          | bridge               | rootless-friendly                    |
| dns_enabled     | **true**             | aardvark-dns comes up                |
| subnet          | 10.10.<N>.0/24       | one /24 per server, easy to remember |
| gateway         | 10.10.<N>.1          | aardvark binds here                  |
| ipv6_enabled    | false                | IPv4 only (no IPv6 stack in SRV fleet) |
| internal        | false                | containers need internet for pulls   |

If `dns_enabled=false` (e.g. legacy CNI network), recreate via
`scripts/apply-standardize.sh` (handles the `default network cannot
be removed` workaround).

## Pre-flight: `systemd-resolved` must be installed

Required for both aardvark-dns to work (forwarder) and podman
rootless netns to set up (`/run/systemd/resolve/` must exist for the
bind-mount). Without it, no container can start.

```bash
sudo apt-get install -y systemd-resolved
sudo systemctl enable --now systemd-resolved
```

## `podman-compose` location

| Source | Path | Version | Status |
|--------|------|---------|--------|
| pip --user (preferred) | `~/.local/bin/podman-compose` | 1.6.0 | standard |
| apt fallback | `/usr/bin/podman-compose` | 1.0.6 | functional, divergence from standard |

Reinstall with:

```bash
sudo -n rm -f /usr/local/bin/podman-compose
pip install --user --break-system-packages --force-reinstall \
  podman-compose python-dotenv
```

## Custom multi-container networks (e.g. `atius`)

For stacks with 3+ services, use the `ip-static-hosts-fallback` pattern:

- Network: `podman network create --subnet 10.89.<X>.0/24 \
  --gateway 10.89.<X>.1 atius`
- Per-service: `networks.atius.ipv4_address: 10.89.<X>.Y`
- Per-service: `extra_hosts: [ "name:10.89.<X>.Z", ... ]` for every
  cross-reference

Allocations:
- `.2-.5` for stateful infra (db, redis, mq, minio)
- `.10-.19` for stateless frontends (web, space, admin, live)
- `.20-.29` for backend services (api, worker, beat, migrator)
- `.30-.39` for proxies and ingress

## Drift detection

```bash
./scripts/drift-detect.sh
```

Output: 7-point check per server (default_network, default_subnet,
99-netavark.conf, podman backend, srv<N>-podman state, systemd-resolved,
podman-compose). Any FAIL = apply the standard.

## Known bugs (workarounds documented)

- **aardvark 1.4.0 self-lookup NXDOMAIN** — see
  `references/aardvark-rootless-bug.md`. Mitigated by
  `systemd-resolved` + IP-static pattern.
- **podman 4.9.3 aardvark external forward TIMEOUT** — same file.
  Mitigated by `systemd-resolved` (uses the host's resolv.conf as
  forwarder automatically).
- **CNI legada em `/etc/cni/net.d/`** — coexistence with netavark is
  supported (podman ignores CNI when backend=netavark). Do not remove
  until you confirm no container is using it.
- **wrapper `~/.local/bin/podman` injeta `--cpus 2`** in
  `volume create` / `network create` (flag inválida). Workaround:
  use `/usr/bin/podman` directly for those two subcommands.
