# Phase 50 Validation - Atius-wide SSO Closeout

## Required Proof

- DNS/Apache/Cloudflare/TLS and Keycloak client assertions pass.
- `return_to` accepts only approved HTTPS hosts and rejects open redirects.
- ATS login preserves `auth-token`, `is_admin` and `can_access_*` RBAC.
- Trade, painel, dashboard, backtest, strategy and approved remote surfaces
  complete login/callback flow.
- Global logout clears Keycloak, host-only and `.atius.com.br` cookies.
- Legacy auth remains available until the acceptance matrix is complete.
- Browser bundles, logs and repo contain no client/session secrets.
- Chromium headless Chrome DevTools captures network, console and accessibility
  evidence for positive and negative flows.

## Stop Conditions

- Missing backup or invalid service certificate.
- Open redirect, RBAC mismatch, cookie not cleared or operator lockout.
- Any app requires embedding privileged tokens in browser state.
- Rollback cannot restore the prior Apache/Keycloak/app configuration.

## Rollback

Restore backed-up vhosts/client/app configuration, reload only validated
services, revert DNS/proxy changes if applied, invalidate test sessions and
repeat legacy login plus protected-route smokes.

## Completion Evidence

Static assertions, live browser matrix, RBAC comparison, cookie/logout proof,
secret scan, backup paths, rollback rehearsal and durable closeout notes.
