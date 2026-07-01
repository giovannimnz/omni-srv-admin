---
phase: 29
date: 2026-06-26
status: applied
scope: landscape-selfhosted-new-dashboard
---

# Landscape New Dashboard Hotfix

## Problem

`https://landscape.atius.com.br/new_dashboard/overview` was reachable through
the root redirect, but direct deep links and some frontend data cards produced
404/loading errors.

The root causes were split:

- public DNS points to `atius-srv-1`, not directly to the Landscape LXD host;
- `atius-srv-1` was proxying to `https://10.1.1.3/`, but Phase 34 DNAT on
  `atius-srv-3` sends `10.1.1.3:443` to the FreeIPA Apache container;
- the Landscape Vite SPA needed static Apache fallback for `/new_dashboard/*`;
- the modern Overview still called the unavailable legacy
  `GetPendingComputers` action for the pending-computers card;
- the dark theme stylesheet was loaded, but needed stronger React/Vanilla
  overrides and a late cache-busted include.

## Changes Applied

- On `atius-srv-3`, the Landscape LXD container is exposed over WireGuard using
  LXD proxy devices:
  - `10.1.1.3:9443` -> Landscape container `:443`
  - `10.1.1.3:9088` -> Landscape container `:80`
- On `atius-srv-1`, Apache now proxies:
  - `/` to `https://10.1.1.3:9443/`
  - `/ping` to `http://10.1.1.3:9088/ping`
- In the Landscape container Apache vhost:
  - `/new_dashboard` is served from the local Vite dashboard directory;
  - `/assets` is served from the local Vite assets directory;
  - React deep links use `FallbackResource /new_dashboard/index.html`.
- Static dashboard assets were hotfixed:
  - `atius-dark.css` received stronger dark-mode overrides for the modern UI;
  - `index.html` includes `/assets/atius-dark.css?v=20260626-2` late in head;
  - `useInstances-0P4zwQR8.js` returns an empty pending-computers list locally
    instead of calling the unavailable legacy `GetPendingComputers` action.

Backups were created in-place before static asset mutation.

## Evidence

Public unauthenticated probes after the fix:

| Probe | Expected | Result |
|---|---|---|
| `https://landscape.atius.com.br/new_dashboard/overview` | SPA HTML | `200 text/html` |
| `https://landscape.atius.com.br/assets/atius-dark.css` | CSS asset | `200 text/css` |
| `https://landscape.atius.com.br/assets/index-_egegmLj.js` | JS asset | `200 text/javascript` |
| `https://landscape.atius.com.br/api/v2/computers` | Auth required | `401 AuthTokenInvalid` |

The `401` on `/api/v2/computers` is expected for CLI probes without the browser
JWT. It confirms that the request reaches the Landscape API service instead of
FreeIPA or a static 404.

## Residual Warning

Browser visual verification was not automated because Chrome DevTools MCP closed
the target and the local Playwright Chromium runtime was missing. The user may
need a hard refresh to discard cached dashboard assets.
