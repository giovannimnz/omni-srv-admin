---
phase: 33-freeipa-foundation-and-host-prep
plan: 02
status: complete
completed_at: 2026-06-25
requirements_addressed:
  - DOM-02
---

# Phase 33 / Plan 33-02 — Summary

FreeIPA foundation was launched privately on `atius-srv-3` using rootful Podman.

## Live baseline

| Item | Value |
|---|---|
| Container | `freeipa-atius` |
| Image | `docker.io/freeipa/freeipa-server:almalinux-9` |
| FQDN | `ipa.atius.internal` |
| Domain | `atius.internal` |
| Realm | `ATIUS.INTERNAL` |
| Container IP | `10.89.53.10` |
| Data | `/srv/freeipa-atius/data` |
| Secrets | `/root/freeipa-atius/bootstrap.env` root-only |
| Backup | `/root/freeipa-atius/backups/freeipa-atius-bootstrap-20260625T203235Z.tgz` root-only |
| Systemd unit | `container-freeipa-atius.service` enabled |

No host public ports were published.

## Smoke evidence

- `ipactl status` reported all IPA services running.
- HTTPS UI returned `200` inside the container.
- DNS resolved `ipa.atius.internal` to `10.89.53.10`.
- Kerberos `kinit admin` succeeded for `admin@ATIUS.INTERNAL`.

## Follow-up

Proceed to Phase 34 for controlled DNS coexistence and client enrollment. Do not enroll fleet hosts until DNS forwarding/routing and rollback are documented.

