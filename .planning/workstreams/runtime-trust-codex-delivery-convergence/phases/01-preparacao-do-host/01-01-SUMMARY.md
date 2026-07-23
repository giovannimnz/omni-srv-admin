---
phase: 01-preparacao-do-host
plan: "01"
subsystem: infra
tags: [fqdn, chrony, ntp, certbot, snap, dns-resolution, time-sync]

# Dependency graph
requires: []
provides:
  - FQDN resolution for ipa.atius.com.br (required by FreeIPA container in Phase 3)
  - NTP synchronization (required by Kerberos authentication in FreeIPA)
  - Working certbot v5.5.0 (required for TLS renewal on all 60+ vhosts)
  - Documented port inventory (required for Apache2 migration in Plan 01-02)
affects:
  - 01-preparacao-do-host plan 01-02 (Apache2 port migration)
  - 01-preparacao-do-host plan 01-03 (Cloudflare Origin Rules)
  - 03-freeipa-install (depends on FQDN + NTP)

# Tech tracking
tech-stack:
  added: [chrony 4.2, certbot 5.5.0 (snap), certbot-dns-cloudflare 5.5.0]
  patterns: [Oracle Cloud NTP as primary with public pool fallback]

key-files:
  created: []
  modified:
    - /etc/hosts (added ipa.atius.com.br FQDN entry)
    - /etc/chrony/chrony.conf (NTP configuration)
    - /usr/bin/certbot (symlink to snap binary)

key-decisions:
  - "Certbot reinstalled via snap (v5.5.0) instead of fixing apt pyOpenSSL incompatibility — gets modern version with reconfigure support"
  - "FQDN configured as alias in /etc/hosts keeping OS hostname as atius-srv-1 (per D-02)"

patterns-established:
  - "Oracle Cloud metadata NTP (169.254.169.254) as primary time source with public pool fallback"
  - "certbot via snap for automatic updates and reconfigure subcommand support"

requirements-completed: [PREP-01, PREP-02, PREP-04, PREP-05]

# Metrics
duration: ~5min
completed: 2026-04-19
---

# Phase 01 Plan 01: Host Preparation Foundation Summary

**FQDN resolution for FreeIPA, NTP synchronization via chrony, working certbot v5.5.0, and comprehensive port inventory audit**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-19T08:30:00Z
- **Completed:** 2026-04-19T08:35:00Z
- **Tasks:** 4/4
- **Files modified:** 3 system config files (/etc/hosts, /etc/chrony/chrony.conf, /usr/bin/certbot symlink)

## Accomplishments

- **Audit report**: Comprehensive port/vhost/certbot/chrony/systemd-resolved/Docker inventory at `/tmp/01-prep-audit-report.txt` (188 lines)
- **certbot fixed**: Broken apt certbot 1.21.0 (pyOpenSSL crash) replaced with snap certbot 5.5.0 + DNS Cloudflare plugin
- **FQDN configured**: `ipa.atius.com.br` resolves to 10.1.1.1 via `/etc/hosts`, OS hostname preserved as `atius-srv-1`
- **chrony installed and synced**: Oracle Cloud NTP primary, public pools fallback, Leap status Normal, Stratum 2

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit ports, vhosts, and certbot** — (audit report at /tmp, outside repo)
2. **Task 2: Fix certbot** — `96913f8` (fix)
3. **Task 3: Configure FQDN resolution** — `875be3f` (feat)
4. **Task 4: Install and configure chrony** — `609727d` (feat)

## Key Audit Findings

| Service | Port | Status |
|---------|------|--------|
| Apache2 | 80, 443 | Active (52 vhosts: 37 on :80, 40 on :443) |
| Docker (plane-app) | 8080→80 | Active (conflicts with D-05 Apache2 target 8080) |
| Docker (portainer) | 9443→9443 | Active (conflicts with D-05 Apache2 target 9443 is OK — D-05 uses 9444) |
| Docker (jenkins) | 8085→8080 | Active |
| Docker (open-webui) | 3001→8080 | Active (localhost only) |
| certbot | — | Was broken (1.21.0 pyOpenSSL crash), now fixed (5.5.0) |
| chrony | — | Was not installed, now active and synced |
| systemd-resolved | 127.0.0.53:53 | Active (conflict for FreeIPA BIND DNS — needs Phase 3 resolution) |

## Files Created/Modified

- `/etc/hosts` — Added `ipa.atius.com.br` as canonical name for 10.1.1.1 (was: `10.1.1.1 atius-srv-1`)
- `/etc/chrony/chrony.conf` — Full NTP configuration with Oracle Cloud primary + public fallbacks
- `/usr/bin/certbot` — Symlink to `/snap/bin/certbot` (snap certbot 5.5.0)
- `/tmp/01-prep-audit-report.txt` — Comprehensive audit report (188 lines, operational artifact)

## Decisions Made

1. **certbot via snap (not apt fix)** — Plan specified snap install; executed as written. Gets certbot 5.5.0 with `reconfigure` subcommand support and auto-updates. DNS Cloudflare plugin also installed for DNS-01 challenges (needed if HTTP-01 fails on non-standard ports).

2. **FQDN as alias, not hostname change** — Per user decision D-02, OS hostname remains `atius-srv-1`. FreeIPA container will get its own hostname via Docker `-h` flag in Phase 3.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All tasks completed without errors or blocking issues.

## Known Stubs

None — no stub patterns found in modified files.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:spoofing | /etc/chrony/chrony.conf | Oracle Cloud NTP (169.254.169.254) configured as primary — mitigated with `iburst prefer` flags, public pool fallback, and stratum verification (currently Stratum 2) |
| threat_flag:tampering | /etc/hosts | Only modified the 10.1.1.1 line — validated before/after with getent, no other lines changed |

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **FQDN resolution**: Ready for FreeIPA container (Phase 3)
- **NTP sync**: Ready for Kerberos (Phase 3)
- **certbot**: Ready for TLS renewal config updates (Plan 01-02)
- **Port inventory**: Ready for Apache2 migration planning (Plan 01-02)
- **Note**: systemd-resolved still listening on 127.0.0.53:53 — will need to be disabled before FreeIPA BIND starts (Phase 3)

## Self-Check: PASSED

All claims verified: SUMMARY.md exists, audit report at /tmp (188 lines), all 3 commits found, certbot 5.5.0 working, FQDN resolves correctly, chrony active with Normal leap status.

---
*Phase: 01-preparacao-do-host*
*Completed: 2026-04-19*
