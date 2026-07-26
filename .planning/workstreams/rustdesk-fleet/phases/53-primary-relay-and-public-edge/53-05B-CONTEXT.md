# Phase 53 Plan 05B — Production-bound live adapter closure

**Gathered:** 2026-07-23

**Status:** Ready for planning
**Scope:** gap closure for the blocked Plan 53-05; no runtime mutation is
authorized by this context alone.

## Boundary

This unit closes the remaining implementation gap between the hermetic
53-05A runner seam and a production-bound Plan 53-05 transaction. It evaluates
RustDesk Server `1.1.16`, refreshes supply/capacity/currentness, validates the
client `1.4.9` compatibility matrix without installing a client, implements
real provider adapters, and proves pre-state/rollback, external edge probes,
and the separate Atius operations API. The only production placement that may
be mutated after all gates is `horistic-srv`; `atius-srv-2` then `atius-srv-3`
then `horistic-srv` remains the read-only capacity-finalize order.

Included probe scope is `GIOVANNI-W11-PC` (private-first, public-native
fallback evidence when required) plus one genuinely independent external
origin. `WSL` and `GIOVANNI-S23` are excluded. No cleanup, client install,
Phase 48 edit, Phase 52 freeze rewrite, or fallback retirement is permitted.

## Locked decisions for this closure

- **D-05B-01 — Explicit live admission:** a live provider factory and every
  mutating stage require both `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1` and
  `ADMITTED_PHASE53=1`, the current Git HEAD and contract digests, fresh
  pre-state, unambiguous ownership, and rollback readiness. A stale or replayed
  receipt never authorizes a write.
- **D-05B-02 — Provenance state machine:** an unsigned upstream `1.1.16` tag
  is `UNSIGNED`/`OWNER_EXCEPTION_PENDING` until either a new owner-bound
  exception records the exact candidate hashes and vulnerability disposition,
  or a signed rebuild reaches `SIGNED_REBUILD_VERIFIED`. Only then, and after
  compatibility, supply and capacity gates, can it become `ADMITTED`. The
  frozen `1.1.15` contract is not silently substituted.
- **D-05B-03 — Fresh placement chain:** fresh official supply and read-only
  capacity samples run in the exact order `atius-srv-2` → `atius-srv-3` →
  `horistic-srv`, including `capacity_finalize`, two samples, backup/log/image
  reservations and recovery/security inputs. `srv-2` and `srv-3` remain
  zero-cleanup; a failed predecessor is persisted before the next attempt.
- **D-05B-04 — Client compatibility without installation:** the candidate is
  checked against the pinned RustDesk client `1.4.9` Linux ARM64 and Windows
  x86-64 artifacts, native ports, public-key/fingerprint continuity and the
  client `API Server` prohibition. The matrix is value-free and does not
  install or contact the clients.
- **D-05B-05 — Real, explicit adapters:** production adapters for Vault
  hydration, Horistic/Atius SSH, OCI ingress, Cloudflare DNS, Apache/ops API,
  and external probes are concrete and bounded. They are selected only from
  an explicit provider manifest/configuration; ambient `PATH`, SSH aliases,
  credentials, or unreviewed shell commands are never inferred. Tests inject
  fakes through the existing seam.
- **D-05B-06 — Transaction and evidence safety:** pre-state is captured before
  mutation; CAS/ownership checks prevent blind overwrite; failures contain
  first and restore exact owned state or reach an explicit terminal blocked
  state. Receipts and parity artifacts contain digests/metadata only, never
  secrets, raw probe payloads, or stored `PASS` verdicts.
- **D-05B-07 — External proof and API separation:** IP probes precede DNS-last
  publication, then hostname probes repeat the positive/negative TCP contract
  and correlated UDP proof from both origins. The HTTPS ops API remains
  separate from RustDesk native semantics, backend-authenticated, redacted,
  and must not open TCP `21114` or configure a client API server.
- **D-05B-08 — Resource and fleet boundary:** all CPU-heavy validation and
  live orchestration run through the `builds` governor (20% total host CPU;
  `CPUQuota=80%` on the four-vCPU runner). Only `srv1-3`, Horistic and W11
  appear in evidence; WSL/S23 and future client/rollout phases remain absent.

## Converged review result

The argument/repllica/treplica review rounds converge on the same blockers:
the 53-05A adapter seam is correct but intentionally refuses a missing
production backend; the 1.1.16 tag has no verified signature; Phase 52
observations are outside the current admission TTL/source binding; and a
successful live transaction must bind fresh capacity-finalize, compatibility,
pre-state, rollback and two-origin probes before DNS or ops HTTPS is touched.
No review round authorizes fabricated evidence, a 1.1.15 downgrade, cleanup,
or a live retry that seeks a different PASS after a functional probe failure.

## Existing contracts that remain locked

The prior Phase 53 decisions D-01–D-15 remain in force. In particular,
rootless digest-pinned Quadlets, the `0.8 CPU`/`1 GiB` aggregate limit, the
minimal public ports, DNS-only native hostname, Vault-only identity, legacy
fallback preservation, no standby claim, and the separate authenticated ops
API are prerequisites rather than choices reopened by this gap closure.

## Deferred and excluded

Client installation/canary proof, WSL/S23 access, serialized client rollout,
full direct/relay matrix, standby/failover, and Phase 48 changes remain in
their roadmap phases and must not appear as implementation tasks here.

*Phase: 53-primary-relay-and-public-edge*

*Context: 53-05B*
