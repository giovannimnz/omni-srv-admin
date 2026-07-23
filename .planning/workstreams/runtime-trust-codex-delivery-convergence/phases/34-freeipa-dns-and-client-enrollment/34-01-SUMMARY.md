---
phase: 34
plan: 34-01
status: complete
completed: 2026-06-25T17:42:08-03:00
requirements:
  - DOM-03
  - DOM-04
key-files:
  created:
    - docs/domain/freeipa-dns-client-enrollment.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/34-freeipa-dns-and-client-enrollment/34-VERIFICATION.md
  modified:
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
metrics:
  disposable_dns: passed
  disposable_enrollment: passed
  real_host_enrollment: not_attempted
---

# Summary: 34-01 FreeIPA Disposable Client Gate

## Outcome

34-01 passed as a controlled disposable-client gate.

On `atius-srv-3`, a disposable AlmaLinux 9 container named `freeipa-client-test` was started on `freeipa-atius-net` with hostname `client1.atius.internal` and DNS server `10.89.53.10`.

## Evidence

| Check | Result |
|---|---|
| Container start | PASS |
| Package install: `freeipa-client bind-utils krb5-workstation oddjob-mkhomedir` | PASS |
| DNS: `dig +short ipa.atius.internal @10.89.53.10` | PASS, returned `10.89.53.10` |
| Enrollment: `ipa-client-install` to `ATIUS.INTERNAL` | PASS |
| Auth smoke: `kinit admin` and `ipa ping` | PASS |
| Managed host enrollment | NOT ATTEMPTED |

Remote evidence:

- `/root/freeipa-atius/client-test-20260625T204002Z.log` on `atius-srv-3`

The remote log is intentionally not copied into the repo because it may contain sensitive enrollment diagnostics.

## Scope Control

No `atius-srv-*` host or `horistic-srv` was joined to FreeIPA.

No production CoreDNS, WireGuard, host resolver, Apache, Cloudflare, K3s, PM2, RDP, or public FreeIPA exposure change was made.

## Remaining Gap

Phase 34 is not complete yet.

The disposable client proves FreeIPA DNS and enrollment inside the private Podman network. It does not prove WireGuard/CoreDNS fleet forwarding or real-host enrollment. A follow-up `34-02` must cover:

- reachable `ipa.atius.internal` for WireGuard clients;
- scoped CoreDNS forwarding for `atius.internal`;
- reversible SRV3 firewall/NAT or routed-IP design;
- first real Linux host enrollment with rollback;
- FreeIPA groups/sudo smoke.

## Deviations

The original roadmap had one broad Phase 34 plan. Execution was split intentionally because joining real hosts before a disposable enrollment proof would make DNS and login rollback riskier.

## Self-Check

PASSED for 34-01.

GATED for full Phase 34 closeout until 34-02 is planned and executed.
