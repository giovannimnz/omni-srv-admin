# Phase 56 Research: Paseo Fleet Deployment & Dual-Domain Gateway

**Date:** 2026-11-02  
**Researcher:** Worker 1 (`7c2b86c3-8747-4b7f-a04c-a06b167fc806`)  
**Orchestrator:** `2251a1d9-3260-4bde-88e2-490063470338`

---

## 1. Current Fleet State — Node.js & Paseo Packages

### atius-srv-1 (Edge Gateway / Apache Proxy)
- **Node.js:** `v24.22.2` via `nvm` (`~/.nvm/versions/node/v24.22.2/bin/node`)
- **npm:** `12.2.1`
- **fnm:** NOT installed (plan specifies fnm; NVM already satisfies the requirement)
- **@getpaseo/cli@0.14.0:** ✅ Installed globally
- **@getpaseo/server@0.14.0:** ✅ Installed globally
- **paseo-agy-acp:** ❌ NOT installed
- **paseo binary:** `/home/ubuntu/.nvm/versions/node/v24.22.2/bin/paseo`
- **~/.paseo/ directory:** ❌ Does NOT exist

### atius-srv-4 (This Host — Hub Central Target)
- **hostname:** `atius-srv-4.atius.internal`
- **Node.js:** v24 via nvm (same fleet-wide rollout via `fleet-runtimes-upgrade` script)
- **Apache:** NOT installed on srv-4 (Apache is on srv-1 only)

## 2. Port Availability

| Host | Paseo Port | Status |
|---|---|---|
| atius-srv-1 | 37815 | ✅ FREE (no listener on 378xx range) |
| atius-srv-2 | 37825 | Assumed free (pending probe) |
| atius-srv-3 | 37835 | Assumed free (pending probe) |
| atius-srv-4 | 37845 | Assumed free (pending probe) |

## 3. Apache Vhosts (atius-srv-1)

- **Existing Paseo vhosts:** NONE (`/etc/apache2/sites-available/*paseo*` — empty)
- **Existing Paseo enabled:** NONE (`/etc/apache2/sites-enabled/*paseo*` — empty)
- New vhost `paseo.atius.io.conf` must be created from scratch.

## 4. DNS (Cloudflare)

| Domain | Resolution | Status |
|---|---|---|
| `paseo.atius.io` | `172.67.176.236`, `104.21.51.66` | ✅ Proxied via Cloudflare |
| `paseo.atius.com.br` | `172.67.185.180`, `104.21.19.90` | ✅ Proxied via Cloudflare |

Both subdomains are already provisioned in Cloudflare DNS. No DNS work needed.

## 5. Landscape Control-Plane

- **Manifest:** 24 scripts registered; zero mention of Paseo.
- **New script needed:** `fleet-paseo-install.sh` (next ID: 25)
- **Connectivity caveat:** The Vault profile `landscape` currently holds SaaS keys, NOT self-hosted. The `omni landscape run` command requires the correct self-hosted endpoint + keys. The `omni` wrapper at `~/.local/bin/omni` handles this routing.

## 6. Systemd Units

- **Existing Paseo units:** NONE (neither system nor user-level `*paseo*` units exist)
- **Unit to create:** `paseo-daemon.service` (user-level via `~/.config/systemd/user/`)

## 7. Node.js Runtime Decision

The plan specifies `fnm` for Node.js bootstrap. However, the fleet already uses `nvm` with Node.js v24.22.2 installed fleet-wide via the `fleet-runtimes-upgrade` Landscape script. **Decision: Use existing `nvm`-managed Node.js v24 rather than introducing fnm as a second Node version manager.**

## 8. Phase Number Decision

- Highest standalone phase: 55 (`fleet-apt-cache-gdrive-drg`)
- Next available: **Phase 56**
- No collision with workstream phases (those are namespaced under workstreams)

## 9. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| fnm vs nvm conflict | Use existing nvm; skip fnm bootstrap |
| Landscape credentials mismatch (SaaS vs self-hosted) | Use `omni` CLI wrapper which handles endpoint routing |
| Port collision on 378xx range | Verified free on srv-1; verify others during Wave 1 |
| v0.14.0 patches need source locations | Must locate exact patch files or document workarounds |
| CORS config for Hub on srv-4 | Explicit allowlist for `paseo.atius.io`, `paseo.atius.com.br`, `app.paseo.sh` |
| Apache WebSocket upgrade header | Must include `RewriteEngine On` + `RewriteCond %{HTTP:Upgrade} websocket` pattern |
