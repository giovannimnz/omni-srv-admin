---
phase: 01-preparacao-do-host
plan: "02"
subsystem: infra
tags: [apache2, port-migration, certbot, webroot, vhost, sed-batch]

# Dependency graph
requires:
  - 01-01 (certbot fixed, FQDN configured, chrony synced)
provides:
  - Apache2 serving on ports 9080/9444 (frees 80/443 for FreeIPA)
  - certbot configured with webroot authenticator for non-standard ports
  - Rollback script at /tmp/02-rollback-ports.sh
affects:
  - 01-preparacao-do-host plan 01-03 (Cloudflare Origin Rules must update before releasing 80/443)
  - 03-freeipa-install (needs ports 80/443 free)

# Tech tracking
tech-stack:
  added: [webroot authenticator for certbot]
  patterns: [batch sed migration with dry-run verification, webroot fallback for non-standard ports]

key-files:
  created:
    - /tmp/02-migration-dryrun.txt (210-line dry-run report)
    - /tmp/02-rollback-ports.sh (rollback script)
    - /etc/apache2/conf-available/certbot.conf (webroot Alias directive)
    - /var/www/certbot/.well-known/acme-challenge/ (webroot directory)
  modified:
    - /etc/apache2/ports.conf (Listen 80->9080, Listen 443->9444)
    - /etc/apache2/sites-available/*.conf (37 vhosts :80->9080, 40 vhosts :443->9444)
    - /etc/apache2/sites-enabled/*.conf (direct files also migrated)
    - /etc/letsencrypt/renewal/*.conf (24 configs: authenticator apache->webroot)

key-decisions:
  - "sites-enabled contained both symlinks AND direct files — migrated both locations (deviation from plan which assumed only symlinks)"
  - "certbot renew --dry-run --http-01-port 9080 fails because Cloudflare still proxies to port 443 (Plan 03 must update Origin Rules first) — switched to webroot authenticator manually via sed instead of certbot reconfigure (which also tries validation)"
  - "certbot reconfigure command attempts live validation, not just config changes — used manual sed edit of renewal configs instead"

# Metrics
duration: ~15min
completed: 2026-04-19
---

# Phase 01 Plan 02: Apache2 Port Migration Summary

**Migrate Apache2 from ports 80/443 to 9080/9444 across 54+ vhosts with certbot webroot fallback**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-19T05:35:00Z
- **Completed:** 2026-04-19T05:55:00Z
- **Tasks:** 4/4 (Tasks 3+4 combined — webroot fallback was required)
- **Files modified:** 54+ vhost configs, ports.conf, 24 certbot renewal configs

## Accomplishments

- **Dry-run audit**: Complete migration preview at `/tmp/02-migration-dryrun.txt` (210 lines) with vhost counts, sed diffs, hardcoded port check, and rollback script
- **Port migration**: All 37 HTTP vhosts migrated :80->:9080, all 40 HTTPS vhosts migrated :443->:9444
- **Apache2 verified**: Listening on 9080 (HTTP 200) and 9444 (HTTPS 403 — expected, no default vhost), NOT on 80/443
- **certbot webroot**: All 24 renewal configs switched from apache to webroot authenticator with `/var/www/certbot` webroot path
- **Rollback script**: `/tmp/02-rollback-ports.sh` created and executable

## Task Commits

1. **Task 1: Dry-run audit** — (artifacts at /tmp, outside repo)
2. **Task 2: Batch port migration** — (system config changes, outside repo)
3. **Task 3: certbot verification** — apache authenticator fails on port 9080 (Cloudflare still proxies to 443)
4. **Task 4: Webroot fallback** — all 24 renewal configs switched to webroot authenticator

## Key Findings

| Finding | Impact | Resolution |
|---------|--------|------------|
| sites-enabled has direct files (not just symlinks) | 25 files missed by sites-available sed | Migrated sites-enabled directly as well |
| certbot renew --dry-run hangs on 25 certs | Takes 10+ minutes for full dry-run | Tested single cert instead |
| Cloudflare still proxies to 443 | HTTP-01 challenge fails on port 9080 | Expected — Plan 03 must update Origin Rules |
| certbot reconfigure tries live validation | Cannot use for offline config changes | Manual sed edit of renewal configs |
| vnc.atius-srv-1.atius.com.br broken cert | Symlink error in renewal config | Skipped — pre-existing issue, not caused by migration |

## Verification Results

| Check | Result |
|-------|--------|
| `apache2ctl configtest` | Syntax OK |
| Apache on :9080 | YES (HTTP 200) |
| Apache on :9444 | YES (HTTPS 403) |
| Apache on :80 | NO |
| Apache on :443 | NO |
| SSL cert paths unchanged | YES (Cloudflare origin certs) |
| Vhost count matches before/after | YES (37+40 -> 37+40) |
| certbot lists certificates | YES (24 valid, 1 broken pre-existing) |
| Webroot configs in place | YES (24 configs updated) |
| Rollback script exists | YES (/tmp/02-rollback-ports.sh) |

## Decisions Made

1. **Migrated sites-enabled directly** — Plan assumed sites-enabled were all symlinks to sites-available, but 25 files were direct copies (placed there manually or by certbot). Applied sed to both directories to ensure complete migration.

2. **Manual sed for certbot configs** — `certbot reconfigure` subcommand attempts live ACME validation, not just config changes. Since Cloudflare still proxies to port 443 (Plan 03 will fix this), validation fails. Used direct sed edits on renewal config files instead.

3. **Webroot as default authenticator** — All 24 renewal configs switched from `authenticator = apache` to `authenticator = webroot` with `webroot_path = /var/www/certbot`. This is permanent — even after Plan 03 updates Cloudflare Origin Rules, webroot is more reliable for non-standard ports.

## Deviations from Plan

### Deviation 1: sites-enabled direct files
- **Found during:** Task 2
- **Issue:** Plan assumed sites-enabled were all symlinks to sites-available. In reality, 25 files were direct copies in sites-enabled that were not touched by the sites-available sed.
- **Fix:** Applied same sed batch to sites-enabled directory directly.
- **Files modified:** 25 direct files in /etc/apache2/sites-enabled/
- **Type:** Rule 2 (missing critical functionality — incomplete migration)

### Deviation 2: certbot reconfigure uses live validation
- **Found during:** Task 4
- **Issue:** `certbot reconfigure --authenticator webroot` attempts live ACME validation, not just config changes. This fails because Cloudflare still proxies to port 443 (Plan 03 task).
- **Fix:** Used manual `sed` to edit authenticator and webroot_path in each renewal config file.
- **Files modified:** 24 files in /etc/letsencrypt/renewal/
- **Type:** Rule 3 (blocking issue — certbot reconfigure command doesn't work as expected)

## Issues Encountered

1. **certbot renew --dry-run hangs** — With 25 certificates to check, the dry-run takes 10+ minutes. Single-cert test shows HTTP-01 challenge fails with "unauthorized" (521) because Cloudflare proxies to port 443, not 9444. This is expected and will be resolved by Plan 03 (Cloudflare Origin Rules update).

2. **vnc.atius-srv-1.atius.com.br broken renewal config** — Pre-existing issue: "expected cert.pem to be a symlink" error. Not caused by this migration. Needs manual investigation.

## Known Stubs

None — no stub patterns in configuration files.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:tampering | /etc/apache2/ports.conf | Listen directives changed from 80/443 to 9080/9444 — verified with configtest before reload |
| threat_flag:tampering | /etc/apache2/sites-available/*.conf | Batch sed on 54+ vhost files — mitigated by dry-run first, rollback script, and post-migration vhost count verification (37+40 before = 37+40 after) |
| threat_flag:tampering | /etc/apache2/sites-enabled/*.conf | Additional 25 direct files migrated — same mitigations as above |
| threat_flag:tampering | /etc/letsencrypt/renewal/*.conf | Authenticator changed from apache to webroot — verified certbot can parse all configs after changes |
| threat_flag:denial | Cloudflare Origin Rules | Cloudflare still proxies to port 443 — Plan 03 MUST update Origin Rules to 9444 before ports 80/443 are released to FreeIPA |

## User Setup Required

- **Cloudflare Origin Rules** (Plan 03): Must update to route port 443 -> origin:9444 for all *.atius.com.br domains. Until then, certbot renewals will fail via HTTP-01 challenge (Cloudflare connects to port 443, Apache2 is on 9444).

## Next Phase Readiness

- **Ports 80/443**: Freed from Apache2 (Apache2 no longer listens on these ports)
- **Ports 9080/9444**: Apache2 serving content, all vhosts migrated
- **certbot**: Configured with webroot authenticator for non-standard ports
- **Blocker for FreeIPA**: Cloudflare Origin Rules must be updated (Plan 03) BEFORE ports 80/443 can be bound to FreeIPA container
- **Blocker for certbot renewal**: Same — Cloudflare Origin Rules update needed, OR DNS-01 challenge via Cloudflare API as fallback

## Self-Check: PASSED

All claims verified: SUMMARY.md exists, dry-run report at /tmp (210 lines), rollback script at /tmp (executable), Apache2 listening on 9080/9444, NOT on 80/443, 24 certbot configs updated to webroot, vhost counts match (37+40).

---
*Phase: 01-preparacao-do-host*
*Completed: 2026-04-19*
