# Phase 51: Contract, Threat Model and Workstream Isolation - Research

**Researched:** 2026-07-20
**Domain:** Secret-free remote-access governance, threat modeling, evidence contracts, and GSD workstream integrity
**Confidence:** HIGH for project scope and repo patterns; MEDIUM-HIGH for negative OSS capability claims

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Fleet and coexistence
- **D-01:** Include exactly `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, and `GIOVANNI-W11-PC`; WSL and `GIOVANNI-S23` are excluded from every mutation and evidence path. `[SCP-01]`
- **D-02:** RustGuac, XRDP, AnyDesk, NoMachine, and noVNC remain installed and independently usable; this milestone contains no decommission scope. `[SCP-01]`

### Product and transport boundary
- **D-03:** RustDesk Server OSS is acceptable only for a single operator after explicit acceptance of missing mandatory SSO/OIDC, RBAC, MFA, centralized API/device policy, and human-attributed audit; any mandatory control makes the decision `NO-GO` until Pro is selected. `[SCP-02]`
- **D-04:** Production policy is direct-first. Forced relay is allowed only for controlled validation and proven fallback and cannot be the default fleet setting. `[SCP-03]`

### Secrets, identity, and permissions
- **D-05:** Treat the server private key, distributed server public key, five distinct permanent target passwords, RustDesk client IDs, permission profiles, and recovery authority as separate assets. Only names and Vault paths may appear in versioned or documented artifacts.
- **D-06:** Define least-privilege `admin-maintenance` and `support-observe` permission profiles. Any OSS limitation preventing centralized enforcement is an explicit compensating-control risk, not a claimed capability.
- **D-07:** Evidence validators reject secret-looking values and command/process/screenshot leakage. No secret value may enter repo files, Markdown, logs, fixtures, Obsidian, GBrain, or evidence manifests.

### GSD isolation and proof
- **D-08:** Every RustDesk lifecycle command explicitly supplies `--ws rustdesk-fleet`; the active marker alone is not authority. Shared `PROJECT.md`, `MILESTONES.md`, and Graphify writers are serialized. `[SCP-05]`
- **D-09:** Capture a Phase 48 integrity baseline from `runtime-trust-codex-delivery-convergence` and verify it after each lifecycle transition. Any unexplained drift blocks advancement. `[SCP-05]`
- **D-10:** Requirement acceptance is evidence-addressed: every requirement maps to current machine-readable proof, and summary-only PASS text never closes a gate.

### the agent's Discretion
- Exact file names and implementation language for small validators, provided they follow existing repo patterns and run without heavy builds.
- Exact normalized schema for evidence manifests and permission tables, provided it is deterministic, redacted, and extensible through Phase 58.

### Deferred Ideas (OUT OF SCOPE)
- Runtime server placement and capacity gate: Phase 52.
- DNS, ports, server containers, client installs, live sessions, DR, rollback, and UAT: Phases 52-58.
- RustDesk Server Pro implementation: deferred unless D-03 returns `NO-GO` for OSS.
</user_constraints>

## Project Constraints (from AGENTS.md)

- Treat this as GSD-managed work. Graphify status/query precedes repository routing; if stale, relationships are approximate until focused reads confirm them. Do not use Graphify as a replacement for exact reads or tests. `[VERIFIED: user-provided AGENTS.md]`
- Historical research observation: before the governed rebuild, the graph had `stale: false` but `commit_stale: true`, one commit behind; the researcher correctly did not rebuild it inside the read-only slice. The serialized root owner subsequently rebuilt Graphify under `omni-builds.slice`; the current measured state at `e36e47b` is `stale: false`, `commit_stale: false`, zero commits behind. `[VERIFIED: gsd-tools graphify status before and after governed rebuild]`
- Any CPU-heavy build, compile, test suite, container build, bundler, or broad indexer must stay at or below 20% of host CPU and use the governed wrapper/profile. Phase 51 should need only narrow Python tests and read-only GSD queries. `[VERIFIED: AGENTS.md]`
- Managed k3s pods use a 500m total pod CPU unit. This is not exercised by Phase 51 because runtime deployment is out of scope. `[VERIFIED: AGENTS.md; 51-CONTEXT.md]`
- HashiCorp Vault is the only secret authority. Versioned artifacts may record profile/path/field names and non-secret fingerprints, never secret values. `[VERIFIED: AGENTS.md; 51-CONTEXT.md]`
- Browser automation, if later required, is headless and must retain evidence. Phase 51 has no browser requirement. `[VERIFIED: AGENTS.md]`
- Research/validation may run in parallel, but writers are serialized per file and shared planning/Graphify writers are single-owner. `[VERIFIED: AGENTS.md; 51-CONTEXT.md]`
- GBrain and the relevant Obsidian project log were consulted read-only. The current operational note says no RustDesk runtime mutation has occurred and Phase 51 is the next gate. `[VERIFIED: GBrain query; AiSecondBrain/60-LOGS/2026-07-19-rustdesk-v19-research-milestone.md]`

## Summary

Phase 51 should implement a small, dependency-free Python validator over versioned JSON contracts and emit both a machine-readable report and `51-CONTRACT-VALIDATION.md`. The authoritative contract must freeze the exact five-host allowlist, two-host denylist, five preserved legacy tools, direct-first transport, OSS/Pro decision algorithm, permission profiles, secret roles, all 36 requirement IDs, and the Phase 48 integrity mapping. Use strict parsing, exact-set comparisons, stable IDs, deterministic serialization, redacted findings, and fail-closed exit codes. `[VERIFIED: 51-PRD.md; repo validator patterns]`

RustDesk's official documentation assigns centralized accounts, web console, API, OIDC/LDAP/2FA, device/policy management, access control, and audit/log management to Server Pro. Phrase the negative claim narrowly: OSS has no documented contract for those centralized Pro controls; do not claim that OSS clients have no local settings or logs. `[CITED: https://rustdesk.com/docs/en/self-host/#which-rustdesk-server-should-you-choose] [CITED: https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/#when-to-choose-rustdesk-server-pro]`

The Phase 48 baseline must not rely on `git ls-files` at the new workstream path. The nine migrated Phase 48 files are currently untracked at the new path, while a read-only comparison found them byte-identical to the nine blobs tracked at the legacy `HEAD:.planning/phases/48-*` path. Record an explicit old-path to new-path mapping, source HEAD, Git blob ID, filesystem SHA-256, exact file count, and allowed exclusions; any missing, extra, or mismatched entry is blocking. `[VERIFIED: git ls-files/rev-parse/hash-object comparison at HEAD 7829bdb5693bb3c6c41a454cf8d037b5168b8776]`

**Primary recommendation:** implement one standard-library Python validator and one focused pytest module; make its JSON report the source of truth from which `51-CONTRACT-VALIDATION.md` is rendered, and block Phase 52 unless automated checks plus the operational OSS/Pro and threat-model review are current PASS. Reserve `51-VALIDATION.md` for the GSD Nyquist strategy.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCP-01 | Include exactly five authorized hosts; exclude WSL and `GIOVANNI-S23`. | Exact-set scope schema, denylist fixtures, and preserved-tool invariant. |
| SCP-02 | OSS only for accepted single-operator risk; any mandatory enterprise control requires Pro. | Deterministic decision table, official Pro provenance, and human review checkpoint. |
| SCP-03 | Production direct-first; forced relay only for controlled tests/fallback. | Transport enum, forbidden default, config/fixture validation. |
| SCP-05 | All lifecycle artifacts/commands target `rustdesk-fleet`; preserve Phase 48. | Command-scope scanner, shared-writer policy, and explicit nine-file integrity baseline. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Scope/product/transport contracts | Repo governance | Validation tool | Versioned truth is reviewed in Git; the validator enforces exact semantics. |
| OSS/Pro decision | Operational governance | Product boundary | A human declares which controls are mandatory; code deterministically derives `GO` or `NO-GO`. |
| Threat and permission model | Security governance | Managed clients | Phase 51 defines desired policy; later phases prove per-client enforcement. |
| Secret role inventory | Vault governance | Runtime hydration | Repo contains names/paths only; values remain in Vault/runtime. |
| Requirement evidence ledger | Evidence layer | GSD planning | Stable requirement/evidence IDs prevent summary-only completion. |
| Workstream integrity | GSD planning | Git/filesystem | Explicit scope and hashes detect wrong-lane mutation despite the dirty migration state. |

## Standard Stack

### Core

| Tool | Observed Version | Purpose | Recommendation |
|------|------------------|---------|----------------|
| Python standard library | 3.12.3 | Strict JSON parsing, regex-based redacted scanning, SHA-256, deterministic reports | Use; no external runtime package is needed. `[VERIFIED: local command]` |
| pytest | 7.4.4 | Positive/negative contract fixtures | Use the existing test framework. `[VERIFIED: local command and existing repo tests]` |
| Git | 2.43.0 | Legacy blob provenance and HEAD capture | Use read-only commands; do not treat tracking state as the only baseline. `[VERIFIED: local command]` |
| GSD tools | repository runtime | Workstream state/roadmap checks | Always pass `--ws rustdesk-fleet` for RustDesk lifecycle/state queries. `[VERIFIED: workstream-flag.md]` |

### Package Legitimacy Audit

No package installation is authorized or needed. The package legitimacy gate is therefore not applicable. `[VERIFIED: 51-CONTEXT.md scope fence]`

## Recommended Artifact Layout

```text
modules/rustdesk-fleet/
├── contracts/
│   ├── scope.json
│   ├── product-decision.json
│   ├── threat-model.json
│   ├── permission-profiles.json
│   └── secret-roles.json
├── evidence/
│   ├── ledger.json
│   └── phase48-baseline.json
├── tools/
│   └── validate_phase51.py
└── tests/
    ├── fixtures/
    │   ├── valid/
    │   └── invalid/
    └── test_phase51_contracts.py

.planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/
├── 51-SECURITY.md
├── 51-OPERATIONAL-REVIEW.md
├── 51-CONTRACT-VALIDATION.json
├── 51-CONTRACT-VALIDATION.md
└── 51-VALIDATION.md                 # GSD Nyquist strategy, never overwritten by runtime reporting
```

Use JSON rather than YAML for machine contracts so the implementation stays in the standard library and strict duplicate/shape checks can be centralized. Human-readable rationale belongs in `51-SECURITY.md` and `51-OPERATIONAL-REVIEW.md`; JSON remains authoritative for validators. This is a prescriptive Phase 51 design, not a claim that these files already exist.

## Architecture Patterns

### Pattern 1: Exact-set scope, never substring discovery

`scope.json` must contain exactly these ordered sets:

- included: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, `GIOVANNI-W11-PC`;
- excluded: `WSL`, `GIOVANNI-S23`;
- preserved tools: `RustGuac`, `XRDP`, `AnyDesk`, `NoMachine`, `noVNC`.

The validator compares sets and cardinality, rejects aliases/unknown hosts, and scans every Phase 51 contract/evidence target for an excluded-host mutation target. A mention inside the explicit denylist or a negative test is allowed only when the parsed field/fixture role is `excluded`.

### Pattern 2: Deterministic OSS/Pro state machine

Define enterprise controls as stable IDs: `sso_oidc`, `rbac`, `mfa`, `central_api`, `central_device_policy`, `human_attributed_audit`. Each has `mandatory: true|false`, `source`, and `review_status`. The derived result is:

```text
if any control.mandatory == true:
    decision = NO-GO
    required_edition = pro
else if operator_scope == single and every absence is explicitly accepted:
    decision = GO
    required_edition = oss
else:
    decision = BLOCKED
```

Do not allow a manually typed `GO` to disagree with derived inputs. The validator must also require a current operational-review artifact before PASS.

### Pattern 3: Stable evidence addressing

`ledger.json` reserves exactly the 36 v1.9 requirement IDs currently present in `REQUIREMENTS.md`. Each row has `requirement_id`, `owner_phase`, `acceptance_kind`, `status`, `evidence_ids`, and `last_verified_at`. The validator parses canonical requirement IDs, rejects missing/orphan/duplicate rows, rejects evidence paths outside the RustDesk workstream/module, and treats missing/currentness failure as `BLOCKED`. `[VERIFIED: REQUIREMENTS.md contains 36 uniquely mapped v1.9 IDs]`

### Pattern 4: Filesystem-and-Git integrity bridge

`phase48-baseline.json` must list all nine authoritative Phase 48 files explicitly. For each row record:

- `legacy_git_path` under `.planning/phases/48-codex-oauth-wayland-acp-convergence/`;
- `workstream_path` under `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/`;
- Git `source_head` and blob ID for the legacy path;
- SHA-256 of the current workstream file;
- `file_count: 9` and explicit exclusions for transient noise only (`__pycache__`, `*.pyc`, editor swap/backup files).

Default mode verifies only. Re-baselining must require an explicit flag, serialized writer ownership, a reason, and review provenance; never auto-accept drift. Because Phase 48 is still active, legitimate changes also block RustDesk advancement until reviewed and re-baselined.

### Pattern 5: Redacted fail-closed findings

Follow the repo's secret scanners: print category, path, and line/field only, never the matched content. Expand coverage beyond the older SSO scanner to generic PKCS#8/private-key headers, bearer/JWT-like tokens, password/secret assignments, URI credentials, high-entropy key material, process/argv transcript markers, and screenshot-manifest OCR/redaction status. `[VERIFIED: scripts/sso-secret-hygiene-scan.sh; Phase 48 verify-router-evidence.py]`

Tests must generate secret-like sentinel strings dynamically inside `tmp_path`; do not commit realistic high-entropy literals as fixtures.

## Security Domain and Threat Model

### Assets and trust boundaries

| Asset/boundary | Authority | Versioned representation | Forbidden representation |
|----------------|-----------|--------------------------|--------------------------|
| Server private key | Vault + restricted hydrated server state | Vault path/field name and public fingerprint only | Key value, private-key block, command output |
| Server public key | Desired state | Public value/fingerprint may be versioned | Treating it as the private key or Pro license key |
| Five target passwords | Five distinct Vault roles | Five unique Vault references | Values, shared reference, argv/history/log/screenshot |
| RustDesk client IDs | Each client | Redacted mapping/fingerprint and evidence ID | Unnecessary full inventory in broad logs |
| Permission profiles | Contract | Explicit allow/deny table | Product defaults or undocumented inheritance |
| Recovery authority | Operational review | Role/path/runbook reference | Secret material or implicit unlimited authority |
| Evidence | Phase-local evidence area | Sanitized JSON/Markdown + hashes | Secret-looking data, stale summary-only PASS |
| GSD workstreams | Explicit `--ws` scope | Namespaced artifacts + integrity manifest | Active-marker-only routing or concurrent shared writers |

### STRIDE register

Blocking rule: any unresolved `high` threat makes Phase 51 and Phase 52 advancement `BLOCKED`; `medium` risks require an owner, compensating control, and evidence ID. No risk may be silently downgraded by summary prose.

| ID | Threat | STRIDE | Severity | Required mitigation/evidence |
|----|--------|--------|----------|------------------------------|
| T-01 | Server key substitution or restore with a different identity | Spoofing/Tampering | high | Pin public fingerprint; separate private/public roles; require wrong-key negative and restore proof in later phases. |
| T-02 | Private key leaks into repo, logs, fixtures, process output, screenshots, Obsidian or GBrain | Information disclosure | high | Vault-only authority, redacted scanner, manifest screenshot status, zero-value inventory. |
| T-03 | Reused or exposed permanent target password | Information disclosure/Elevation | high | Five unique Vault references now; value distinctness proved later without stdout/argv. |
| T-04 | Over-permissive remote session | Elevation/Tampering | high | Explicit profiles, deny-by-default high-impact capabilities, negative tests per capability. |
| T-05 | OSS approved while centralized identity/policy/audit is mandatory | Repudiation/Elevation | high | Deterministic `NO-GO` and Pro selection before runtime mutation. |
| T-06 | Forced relay becomes production default or is inferred without proof | Denial of service/Tampering | high | `direct-first`, `force_relay_default=false`, allowed-purpose enum, transport evidence. |
| T-07 | Automation targets WSL, S23, or an unknown host | Tampering/Elevation | high | Exact allowlist/denylist, negative fixtures, reject unknown aliases. |
| T-08 | RustDesk disables or becomes a dependency of a legacy recovery path | Denial of service | high | Preserve five tools; reject disable/remove/port-reassignment intent in Phase 51. |
| T-09 | RustDesk lifecycle mutates Phase 48 or shared planning state | Tampering/Repudiation | high | Explicit `--ws`, serialized shared writer, nine-file baseline, fail on unexplained drift. |
| T-10 | Stale or summary-only evidence closes a requirement | Repudiation | high | Machine ledger, input hashes/timestamps, exact evidence IDs, current report required. |
| T-11 | Client IDs or session metadata are over-collected | Information disclosure | medium | Data minimization, redaction, purpose-bound retention fields. |
| T-12 | Recovery authority is implicit or unreviewed | Elevation/Repudiation | high | Named operational role, Vault path, approval/rollback boundary, human review. |

### Applicable ASVS 5.0.0 controls

ASVS 5.0.0 is the current stable release and OWASP recommends versioned IDs such as `v5.0.0-x.y.z`. `[CITED: https://owasp.org/www-project-application-security-verification-standard/]`

| ASVS area | Phase 51 application | Required evidence |
|-----------|----------------------|-------------------|
| `v5.0.0-2.1.1`, `2.2.1`, `2.2.2` | Document and enforce positive input validation for contract enums, IDs, paths, hosts, statuses, and severities at the trusted validator layer. | Schema tests and malformed/unknown-value fixtures. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x11-V2-Validation-and-Business-Logic.md]` |
| `v5.0.0-2.3.1` | Enforce ordered gates: contract/review/integrity before Phase 52. | Transition fixture cannot skip a failed/blocked check. `[CITED: same V2 source]` |
| `v5.0.0-6.1.1`, `6.3.1` | Document password/brute-force ownership and later negative-test obligations; Phase 51 does not implement RustDesk authentication internals. | Threat rows and downstream evidence reservations. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x15-V6-Authentication.md]` |
| `v5.0.0-8.1.1`, `8.2.1`, `8.2.2`, `8.3.1` | Document function/data authorization and explicit permissions; do not rely on a manipulable client-side claim. | Permission matrix and OSS enforcement limitation. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x17-V8-Authorization.md]` |
| `v5.0.0-11.4.1` | Use an approved hash for evidence/integrity checks. | SHA-256 manifest and deterministic comparison. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x20-V11-Cryptography.md]` |
| `v5.0.0-15.3.1` | Emit only required fields and redacted findings. | Report schema excludes raw matched data. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x24-V15-Secure-Coding-and-Architecture.md]` |

ASVS V16 has no L1 requirements in 5.0.0, so “ASVS L1” alone does not satisfy this phase's audit/evidence needs. Add an explicit risk-based V16 L2 subset for security logging documentation, event coverage, log protection, and safe error handling, while keeping secret values out of logs. `[CITED: https://github.com/OWASP/ASVS/blob/v5.0.0_release/5.0/en/0x25-V16-Security-Logging-and-Error-Handling.md]`

### Permission profiles

RustDesk documents local client settings for keyboard, clipboard, file transfer, audio, terminal, tunnel, restart, recording, privacy mode, and remote configuration. Central Strategy/Override/Control Role enforcement is documented in Pro, so the OSS baseline must call these desired local profiles plus compensating verification—not centralized RBAC. `[CITED: https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/#security-settings] [CITED: https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/control-role/]`

| Capability | `admin-maintenance` | `support-observe` | Rule |
|------------|---------------------|-------------------|------|
| Screen view | allow | allow | Minimum function of each profile. |
| Keyboard/mouse | allow | deny | Observe remains view-only. |
| Clipboard | allow | deny | Admin only; validate both positive/negative paths. |
| File transfer | deny | deny | Enable only by separately approved, time-bounded exception. |
| Audio | deny | deny | Not required for maintenance/observation. |
| Terminal | allow | deny | Admin only; high-impact capability. |
| TCP tunnel | deny | deny | Separate network threat model required before enabling. |
| Remote restart | allow | deny | Admin only; rollback path must remain independent. |
| Privacy mode | deny | deny | Requires separate operator/consent decision. |
| Recording | deny | deny | Evidence capture is separate and explicitly governed. |
| Remote config modification | deny | deny | Prevent session-side policy weakening. |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing/serialization | Ad-hoc line or substring parser | Python `json` with strict shape checks and `sort_keys=True` | Free-form markers can pass in the wrong section or duplicate context. |
| Integrity hash | Custom checksum | `hashlib.sha256` plus Git blob provenance | Existing repo pattern and deterministic cross-platform output. |
| Secret reporting | Print matching lines for debugging | Category/path/field-only findings | Prevent the validator from becoming a leak source. |
| Product RBAC/SSO/API/audit | Simulate Pro controls in Phase 51 | Deterministic OSS risk gate; select Pro if mandatory | Product control-plane implementation is out of scope and security-sensitive. |
| Workstream selection | Trust active marker | Explicit `--ws rustdesk-fleet` | The shared pointer is not concurrency authority. |
| Phase 48 tracking | `git ls-files` on new path only | Explicit old→new mapping + blob/SHA-256 | New path is currently untracked and would yield a false empty PASS. |

## Common Pitfalls

### False-empty Phase 48 baseline

**What goes wrong:** `git ls-files` returns no files under the new workstream and the validator calls that intact.
**Avoidance:** require exactly nine mapped files, non-empty hashes, source HEAD, no extras, and legacy blob equivalence.
**Warning sign:** `file_count: 0` or a baseline generated solely from tracked files.

### Secret scanner becomes a disclosure oracle

**What goes wrong:** failure output echoes the matched token/key/password.
**Avoidance:** report only category/path/line or JSON field; generate test sentinels at runtime.
**Warning sign:** raw line content in stdout, Markdown, CI logs, or fixture files.

### Pro absence overstated

**What goes wrong:** the contract claims OSS has no settings/logs of any kind.
**Avoidance:** state only that official centralized identity, policy, API, role, and attributed-audit controls are assigned to Pro; distinguish local client settings/logs.
**Warning sign:** a blanket “OSS has no policy/logging” sentence.

### Password distinctness proved by reading values

**What goes wrong:** Phase 51 retrieves or compares live passwords and leaks them.
**Avoidance:** now require five distinct roles/Vault references; reserve value-distinctness proof for the later runtime gate using non-output comparison.
**Warning sign:** Vault reads, values, argv, or hashes derived from low-entropy passwords in Phase 51 evidence.

### Lifecycle scanner accepts descriptive or stale text

**What goes wrong:** a valid scoped command elsewhere hides an unscoped executable command.
**Avoidance:** scan fenced shell blocks/scripts command-by-command, classify mutating GSD verbs, and require `--ws rustdesk-fleet` on each.
**Warning sign:** substring search for one occurrence of `--ws` across a whole file.

### Summary-only gate

**What goes wrong:** a narrative PASS is accepted without current inputs/hashes.
**Avoidance:** require the current JSON report, exact check IDs, input SHA-256, validator version, timestamp, and operational review.
**Warning sign:** `51-CONTRACT-VALIDATION.md` exists but has no machine report or input manifest.

## Validation Architecture

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 + Python 3.12.3 standard library `[VERIFIED: local command]` |
| Config file | Existing repository pytest discovery; no Phase 51-specific config required |
| Quick run | `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q` |
| Contract validator | `python3 modules/rustdesk-fleet/tools/validate_phase51.py --repo . --json-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.json --markdown-out .planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation/51-CONTRACT-VALIDATION.md` |
| GSD state check | `node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" query state.json --ws rustdesk-fleet --pick current_phase` |
| Preserved state check | `node "$HOME/.codex/gsd-core/bin/gsd-tools.cjs" query state.json --ws runtime-trust-codex-delivery-convergence --pick current_phase` |

### Validator check IDs

| Check ID | Requirements | Behavior | Failure fixtures |
|----------|--------------|----------|------------------|
| `P51-SCOPE-001` | SCP-01 | Exact 5 included, exact 2 excluded, no unknown/overlap | excluded host added; included host missing; alias added |
| `P51-LEGACY-001` | SCP-01 | Exact 5 legacy tools marked preserve/independent; reject remove/disable/port-change intent | missing `noVNC`; decommission action |
| `P51-PRODUCT-001` | SCP-02 | Derive GO/NO-GO/BLOCKED from mandatory controls and explicit acceptance | mandatory SSO with OSS GO; missing review |
| `P51-TRANSPORT-001` | SCP-03 | `direct-first`, `force_relay_default=false`, forced purposes allowlisted | forced-relay default; unknown fallback reason |
| `P51-SECRET-001` | SCP-01/02/03/05 security | Five unique Vault refs, separate key roles, no secret-looking values | duplicate ref; PKCS#8/token/password-like runtime sentinel |
| `P51-PERM-001` | SCP-02 | Exact profiles/capabilities; deny high-impact defaults; record OSS limitation | missing capability; support terminal allowed |
| `P51-LEDGER-001` | all 36 | Exact equality with canonical requirements; unique evidence IDs; current status rules | duplicate/orphan/missing ID; summary-only evidence |
| `P51-WS-001` | SCP-05 | Every mutating RustDesk GSD command includes exact `--ws rustdesk-fleet` | unscoped command; wrong workstream |
| `P51-P48-001` | SCP-05 | Nine old→new mappings; blob/SHA-256 match; no missing/extra files | modified file; empty manifest; extra file |
| `P51-THREAT-001` | SCP-02/05 | All assets/boundaries present; unresolved high means BLOCKED; ASVS IDs versioned | missing asset; high marked accepted without mitigation |
| `P51-REPORT-001` | all four | JSON and Markdown agree; all inputs hashed; no secret material; operational review PASS | stale hash; mismatched verdict; missing reviewer gate |

### Required fixtures

- `valid/minimal-contracts/` — full positive set with 36 pending ledger rows and a copied nine-file Phase 48 fixture manifest.
- `invalid/excluded-host.json` — mutation/evidence target set to WSL or S23.
- `invalid/duplicate-secret-ref.json` — two host roles share a Vault reference; no values.
- `invalid/forced-relay-default.json` — default forced relay.
- `invalid/missing-legacy-tool.json` — omits one fallback.
- `invalid/unscoped-gsd-command.md` — executable lifecycle command missing `--ws rustdesk-fleet`.
- `invalid/phase48-drift.json` — expected hash differs from a temp-copy file.
- `invalid/summary-only-ledger.json` — PASS row points only to a summary.
- Secret-like cases are constructed dynamically in `tmp_path`, not stored as realistic literals.

### Report schema and `51-CONTRACT-VALIDATION.md` generation

The validator writes canonical JSON first, then renders Markdown from that exact in-memory object. Required top-level fields:

```json
{
  "schema_version": 1,
  "phase": 51,
  "workstream": "rustdesk-fleet",
  "source_head": "<git-commit>",
  "validator_version": 1,
  "generated_at": "<UTC-RFC3339>",
  "inputs": [{"path": "<repo-relative>", "sha256": "<digest>"}],
  "checks": [{"id": "P51-SCOPE-001", "status": "PASS", "evidence_ids": ["P51-EV-SCOPE"]}],
  "secret_material_present": false,
  "overall_status": "PASS"
}
```

Exit codes: `0=PASS`, `1=FAIL` for asserted contract violation, `2=BLOCKED` for missing/stale/unreviewed prerequisite or invalid invocation. Markdown must include the same source HEAD, input digests, check IDs/statuses, and overall verdict. Re-parsing the Markdown is never the source of truth.

### Phase requirements to test map

| Req ID | Automated command | Human/live gate | File exists now? |
|--------|-------------------|-----------------|------------------|
| SCP-01 | focused pytest + validator checks `P51-SCOPE-001`, `P51-LEGACY-001`, `P51-SECRET-001` | Review exact fleet/fallback list | No — Wave 0 |
| SCP-02 | checks `P51-PRODUCT-001`, `P51-PERM-001`, `P51-THREAT-001` | Operator declares mandatory controls and accepts OSS absences or selects Pro | No — Wave 0 |
| SCP-03 | check `P51-TRANSPORT-001` | Review fallback purposes; no runtime test in Phase 51 | No — Wave 0 |
| SCP-05 | checks `P51-WS-001`, `P51-P48-001`, `P51-LEDGER-001` plus scoped state queries | Serialized writer confirms any legitimate Phase 48 drift/rebaseline | No — Wave 0 |

### Sampling rate

- **Per implementation task:** focused test node(s) for the changed contract/check, then the full single test file; target under 30 seconds.
- **Per plan/wave merge:** full `modules/rustdesk-fleet/tests` suite, validator report regeneration, both scoped state queries, `git diff --check`, and a secret-hygiene scan over the exact Phase 51/module paths.
- **Every GSD lifecycle transition:** run `P51-WS-001` before the command and `P51-P48-001` after it; verify both workstream states with explicit `--ws`.
- **Phase gate:** all 11 check IDs PASS, `secret_material_present=false`, current input hashes, operational review PASS, and JSON/Markdown parity before Phase 52.

### Wave 0 gaps

- [ ] `modules/rustdesk-fleet/tools/validate_phase51.py`
- [ ] `modules/rustdesk-fleet/tests/test_phase51_contracts.py`
- [ ] positive/negative fixtures listed above
- [ ] five contract JSON files and two evidence JSON files
- [ ] `51-SECURITY.md` and `51-OPERATIONAL-REVIEW.md`
- [ ] generated `51-CONTRACT-VALIDATION.json` and `51-CONTRACT-VALIDATION.md`

No framework or package installation gap exists. `[VERIFIED: Python/pytest available locally; Phase 51 scope fence]`

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | validator/tests | yes | 3.12.3 | none needed |
| pytest | focused tests | yes | 7.4.4 | `unittest` if pytest becomes unavailable, but do not change now |
| Git | blob/source provenance | yes | 2.43.0 | filesystem SHA-256 remains mandatory but does not replace source provenance |
| GNU `sha256sum` | operator spot-check | yes | coreutils 9.4 | Python `hashlib.sha256` |
| Node/GSD tools | scoped state queries | yes | Node 24.13.1 | none for GSD lifecycle |
| ripgrep | focused scans | yes | 15.1.0 | Python path iteration/regex |

## Resolved Planning Questions

1. **Are any centralized controls mandatory now? — Resolved as a blocking operational decision**
   - Known: official docs allocate the relevant centralized controls to Pro; D-03 allows OSS only for accepted single-operator risk.
   - Resolution: start `product-decision.json` as `BLOCKED`; the accountable Phase 51 operational review records all six answers and deterministically derives `GO/oss`, `NO-GO/pro`, or remains `BLOCKED`. Do not infer acceptance from the PRD.

2. **What exact Vault paths will own the RustDesk roles? — Resolved as reserved paths pending accountable approval**
   - Known: Phase 51 may record paths/names only and must not create/read values.
   - Resolution: reserve `kv/atius/rustdesk/server` for server identity/recovery metadata and `kv/atius/rustdesk/targets/<canonical-host-id>` for one target password role each. The Phase 51 operational review must record an accountable Vault owner, the five reserved references, approval status and timestamp before PASS. Value creation/hydration remains Phase 52.

3. **How is legitimate concurrent Phase 48 work handled? — Resolved by fail-closed serialization**
   - Known: Phase 48 remains active and the migrated path is currently untracked; automatic rebaseline would hide drift.
   - Resolution: serialize the writer, stop the RustDesk transition, review the Phase 48 change against its own workstream, then explicitly rebaseline with old/new provenance and reviewer reason. Automatic rebaseline is prohibited.

## Assumptions Log

No unverified factual assumption is required for the recommended plan. The three planning questions above have explicit fail-closed resolution contracts; their accountable runtime approvals remain planned gates rather than assumed answers.

## Sources

### Primary and local authoritative

- `51-CONTEXT.md`, `51-PRD.md`, workstream `REQUIREMENTS.md`, `ROADMAP.md`, and `STATE.md` — locked scope, gates, and 36-requirement truth.
- `.planning/research/rustdesk-fleet/{SUMMARY,FEATURES,ARCHITECTURE,PITFALLS}.md` — prior primary-source synthesis and rollout boundaries.
- [RustDesk self-host selection](https://rustdesk.com/docs/en/self-host/#which-rustdesk-server-should-you-choose) — OSS/Pro boundary and direct/relay flow.
- [RustDesk Server Pro](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/#when-to-choose-rustdesk-server-pro) — centralized identity, management, policy, API, and log features.
- [RustDesk Pro console](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/console/) — devices, users, roles, strategies, tokens, and logs.
- [RustDesk Pro audit logs](https://rustdesk.com/docs/en/self-host/rustdesk-server-pro/audit-logs/) — documented attributed log surfaces.
- [RustDesk advanced settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/#security-settings) — local client permission and relay settings.
- [OWASP ASVS 5.0.0](https://owasp.org/www-project-application-security-verification-standard/) — stable version and reference convention.

### Reused repository patterns

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence/tools/verify-router-evidence.py` — small fail-closed validator and exit-code pattern.
- `scripts/sso-secret-hygiene-scan.sh` — redacted category/path/line findings.
- `scripts/g18-pro-esm-inventory.py` — host allowlist and negative self-test pattern.
- `cli/omni/fleet.py` and `modules/fleet-control-plane/tests/test_m004_contract.py` — recursive redaction, stable JSON, `tmp_path`, and negative contract tests.
- `cli/omni/xrdp_abnt2.py` — streaming SHA-256 and deterministic comparison.
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/26-production-guard-boot-login-protocol/26-SECURITY.md` — STRIDE/security artifact structure.

## Metadata

**Confidence breakdown:**
- Scope and requirements: HIGH — locked in current workstream artifacts.
- Validator/evidence architecture: HIGH — composed from verified repo patterns and local tool availability.
- Phase 48 baseline: HIGH — nine-file old/new equivalence and current untracked-state risk were checked read-only.
- OSS/Pro negative claims: MEDIUM-HIGH — official documentation clearly assigns centralized features to Pro, but claims are deliberately narrowed to the documented product contract.
- ASVS mapping: HIGH — stable v5.0.0 primary sources and exact L1 IDs checked.

**Research date:** 2026-07-20
**Valid until:** 2026-08-19 for repo architecture; revalidate RustDesk product documentation at execution if the OSS/Pro decision remains open.
