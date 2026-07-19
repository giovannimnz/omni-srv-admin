# Phase 48-03: Wayland Owner-Local Transport Convergence - Research

**Researched:** 2026-07-19
**Domain:** Wayland remote development, NFS fallback, encrypted SSH multiplexing
**Confidence:** MEDIUM — the architecture and negative security gates are supported, but fleet latency and parity remain unproven.

## Scope

Define the plan boundary for owner-host execution and active development without removing the existing NFS discovery plane or weakening SSH confidentiality. [VERIFIED: spikes 002-004]

This synthesis covers only Spike 002 (FreeIPA/FQDN/SSH multiplexing), Spike 003 (NFS versus owner-local development), and Spike 004 (plaintext negative gate). [VERIFIED: local spike artifacts]

## Evidence

- The four canonical lowercase `*.atius.internal` names already resolve to their OCI/DRG addresses; Horistic uniquely requires user `horistic`, while srv-1 through srv-3 use `ubuntu`. [VERIFIED: spike 002]
- The live aliases are not activation-ready: strict host-key verification failed, Windows aliases/trust are absent, and srv-3 has degraded FreeIPA/resolver state. [VERIFIED: spike 002]
- A direct encrypted SSH master opened in about 158-159 ms; warm commands were about 14-18 ms, with 13-14 ms samples for both ChaCha20-Poly1305 and AES128-GCM. [VERIFIED: spikes 002, 004]
- The sample set is insufficient for an honest fleet mean or percentile claim, so 13-15 ms is only a stretch warm p50 target. [VERIFIED: spike 002]
- SSH multiplexing reuses transport but does not provide filesystem namespace, locking, caching, project discovery, or folder-picker behavior. [VERIFIED: spike 003]
- NFS automount and owner-local sessions solve different problems; complete NFS removal was invalidated, and observed idle NFS cost did not justify it. [VERIFIED: spike 003]
- Plaintext SSH, patched `none`, HPN NoneSwitch, Telnet, rsh, and raw TCP fail the interactive security/performance gate. [VERIFIED: spike 004]

### Canonical Owner Identity Matrix

The owner contract is explicit even when no network hop is required. In
particular, `mode: local` for srv-3 skips SSH loopback but does not omit its
canonical user, FQDN, address, or workspace. [VERIFIED: fleet inventory and
spikes 002-003]

| Host ID | FQDN | OCI/DRG address | User | Owner workspace | Mode from srv-3 |
|---|---|---|---|---|---|
| `atius-srv-1` | `atius-srv-1.atius.internal` | `10.11.1.11` | `ubuntu` | `/home/ubuntu/GitHub` | `ssh` via `wayland-owner-atius-srv-1` |
| `atius-srv-2` | `atius-srv-2.atius.internal` | `10.12.1.12` | `ubuntu` | `/home/ubuntu/GitHub` | `ssh` via `wayland-owner-atius-srv-2` |
| `atius-srv-3` | `atius-srv-3.atius.internal` | `10.13.1.13` | `ubuntu` | `/home/ubuntu/GitHub` | `local` |
| `horistic-srv` | `horistic-srv.atius.internal` | `10.21.1.21` | `horistic` | `/home/horistic/GitHub` | `ssh` via `wayland-owner-horistic-srv` |

## Target Three-Plane Architecture

```text
Wayland on srv-3
  |-- NFS automount plane
  |     `-- discovery, folder picker, light read/diff, compatibility, fallback
  |-- owner-local session plane
  |     `-- active edit/search/Git/watchers/LSP/test/build/runtime
  `-- encrypted OpenSSH control-master plane
        `-- terminal, one-off commands, reconnect and session bootstrap
```

Keep all three planes distinct: NFS owns namespace/discovery, owner-local owns active development, and persistent OpenSSH owns secure low-latency command transport. [VERIFIED: spikes 002-004]

## WAC-09 / WAC-10 Proposals

> Requirement names are proposals because canonical WAC descriptions were outside the authorized source set.

### WAC-09 — Hybrid Owner-Local Workspace

Wayland SHALL prefer an owner-local remote session for active edit/search/Git/watcher/LSP/test/build/runtime work while retaining `/home/ubuntu/Servers` NFS automounts for discovery, picker, light reads/diffs, compatibility, and fallback. [VERIFIED: spike 003]

Acceptance SHALL require per-host parity, explicit session lifecycle, resource measurements, owner/DRG outage isolation, and per-host rollback before any NFS retirement is considered. [VERIFIED: spike 003]

### WAC-10 — Encrypted Multiplexed Owner Transport

Owner commands SHALL use canonical OCI/DRG FQDNs, exact per-host users, one managed identity, strict fail-closed host-key trust, modern encrypted OpenSSH, and persistent connection/channel reuse. [VERIFIED: spikes 002, 004]

Acceptance SHALL measure at least 30 samples per host for cold setup, warm no-op, interactive shell, and a real owner command, publishing mean/p50/p95/p99 and failures; 13-15 ms remains a stretch warm p50 target until proven. [VERIFIED: spike 002]

