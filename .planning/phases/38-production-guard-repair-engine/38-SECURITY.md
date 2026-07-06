---
phase: 38
slug: production-guard-repair-engine
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 38 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| Operator to repair planner | Operator can request `repair --dry-run --json` and gated apply commands. | Repair candidates and approval flags |
| Repair planner to live host | Only allowlisted commands may be planned/applied. | Controlled service/container actions |
| Repair audit trail | Snapshots and audit JSONL record approved actions. | Redacted operational metadata |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-38-01 | Elevation of Privilege | Repair apply gate | high | mitigate | Repair is dry-run by default; apply requires explicit scope, target and production-risk confirmation. | closed |
| T-38-02 | Denial of Service | Forbidden operations | high | mitigate | Code and verification block PM2 daemon teardown, XRDP/RDP restart, Apache mutation and webhook POST. | closed |
| T-38-03 | Repudiation | Repair execution trail | high | mitigate | Snapshots and `audit.jsonl` are documented before apply; dry-run output includes rollback hints and blocked reasons. | closed |

## Accepted Risks Log

No accepted risks.

## Evidence

- `38-VERIFICATION.md` records compile, focused repair tests, dry-run and forbidden command scan as passed.
- `modules/srv1-ops/scripts/production_guard.py` includes `_forbidden_reason` checks for XRDP, Apache and POST operations.
- `38-UAT.md` records 3/3 UAT checks passed.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|---|---:|---:|---:|---|
| 2026-07-05 | 3 | 3 | 0 | Codex inline secure-phase |

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

Approval: verified 2026-07-05
