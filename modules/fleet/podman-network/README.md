# Fleet — podman-network

> Podman networking standard for the ATIUS fleet (SRV-1/2/3).
> Canonical home of the `podman-fleet-standardize` skill.
>
> Owner: omni-srv-admin
> Maintained by: Hermes Agent + Giovanni
> Cross-refs: `~/.hermes/skills/devops/podman-fleet-standardize/`,
>             `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md`,
>             `modules/fleet/podman-network/references/` (deep dives)

## What this module is

The **infra-plane** for every podman-based service on the ATIUS fleet.
Defines the standard config (`containers.conf`, `containers.conf.d/`,
network `srv<N>-podman`, `systemd-resolved` requirement, PATH
conventions, `podman-compose` location) and the drift detection +
correction scripts that enforce it.

This module is **not** the container-migration playbook
(see `../multi-server-podman-migration` from the Hermes skill index
for that). It's the foundation those migrations land on.

## Files

| Path | Purpose |
|------|---------|
| `README.md` | this file |
| `STANDARD.md` | the fleet-wide podman networking standard (one-page canonical spec) |
| `scripts/drift-detect.sh` | run on all 3 servers, output drift table |
| `scripts/apply-standardize.sh` | run on one server to apply the standard (idempotent) |
| `scripts/smoke-test.sh` | validate the standard (aardvark + DNS) on one server |
| `templates/containers.conf.template` | `containers.conf` template (per-server) |
| `templates/99-netavark.conf.template` | `containers.conf.d/99-netavark.conf` template |
| `templates/profile-path-fix.snippet` | `~/.profile` PATH fix for non-interactive shells |
| `references/aardvark-rootless-bug.md` | the aardvark 1.4.0 self-lookup NXDOMAIN bug |
| `references/network-migration.md` | how to migrate systemd services between networks |
| `references/ip-static-hosts-fallback.md` | static-IP + extra_hosts pattern (for multi-container stacks) |

All scripts are also vendored in
`~/.hermes/skills/devops/podman-fleet-standardize/scripts/` so the
Hermes Agent can find them via `skill_view()` without needing the
omni-srv-admin repo cloned.

## Quick start (drift check)

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
./modules/fleet/podman-network/scripts/drift-detect.sh
```

Expected output (CONFORME):

```
default_network          | srv1-podman                  | srv2-podman                  | srv3-podman
default_subnet           | 10.10.1.0/24                 | 10.10.2.0/24                 | 10.10.3.0/24
99-netavark.conf         | netavark                     | netavark                     | netavark
podman info backend      | netavark                     | netavark                     | netavark
srv<N>-podman            | dns: True subnet: 10.10.1... | dns: True subnet: 10.10.2... | dns: True subnet: 10.10.3...
systemd-resolve files    | 3                            | 3                            | 3
systemd-resolved status  | active                       | active                       | active
podman-compose           | podman-compose version 1.6.0 | podman-compose version 1.6.0 | podman-compose version 1.0.6
aardvark-dns PID         | 832467                       | 2541164                      | 2110253
```

Any FAIL line = apply the standard to that server.

## Apply (correction)

```bash
./modules/fleet/podman-network/scripts/apply-standardize.sh 2
./modules/fleet/podman-network/scripts/smoke-test.sh 2
```

The apply script will:
- install `systemd-resolved` if missing
- create `~/.config/containers/containers.conf.d/99-netavark.conf`
- write canonical `containers.conf` (with `default_network` and `default_subnet`)
- recreate `srv<N>-podman` with `dns_enabled=true` (idempotent)
- update `~/.profile` for non-interactive PATH
- reinstall `podman-compose` 1.6.0 in `~/.local/bin/`

The smoke script validates end-to-end: aardvark PID, resolv.conf,
self-lookup, external lookup, ICMP + TCP to gateway.

## Multi-container stacks (custom networks like `atius`)

For stacks with 3+ containers needing stable cross-service DNS, use
the `ip-static-hosts-fallback` pattern (see `references/`):

- Create a network with explicit `--subnet` (e.g. `10.89.1.0/24`)
- Assign each service a static `ipv4_address`
- Inject cross-service hostnames via `extra_hosts` (name → IP)

This works around the aardvark rootless bug for self-lookup and
external resolution. Pattern validated for plane-app v1.3.1 on SRV-1
(2026-06-16).

## Origin

Standard solidified 2026-06-16 during the plane-app v1.2.1 → v1.3.1
cutover on SRV-1 (vault: `60-LOGS/2026-06-16-plane-app-podman-v131-cutover.md`).
Drift detection applied fleet-wide same day
(vault: `60-LOGS/2026-06-16-fleet-podman-network-standardize.md`).
Materialized as a skill on 2026-06-16 21:50 BRT.

## Cross-refs

- Skill: `~/.hermes/skills/devops/podman-fleet-standardize/` (canonical skill index)
- Doc: `../../docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` (topology + ports)
- Vault: `60-LOGS/2026-06-16-fleet-podman-network-standardize.md` (origin)
- Vault: `60-LOGS/2026-06-16-plane-app-podman-v131-cutover.md` (cutover that surfaced the bugs)
- Module: `../fleet/` (this directory's parent, fleet-level orchestration)
- Skill: `multi-server-podman-migration` (uses this standard as foundation)
- Skill: `fork-container-rebrand-podman-migration` (container-plane, lands on this infra)
