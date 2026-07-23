# Plan 01 Check — Re-Review After Fixes

**Date:** 2026-04-19
**Reviewer:** GSD Plan Checker
**Scope:** Plans 01-01, 01-02, 01-03 and 01-RESEARCH for Phase 1 (Preparacao do Host)

---

## Blockers

Items that MUST be fixed before execution. If any item is present, verdict is BLOCKED.

| # | Blocker | Status | Evidence |
|---|---------|--------|----------|
| B1 | Human checkpoint in Plan 01-03 that executor can't handle | **FIXED** | Task 3 (`01-03-PLAN.md` line 202) is now `<task type="auto">` with fully scripted bash checks (8 PASS/FAIL validations), no manual intervention or human checkpoint required. All commands are executable by the agent autonomously. |
| B2 | Missing certbot fallback path after Apache2 port migration | **FIXED** | Plan 01-02 now has Task 4 (line 244) explicitly handling certbot dry-run failure. It covers: (a) webroot directory creation, (b) Apache `.well-known` alias config, (c) `certbot reconfigure --authenticator webroot`, (d) manual `.conf` editing fallback for certbot < 2.3, (e) DNS-01 recommendation if webroot also fails. |
| B3 | No-op sed command in Plan 01-02 Task 2 | **FIXED** | The sed in Task 2 Step 2 (`01-02-PLAN.md` lines 157-162) now has four distinct, non-overlapping patterns: `Listen 80`, `Listen 0.0.0.0:80`, `Listen 443` (with whitespace capture), and `Listen 0.0.0.0:443` (with whitespace capture). No redundant or duplicate sed lines remain. |

**All 3 previously reported blockers are resolved.**

---

## Warnings

Non-blocking issues that the executor should be aware of during execution.

| # | Warning | Severity | Details |
|---|---------|----------|---------|
| W1 | Broken grep pipe in Plan 01-03 Task 3, Check 4 (line 241) | Low | The verification command `ss -tlnp | grep -qE ':(9080\|9444)\s' \| grep -q apache2` has a pipe bug: the first `grep -q` consumes and exits, so the second `grep -q apache2` receives no input and will always fail (false negative). The action block commands (Steps 5-6) are correct — only the `<automated>` verify line is affected. The executor should rely on the Step 5/6 commands in the action, not the verify one-liner. |
| W2 | Silent no-op risk in Plan 01-03 Task 1, Step 3 (line 98) | Low | `sudo sed -i 's/^#DNS=.*/DNS=10.1.1.2 169.254.169.254/' /etc/systemd/resolved.conf` will silently do nothing if the `#DNS=` comment line doesn't exist (e.g., if it was already uncommented or absent). The Step 4 verification (`grep '^DNS='`) will catch this, but the sed itself won't error. |
| W3 | Plan 01-02 Task 3 certbot `--http-01-port 9080` behavior with Cloudflare proxy | Medium | If Cloudflare proxies port 80 to origin 9444 (not 9080), Let's Encrypt's ACME server connects to Cloudflare:80, Cloudflare forwards to origin:9444, but certbot binds locally on :9080. The challenge response may not reach certbot. Task 4 (webroot fallback) handles this case, but the executor should not interpret a Task 3 failure as a certbot problem — it's expected behavior in the proxied scenario. |
| W4 | Plan 01-01 Task 2 assumes snap is available | Low | `sudo snap install --classic certbot` requires snapd to be installed and running. On some minimal Ubuntu 22.04 installs (especially containers or cloud images), snapd may not be present. If snap is unavailable, the executor should fall back to `pip3 install --upgrade pyOpenSSL cryptography` as documented in RESEARCH.md line 89. |

---

## Info

Observations about the plans that are neither blockers nor warnings.

| # | Observation |
|---|-------------|
| I1 | All three plans have `autonomous: true` in their frontmatter, which is consistent with the fixes applied. |
| I2 | Plan 01-02 Task 2 correctly targets `sites-available` (symlink targets) rather than `sites-enabled` (symlinks), preventing duplicate edits. |
| I3 | Plan 01-02 Task 1 creates a rollback script (`/tmp/02-rollback-ports.sh`) before any changes are made — good practice for live production migration. |
| I4 | Plan 01-03 Task 2 is purely investigative (no changes), which is correct — Cloudflare Origin Rules updates are deferred to Phase 6 per RESEARCH.md. |
| I5 | The dependency chain is correct: 01-01 (no deps) → 01-02 (depends on 01-01) → 01-03 (depends on 01-01, 01-02). Wave numbers 1, 2, 3 are sequential. |
| I6 | RESEARCH.md is comprehensive (612 lines) and documents all pitfalls, alternatives, and assumptions. Pitfall 6 (ARM64 FreeIPA image) is correctly flagged as a Phase 3 risk, not a Phase 1 blocker. |
| I7 | Each plan's `<threat_model>` section covers STRIDE threats with specific mitigation strategies tied to the task steps. |
| I8 | Plan 01-01 has 4 tasks covering: audit, certbot fix, FQDN, chrony — all foundational dependencies for subsequent plans. |

---

## Verdict

**READY**

All 3 previously reported blockers (B1, B2, B3) are confirmed fixed. The plans are coherent, dependencies are correct, tasks are autonomous, and fallback paths exist for the critical certbot migration scenario. The 4 warnings above are execution-time awareness items, not blocking issues.
