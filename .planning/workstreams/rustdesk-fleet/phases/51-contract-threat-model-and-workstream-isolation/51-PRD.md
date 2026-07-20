# Phase 51 PRD: Contract, Threat Model and Workstream Isolation

## Objective

Create a testable, secret-free contract that decides whether RustDesk Server OSS is acceptable, freezes the exact fleet scope and transport policy, defines the threat and permission model, and prevents this milestone from mutating the preserved Phase 48 workstream.

## Requirements

- **SCP-01:** Include exactly `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv`, and `GIOVANNI-W11-PC`. Exclude WSL and `GIOVANNI-S23` from package, config, service, session, and evidence automation.
- **SCP-02:** OSS is permitted only for the current single-operator scope after explicit acceptance that it does not provide mandatory SSO/OIDC, RBAC, MFA, centralized API/device policy, or human-attributed audit. If any such control is mandatory, record `NO-GO` and select Pro before runtime mutation.
- **SCP-03:** Production is direct-first. Forced relay is limited to controlled validation and proven fallback; it must not become the default fleet policy.
- **SCP-05:** All phase-local artifacts and lifecycle commands explicitly target the `rustdesk-fleet` workstream. Shared-file writers are serialized. Every transition proves that the preserved Phase 48 artifacts under `runtime-trust-codex-delivery-convergence` remain intact.

## Security Contract

- Model the server identity keypair, the public key distributed to clients, five distinct permanent target passwords, RustDesk IDs, client permission profiles, Vault hydration, redaction, evidence retention, and rollback authority as separate assets and trust boundaries.
- The server private key and permanent target passwords exist only in Vault/runtime hydration and recoverable backups. Never write their values to repo files, Markdown, shell history, process logs, screenshots, Obsidian, GBrain, test fixtures, or evidence manifests.
- Preserve RustGuac, XRDP, AnyDesk, NoMachine, and noVNC. Phase 51 must reject any decommission, disable, port reassignment, or dependency on RustDesk for its own rollback.
- Define two minimum permission profiles: `admin-maintenance` and `support-observe`. Each capability must be explicit and least-privilege; unsupported centralized enforcement in OSS must be recorded as a compensating-control limitation.

## Required Deliverables

- Machine-readable scope contract and validator.
- OSS/Pro decision record with deterministic `GO`/`NO-GO` criteria.
- Threat model and permission matrix with ASVS L1 coverage and blocking threshold `high`.
- Secret-role and Vault-path inventory containing names/paths only.
- Requirement-to-evidence ledger skeleton for all milestone requirements.
- Workstream isolation/integrity validator, including a Phase 48 baseline.
- Phase-local tests that fail on excluded hosts, duplicated passwords, secret-looking evidence, missing legacy tools, forced-relay default, unscoped GSD commands, or changed Phase 48 baseline.

## Acceptance

Automated validators must record current PASS artifacts for scope, requirement IDs, secret absence, direct-first policy, legacy-tool preservation, and workstream isolation. An operational review of the threat model and OSS/Pro decision must also pass. Summary-only claims do not satisfy the gate.

## Out of Scope

- Installing RustDesk packages or services.
- Pulling server images, opening ports, changing DNS, changing OCI rules, or creating Vault secret values.
- Selecting `atius-srv-3` as primary, changing display managers, or removing any existing remote-access path.
- Implementing Pro-only controls while the decision remains OSS.

