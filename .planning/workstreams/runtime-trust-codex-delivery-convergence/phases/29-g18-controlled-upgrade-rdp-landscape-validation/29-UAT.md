---
status: complete
phase: 29-g18-controlled-upgrade-rdp-landscape-validation
source:
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-VERIFICATION.md
  - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/29-g18-controlled-upgrade-rdp-landscape-validation/29-11-LANDSCAPE-NEW-DASHBOARD-HOTFIX.md
updated: 2026-06-26T19:45:00-03:00
---

# Phase 29 UAT

## Current Test

number: 5
name: Landscape self-hosted modern dashboard route and theme
expected: |
  `https://landscape.atius.com.br/new_dashboard/overview` returns the modern
  SPA, dark CSS loads, public traffic reaches the Landscape API instead of
  FreeIPA, and the unavailable legacy pending-computers Overview call does not
  emit a 404 toast.
awaiting: none

## Tests

### 1. Controlled Upgrade Closeout

expected: Controlled apt execution is documented, no uncontrolled reboot,
full-upgrade or autoremove happened, and all four managed servers have no final
package drift.

result: [passed]

notes: `29-VERIFICATION.md` records the staged upgrade evidence and
`upgradable_count=0` on `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and
`horistic-srv`.

### 2. RDP Validation

expected: Microsoft RDP access remains available on all four servers after the
upgrade window.

result: [passed]

notes: Operator confirmation is recorded in
`29-02-G18-RDP-LANDSCAPE-VALIDATION.md`.

### 3. Landscape SaaS Fleet Validation

expected: All four hosts are online in Canonical Landscape SaaS.

result: [passed]

notes: `29-VERIFICATION.md` and `29-POST-UPGRADE-LANDSCAPE-API.md` record all
four hosts online.

### 4. Landscape Self-hosted Routing

expected: Public `landscape.atius.com.br` traffic reaches the self-hosted
Landscape container and deep React routes return the SPA instead of Apache/Zope
404.

result: [passed]

notes: Public probes returned `200` for `/new_dashboard/overview`, dark CSS and
dashboard JS assets. API v2 returned `401 AuthTokenInvalid` without browser JWT,
which is expected and proves traffic reaches the Landscape API service.

### 5. Modern Dashboard Dark Theme and Legacy Pending Card

expected: The modern dashboard loads the late dark-theme override and does not
call the unavailable legacy `GetPendingComputers` action on Overview.

result: [passed_with_warnings]

notes: Static assets were hotfixed in the Landscape container. Browser visual
automation was unavailable, so final appearance remains a documented warning
rather than an open UAT blocker.

## Summary

total: 5
passed: 4
passed_with_warnings: 1
issues: 0
pending: 0
blocked: 0

## Gaps

- Visual browser automation was unavailable in this session.
- If a browser keeps old cached assets, use a hard refresh before judging the
  final theme.
