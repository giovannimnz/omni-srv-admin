# Phase 52: Supply Chain, Capacity and Recoverable Placement - Research

**Researched:** 2026-07-20
**Domain:** RustDesk artifact provenance, byte/inode admission control, Vault-only identity recovery, and isolated restore
**Confidence:** MEDIUM

## Summary

Phase 52 must be planned as a fail-closed authorization pipeline, not as a server deployment. It has four independent gates: immutable artifact provenance (`SCP-04`), exact capacity admission and explicit placement (`SRV-01`), Vault-only secret handling (`SRV-05`), and a real isolated restore that reproduces the public-key fingerprint (`SRV-07`). A PASS requires current machine-readable evidence for all four; a release page, projected capacity, existing backup file, or summary-only statement is insufficient. `[VERIFIED: ROADMAP.md, REQUIREMENTS.md, ledger.json]`

The official release facts are sufficiently concrete for planning. RustDesk Server OSS `1.1.15` is tag `1.1.15` at commit `9bae9f2f39d92c4b4ba2e28e089da5071897b22e`; its official classic Docker image has a current multi-architecture manifest digest `sha256:10818ec05b179039c6660f4d8e74b303f0db2858bbad2b18e24992ea22d54cd6` and Linux ARM64 child digest `sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208`. RustDesk client `1.4.9` is tag `1.4.9` at commit `6c578292e8ebbbec708b76986ba8c4bc7c509747`; the Ubuntu AArch64 DEB SHA-256 is `ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0`, and the Windows x86-64 MSI SHA-256 is `c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa`. These values were verified from official Git refs, GitHub Releases/API, and Docker Hub on 2026-07-20; execution must resolve them again and block rather than silently accepting drift. `[VERIFIED: official GitHub API, git ls-remote, Docker Hub API]`

The current capacity snapshot is a planning warning, not acceptance evidence. At `2026-07-20T08:40Z`, `atius-srv-2` was `173881397248 / 207907635200` bytes used (`83.633964%`, `df` rounded to `84%`) with `11%` inodes used. `atius-srv-3` was `171940089856 / 207907635200` bytes used (`82.700229%`, rounded to `83%`) with `9%` inodes used. Both currently fail the locked `<=78%` pre-gate and are already above the `<=80%` post ceiling. The operator additionally authorized `horistic-srv` as a tertiary recoverable-placement candidate only after `srv-2` and `srv-3` fail; its read-only snapshot at `2026-07-20T08:57:34Z` was `43916230656 / 103859404800` bytes (`42.284308%`) and `5%` inodes. This passes only the raw pre-threshold snapshot: reservations, supply chain, backup/restore, rollback, security, and co-location gates remain unproved, so it is not a placement GO. `[VERIFIED: read-only SSH snapshots; operator authorization 2026-07-20; ROADMAP.md]`

**Primary recommendation:** implement one fail-closed candidate runner whose ordered attempts are `srv-2 -> srv-3 -> horistic-srv`. Every attempt records the complete stage vector `supply -> capacity -> Vault -> backup A/B -> isolated restore -> capacity_finalize -> rollback -> topology/security`; a failing stage persists a current candidate `NO-GO`, marks later unsafe stages as skipped by that exact gate, safely rolls back any disposable drill artifacts already created, and continues to the next authorized candidate. `srv-2` and `srv-3` receive zero cleanup/remediation; after current capacity PASS they may receive only the bounded isolated reversible writes required by the full gate. One integrated Phase 52 report may PASS only for the first candidate whose full vector passes. `[VERIFIED: repo contracts, operator approval 2026-07-22T00:51:46Z, and Phase 51 evidence pattern]`

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Tag/commit/asset/image provenance | Supply-chain control plane | Artifact storage | Resolve only official sources, pin immutable identifiers, and reject mutation. `[VERIFIED: official release and workflow sources]` |
| Capacity admission | Host/storage | Control-plane validator | The filesystem and inode counters are host facts; the validator makes the fail-closed decision. `[VERIFIED: SRV-01]` |
| Placement decision | Operations control plane | Host/storage | `srv-2` is preferred only after its gate; then `srv-3`; only after both fail may fully gated `horistic-srv` be selected. Every fallback is explicit, never runtime auto-promotion. `[VERIFIED: ROADMAP.md, STATE.md, operator authorization]` |
| Secret authority and hydration | HashiCorp Vault | Ephemeral host runtime | Vault owns values; the host receives only short-lived runtime material with metadata-only evidence. `[VERIFIED: AGENTS.md, secret-roles.json]` |
| Persistent RustDesk state | Host storage | Backup storage | `db_v2.sqlite3` and non-secret state persist; the private identity key is rehydrated from Vault. `[VERIFIED: RustDesk Server 1.1.15 source]` |
| Identity recovery | Isolated restore runtime | Vault + backup storage | Restore state, hydrate the same key, start the pinned image without public exposure, and compare the public fingerprint. `[VERIFIED: SRV-07; RustDesk docs/source]` |
| Phase acceptance evidence | Repo evidence ledger | Live validators | Only current JSON/Markdown reports with input digests can advance the workstream. `[VERIFIED: Phase 51 validator pattern]` |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| SCP-04 | Pin server `1.1.15` and clients `1.4.9` by tag, commit, digest/checksum, and architecture; no `latest` or host builds. | Exact official identifiers, verification matrix, mutation stop conditions, and acquisition flow below. `[VERIFIED: REQUIREMENTS.md and official releases]` |
| SRV-01 | Admit `atius-srv-2` only at `<=78%` pre, `<=80%` post, inodes `<=80%`, and enough bytes for image, two backups, and 30 days of logs. | Exact rational comparisons, byte-reservation formula, remeasurement sequence, and explicit `srv-3` then authorized Horistic fallback branches below. `[VERIFIED: REQUIREMENTS.md, operator authorization, and live read-only snapshots]` |
| SRV-05 | Keep server private key and five permanent passwords only in Vault/ephemeral runtime; distribute one public key and persist only fingerprints/hashes. | Approved paths/fields, metadata-only hydration contract, non-output distinctness proof, tmpfs/file-mode controls, and evidence prohibitions below. `[VERIFIED: secret-roles.json, AGENTS.md]` |
| SRV-07 | Execute real backup/restore and preserve the public-key fingerprint before edge or fleet clients. | Quiesced two-backup flow, isolated restore topology, SQLite integrity check, fingerprint comparison, and negative tests below. `[VERIFIED: REQUIREMENTS.md; official RustDesk source/docs]` |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- Use PT-BR operational artifacts, exact paths/evidence, and preserve user changes in the dirty worktree. `[VERIFIED: AGENTS.md]`
- Do not read, print, log, document, or commit secret values. HashiCorp Vault is authoritative; `.env`, shell state, Markdown, Obsidian, GBrain, and repo files are not secret stores. `[VERIFIED: AGENTS.md]`
- Use only the approved RustDesk Vault references: `kv/atius/rustdesk/server` fields `private_key` and `public_key`, plus `kv/atius/rustdesk/targets/<canonical-host-id>` field `permanent_password` for the five included hosts. `[VERIFIED: secret-roles.json and approved 51-OPERATIONAL-REVIEW.md]`
- Helpers that reach Vault by SSH must be stdin-safe; hydration must not leak through argv, stdout, shell history, xtrace, screenshots, or persistent environment. `[VERIFIED: AGENTS.md; Phase 51 security contract]`
- Every build, compile, broad test/index, container build, or other CPU-heavy action must run through the `builds` resource-governor profile and stay at or below 20% total host CPU. On a four-vCPU host, the canonical ceiling is `cpu.max = 80000 100000`. `[VERIFIED: AGENTS.md, resource-governor.env]`
- Never build RustDesk on a target host. Phase 52 may verify, transfer, load, and run already-published pinned artifacts under the resource guard; it must not run `cargo build`, `podman build`, `docker build`, or equivalent. `[VERIFIED: phase boundary supplied by orchestrator]`
- Graphify is mandatory before routing and after changes. It was fresh at commit `e3bc12b` during research; execution must check freshness again after Phase 52 artifacts are committed. `[VERIFIED: Graphify status 2026-07-20]`
- All GSD lifecycle mutations explicitly target `--ws rustdesk-fleet`; shared planning/Graphify writers are serialized and Phase 48 integrity remains a transition gate. `[VERIFIED: scope.json]`
- Browser automation, if any, is headless and preserves evidence. Phase 52 does not require a browser. `[VERIFIED: AGENTS.md]`
- Do not update GBrain or Obsidian during this research/phase-planning step. GBrain was consulted read-only. `[VERIFIED: task boundary]`
- The RustDesk client is **not installed** on `GIOVANNI-W11-PC`. Installation remains mandatory in Phase 54, only after Phase 52 and Phase 53 pass; Phase 52 may verify/stage the MSI but must not claim or perform the client installation. `[VERIFIED: 51-VERIFICATION.md; ROADMAP.md]`
- `horistic-srv` is an authorized tertiary primary candidate only after capacity NO-GO on both `srv-2` and `srv-3`. It receives the same live byte/inode/reservation, supply-chain, Vault, backup/restore, rollback, and security gates; its current favorable pre-threshold does not authorize placement. `[VERIFIED: operator authorization 2026-07-20]`
- If `horistic-srv` is selected, the placement record must set `client_colocation=true` and `phase54_replan_required=true`: the same host is also the mandatory Linux canary target in Phase 54, so server and client evidence, resource accounting, reboot behavior, and rollback domains must remain distinguishable. `[VERIFIED: operator authorization; ROADMAP Phase 54]`

