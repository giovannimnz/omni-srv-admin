---
phase: 42
phase_name: "atius-wide-sso-login-on-sso-atius-com-br"
project: "Omni Srv Admin (omni-srv-admin)"
generated: "2026-07-10T05:00:00-03:00"
counts:
  decisions: 5
  lessons: 5
  patterns: 5
  surprises: 5
missing_artifacts:
  - "42-03-SUMMARY.md"
  - "42-VERIFICATION.md"
  - "42-UAT.md"
---

# Phase 42 Learnings: atius-wide-sso-login-on-sso-atius-com-br

## Decisions

### `sso.atius.com.br` Owns the Login UX
The canonical login experience must live on `sso.atius.com.br`, not on raw Keycloak pages.

**Rationale:** The ATS facade needs to control `return_to`, callback handling, cookie re-issuance, and logout behavior while preserving legacy ATS session semantics.
**Source:** 42-02-SUMMARY.md

---

### Keycloak Stays Identity-Only While ATS DB Stays Authoritative for RBAC
The OIDC bridge may identify the user, but ATS DB flags and `permissions.js` remain the authorization source.

**Rationale:** This preserves existing protected-route behavior and prevents Keycloak claims from becoming an accidental authorization backend.
**Source:** 42-01-SUMMARY.md

---

### Live Auth Validation Must Fail Closed on Missing Environment
Wave 0 validation removed fallback credentials and made live auth smoke depend only on explicit `SSO_*` and `ADMIN_*` environment variables.

**Rationale:** The phase treats missing auth material as a hard gate and avoids leaking credentials or smuggling unapproved live checks into the repo.
**Source:** 42-01-SUMMARY.md

---

### `return_to` Must Be Strictly Allowlisted by Scheme, Host, and Path
Redirect targets must be normalized server-side and accepted only for exact approved hosts and bounded path prefixes.

**Rationale:** This closes open-redirect risk while still allowing app-to-app handoff across the ATS system surface.
**Source:** 42-01-PLAN.md, 42-02-SUMMARY.md

---

### Logout Must Be Global but Backward-Compatible
The logout path must clear both legacy ATS cookie variants and only hand off to Keycloak end-session when explicitly enabled.

**Rationale:** This prevents cookie residue and avoids loops while keeping rollback and compatibility manageable.
**Source:** 42-02-SUMMARY.md, 42-VALIDATION.md

---

## Lessons

### Redirect Safety Needs Executable Tests Before Implementation
It was not enough to describe allowlists in prose; the phase needed a concrete Jest matrix for accepted and rejected `return_to` payloads before facade work was safe.

**Context:** Wave 0 established that the redirect contract itself was the safety boundary for all later SSO work.
**Source:** 42-01-SUMMARY.md

---

### Browser-Based Logout Needs Its Own E2E Contract
Logout correctness is not captured by backend tests alone because cookie cleanup and redirect loops only become obvious in browser flows.

**Context:** The Playwright logout contract was treated as a first-class requirement before publication.
**Source:** 42-01-SUMMARY.md

---

### The ATS Facade Solves Problems a “Pure Keycloak Host” Cannot
The team learned that a plain Keycloak login host would not be sufficient because ATS must own the allowlist, callback bridge, and legacy `auth-token` issuance.

**Context:** The implementation decision came from coupling between UX, redirect safety, and ATS session compatibility.
**Source:** 42-02-SUMMARY.md

---

### Forwarded Header Drift Is a Real Production Risk
The phase repeatedly treated `X-Forwarded-*` as fragile enough to deserve explicit contracts and smoke scripts for each ATS app host.

**Context:** A raw successful `curl` was considered insufficient evidence without status/header assertions and host-specific redirect checks.
**Source:** 42-01-SUMMARY.md, 42-03-PLAN.md, 42-VALIDATION.md

---

### Publication Work Should Stay Manual-Gated Even After Code Is Ready
Even with ATS code and tests green, DNS, Cloudflare, Apache reload, and Keycloak client mutation remained a separate human checkpoint.

**Context:** The planning state explicitly kept `42-03` open after `42-01` and `42-02` were complete, showing that live edge rollout is a different class of risk.
**Source:** 42-03-PLAN.md, .planning/STATE.md

---

## Patterns

### Redirect Validation Pattern
Centralize redirect validation in one utility and reuse it in middleware, login routes, callback routes, logout handling, and UI display.

**When to use:** Any SSO or cross-app navigation surface that accepts a destination URL and must be protected from open redirects.
**Source:** 42-02-SUMMARY.md

---

### Identity Bridge Pattern
Split callback handling cleanly: the Next layer validates browser state, the backend exchanges the OIDC code, maps one ATS user, and only the legacy cookie returns to the browser.

**When to use:** Any migration where an external IdP must preserve a preexisting local session contract.
**Source:** 42-02-SUMMARY.md

---

### Env-Only Live Smoke Pattern
Runtime auth tests should refuse to run without explicit operator-provided environment variables and must never hide fallback credentials in test code.

**When to use:** Any live integration smoke that touches auth, secrets, or real production identity systems.
**Source:** 42-01-SUMMARY.md

---

### Header-and-Status Smoke Pattern
Edge smoke should assert HTTP status, redirect `Location`, discovery JSON, cookie behavior, and forwarded-header expectations instead of treating “curl did not error” as success.

**When to use:** Apache/Cloudflare/edge publication gates and any reverse-proxy rollout that can silently drift.
**Source:** 42-01-SUMMARY.md, 42-03-PLAN.md

---

### No-Secrets Evidence Pattern
Documentation, scripts, worklogs, and summaries should record only timestamps, hosts, paths, pass/block results, and backup locations while keeping values redacted or absent.

**When to use:** Any SSO, identity, token, or cookie work where the evidence itself can become a leakage vector.
**Source:** 42-03-PLAN.md, 42-VALIDATION.md

---

## Surprises

### Wave 0 Produced More Value Than a Typical “Test Prep” Step
What looked like a preliminary validation wave actually defined core contracts for redirect safety, bridge behavior, logout, and secret hygiene.

**Impact:** The implementation phase became narrower and safer because risky decisions were forced into executable artifacts first.
**Source:** 42-01-SUMMARY.md

---

### The Facade Needed to Preserve Local Login Semantics, Not Replace Them
The SSO system did not simply swap ATS credentials for Keycloak; it had to keep the existing `auth-token` lifecycle and RBAC semantics intact.

**Impact:** This shaped both the frontend shell and the backend bridge, and it ruled out a simpler “just redirect to Keycloak” approach.
**Source:** 42-02-SUMMARY.md

---

### Edge Publication Was Still Open Even After the Core SSO Implementation Was Complete
The phase status in `STATE.md` showed that code completion and edge publication readiness are not the same thing.

**Impact:** Manual infra gates, backups, and rollback posture remained mandatory, which affects how future teams should scope “done”.
**Source:** .planning/STATE.md

---

### Missing `42-03-SUMMARY.md` Is Itself a Signal
The absence of a completion summary for the publication wave highlights that the most operationally sensitive step had not been closed with the same rigor as the earlier implementation waves.

**Impact:** Future work should treat the publication/rollback summary as essential, not optional, because that is where the live cutover truth gets captured.
**Source:** phase artifact inventory

---

### The Canonical Runbook Became Part of the Architecture
`docs/domain/atius-wide-sso.md` is not just a supporting note; it encodes contracts around host ownership, env keys, cookie policy, publication sequence, and rollback.

**Impact:** Future SSO changes should treat the runbook as architecture, not as after-the-fact documentation.
**Source:** docs/domain/atius-wide-sso.md
