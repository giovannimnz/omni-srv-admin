---
phase: 34
status: passed
verified: 2026-06-26T07:35:00-03:00
requirements:
  - DOM-03
  - DOM-04
---

# Verification: Phase 34 FreeIPA DNS and Client Enrollment

## Automated / Operational Checks

| Must-have | Result | Evidence |
|---|---|---|
| Disposable client can resolve `ipa.atius.internal` through FreeIPA DNS | PASS | `dig +short ipa.atius.internal @10.89.53.10` returned `10.89.53.10` in `34-01` |
| Disposable Linux client can enroll to `ATIUS.INTERNAL` | PASS | `ipa-client-install` exited successfully in `freeipa-client-test` in `34-01` |
| Disposable client can authenticate and reach FreeIPA API | PASS | `kinit admin` and `ipa ping` succeeded in `34-01` |
| WireGuard/CoreDNS production forwarding works | PASS | CoreDNS on `10.1.1.2` now forwards `atius.internal` to `10.1.1.3` |
| `ipa.atius.internal` is reachable privately to WireGuard clients | PASS | `srv3` and `horistic-srv` resolved `ipa.atius.internal` as `10.1.1.3` and reached `https://ipa.atius.internal/ipa/ui/` |
| First real Linux host enrollment over WireGuard works | PASS | `ipa-client-install` succeeded on `atius-srv-3` as `atius-srv-3.atius.internal` |
| Basic FreeIPA group/sudo behavior works on a real host | PASS | `getent passwd admin`, `id admin`, and `sudo -l -U admin` succeeded on enrolled `srv3` |
| DNS rollback documented | PASS | `docs/domain/freeipa-dns-client-enrollment.md` |
| Client rollback documented | PASS | `docs/domain/freeipa-dns-client-enrollment.md` |

## Status

`34-01` plus `34-02` together satisfy Phase 34.

The phase now has:

1. FreeIPA reachable over the WireGuard/CoreDNS path
2. scoped CoreDNS forwarding for `atius.internal`
3. reversible `srv3` private gateway state and backups
4. first real Linux host enrollment on `atius-srv-3`
5. group/sudo smoke on the enrolled host

## Human Verification

No human GUI verification was required for `34-02`.

Operator approval for the real-host pilot was explicitly provided:

- real `34-02` execution approved
- first pilot host: `atius-srv-3`
- `horistic-srv` deferred until after the `srv3` pilot
