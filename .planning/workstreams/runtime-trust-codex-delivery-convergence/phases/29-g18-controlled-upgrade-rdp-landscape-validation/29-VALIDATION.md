---
phase: 29
title: "Validation - G18 controlled upgrade, RDP, Landscape SaaS and self-hosted"
date: 2026-06-26
status: passed_with_warnings
requirements:
  - G18-02
  - G18-03
  - G18-04
  - G18-05
---

# Phase 29 Validation

## Validation Result

Phase 29 validates as complete with warnings.

## Evidence Reviewed

- `29-VERIFICATION.md` is marked `status: passed`.
- Controlled apt execution and final drift evidence are recorded in the phase
  artifacts.
- RDP validation was confirmed by the operator for all four managed hosts.
- Landscape SaaS showed all four hosts online.
- Landscape self-hosted public routing was repaired and recorded in
  `29-11-LANDSCAPE-NEW-DASHBOARD-HOTFIX.md`.

## Additional Runtime Checks

The modern dashboard route and assets were checked through public HTTP probes:

- `/new_dashboard/overview` -> `200 text/html`
- `/assets/atius-dark.css` -> `200 text/css`
- `/api/v2/computers` without browser auth -> `401 AuthTokenInvalid`

The unauthenticated API `401` is expected and confirms that public traffic
reaches the Landscape API service.

## Nyquist Gap Review

| Axis | Result | Notes |
|---|---|---|
| Functional | PASS | Upgrade, RDP, SaaS online status and self-hosted routing are covered. |
| Integration | PASS | `srv1` public Apache, WireGuard to `srv3`, LXD proxy and container Apache are documented. |
| Security | PASS | No secrets were copied into artifacts; unauthenticated API remains protected. |
| Rollback | PASS | Remote static assets and Apache configs were backed up before mutation. |
| Observability | WARN | Browser visual automation was unavailable. |

## Residual Warnings

- Observability remains yellow rather than fully green.
- Disk pressure warnings on `atius-srv-1` and `atius-srv-2` remain outside this
  validation.
- The user should hard-refresh the browser if old dashboard assets are cached.