## Implementation Tasks

1. Repair `ipa.atius.internal` resolution and srv-3 enrolled-FQDN consistency without weakening resolver fallback. [VERIFIED: spike 002]
2. Reconcile host records and SSH host keys through FreeIPA/SSSD; provision Windows trust through a verified channel, never TOFU. [VERIFIED: spike 002]
3. Define exact FQDN aliases and users, `IdentitiesOnly=yes`, one managed identity, strict checking, and a private control-socket directory using collision-safe `ControlPath` such as `%C`. [VERIFIED: spike 002]
4. Implement master prewarm, health check, reconnect, expiry, stale-session detection, teardown, and bounded failure behavior. [VERIFIED: spikes 002, 003]
5. Add an owner-local session adapter for browse/edit/search/diff/Git/watchers/LSP/terminal/test/build/runtime, without making NFS its active execution path. [VERIFIED: spike 003]
6. Preserve current NFS automounts as discovery and rollback infrastructure; do not remove them for idle-resource savings. [VERIFIED: spike 003]
7. Add per-host feature gating and telemetry so owner-local activation and rollback are independent. [VERIFIED: spike 003]
8. Benchmark the encrypted multiplexed baseline before evaluating any alternative transport. [VERIFIED: spike 004]

## Security and Rollback

- Keep confidentiality, integrity, and authentication mandatory even on private DRG paths; compromised peers, lateral capture, routing mistakes, credentials, and forwarded traffic remain relevant. [VERIFIED: spike 004]
- Fail closed when DNS resolves outside the expected OCI address set, host-key lookup fails, or the pinned identity is unavailable. [VERIFIED: spike 002]
- Do not disable the live SSSD 2.9.4 proxy path until equivalent host-key verification is demonstrated; do not treat unsigned SSHFP as automatic trust. [VERIFIED: spike 002]
- Reject plaintext, `none`, HPN NoneSwitch, Telnet, rsh, and raw TCP for this workflow. [VERIFIED: spike 004]
- Roll back per host by disabling owner-local preference, closing its control master/session, and restoring the existing NFS-read/edit plus owner-execution contract; retain automount definitions throughout rollout. [VERIFIED: spike 003]

## Validation

| Gate | Required proof |
|---|---|
| Identity/routing | Each canonical FQDN resolves only to its expected OCI/DRG address and selects the exact owner user. [VERIFIED: spike 002] |
| Host trust | Known valid keys connect non-interactively; unknown, changed, missing, or misrouted keys fail before authentication and do not mutate trust. [VERIFIED: spike 002] |
| Performance | >=30 samples per host for cold, warm no-op, interactive, and real commands; report mean/p50/p95/p99/failures. [VERIFIED: spike 002] |
| Workspace parity | Project browse/picker/Recent Chats ownership plus edit/search/diff/Git/watcher/LSP behavior operate on the owner filesystem. [VERIFIED: spike 003] |
| Lifecycle | Prewarm, reconnect, stale detection, teardown, expiry, and per-host rollback are deterministic. [VERIFIED: spikes 002, 003] |
| Failure isolation | Owner or DRG loss does not block the Wayland UI; NFS discovery/fallback remains usable where available. [VERIFIED: spike 003] |
| Resources | Measure idle CPU/RSS and concurrency against the fleet budget before enabling always-on sessions broadly. [VERIFIED: spike 003] |
| Negative transport | No plaintext-capable path is accepted; alternatives must beat the encrypted multiplexed baseline and remain reversible. [VERIFIED: spike 004] |

## Unknowns

- Canonical wording and current acceptance criteria for WAC-09 and WAC-10 were not in the authorized source set. [ASSUMED]
- Fleet-wide warm latency distribution is unknown; existing samples do not establish the 13-15 ms target. [VERIFIED: spike 002]
- The complete host-key publication/trust state and exact srv-3 FreeIPA repair procedure remain unresolved. [VERIFIED: spike 002]
- Controlled same-repository NFS-versus-owner-local performance and the acceptable per-session concurrency/resource ceiling remain unmeasured. [VERIFIED: spike 003]
- The concrete Wayland owner-local protocol/API and persistence boundary are not selected by these spikes. [ASSUMED]

## Planning Recommendation

Plan WAC-09 as a reversible hybrid workspace slice and WAC-10 as its encrypted identity/transport prerequisite; gate preferred owner-local activation on trust, parity, lifecycle, resource, outage, and percentile evidence. [VERIFIED: spikes 002-004]

## Sources

- `.planning/spikes/002-freeipa-fqdn-ssh-multiplexing/README.md` — canonical identity, trust, multiplexing, lifecycle, and benchmark requirements.
- `.planning/spikes/003-wayland-nfs-vs-owner-local/README.md` — hybrid three-plane architecture, parity, resources, failure isolation, and rollback.
- `.planning/spikes/004-plaintext-transport-negative-gate/README.md` — encrypted transport boundary and rejected alternatives.
