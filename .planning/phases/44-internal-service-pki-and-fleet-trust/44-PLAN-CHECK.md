# Phase 44 Plan Check

**Status:** passed-with-implementation-gate
**Checked:** 2026-07-05

## Goal Backward Check

The operator asked for:

1. each server to have its own certificate;
2. those certificates/trust to be installed across the fleet;
3. the capability to become an `omni-srv-admin` feature;
4. complete validation before execution;
5. remote SSH generation/validation where needed.

The plan set covers this as:

- `44-01`: repo feature surface, CLI, templates, tests and dry-run behavior.
- `44-02`: controlled remote bootstrap, CA/CSR/leaf installation and backups.
- `44-03`: 4x4 HTTPS matrix, docs, Obsidian and GBrain closeout.

## Critical Correction

Do not install each peer leaf as a trusted root. That creates revocation and
trust-boundary problems. The planned implementation gives each server its own
leaf cert/key, installs the CA chain into every trust store, and optionally
copies peer public leafs as evidence/pinning material.

## Blocking Gates Before Execution

- User approval to begin live CA/key generation.
- Confirm whether the service CA should remain file-backed on `atius-srv-1`
  for v1, or whether this phase should first integrate HashiCorp Vault PKI.
- Confirm whether Windows trust-store import belongs in Phase 44 or a follow-up.

## Verification Adequacy

The validation plan is sufficient for the fleet trust objective because it
requires local certificate checks plus all 12 remote source-target HTTPS checks.
It does not claim service-specific HTTPS migration until those services receive
their own gates.
