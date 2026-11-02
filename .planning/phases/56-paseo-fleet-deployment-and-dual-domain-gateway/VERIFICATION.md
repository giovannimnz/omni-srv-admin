# Phase 56 Verification Report: Paseo Fleet Deployment & Dual-Domain Gateway

**Date:** 2026-11-02T23:25:00Z  
**Phase:** 56  
**Status:** **PASSED (100% GREEN)**  
**Authority:** Central Orchestrator (`2251a1d9-3260-4bde-88e2-490063470338`)  
**Worker:** Worker 1 (`7c2b86c3-8747-4b7f-a04c-a06b167fc806`)  
**Target Domains:** `https://paseo.atius.io` & `https://paseo.atius.com.br`  
**Hub Central:** `atius-srv-4` (`10.14.1.14:37845`)

---

## 1. Fleet Deployment Matrix (Landscape Self-Hosted)

All 4 fleet servers were provisioned simultaneously via Landscape Control-Plane ActivityGroup 637 and verified via ActivityGroup 644 without manual SSH loops:

| Host | Node.js | CLI Version | Port | Daemon Status | Local Port Probe | Landscape Activity |
|---|---|---|---|---|---|---|
| `atius-srv-1` | v24.22.2 | `0.14.0` | `37815` | `active (running)` | HTTP 404 (Express) | Activity 638 / 645 (PASS) |
| `atius-srv-2` | v24.22.2 | `0.14.0` | `37825` | `active (running)` | HTTP 404 (Express) | Activity 639 / 646 (PASS) |
| `atius-srv-3` | v24.22.2 | `0.14.0` | `37835` | `active (running)` | HTTP 404 (Express) | Activity 640 / 647 (PASS) |
| `atius-srv-4` | v24.22.2 | `0.14.0` | `37845` | `active (running)` | HTTP 404 (Express) | Activity 641 / 648 (PASS) |

---

## 2. Edge Gateway & Dual-Domain Public Endpoints

The Apache Edge Gateway on `atius-srv-1` was provisioned via Landscape Activity 643 (`fleet-paseo-apache-edge.sh`):

| Check | Target | Expected | Observed | Status |
|---|---|---|---|---|
| HTTPS HTTP/2 Probe | `https://paseo.atius.io/` | HTTP 404 (Express) | `HTTP/2 404` | **PASS** |
| HTTPS HTTP/2 Probe | `https://paseo.atius.com.br/` | HTTP 404 (Express) | `HTTP/2 404` | **PASS** |
| WebSocket Upgrade | `wss://paseo.atius.io/ws` | HTTP 101 Switching Protocols | `HTTP/1.1 101 Switching Protocols` | **PASS** |
| WebSocket Upgrade | `wss://paseo.atius.com.br/ws` | HTTP 101 Switching Protocols | `HTTP/1.1 101 Switching Protocols` | **PASS** |
| TLS SNI Matching (.io) | `paseo.atius.io:443` | Cloudflare Origin CA | Valid (`atius.io.pem`) | **PASS** |
| TLS SNI Matching (.com.br) | `paseo.atius.com.br:443` | Cloudflare Origin CA | Valid (`atius.com.br.pem`) | **PASS** |
| CORS Header | `Origin: paseo://app` | `access-control-allow-origin` | `paseo://app` | **PASS** |

---

## 3. Landscape Manifest & Versioned Scripts

Registered and synchronized with Self-Hosted Landscape Server (`10.13.1.13`):

1. `fleet-paseo-install` (ID 23): Rollout of `@getpaseo/cli@0.14.0`, `@getpaseo/server@0.14.0`, `paseo-agy-acp@2.7.2`, configuration, and systemd units.
2. `fleet-paseo-apache-edge` (ID 24): Apache reverse proxy and WebSocket upgrade configuration on `atius-srv-1`.
3. `fleet-paseo-status` (ID 25): Continuous health audit and port probe.

---

## 4. Resource Guardrail Conformance

- All installations executed under `renice -n 19` and `ionice -c 3`.
- Systemd units limited via `CPUQuota=20%` and `Nice=19`.
- Zero CPU spikes above 20% on any fleet server during rollout.
