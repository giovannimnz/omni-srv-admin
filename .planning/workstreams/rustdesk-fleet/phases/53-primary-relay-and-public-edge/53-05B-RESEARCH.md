# Phase 53 Plan 05B — Research and implementation findings

**Researched:** 2026-07-23  
**Mode:** gap closure; existing repository patterns and Phase 53-05A seam
were inspected, with no new package dependency.

## Current blocker

- `run-phase53-live-gate.py` accepts `edge-probes` and enforces ordered,
  value-free receipts, but its CLI calls `build_live_adapters(...)` without a
  concrete provider bundle. The current factory deliberately raises
  `live-backend-not-configured` when `injected` is absent.
- `server-1.1.16-evaluation.json` records official commit, OCI index/ARM64
  digests and ARM64 ZIP checksum, but the tag signature is unverified,
  `compatibility_tested=false`, and `candidate_status=NOT_ADMITTED`.
- Existing Phase 52 observations are historical inputs only: they must be
  re-read with current TTL/source binding and must not be replayed as an
  authorization token. `horistic-srv` is the only candidate that previously
  passed the complete gate; `atius-srv-2` and `atius-srv-3` remain NO-GO and
  must be evaluated first in the fresh serial chain.
- The hermetic suite already proves the dispatcher alias, receipt schema,
  journal redaction, candidate-admission blocker, and containment callback.
  It does not prove concrete Vault/SSH/OCI/DNS/Apache/probe adapters, the
  provenance transition branches, fresh supply/capacity-finalize, or a
  current ops/API transaction.

## Reusable implementation surfaces

| Surface | Existing seam | 05B requirement |
|---|---|---|
| Runtime/identity | `Phase53ServerTransaction.install_closed()` and `rollback_server()` | Wrap with an explicit bounded host provider and preserve tmpfs identity/pre-state receipts. |
| Host/OCI edge | `EdgeTransaction.execute_edge()`, CAS and semantic rollback | Inject effective nft/OCI snapshots, apply once, read back semantics, contain on drift, and keep DNS last. |
| External probes | `probe-phase53-edge.py` validators and `run_windows_private_first()` | Add production transport execution with W11 private-first/fallback evidence and an independent origin; persist metadata only. |
| Ops API | `ApacheVhostTransaction`, `rustdesk-ops-api.py` | Snapshot exact vhost/backend state, configtest/reload, probe uniform auth negatives and redaction, rollback owned scope. |
| Evidence | `ValueFreeJournal`, strict JSON receipts | Extend with candidate/admission/currentness digests, parity and terminal rollback; reject secrets and stored verdicts. |

## Required state and ordering

The candidate admission state machine must make the unsigned-vs-signed choice
observable without treating either branch as admitted by itself:

`UNSIGNED → OWNER_EXCEPTION_PENDING → OWNER_EXCEPTION_APPROVED → ADMITTED`

or

`UNSIGNED → SIGNED_REBUILD_PENDING → SIGNED_REBUILD_VERIFIED → ADMITTED`.

Any missing signature/owner binding, stale source or contract digest,
compatibility failure, fresh supply mismatch, capacity-finalize failure,
recovery/security failure, or rollback-unready state becomes `BLOCKED` and
prevents the live factory. The state record stores hashes, timestamps,
approval reference and vulnerability disposition only.

Fresh placement evidence must evaluate `atius-srv-2`, then `atius-srv-3`, then
`horistic-srv`; each candidate has two bounded read-only samples and a complete
`capacity_finalize` reconciliation. No cleanup or data reclamation is allowed.
The current Phase 52 backup and restore facts are inputs to revalidation, not
permission to skip the new chain.

## Provider boundary design

Use an explicit production provider bundle in the existing adapter module (or
an adjacent private helper) with typed operations for:

- bounded `ssh -n`/BatchMode calls to the named hosts and the approved Vault
  dispatcher;
- official GitHub/Docker release and manifest retrieval with cache/checksum
  verification;
- OCI VNIC/NSG/security-list read/write and CAS readback;
- Cloudflare DNS record-set snapshot/apply/rollback;
- local installer, Apache vhost and ops API transactions;
- W11 private-first/public-native route probes and independent-origin probes.

The CLI may construct this bundle only after both live flags, admission state,
current source/contracts, pre-state digest and rollback readiness pass. No
secret value or raw command output crosses the adapter-to-receipt boundary.
Hermetic tests inject fake providers and fault each boundary without network,
Vault, DNS, OCI, Apache, SSH or RustDesk calls.

## Live gate invariant

`ADMITTED_PHASE53=1` is a second explicit authorization in addition to
`ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1`. The live command is never run during
hermetic planning/test setup. The only allowed order is:

`fresh admission/currentness → pre-state/rollback → closed runtime + ops
backend → host edge → OCI edge → external IP probes → DNS A (proxied=false)
→ hostname probes → parity/regression report`.

Any failure invokes containment-first rollback and blocks Phase 53/54. A
functional probe failure is recorded and terminates the transaction; the
runner must not retry via another WAN route to manufacture a PASS.

## Validation approach

- Strict unit tests for every provenance transition, source/digest/checksum
  mismatch, stale observation, owner-approval mismatch, compatibility matrix
  row, capacity order/finalize failure, adapter construction and receipt
  redaction.
- Fault-injection tests for runtime, Vault, host nft, OCI CAS/readback, DNS,
  Apache configtest/reload, external probe, and rollback/containment paths.
- Governed full Phase 53 suite, JSON parity and secret scan before a live
  command; live stages remain blocked unless the owner creates current
  `ADMITTED_PHASE53` authority.

## No new dependency

The closure uses Python standard-library code and existing repo tools. No
package-manager install or target build is planned; all CPU-heavy commands use
the repository `builds` governor and preserve the Phase 48/52 frozen artifacts.

*Phase: 53-primary-relay-and-public-edge*  
*Research: 53-05B*
