---
phase: 33-freeipa-foundation-and-host-prep
plan: 01
status: complete
completed_at: 2026-06-25
requirements_addressed:
  - DOM-01
---

# Phase 33 / Plan 33-01 — Summary

Completed read-only FreeIPA host prep and preflight.

Result:

- Direct host install is rejected for the current fleet.
- `atius-srv-3` is the preferred infrastructure host only if FreeIPA gets an isolated container/VM network plan.
- SRV1/SRV2 have high root disk usage and public Apache ownership of `80/443`.
- SRV2 already owns `10.1.1.2:53` through CoreDNS.
- SRV3 already uses LXD/dnsmasq and LXD proxy ports for Landscape.
- Horistic is a fallback, not preferred as Atius domain core.

Artifacts:

- `docs/domain/freeipa-foundation.md`
- `scripts/freeipa-preflight.py`
- `33-02-PLAN.md` as explicit live launch gate

No live install or DNS mutation was performed.

