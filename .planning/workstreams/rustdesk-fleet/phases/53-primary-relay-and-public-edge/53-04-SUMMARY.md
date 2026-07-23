---
phase: 53-primary-relay-and-public-edge
plan: 04
subsystem: edge-dns-probes
tags: [rustdesk, nftables, oci, cloudflare, dns-last, hermetic]
requires:
  - phase: 53-03
    provides: authenticated operations API and loopback-only publication candidate
provides:
  - deny-first host/OCI edge transaction state machine
  - ownership-scoped nftables and boot-order contracts
  - DNS-last transaction and two-origin TCP/UDP probe harness
affects: [53-05, 53-06]
tech-stack:
  added: []
  patterns: [injected fake backends, optimistic CAS, revisioned semantic rollback]
key-files:
  created:
    - modules/rustdesk-fleet/tools/apply-phase53-edge.py
    - modules/rustdesk-fleet/tools/probe-phase53-edge.py
    - modules/rustdesk-fleet/tools/probe-phase53-edge.ps1
    - modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
    - modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service
  modified:
    - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
key-decisions:
  - "Plan 04 is hermetic: provider, network, root nftables and systemd calls are forbidden here."
  - "Only IPv4 TCP 21115-21117 and UDP 21116 are eligible; IPv6 and forbidden listeners fail closed."
  - "Barrier A precedes host/OCI mutation, IP proof precedes Barrier B, and DNS publication is last with semantic CAS rollback."
patterns-established:
  - "External UDP evidence requires per-origin correlation, counter delta and socket ownership; localhost/open-filtered is insufficient."
requirements-completed: []
duration: approximately 5min
completed: 2026-07-23
status: complete
---

# Phase 53 Plan 04: Effective edge policy and DNS-last probe harness

**Complete.** The edge transaction and external-proof harness pass all
hermetic gates. No provider, network, root, systemd, DNS, firewall, listener
or RustDesk live surface was invoked.

## Verification

- Edge policy/OCI/nft/rollback selectors: `75 passed, 94 deselected`.
- DNS/address/Cloudflare/external-probe/UDP selectors: `30 passed, 139 deselected`.
- Full `test_phase53_primary_edge.py`: `167 passed, 2 xfailed`.
- All runs used `omni srv1-ops resources run builds`; `structural_ok=true`,
  effective `CPUQuota=80%` and no escaped build workload.
- `git diff --check` passed for the Phase 53 implementation scope.

## Safety boundary

The implementation is injected-backend only. It enforces effective OCI union
auditing, ownership-scoped nftables, IPv6 deny, address-consensus barriers,
two-origin TCP/UDP correlation, DNS-last ordering and revisioned semantic CAS
rollback. Plan 05 remains the sole owner of controlled live publication.

## Next Phase Readiness

Ready for `53-05-PLAN.md`: controlled live deployment and public TCP/UDP/API
proof. That plan must revalidate current Phase 52 authority, address barriers,
Vault/runtime inputs and rollback state immediately before any mutation.

## Self-Check: PASSED

- All five Plan 04 artifacts exist.
- Hermetic selectors and aggregate suite pass.
- Two expected xfails remain ownership-correct.
- No live mutation occurred.

---
*Phase: 53-primary-relay-and-public-edge*
*Plan: 04*
*Completed on 2026-07-23*
