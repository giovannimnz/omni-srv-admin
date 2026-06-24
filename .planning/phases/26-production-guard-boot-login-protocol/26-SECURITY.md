---
phase: 26
slug: production-guard-boot-login-protocol
status: verified
threats_open: 0
threats_total: 4
threats_closed: 4
asvs_level: 1
created: 2026-06-24
updated: 2026-06-24T18:53:00Z
register_authored_at_plan_time: false
---

# Phase 26 - Security

Per-phase security contract for the Production Guard boot/login protocol.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| systemd user manager -> repo script | User units invoke the checked-in Production Guard script. | Unit command line, JSON status/doctor output |
| boot/login session -> production workloads | Boot/login checks run while PM2, RDP/XRDP, Apache and trading workloads may be live. | Scheduler trigger and read-only health probe |
| operator -> live install | Runbook gives commands that can enable recurring checks. | Human approval and `systemctl --user enable --now` |
| guard output -> journald | Unit stdout/stderr is written to user journal. | Redacted JSON health output |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-26-01 | Tampering | `production-guard.service`, `production-guard-login.service` | mitigate | ExecStart is pinned to `production_guard.py status --json` or `doctor --json`; tests reject `repair --apply`, PM2 mutation, RDP/XRDP and Apache mutation. | closed |
| T-26-02 | Denial of Service | Boot/login systemd units | mitigate | Units are `Type=oneshot`, scoped to read-only checks, and the forbidden-command scan over `production-guard*.service/timer` returned no matches. | closed |
| T-26-03 | Elevation of Privilege | Live install runbook | mitigate | Runbook requires explicit operator approval before `systemctl --user enable --now` and states repo validation happens before live install. | closed |
| T-26-04 | Information Disclosure | Journal output from `status`/`doctor` | mitigate | `production_guard.py` redacts configured sensitive fields; tests cover redaction for PM2 environment and audit payloads. | closed |

## Evidence

| Evidence | Result |
|----------|--------|
| `systemd-analyze verify --user modules/srv1-ops/systemd/production-guard.service modules/srv1-ops/systemd/production-guard.timer modules/srv1-ops/systemd/production-guard-login.service` | passed with no output |
| `PYTHONPATH=cli pytest cli/omni/tests/test_srv1_production_guard.py -q -k "boot or login or systemd or redacted"` | `4 passed, 15 deselected` |
| `rg -n "pm2 kill\|systemctl (restart\|stop) xrdp\|xrdp-sesman\|repair --apply\|apache2\|webhook.*POST\|curl .*POST" modules/srv1-ops/systemd/production-guard*.service modules/srv1-ops/systemd/production-guard*.timer` | no matches |
| `docs/operations/production-guard.md` | documents validation, RDP/XRDP impact, live-install checkpoint, troubleshooting and rollback |

## Accepted Risks Log

No accepted risks.

## Audit Notes

- No plan-time `<threat_model>` block existed for Phase 26, so this register was built retroactively from implementation files and phase artifacts.
- The broad legacy scan over all `modules/srv1-ops/systemd` still matches `pm2-ubuntu.service`; that unit predates Phase 26 and is outside the Phase 26 `production-guard*` artifact boundary.
- Phase 26 does not enable units live. It only versions files and documents the gated install procedure.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-24 | 4 | 4 | 0 | codex |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-24