## Standard Stack

### Core

| Component | Version / Pin | Purpose | Why Standard |
|---|---|---|---|
| RustDesk Server OSS classic image | `1.1.15`, Linux ARM64 child digest `sha256:17c3422e...` | Isolated restore now; production `hbbs`/`hbbr` in Phase 53 | Official publisher image; classic image contains the same build-job binaries used for release assets. `[VERIFIED: upstream workflow and Docker Hub]` |
| RustDesk Server ARM64 release ZIP | `1.1.15`, SHA-256 `4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4` | Independent release checksum/binary provenance input | Official release asset for `linux-arm64v8`. `[VERIFIED: GitHub Releases API]` |
| RustDesk Linux client DEB | `1.4.9` AArch64, SHA-256 `ce62c996...` | Pinned artifact for later Linux canary/rollout | Official AArch64 Ubuntu asset; installation is later. `[VERIFIED: GitHub Releases API]` |
| RustDesk Windows client MSI | `1.4.9` x86-64, SHA-256 `c87d2f4c...` | Pinned artifact for Phase 54 Windows canary | Official x86-64 Windows asset; installation remains Phase 54. `[VERIFIED: GitHub Releases API]` |
| Podman rootless | `4.9.3` on `srv-2`/`srv-3`; Horistic wrapper path present, version pending recheck | Load pinned OCI artifact and run isolated restore | Existing repo-native container runtime and user-systemd convention. Horistic cannot receive GO until its effective version/capabilities are verified. `[VERIFIED: read-only SSH audit]` |
| Python standard library | Python `3.12.3` | Deterministic JSON, integer capacity math, SQLite integrity, hashing, validators | Already present; avoids new runtime packages. `[VERIFIED: local and candidate-host probes]` |
| pytest | `7.4.4` | Focused positive/negative contract tests | Existing `modules/rustdesk-fleet/tests` pattern. `[VERIFIED: local probe and Phase 51 validation]` |
| HashiCorp Vault helper | `~/.local/bin/atius-vault-env` present on all three candidates | Approved authentication/bootstrap path for a metadata-only hydration helper | Repo/host policy keeps Vault authoritative. `[VERIFIED: read-only host probe; AGENTS.md]` |
| `sha256sum`, `tar`, `jq`, `curl`, `systemd-run` | Host-provided | Artifact/backup hashing, deterministic archive flow, API parsing, governed execution | Present on all three candidates and avoids extra package installation. `[VERIFIED: read-only host probe]` |

### Supporting

