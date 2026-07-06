---
phase: 34
plan: 34-02
status: complete
completed: 2026-06-26T07:35:00-03:00
requirements:
  - DOM-03
  - DOM-04
key-files:
  created:
    - .planning/phases/34-freeipa-dns-and-client-enrollment/34-CONTEXT.md
    - .planning/phases/34-freeipa-dns-and-client-enrollment/34-02-PLAN.md
  modified:
    - docs/domain/freeipa-dns-client-enrollment.md
    - .planning/phases/34-freeipa-dns-and-client-enrollment/34-VERIFICATION.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
metrics:
  coredns_forwarding: passed
  freeipa_gateway: passed
  srv3_real_enrollment: passed
  sudo_smoke: passed
  horistic_enrollment: deferred
---

# Summary: 34-02 WireGuard/CoreDNS Forwarding and First Real Host Enrollment

## Outcome

34-02 passed and closes Phase 34.

The FreeIPA server remains private inside Podman on `atius-srv-3`, but it is
now reachable to the fleet through the WireGuard/CoreDNS path:

- CoreDNS on `atius-srv-2` forwards only the `atius.internal` zone to
  `10.1.1.3`
- `atius-srv-3` exposes FreeIPA privately on the WireGuard IP `10.1.1.3`
  through a dedicated local gateway service
- the first real enrolled Linux host is `atius-srv-3`

`horistic-srv` remains intentionally deferred and is not part of the automatic
FreeIPA enrollment flow. Enroll it only after an explicit operator request.

## Evidence

| Check | Result |
|---|---|
| CoreDNS `atius.internal` forwarding | PASS |
| `ipa.atius.internal` via CoreDNS on `10.1.1.2` | PASS, returned `10.1.1.3` from `srv3` and `horistic-srv` |
| `_ldap._tcp.atius.internal` via CoreDNS | PASS |
| Private FreeIPA gateway service on `srv3` | PASS, `atius-freeipa-wireguard-gateway.service` active |
| `https://ipa.atius.internal/ipa/ui/` from `srv3` and `horistic-srv` | PASS |
| `ipa-client-install` on `atius-srv-3` | PASS |
| `kinit admin` and `ipa ping` on enrolled `srv3` | PASS |
| `getent passwd admin` and `id admin` on enrolled `srv3` | PASS |
| `sudo -l -U admin` on enrolled `srv3` | PASS |

## Backups and Rollback Anchors

| Item | Path |
|---|---|
| CoreDNS backup | `/home/ubuntu/GitHub/vpn-atius/coredns/backups-freeipa-34-02-20260626T102212Z/` on `atius-srv-2` |
| SRV3 host backup | `/root/freeipa-34-02-20260626T102212Z/` on `atius-srv-3` |
| FreeIPA gateway service | `/etc/systemd/system/atius-freeipa-wireguard-gateway.service` on `atius-srv-3` |
| FreeIPA gateway script | `/usr/local/sbin/atius-freeipa-wireguard-gateway.sh` on `atius-srv-3` |

## Residual Notes

- FreeIPA DNS for `atius-srv-3.atius.internal` now holds both `10.1.1.3` and
  the legacy compatibility alias `10.1.1.7`.
- Reverse PTR entries for `10.1.1.3` and `10.1.1.7` were corrected on
  2026-07-06 through the CoreDNS reverse zone on `atius-srv-2`; both now return
  `atius-srv-3.atius.internal.`.
- `horistic-srv` was not enrolled and must stay out of the FreeIPA enrollment
  flow unless the operator explicitly starts a manual enrollment later.

## Scope Control

No public FreeIPA exposure was introduced.

No Cloudflare record, Apache public vhost, or public ingress rule was created
for FreeIPA.
