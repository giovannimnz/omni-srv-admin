---
name: "atius-sso-governed-release-closeout"
description: "Use when promoting or closing out the governed Atius SSO lifecycle release for ATS, including candidate, external approval, apply/rollback/reapply, browser evidence, and Phase 11 handoff artifacts."
---

# Atius SSO Governed Release Closeout

Use this skill when the task is to operate or continue the governed rollout/closeout flow for the reusable Atius SSO lifecycle in ATS.

## When to use

- Candidate/release of the central SSO lifecycle in ATS
- Digest-bound approval flow for `10-04`
- Browser/vision/knowledge closeout for `10-05`
- Phase 11 handoff artifact generation from the central contract

Do not use this skill for:

- AdGuard app-local rollout itself
- generic OIDC debugging unrelated to the governed release flow
- non-ATS applications

## Source of truth

- Candidate and release artifacts live under:
  - `/home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/`
- Runtime code and release harness live under:
  - `/home/ubuntu/GitHub/Atius-Capital/ats/`

Read these references before mutation:

- [references/phase10-runbook.md](references/phase10-runbook.md)

## Workflow

1. Validate current candidate/release artifacts before assuming any state.
2. Never reuse approval artifacts. Approval must be externally produced, short-lived, and digest-bound.
3. Apply only after approval exists and validates.
4. After release, prove browser lifecycle and vision evidence before claiming Phase 10 complete.
5. Keep Phase 11 explicit: central contract may be ready while AdGuard facade remains unapproved.

## Hard rules

- `/login` remains the canonical human URL.
- `/sso` remains internal or compatibility-only.
- Central logout is POST-only `/api/sso/logout` with real browser `Origin`, `Content-Type: application/json`, and session-bound one-time `X-CSRF-Token`.
- `frontend/src/contexts/auth-context.tsx` must not send users directly to `GET /api/sso/logout`; use the app-local `/logout` bridge.
- Browser evidence must run headless with `workers=1`.
- No secret value may be persisted into repo docs, evidence, Obsidian, or GBrain.

## Quick commands

- Candidate validate:
  - `node /home/ubuntu/GitHub/Atius-Capital/ats/utils/scripts/validate-sso-lifecycle-release.mjs --mode candidate --report /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-candidate.json`
- Release validate:
  - `node /home/ubuntu/GitHub/Atius-Capital/ats/utils/scripts/validate-sso-lifecycle-release.mjs --mode release --report /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-04-release.json`
- Browser report validate:
  - `node /home/ubuntu/GitHub/Atius-Capital/ats/utils/scripts/validate-sso-lifecycle-browser.mjs --report /home/ubuntu/GitHub/vpn-atius/home-proxy/.planning/phases/10-atius-sso-canonical-login-and-destination-lifecycle/evidence/10-05-browser-report.json`

## Artifacts to update at closeout

- `10-04-candidate.json`
- `10-04-release-approval.json`
- `10-04-release.json`
- `10-05-browser-report.json`
- `10-05-vision-review.json`
- `10-05-knowledge-readback.json`
- `10-sso-lifecycle-interface.json`
- `10-sso-lifecycle-interface.sha256`
- `10-05-graphify-post-summary.json`

