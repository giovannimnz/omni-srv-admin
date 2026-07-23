# Phase 34: FreeIPA DNS and Client Enrollment - Context

**Gathered:** 2026-06-26
**Status:** Ready for `34-02`
**Mode:** Directed carry-over execution after operator approval

<domain>
## Phase Boundary

Phase 34 is no longer about disposable proof only. `34-02` must connect the
private FreeIPA server on `atius-srv-3` to the WireGuard/CoreDNS fleet path
without exposing FreeIPA publicly, then enroll the first real Linux host with
rollback.

Current approved rollout order:

1. Pilot real-host path on `atius-srv-3`
2. Expand to `horistic-srv` only after the `srv3` pilot is stable

</domain>

<decisions>
## Implementation Decisions

### D-01 | DNS model | CoreDNS forwards `atius.internal` to `10.1.1.3`
FreeIPA remains authoritative for the zone, but WireGuard clients keep using
CoreDNS on `10.1.1.2` as their fleet resolver. CoreDNS should forward only the
`atius.internal` zone to `10.1.1.3`.

### D-02 | Reachability | FreeIPA is published only on the WireGuard IP
FreeIPA must stay private. The container keeps `10.89.53.10`, but the fleet
must reach it through `10.1.1.3` only, using scoped forwarding/NAT for the
FreeIPA ports required by DNS, Kerberos, LDAP and HTTP(S).

### D-03 | Pilot host | First real enrollment is `atius-srv-3`
The first real Linux host join will be the host that already runs the FreeIPA
container. This keeps the blast radius lower than touching `atius-srv-1` first.

### D-04 | Safety | Public internet exposure stays forbidden
No Cloudflare record, Apache public vhost, OCI public ingress, or public port
open is allowed for FreeIPA in this phase.

### D-05 | Validation | `srv3` must prove NSS/group/sudo resolution
The phase is not done after DNS only. The pilot host must resolve the realm,
enroll successfully, and show basic group/sudo integration through SSSD.

</decisions>

<code_context>
## Existing Code / Runtime Insights

- `docs/domain/freeipa-foundation.md` documents the live server baseline:
  `ipa.atius.internal`, realm `ATIUS.INTERNAL`, container IP `10.89.53.10`.
- `docs/domain/freeipa-dns-client-enrollment.md` already documents rollback for
  DNS and client uninstall.
- `inventory/hosts/horistic-srv.yaml` shows `horistic-srv` already uses
  `10.1.1.2` as DNS over `wg0`.
- `resolvectl status` on `atius-srv-3` shows `wg0` also uses `10.1.1.2`.
- CoreDNS runs on `atius-srv-2` from
  `/home/ubuntu/GitHub/vpn-atius/coredns/Corefile`.

</code_context>

<specifics>
## Specific Ideas

- Add a narrow `atius.internal` forwarding block in the CoreDNS config on
  `srv2`, with rollback backup before restart.
- Publish FreeIPA privately on `10.1.1.3` for TCP/UDP 53, 88, 464 and TCP 389,
  636, 80, 443 only.
- Keep the container IP private and avoid public listeners.
- Add/verify DNS records needed for `atius-srv-3.atius.internal`.
- Enroll `atius-srv-3` using the root-only bootstrap path already present on
  the host.
- Capture `getent`, `id`, and `sudo -l -U` evidence for the pilot account path.

</specifics>

<deferred>
## Deferred Ideas

- `horistic-srv` enrollment happens after the `srv3` pilot is verified.
- Samba and Keycloak remain Phase 35 and Phase 36 scope.

</deferred>
