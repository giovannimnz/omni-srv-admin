---
phase: 39
slug: production-guard-boot-login-protocol
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 39 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|---|---|---|
| systemd user units to Production Guard | Boot/login units invoke guard checks. | Host health evidence |
| Operator to live install | Enabling units requires explicit operator approval. | systemd user unit activation |
| Runbook to rollback | Rollback commands disable only the guard units. | systemd user unit state |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|---|---|---|---|---|---|---|
| T-39-01 | Denial of Service | Boot/login units | high | mitigate | Units are documented and verified as read-only, running only `status --json` or `doctor --json`; no repair apply path is enabled. | closed |
| T-39-02 | Tampering | Live enablement | high | mitigate | Runbook requires an explicit manual checkpoint before enabling automatic boot/login checks. | closed |
| T-39-03 | Denial of Service | Rollback | medium | mitigate | Rollback stops/disables only Production Guard user units and does not restart PM2, XRDP or Apache. | closed |

## Accepted Risks Log

No accepted risks.

## Evidence

- `39-VERIFICATION.md` records `systemd-analyze verify`, focused boot/login tests and read-only units as passed.
- `docs/operations/production-guard.md` records install checkpoint and rollback commands.
- `39-UAT.md` records 3/3 UAT checks passed.

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
