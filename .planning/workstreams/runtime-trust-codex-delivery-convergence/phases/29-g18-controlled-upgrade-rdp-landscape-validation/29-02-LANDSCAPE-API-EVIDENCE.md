# Phase 29 Task 02: Landscape SaaS API Evidence

**Generated:** 2026-06-25T02:50:45Z
**Endpoint:** https://landscape.canonical.com/api/
**Account:** Atius (`vtqxvjv3`)
**Mode:** read-only API query, credentials not persisted in this artifact

No API key, secret key, signature, JWT, cookie, or raw API response is stored here.

## Expected fleet

| Host | API status | Landscape id | Hostname | Title | Distribution | Last ping | Last exchange | Reboot required | Access group |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `atius-srv-1` | present | 103036176 | atius-srv-1 | atius-srv-1 | 24.04 | 2026-06-25T02:50:27Z | 2026-06-25T02:44:13Z | False | global |
| `atius-srv-2` | present | 103036177 | atius-srv-2 | atius-srv-2 | 24.04 | 2026-06-25T02:50:21Z | 2026-06-25T02:43:51Z | False | global |
| `atius-srv-3` | present | 103036178 | atius-srv-3 | atius-srv-3 | 24.04 | 2026-06-25T02:50:05Z | 2026-06-25T02:44:24Z | False | global |
| `horistic-srv` | present | 103414385 | horistic-srv | horistic-srv | 24.04 | 2026-06-25T02:50:23Z | 2026-06-25T02:43:00Z | False | global |

## Decision

**Landscape SaaS evidence:** PASS

All 4 expected hosts are visible through the Landscape SaaS API.

## Local client permission note

`landscape-config --is-registered` can fail for non-root users when `/etc/landscape/client.conf` is not readable. Treat the previous non-root local check as a permission-limited probe, not authoritative offline evidence.