| Component | Purpose | When to Use |
|---|---|---|
| GitHub Releases API + `git ls-remote` | Resolve asset digest and immutable tag commit | At manifest creation and again immediately before acquisition. `[VERIFIED: official API/Git]` |
| Docker Hub tag API / registry manifest | Resolve multiarch and ARM64 platform digests | Before artifact acquisition and at the final supply gate. `[VERIFIED: Docker Hub API]` |
| Python `sqlite3` | `PRAGMA integrity_check` on restored `db_v2.sqlite3` | After quiesced restore, without installing `sqlite3` CLI. `[VERIFIED: Python standard library availability]` |
| `flock` + bounded `timeout` + verify-before-delete | Serialize backup/restore operations | Reuse the repo-native fleet-backup safety pattern, not its broad GDrive scope. `[VERIFIED: modules/fleet-backup]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| Official classic image by ARM64 child digest | Native `hbbs`/`hbbr` DEBs by checksum | Native packages are official, but Phase 53 is locked to rootless digest-pinned Quadlets. `[VERIFIED: Phase 53 ROADMAP]` |
| Vault hydration into runtime tmpfs | Persist private key in the ordinary server data directory | Simpler upstream layout, but violates the locked Vault/runtime-only boundary. `[VERIFIED: SRV-05]` |
| Isolated rootless restore with no published ports | Restore directly into the future primary path | Fewer steps, but cannot prove isolation or distinguish a restore from in-place reuse. `[VERIFIED: SRV-07 advance gate]` |
| Explicit `srv-3` replan after `srv-2` failure | Automatic scheduler/failover | Automation hides capacity/security failure and can create false standby/split-brain claims. `[VERIFIED: ROADMAP.md]` |

**Installation:** no new language package is required. Acquisition uses prebuilt official artifacts only; no target-host build is allowed. `[VERIFIED: environment audit and phase boundary]`

## Package Legitimacy Audit

Not applicable to npm, PyPI, or crates: Phase 52 installs no new ecosystem library. External RustDesk artifacts instead pass the supply-chain matrix below. `[VERIFIED: planned stack]`

## Supply-Chain Verification Matrix

| Artifact | Required tag | Tag commit | Required architecture | Immutable digest/checksum | Execution verification | Stop condition |
|---|---|---|---|---|---|---|
| Server source | `1.1.15` | `9bae9f2f39d92c4b4ba2e28e089da5071897b22e` | Source/N/A | Commit SHA | `git ls-remote --tags` must return exactly the pinned commit. `[VERIFIED: official Git]` | Missing tag, changed commit, or ambiguous ref => `BLOCKED`. |
| Server classic OCI image | `1.1.15` | Bound to server tag by official tag-triggered workflow | `linux/arm64` | child `sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208`; multiarch `sha256:10818ec...` | Resolve tag manifest, assert child platform, acquire by child digest, inspect `Architecture=arm64`, save/load, and re-inspect digest. `[VERIFIED: Docker Hub; Podman docs]` | Any `latest`, architecture mismatch, digest drift, or tag-only Quadlet => `BLOCKED`. |
| Server ARM64 ZIP | `1.1.15` | Same server commit | `linux-arm64v8` | `sha256:4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4` | Download from exact release URL; hash exact bytes; inspect contained `hbbs`/`hbbr` architecture. `[VERIFIED: GitHub API]` | Hash/architecture mismatch => delete quarantined bytes and `BLOCKED`. |
| Linux client DEB | `1.4.9` | `6c578292e8ebbbec708b76986ba8c4bc7c509747` | Debian `arm64` / host `aarch64` | `sha256:ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0` | Hash bytes, require `dpkg-deb -f ... Architecture` = `arm64`, preserve as Phase 54/55 input only. `[VERIFIED: GitHub API]` | Hash/metadata mismatch or install in Phase 52 => `BLOCKED`. |
| Windows client MSI | `1.4.9` | Same client commit | Windows x86-64 | `sha256:c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa` | Hash exact bytes now; Phase 54 additionally checks MSI metadata and Authenticode on Windows before install. `[VERIFIED: GitHub API; ROADMAP Phase 54]` | Hash mismatch, wrong product architecture, or Phase 52 install => `BLOCKED`. |

The upstream server workflow is useful but not a complete attestation chain: the same `build` job artifacts feed the release ZIP and container jobs, while `docker/build-push-action` explicitly sets `provenance: false`. Therefore the local supply manifest must bind official tag, commit, release-asset SHA-256, multiarch digest, ARM64 child digest, byte size, source URL, and observation timestamp; do not claim SLSA/cosign provenance. `[VERIFIED: https://github.com/rustdesk/rustdesk-server/blob/1.1.15/.github/workflows/build.yaml]`

No detached signature, SBOM, or checksum-file asset appears in the official `1.1.15` server or `1.4.9` client release asset lists. The checksums above are GitHub's release-asset `digest` fields, independently rechecked by hashing downloaded bytes during execution. `[VERIFIED: official GitHub Releases API asset lists]`

## Architecture Patterns

### System Architecture Diagram

```text
[Official Git tag + GitHub Release + Docker Hub]
                       |
                       v
             [immutable supply manifest]
                       |
                       v
             [exact capacity pre-gate]
                       |
             +---------+----------+
             | srv-2 PASS         | srv-2 FAIL
             v                    v
      [candidate srv-2]     [record NO-GO]
                                  |
                                  v
                        [same full gate on srv-3]
                           | PASS       | FAIL
                           v            v
                  [replan srv-3] [same full gate on horistic]
                                      | PASS       | FAIL
                                      v            v
                          [replan colocated]  [BLOCKED/no primary]

[Vault approved paths] --metadata-only hydration--> [0700 tmpfs runtime]
                                                        |
[pinned ARM64 image] --> [isolated source, no public network, quiesce]
                                                        |
                                                [backup A + backup B]
                                                        |
                                                        v
                                  [fresh isolated restore directory/runtime]
                                                        |
                                     [SQLite integrity + same public SHA-256]
                                                        |
                                                        v
                                      [integrated Phase 52 PASS report]
```

### Recommended Project Structure

```text
modules/rustdesk-fleet/
├── contracts/
│   ├── supply-chain.json          # expected immutable identifiers
│   ├── capacity-policy.json       # integer thresholds and named reservations
│   └── placement-decision.json    # explicit candidate verdict/topology
├── tools/
│   ├── validate_phase52.py        # integrated fail-closed validator
│   └── rustdesk-vault-hydrate     # metadata-only, stdin-safe runtime helper
├── tests/
│   ├── test_phase52_supply_capacity_restore.py
│   └── fixtures/{valid,invalid}/
└── evidence/
    └── phase52/                   # redacted JSON reports, manifests, hashes

.planning/workstreams/rustdesk-fleet/phases/
└── 52-supply-chain-capacity-and-recoverable-placement/
    ├── 52-VALIDATION.md
    └── 52-GATE-REPORT.{json,md}
```

Exact names are planner discretion, but contracts, live evidence, and generated reports must remain separate so fixtures cannot be mistaken for current proof. `[VERIFIED: Phase 51 project pattern]`

### Pattern 1: Immutable expectation + fresh observation

Store expected identifiers in a reviewed contract and live observations in a timestamped evidence record. The validator compares them and never updates expected values automatically. A mutable tag mismatch is an incident/blocker, not an upgrade path. `[VERIFIED: Phase 51 currentness pattern; official registries]`

### Pattern 2: Integer-only capacity math

Use bytes and inode counts, never rounded `df -h` percentages or floating-point acceptance. Compare `used_bytes * 100 <= total_bytes * threshold` and preserve raw numerator/denominator in evidence. `[VERIFIED: SRV-01; current snapshot demonstrates rounded-value ambiguity]`

### Pattern 3: Split persistent state from secret identity

Persist non-secret RustDesk state such as `db_v2.sqlite3`; hydrate `id_ed25519` and `id_ed25519.pub` into a restricted runtime tmpfs for each isolated start. Backups contain state and public fingerprint metadata, not the private-key value; Vault remains the recovery authority. `[VERIFIED: RustDesk 1.1.15 source; SRV-05]`

### Pattern 4: Restore into a fresh isolated target

Stop the source container, create two separately hashed backups, restore one into a new directory/runtime, hydrate from Vault, start the pinned image with no published/public network, run database and identity checks, then destroy only the disposable runtime after evidence is safely captured. `[VERIFIED: SRV-07; repo backup verify-before-delete pattern]`

### Pattern 5: Explicit placement state machine

Allowed outcomes are exactly: `srv-2/PASS -> primary_candidate=srv-2`; `srv-2/FAIL + srv-3/PASS -> primary_candidate=srv-3 + topology_replan_required=true`; `srv-2/FAIL + srv-3/FAIL + horistic/PASS -> primary_candidate=horistic-srv + topology_replan_required=true + client_colocation=true + phase54_replan_required=true`; or all fail -> `BLOCKED`. No candidate is called cold standby in Phase 52, and no automatic promotion occurs. `[VERIFIED: ROADMAP Phases 52/57; operator authorization]`

### Pattern 6: Separate evidence domains on a colocated primary/client

If `horistic-srv` is selected, Phase 53 server identity/state/services and Phase 54 client package/config/ID/service are separate assets even though they share a host. Phase 54 must use distinct evidence IDs and resource counters, perform public-edge probes from Windows, and treat the Horistic reboot as a deliberate joint primary+client outage: PASS requires the same server fingerprint, server readiness, client readiness, Windows reconnect, and preserved legacy fallbacks after boot. Client rollback must not modify server Quadlets/state/ports; server rollback must not uninstall or reconfigure the client or existing fallbacks. `[VERIFIED: operator authorization; Phase 53/54 requirements]`

The colocated W11↔Horistic forced-relay canary remains a real functional test only when W11-side transport evidence, `hbbr` byte deltas, and server/client identities are correlated; it is not independent failure-domain evidence and must not substitute for Phase 56 non-colocated fleet paths or Phase 57 failover. `[VERIFIED: ROADMAP Phases 54/56/57]`

### Recommended Plan Decomposition

1. **52-01 — Supply manifest and validators:** create exact source/image/client contracts, acquisition verifier, negative fixtures, and redacted evidence schema. No host runtime mutation. `[VERIFIED: SCP-04]`
2. **52-02/03 — Approved capacity policy and read-only routing:** materialize D-04/D-05 constants, enforce D-06 zero-cleanup on both Atius candidates, and collect exact ordered current capacity evidence without selecting a primary. `[VERIFIED: SRV-01; operator approval 2026-07-22T00:51:46Z]`
3. **52-04 — Vault/recovery engine:** implement and test the no-output hydration helper plus independent two-backup, isolated restore, and rollback state machines without yet binding them to a chosen candidate. `[VERIFIED: SRV-05, SRV-07]`
4. **52-05 — Full candidate runner:** execute every reached candidate through the same stage vector; persist current `NO-GO` before fallback and select only the first full-vector PASS. `[VERIFIED: D-01, D-06, D-07]`
5. **52-06 — Report and transition closeout:** render parity reports, update the ledger, perform the Phase 53 just-in-time topology review, and require fresh Graphify status. Phase 54/57 reviews remain mandatory only immediately before those phases. `[VERIFIED: D-02, D-07]`

### Anti-Patterns to Avoid

- Using `latest`, a version tag alone, or an auto-update directive. `[VERIFIED: SCP-04]`
- Treating Docker Hub compressed size as the complete on-disk cost. Loaded image, preserved archive, transient import workspace, state, both backups, and log reservation are separate terms. `[VERIFIED: Podman storage model; SRV-01]`
- Pulling before the `<=78%` gate or cleaning blindly to make the number pass. `[VERIFIED: SRV-01; AGENTS.md backup rule]`
- Putting a Vault value in argv, an exported persistent environment, a Markdown report, or a backup archive. `[VERIFIED: AGENTS.md, SRV-05]`
- Comparing or persisting raw password hashes. Use an ephemeral keyed comparison and output only cardinality/verdict. `[VERIFIED: Phase 51 secret-hygiene boundary]`
- Calling a copied directory a restore, or comparing only filenames. A fresh start plus DB integrity and public fingerprint equality is required. `[VERIFIED: SRV-07]`
- Calling `srv-3` standby or primary without the corresponding explicit gate/topology decision. `[VERIFIED: ROADMAP.md]`
- Selecting `horistic-srv` from its raw `43%` display alone, or ignoring that it is also the Phase 54 Linux canary. `[VERIFIED: live snapshot; operator authorization]`

## Capacity Measurement and Decision Procedure

### Required raw observations

For each candidate, record UTC timestamp, canonical hostname, `uname -m`, filesystem source/mount, `total_bytes`, `used_bytes`, `available_bytes`, `inode_total`, `inode_used`, `inode_available`, Podman graph root, and input-command version. Evidence stores numbers, not only human-readable percentages. `[VERIFIED: SRV-01 and host audit]`

### Exact gates

```text
pre_disk_ok   := used0_bytes * 100 <= total_bytes * 78
inode_ok      := inode_used * 100 <= inode_total * 80

image_reserve := loaded_image_delta
               + preserved_oci_archive_bytes
               + peak_import_workspace_bytes

backup_reserve := backup_A_bytes + backup_B_bytes
log_reserve_30d := 30 * approved_combined_daily_log_budget_bytes
state_reserve := approved_state_growth_budget_bytes

required_incremental_bytes := image_reserve
                            + backup_reserve
                            + log_reserve_30d
                            + state_reserve

projected_post_ok := (used0_bytes + required_incremental_bytes) * 100
                     <= total_bytes * 80
headroom_ok       := available0_bytes >= required_incremental_bytes

measured_post_ok  := used1_bytes * 100 <= total_bytes * 80
                     AND
                     (used1_bytes + still_unmaterialized_reservations) * 100
                     <= total_bytes * 80

backup_actuals_ok := backup_A_actual_bytes <= approved_backup_A_reserve_bytes
                     AND backup_B_actual_bytes <= approved_backup_B_reserve_bytes
```

`capacity_finalize` executes after image, both backups and isolated restore have materialized and before selection. It captures a fresh `used1_bytes`, raw filesystem source/mount, inode counters and timestamp; requires currentness, the same mount, checked integer additions without overflow, and actual backup A/B sizes at or below their independent 4 GiB reserves. It reconciles measured materialized bytes against the originally reserved image/archive/workspace/backup terms, removes only terms now proved materialized, retains every still-unmaterialized log/state/image term, and applies `(used1_bytes + still_unmaterialized_reservations) * 100 <= total_bytes * 80`. A failure triggers safe rollback of disposable drill artifacts, persists candidate full-gate `NO-GO`, and continues fallback. `[VERIFIED: SRV-01; Podman inspection docs]`

`loaded_image_delta` and peak import workspace are measured on a guarded staging acquisition before final admission or conservatively reserved until measured. `backup_A_bytes` and `backup_B_bytes` are actual separately generated archive sizes and never replace their approved maximums without the `capacity_finalize` reconciliation. The planner locks concrete byte constants for 30-day combined logs and state growth before execution; an unset, zero-by-default, or prose-only reservation makes the gate `BLOCKED`. `[VERIFIED: SRV-01; Podman inspection docs]`

### Decision sequence

1. Run supply verification remotely/read-only; quarantine any unexpected bytes. `[VERIFIED: SCP-04]`
2. Capture `srv-2` pre-gate twice: before remediation/acquisition and immediately before any image/archive write. `[VERIFIED: SRV-01; avoids TOCTOU]`
3. If `atius-srv-2` or `atius-srv-3` is above `78%`, persist exact current `NO-GO` and continue without cleanup, reclamation, pruning, deletion, movement, compression, or other destructive remediation. No remediation inventory creates authority. `[VERIFIED: D-06 and operator approval 2026-07-22T00:51:46Z]`
4. Reject if inodes exceed `80%`, pre-disk exceeds `78%`, raw available bytes are below reservations, or projected post exceeds `80%`. `[VERIFIED: SRV-01]`
5. Only after a candidate capacity PASS, perform the bounded isolated reversible full-gate writes: transfer/load prebuilt pinned artifacts under the `builds` profile if CPU-heavy, create state-only backups A/B, run the disposable isolated restore, write redacted evidence, execute `capacity_finalize`, then remove only disposable drill artifacts through verified rollback. Missing authorization, capacity, containment or target isolation is `NO-GO`, not authority for cleanup. `[VERIFIED: D-06; AGENTS.md; SRV-01/SRV-05/SRV-07]`
6. If any stage for `srv-2` fails, persist its complete current stage vector and `NO-GO`, then start a fresh full attempt on `srv-3`; never reuse observations, backups, or Vault/runtime evidence. `[VERIFIED: ROADMAP.md; D-07]`
7. If `srv-3` passes, write an explicit placement record naming it primary candidate and requiring Phase 53/57 topology replanning; do not label it cold standby. `[VERIFIED: ROADMAP Phases 52/57]`
8. Only if both `srv-2` and `srv-3` have persisted current full-attempt `NO-GO` records, repeat the same complete procedure on authorized `horistic-srv`, including supply artifact suitability, every byte/inode/reservation term, Vault hydration, two backups, isolated restore, rollback, and the Phase 52 topology/security verdict. A raw pre-gate PASS is not sufficient. `[VERIFIED: D-07 and operator approval 2026-07-22T00:51:46Z]`
9. If `horistic-srv` passes, record it as colocated primary candidate and require explicit Phase 53/54/57 topology/test replans. If it fails, stop Phase 52 with no primary. `[VERIFIED: operator authorization; ROADMAP phase ownership]`

### Current snapshot and minimum remediation before reservations

| Candidate | Raw bytes used / total | Exact use | Inodes | Minimum reclaim to reach 78% before adding any Phase 52 reservation | Current verdict |
|---|---:|---:|---:|---:|---|
| `atius-srv-2` | `173881397248 / 207907635200` | `83.633964%` | `11%` | `11713441792` bytes | `NO-GO` snapshot. `[VERIFIED: SSH 2026-07-20T08:40:26Z]` |
| `atius-srv-3` | `171940089856 / 207907635200` | `82.700229%` | `9%` | `9772134400` bytes | `NO-GO` snapshot. `[VERIFIED: SSH 2026-07-20T08:40:29Z]` |
| `horistic-srv` | `43916230656 / 103859404800` | `42.284308%` | `5%` | `0` bytes; `37094105088` bytes margin to 78% before reservations | Pre-threshold PASS snapshot only; full gate and co-location/rollback remain pending. `[VERIFIED: SSH 2026-07-20T08:57:34Z]` |

The reclaim/margin values only address the pre-gate and do **not** prove room for the image, two backups, state, 30-day logs, transient workspace, or colocated RustDesk client growth. Every execution candidate, including Horistic, must prove all formulas anew. `[VERIFIED: integer calculation from live snapshots]`

## Vault Boundary

### Approved references only

| Asset | Approved path | Field | Evidence allowed |
|---|---|---|---|
| Server private identity | `kv/atius/rustdesk/server` | `private_key` | Path/field, existence boolean, policy/access result, public fingerprint match; never value. `[VERIFIED: secret-roles.json]` |
| Distributed server public key | `kv/atius/rustdesk/server` | `public_key` | Path/field and `sha256:<hex>` fingerprint only. `[VERIFIED: secret-roles.json]` |
| Five permanent passwords | `kv/atius/rustdesk/targets/<canonical-host-id>` | `permanent_password` | Five approved paths, existence booleans, and aggregate distinctness `count=5, unique=5`; never values or reusable hashes. `[VERIFIED: secret-roles.json]` |

### Hydration contract

- The helper authenticates via the approved Vault path, sets `umask 077`, creates a `0700` directory under `/run/user/$UID` or another confirmed tmpfs, writes `0600` runtime files without stdout, disables xtrace, and installs a cleanup trap. `[CITED: https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/template]`
- Secret values never appear in command arguments. Do not use `rustdesk-utils validatekeypair <public> <private>` because its documented positional interface would expose values through argv. Validate by starting `hbbs` against restricted files and comparing only the derived/public file fingerprint. `[VERIFIED: RustDesk docs/source; AGENTS.md]`
- Password distinctness is computed inside one ephemeral process using a fresh in-memory HMAC key; only aggregate cardinality and PASS/FAIL leave the process. The key and per-password HMACs are discarded. `[VERIFIED: Phase 51 non-output distinctness requirement]`
- Process/environment evidence records variable names, PIDs, file modes, tmpfs mount, and absence of secret-bearing argv; it never dumps `/proc/<pid>/environ`, file contents, or shell trace. `[VERIFIED: AGENTS.md]`
- Backups exclude the private key. Recovery restores non-secret state and rehydrates the authoritative identity from Vault. `[VERIFIED: SRV-05; Vault authority boundary]`
- `id_ed25519.pub` is distributable later, but Phase 52 repo/evidence still stores only its SHA-256 fingerprint. `[VERIFIED: SRV-05 and official client configuration docs]`

## Recoverable Placement and Backup/Restore Plan Inputs

### Authoritative state set

RustDesk Server `1.1.15` uses `id_ed25519` as the private key file, derives/writes `id_ed25519.pub`, and defaults to `./db_v2.sqlite3`. Official container guidance requires the data directory to persist. `[VERIFIED: https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/common.rs; https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/peer.rs; https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/]`

For the Atius boundary, classify files as follows:

| Class | Contents | Backup behavior |
|---|---|---|
| Vault authority | `id_ed25519` value; five passwords | Never enter the archive; rehydrate at restore. `[VERIFIED: SRV-05]` |
| Public identity metadata | SHA-256 of exact `id_ed25519.pub` bytes | Store in redacted manifest/evidence. `[VERIFIED: SRV-05]` |
| Persistent server state | `db_v2.sqlite3` and future explicitly allowlisted non-secret state | Quiesce, archive twice, hash, and restore. `[VERIFIED: RustDesk source]` |
| Logs | Sanitized, bounded operational logs | Not part of identity backup; reserve 30-day bytes separately. `[VERIFIED: SRV-01]` |
| Image | Pinned OCI ARM64 digest plus preserved OCI archive checksum | Preserve independently from state backup and count in capacity. `[VERIFIED: SCP-04, SRV-01]` |

### Real restore acceptance sequence

1. Start a source `hbbs` instance from the pinned ARM64 digest in a rootless isolated namespace with no published/public network and a fresh runtime directory. Hydrate identity from Vault without output. `[VERIFIED: SRV-05/SRV-07]`
2. Confirm it creates/opens `db_v2.sqlite3`; calculate the SHA-256 fingerprint of exact public-key file bytes without printing the key. `[VERIFIED: RustDesk source]`
3. Stop/quiesce the source. Run Python `sqlite3` `PRAGMA integrity_check`; a non-`ok` result blocks backup. `[VERIFIED: Python standard library]`
4. Create **backup A** and **backup B** as two separately generated deterministic archives under separate names, with restrictive permissions and manifests containing only allowlisted paths, modes, sizes, archive SHA-256, input digest, and public fingerprint. Private key/password values are excluded. `[VERIFIED: SRV-05/SRV-07; repo backup pattern]`
5. Verify each archive checksum before any source/disposable cleanup. Reserve both actual sizes in the capacity report even if one is replicated off-host. `[VERIFIED: SRV-01; verify-before-delete pattern]`
6. Restore one archive into a brand-new directory and fresh runtime, rehydrate the identity from Vault, and start the same pinned image with no public listener. Do not point DNS/edge or install fleet clients. `[VERIFIED: phase boundary]`
7. Require restored DB integrity `ok`, expected file allowlist/modes, exact image digest/architecture, and restored public fingerprint equal to the source/contract fingerprint. A new key or missing DB is `BLOCKED`. `[VERIFIED: SRV-07]`
8. Stop the disposable restored service and prove it is stopped/disabled. Retain redacted reports and the two verified backups according to the approved storage decision. `[VERIFIED: split-brain prevention boundary]`
9. Execute the drill rollback: remove/disable only the disposable restored runtime, confirm the pre-drill primary-candidate state and all legacy access paths are unchanged, and verify no server/client artifact was installed as a side effect. On a Horistic placement, the rollback evidence must separately cover the future server and canary-client scopes. `[VERIFIED: operator rollback requirement; preserved-fallback contract]`

This is a real restore even before clients exist because a fresh isolated runtime consumes a separately created archive, opens the actual RustDesk database with the pinned server binary, and reconstitutes the same identity from Vault. Phase 57 still owns production failover/failback and the cold-standby label. `[VERIFIED: phase ownership in ROADMAP.md]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Artifact digesting | Custom hash algorithm | SHA-256 from GitHub API plus `sha256sum` of downloaded bytes | Standard, deterministic, and already available. `[VERIFIED: official API/host audit]` |
| OCI platform selection | Filename/tag inference | Registry manifest child digest + Podman `Architecture` inspection | Multiarch tags are mutable and architecture-specific children are explicit. `[VERIFIED: Docker Hub/Podman docs]` |
| Secret storage | Repo encryption format or `.env` convention | HashiCorp Vault approved paths and ephemeral hydration | Vault is the locked authority. `[VERIFIED: AGENTS.md]` |
| Password distinctness evidence | Reusable unsalted hashes | Ephemeral keyed comparison with aggregate result only | Prevents evidence from becoming a password oracle. `[VERIFIED: Phase 51 secret boundary]` |
| Database backup while live | Ad hoc copy of active SQLite bytes | Quiesce first, integrity-check, deterministic archive, restore verification | Avoids internally inconsistent backup claims. `[VERIFIED: SRV-07]` |
| Capacity percentages | Parsed `df -h` strings/floats | Integer byte/inode inequalities | Avoids rounding and locale errors. `[VERIFIED: current snapshot]` |
| Placement automation | Silent fallback/scheduler | Explicit four-outcome state machine and reviewed record | Preserves topology, co-location truth, and accountability. `[VERIFIED: ROADMAP.md; operator authorization]` |

**Key insight:** Phase 52 is a proof pipeline. Existing standard primitives are sufficient; custom crypto, secret stores, image builders, and failover orchestration add risk without satisfying any requirement. `[VERIFIED: phase requirements and environment audit]`

## Common Pitfalls

### Pitfall 1: Accepting the rounded `df` number
**What goes wrong:** a host appears close enough while exact bytes violate the threshold or omit future reservations.  
**How to avoid:** persist raw counts and use integer inequalities; require both projected and measured post evidence. `[VERIFIED: SRV-01]`

### Pitfall 2: Counting only the compressed registry image
**What goes wrong:** OCI archive, extracted graphroot bytes, import workspace, backups, state, and logs consume unbudgeted disk.  
**How to avoid:** measure/count each incremental term once and preserve the formula inputs. `[VERIFIED: Podman docs; SRV-01]`

### Pitfall 3: Automatically changing expected digests
**What goes wrong:** a mutated tag becomes the new "truth" and defeats pinning.  
**How to avoid:** expected identifiers are reviewed inputs; mismatch is `BLOCKED` and requires an explicit upgrade/research change. `[VERIFIED: SCP-04]`

### Pitfall 4: Leaking secrets through a validation command
**What goes wrong:** secret values enter argv, stdout, `ps`, history, or logs even though repo files are clean.  
**How to avoid:** file/stdin-safe hydration, tmpfs, restrictive modes, xtrace off, aggregate-only results, and negative process/log tests. `[VERIFIED: AGENTS.md; SRV-05]`

### Pitfall 5: Backing up the private key outside Vault
**What goes wrong:** the archive becomes a second unmanaged identity authority.  
**How to avoid:** exclude the private key; restore state and rehydrate the identity from Vault. `[VERIFIED: Vault boundary]`

### Pitfall 6: Calling `srv-3` a standby too early
**What goes wrong:** topology evidence claims resilience before equivalent capacity, same-identity restore, stopped/disabled proof, and later failover drills.  
**How to avoid:** Phase 52 records only a primary candidate and restore result; Phase 57 owns the cold-standby label. `[VERIFIED: ROADMAP Phase 57]`

### Pitfall 7: Installing the Windows client during supply verification
**What goes wrong:** Phase 54 canary prerequisites and rollback evidence are bypassed.  
**How to avoid:** hash/stage the MSI only. `GIOVANNI-W11-PC` remains without RustDesk until mandatory Phase 54 execution after Phases 52 and 53. `[VERIFIED: 51-VERIFICATION.md; ROADMAP.md]`

### Pitfall 8: Treating Horistic co-location as ordinary canary topology
**What goes wrong:** a Phase 54 reboot simultaneously removes the primary and the Linux client, client/server metrics are conflated, or a local relay result is overstated as independent resilience.  
**How to avoid:** set explicit co-location flags, split evidence/resource/rollback domains, probe the public edge from Windows, require joint post-reboot recovery, and defer independent-path/failover claims to Phases 56/57. `[VERIFIED: operator authorization; ROADMAP.md]`

## Code Examples

Verified planning patterns; execution scripts must emit JSON rather than free-form text.

### Exact capacity comparison

```python
# Source: SRV-01 contract; integer-only to avoid rounding.
def pct_at_most(used: int, total: int, limit: int) -> bool:
    return total > 0 and used >= 0 and used * 100 <= total * limit

pre_ok = pct_at_most(used0_bytes, total_bytes, 78)
inode_ok = pct_at_most(inode_used, inode_total, 80)
projected_ok = pct_at_most(
    used0_bytes + image_reserve + backup_a + backup_b + logs_30d + state_reserve,
    total_bytes,
    80,
)
```

### Public fingerprint without public-key output

```bash
# Source: SRV-05/SRV-07. The file contents are never printed.
umask 077
public_fingerprint="sha256:$(sha256sum "$runtime_dir/id_ed25519.pub" | awk '{print $1}')"
printf '{"public_key_fingerprint":"%s"}\n' "$public_fingerprint"
```

### Image pin shape

```ini
# Source: official Docker Hub digest, observed 2026-07-20.
# Phase 53 Quadlet input; never replace with :latest or tag-only.
Image=docker.io/rustdesk/rustdesk-server@sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208
```

### Govern CPU-heavy verification/acquisition

```bash
# Source: AGENTS.md and modules/srv1-ops resource governor.
omni srv1-ops resources run builds -- <cpu-heavy-verification-or-acquisition-command>
```

No RustDesk build command belongs in the plan. `[VERIFIED: phase boundary]`

## State of the Art

| Old/unsafe approach | Current required approach | Impact |
|---|---|---|
| `rustdesk/rustdesk-server:latest` examples | Platform child digest for `1.1.15` | Upstream docs still show `latest`; the project contract deliberately overrides it for reproducibility. `[CITED: https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/]` |
| Tag/checksum only | Tag + commit + release digest + OCI manifest/child digest + architecture | Detects mutable tags and wrong-platform pulls. `[VERIFIED: SCP-04]` |
| Persist server key in generic data backup | Vault-authoritative key plus state-only backups | Prevents backup sprawl from becoming identity authority. `[VERIFIED: SRV-05]` |
| Backup-exists acceptance | Fresh isolated start from restored state with fingerprint equality | Converts recoverability from documentation into observed behavior. `[VERIFIED: SRV-07]` |
| Silent failover placement | Explicit `srv-2`, then `srv-3`, then authorized Horistic verdicts | Preserves capacity/security, co-location truth, and later DR role correctness. `[VERIFIED: ROADMAP.md; operator authorization]` |

**Deprecated/outdated for this project:** upstream Compose/Quadlet examples containing `latest` and auto-update are documentation examples only and must not be copied into production contracts. `[CITED: https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| — | None. The operator resolved the numeric policy, retention, zero-cleanup, and Horistic full-gate inputs at `2026-07-22T00:51:46Z`. | — | — |

## Open Questions (RESOLVED)

1. **RESOLVED — What exact combined daily log budget is reserved for 30 days?**
   - Approved: `combined_daily_log_budget_bytes=134217728` (128 MiB/day), `log_retention_days=30`, total reservation `4026531840` bytes. Unset/zero-by-default remains `BLOCKED`.

2. **RESOLVED — What state-growth reserve accompanies the current minimal database?**
   - Approved: `state_growth_budget_bytes=4294967296` (4 GiB), retained as a separate reservation term and changeable only through reviewed contract change.

3. **RESOLVED — Where are backup A and backup B retained after the restore drill?**
   - Approved: reserve `4294967296` bytes for each backup; backup A remains local on the selected candidate, while backup B uses the existing managed `modules/fleet-backup` GDrive destination. Retain both through Phase 57 `PASS` plus 30 days; deletion always requires new explicit approval.

4. **RESOLVED — Can a candidate satisfy the full gate without a storage change?**
   - Approved policy: zero cleanup/remediation/reclamation/pruning/deletion or destructive mutation on `atius-srv-2` and `atius-srv-3`. After current capacity PASS, the only permitted writes are bounded isolated reversible pinned-artifact staging/load, state-only backup A/B creation, disposable isolated restore state, redacted evidence, and verified rollback removal of the disposable drill artifacts. Missing authorization or capacity for them is current `NO-GO` and fallback; Horistic's raw threshold snapshot is not GO.

5. **RESOLVED — How is the Horistic primary/client co-location represented in later plans?**
   - Approved policy: Phase 52 records the topology impact now and sets separate just-in-time review gates before Phase 53, Phase 54, and Phase 57. Each review must preserve separate server/client identities, evidence, resources, reboot and rollback domains, Windows-origin public-edge proof in Phase 54, and no independent-DR claim.

**Approval authority:** Giovanni Muniz; **timestamp:** `2026-07-22T00:51:46Z`; **scope:** the five resolutions above without secret values.

## Environment Availability

| Dependency | Required By | Available | Version / Evidence | Fallback |
|---|---|---|---|---|
| SSH read-only access | Capacity/host probes | ✓ direct aliases | `srv-2`, `srv-3`, and Horistic responded 2026-07-20 | VPN aliases timed out during research; direct paths worked. `[VERIFIED: live probe]` |
| Podman rootless | OCI load/isolated restore | ✓ all three paths | `srv-2`/`srv-3`: `4.9.3`, overlay; Horistic wrapper path present but version output requires recheck | Stop Horistic placement if effective version/capabilities cannot be verified. `[VERIFIED: live probe]` |
| Python | Validators/SQLite | ✓ all three candidates | `3.12.3` on `srv-2`/`srv-3`; present on Horistic | None needed. `[VERIFIED: live probe]` |
| pytest | Repo tests | ✓ control host | `7.4.4` | Python unittest if isolated, but preserve repo pytest pattern. `[VERIFIED: local probe]` |
| `jq`, `curl`, `sha256sum`, `tar`, `systemd-run` | Supply/backup/resource controls | ✓ all three candidates | Host binaries present | Python stdlib for JSON/HTTP/hash/tar if one disappears. `[VERIFIED: live probe]` |
| Vault helper | Secret hydration bootstrap | ✓ all three candidates | executable path present; values not read | Stop if helper contract cannot provide non-output hydration. `[VERIFIED: live probe]` |
| `omni-builds.slice` | CPU-heavy actions | ✓ all three candidates | `srv-2 cpu.max=80000 100000`; `srv-3` and Horistic `cpu.max=20000 100000` observed | All are at/below the global 20%-total ceiling; verify again before heavy work. `[VERIFIED: live probe and AGENTS.md]` |
| `skopeo` | Remote OCI inspection | ✗ candidates/current host | missing | Use official registry API plus Podman inspect/load; do not install merely for Phase 52. `[VERIFIED: probes]` |
| `cosign` | OCI signature verification | ✗ candidates/current host | missing; upstream workflow has `provenance: false` | Do not claim signature provenance; enforce digest pins and official-source binding. `[VERIFIED: probes/upstream workflow]` |
| Vault CLI | Direct local CLI | ✗ control host | missing; approved helper exists on candidates | Use approved helper, never ad hoc secret transport. `[VERIFIED: probe/AGENTS.md]` |

**Missing dependencies with no fallback:** none for the planned verification flow. A non-output Vault hydration operation that the existing helper cannot support would become a blocking Wave 0 implementation requirement. `[VERIFIED: environment audit]`

**Missing dependencies with fallback:** `skopeo`, `cosign`, and direct Vault CLI as described above. `[VERIFIED: environment audit]`

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest `7.4.4` + Python `3.12.3` standard library |
| Config file | Existing repository pytest discovery; no Phase 52-specific config yet |
| Quick run command | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q` |
| Full suite command | `python3 -m pytest modules/rustdesk-fleet/tests -q` |
| Live gate command | `python3 modules/rustdesk-fleet/tools/validate_phase52.py --repo . --json-out <52-GATE-REPORT.json> --markdown-out <52-GATE-REPORT.md>` |

All test infrastructure facts above follow the current Phase 51 pattern; the Phase 52 files are Wave 0 gaps. `[VERIFIED: modules/rustdesk-fleet/tests; 51-VALIDATION.md]`

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| SCP-04 | Exact tag/commit/digest/checksum/architecture; reject `latest`, drift, wrong arch, missing asset | unit + network integration | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k supply` | ❌ Wave 0 |
| SRV-01 | Exact threshold boundaries, byte reservations, live raw fields, explicit `srv-3` then Horistic branch, and co-location flags | unit + live integration | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k 'capacity or placement'` | ❌ Wave 0 |
| SRV-05 | Six approved refs, value existence/distinctness without output, tmpfs/modes/argv/log hygiene | unit + live security | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k vault` | ❌ Wave 0 |
| SRV-07 | Two backups, archive hashes, fresh isolated restore, SQLite integrity, equal public fingerprint | unit + live restore | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py -q -k restore` | ❌ Wave 0 |

### Required Negative Fixtures

- Mutable tag/changed commit, multiarch digest drift, ARM64 child mismatch, wrong DEB/MSI checksum, and `latest` in config. `[VERIFIED: SCP-04 threat surface]`
- Capacity boundary at one byte below/at/above 78% and 80%, inode boundary, omitted backup/log term, negative/overflow values, different mount, stale timestamp, out-of-order Horistic selection, and missing co-location/replan flags. `[VERIFIED: SRV-01; operator authorization]`
- Duplicate password values detected by ephemeral comparison, unknown Vault path/field, secret-looking output, private-key archive entry, permissive modes, non-tmpfs runtime, and secret-bearing argv fixture. `[VERIFIED: SRV-05]`
- Missing backup B, corrupted archive, active-source backup, wrong/missing DB, non-`ok` SQLite integrity, regenerated key, mismatched fingerprint, public listener, and restored service left active. `[VERIFIED: SRV-07]`

### Sampling Rate

- **Per task commit:** focused `-k` node plus quick suite; no watch mode. `[VERIFIED: GSD Nyquist pattern]`
- **Per wave merge:** full RustDesk fleet suite, live validator in no-persist/dry-run mode where applicable, secret-hygiene scan, `git diff --check`, Phase 48 integrity, and Graphify status. `[VERIFIED: Phase 51 transition pattern]`
- **Phase gate:** all four requirement checks current PASS, two backup hashes verified, restore-live PASS, placement explicit, `secret_material_present=false`, JSON/Markdown parity, then `$gsd-verify-work --ws rustdesk-fleet`. `[VERIFIED: ROADMAP advance gate]`

### Wave 0 Gaps

- [ ] `modules/rustdesk-fleet/contracts/supply-chain.json` — exact immutable identifiers and sources.
- [ ] `modules/rustdesk-fleet/contracts/capacity-policy.json` — thresholds and every named byte reservation.
- [ ] `modules/rustdesk-fleet/contracts/placement-decision.json` — explicit four-outcome placement schema, including Horistic co-location flags.
- [ ] `modules/rustdesk-fleet/tools/validate_phase52.py` — deterministic integrated validator/renderer.
- [ ] `modules/rustdesk-fleet/tools/rustdesk-vault-hydrate` — stdin-safe, no-output, tmpfs hydration/distinctness helper.
- [ ] `modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py` and valid/invalid fixtures.
- [ ] Phase-local `52-VALIDATION.md` and generated `52-GATE-REPORT.{json,md}`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | Vault-authenticated helper and named accountable owner; no anonymous secret access. `[VERIFIED: Phase 51 ASVS baseline]` |
| V3 Session Management | yes | Short-lived/wrapped Vault authentication, runtime cleanup, no persistent token. `[CITED: https://developer.hashicorp.com/vault/docs/concepts/response-wrapping]` |
| V4 Access Control | yes | Exact Vault paths, `0700/0600`, rootless user scope, fail closed. `[VERIFIED: AGENTS.md/secret-roles.json]` |
| V5 Input Validation | yes | Strict schemas, exact sets/enums, integer bounds, repo-relative paths, digest syntax. `[VERIFIED: Phase 51 validator pattern]` |
| V6 Cryptography | yes | SHA-256 for artifact/public fingerprints; ephemeral keyed HMAC for non-output distinctness; no custom crypto. `[VERIFIED: SRV-05 and standard tools]` |

### Known Threat Patterns for Phase 52

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Mutable tag/artifact substitution | Tampering | Resolve official tag/commit/digests twice; acquire by immutable digest; block drift. `[VERIFIED: SCP-04]` |
| Wrong architecture | Tampering/DoS | Require ARM64 child digest and package metadata, not filename alone. `[VERIFIED: SCP-04]` |
| Disk exhaustion during load/backup/log growth | DoS | Exact pre/projected/measured gate with all reservations. `[VERIFIED: SRV-01]` |
| Secret in argv/stdout/archive | Information Disclosure | Non-output tmpfs hydration, restrictive modes, negative scans, state-only backup. `[VERIFIED: SRV-05]` |
| Key rotation during restore | Spoofing/Tampering | Rehydrate from Vault and compare exact public SHA-256. `[VERIFIED: SRV-07]` |
| Corrupt/inconsistent SQLite backup | Tampering/DoS | Quiesce, integrity-check before/after, checksum both archives, fresh restore. `[VERIFIED: SRV-07]` |
| Silent `srv-3` promotion/false standby | Repudiation/Tampering | Explicit placement record and topology-replan flag; no automated waiver. `[VERIFIED: ROADMAP.md]` |
| Horistic server/client co-location conflation | Repudiation/DoS | Separate identities/evidence/resource/rollback domains; Windows-origin probe; joint reboot recovery; no independent-DR claim. `[VERIFIED: operator authorization; Phase 54 boundary]` |
| Two active restored instances | Elevation/DoS | No public network during drill and stopped/disabled proof at completion. `[VERIFIED: recovery boundary]` |

## Sources

### Primary (HIGH confidence for local locked/runtime facts)

- `AGENTS.md`, `.planning/workstreams/rustdesk-fleet/{ROADMAP,REQUIREMENTS,STATE}.md` — locked thresholds, phase ownership, secret/resource policies.
- Phase 51 contract, operational review, security, validation, and verification artifacts — approved Vault paths, threats, evidence/currentness pattern, and Windows deferment.
- `modules/rustdesk-fleet/contracts/*.json`, `modules/rustdesk-fleet/evidence/ledger.json` — machine-readable scope/secret/evidence truth.
- `modules/srv1-ops/configs/resource-governor.env`, `modules/fleet-backup/` — governed CPU and serial copy/verify patterns.
- Operator authorization received 2026-07-20 — Horistic is a tertiary recoverable-placement candidate after `srv-2`/`srv-3` capacity NO-GO, with identical gates and explicit Phase 54 co-location handling.
- Read-only SSH observations on `atius-srv-2-direct`, `atius-srv-3-direct`, and `horistic-srv-1`, 2026-07-20 — current capacity, architecture, tools, graph root where available, and cgroup evidence.

### Primary authoritative upstream (MEDIUM confidence per research seam)

- [RustDesk Server OSS 1.1.15 release](https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.15) — tag, commit, official assets and GitHub digests.
- [RustDesk client 1.4.9 release](https://github.com/rustdesk/rustdesk/releases/tag/1.4.9) — tag, commit, platform assets and GitHub digests.
- [Docker Hub RustDesk Server tags](https://hub.docker.com/r/rustdesk/rustdesk-server/tags) — version tag and platform digests.
- [RustDesk Server 1.1.15 build workflow](https://github.com/rustdesk/rustdesk-server/blob/1.1.15/.github/workflows/build.yaml) — tag-triggered build/release/image relationship and `provenance: false`.
- [RustDesk Server key source](https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/common.rs) — `id_ed25519`, public derivation/file generation.
- [RustDesk Server database source](https://github.com/rustdesk/rustdesk-server/blob/1.1.15/src/peer.rs) — default `db_v2.sqlite3`.
- [RustDesk Server OSS Docker/Podman guide](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/) — persistent data directory and official container pattern.
- [RustDesk client configuration](https://rustdesk.com/docs/en/self-host/client-configuration/) — client consumption of `id_ed25519.pub`.
- [Podman image inspect](https://docs.podman.io/en/latest/markdown/podman-image-inspect.1.html) — `Digest`, `RepoDigests`, `Architecture`, `Os`, and `Size`.
- [Podman save](https://docs.podman.io/en/latest/markdown/podman-save.1.html) — OCI archive export.
- [Vault Agent templates](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/template) and [response wrapping](https://developer.hashicorp.com/vault/docs/concepts/response-wrapping) — ephemeral delivery primitives.

### Secondary (MEDIUM confidence)

- GBrain `projects/omni-srv-admin/rustdesk-v19-phase51-checkpoint` and `atius-build-and-k3s-resource-policy` — read-only historical cross-check; repo/current runtime remained authoritative.
- `.planning/research/rustdesk-fleet/{SUMMARY,ARCHITECTURE,FEATURES,PITFALLS}.md` — prior converged risk/background, revalidated here against current contracts and sources.

### Tertiary (LOW confidence)

- None used as authority.

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM — exact releases/digests and host tools are verified, but upstream publishes no OCI provenance attestation and the research seam classifies web/context sources MEDIUM.
- Architecture: HIGH — directly constrained by local requirements, Phase 51 contracts, upstream file layout, and repo-native patterns.
- Capacity: HIGH for the formula/current snapshots; MEDIUM for execution outcome — `srv-2`/`srv-3` currently fail, while Horistic passes only the raw pre-threshold and still lacks full reservation/restore/rollback proof.
- Vault boundary: HIGH — approved paths and prohibitions are locked; the non-output helper still needs Wave 0 implementation/live proof.
- Recoverability: MEDIUM — source/state inputs are verified, but only Phase execution can prove the actual backup/restore and fingerprint invariant.
- Pitfalls: HIGH — each maps to a locked stop condition or observed host state.

**Research date:** 2026-07-20  
**Valid until:** 2026-07-27 for mutable registry/release observations; local locked contracts remain valid until changed. Re-resolve all external identifiers at execution regardless of this date.
