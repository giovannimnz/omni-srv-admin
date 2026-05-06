---
phase: 01-preparacao-do-host
plan: "03"
subsystem: infra
tags: [systemd-resolved, dns, port-53, cloudflare, origin-rules, phase-validation]

# Dependency graph
requires:
  - 01-01 (FQDN configured, chrony synced, certbot fixed)
  - 01-02 (Apache2 migrated to 9080/9444)
provides:
  - Port 53 freed for FreeIPA BIND DNS (systemd-resolved stub disabled)
  - DNS resolution preserved with upstream servers (10.1.1.2, 169.254.169.254)
  - Cloud-init protected from overwriting /etc/resolv.conf
  - Cloudflare Origin Rules investigation report and update script template
  - Full Phase 1 validation report (all 8 checks PASS)
affects:
  - 03-freeipa-install (needs port 53 free for BIND)
  - Cloudflare Origin Rules update (requires API credentials)

# Tech tracking
tech-stack:
  added: []
  patterns: [systemd-resolved stub disable while preserving upstream DNS, cloud-init resolv.conf protection]

key-files:
  created:
    - /tmp/03-cloudflare-api-report.txt (174-line Cloudflare investigation report)
    - /tmp/03-cloudflare-update.sh (template API update script)
    - /tmp/03-all-hostnames.txt (66 hostnames from Apache2 vhosts)
    - /tmp/03-phase-validation-report.txt (Phase 1 validation, all PASS)
  modified:
    - /etc/systemd/resolved.conf (DNSStubListener=no, DNS=10.1.1.2 169.254.169.254)
    - /etc/resolv.conf (automatically updated by resolvconf after stub disable)
    - /etc/cloud/cloud.cfg (manage_resolv_conf: false added)

key-decisions:
  - "Cloud-init manage_resolv_conf setting was absent (not 'true') — added explicit 'false' to prevent future overwrites"
  - "resolv.conf managed by resolvconf package (not systemd symlink) — stub disable automatically removed 127.0.0.53 from nameserver list"

# Metrics
duration: ~5min
completed: 2026-04-19
---

# Phase 01 Plan 03: DNS Stub Disable and Phase Validation Summary

**systemd-resolved stub disabled on port 53 for FreeIPA BIND, Cloudflare Origin Rules investigated, full Phase 1 validation complete**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-19T08:35:00Z
- **Completed:** 2026-04-19T08:40:00Z
- **Tasks:** 3/3
- **Files modified:** 3 system config files + 4 operational artifacts

## Accomplishments

- **systemd-resolved stub disabled**: DNSStubListener=no configured, port 53 freed, upstream DNS preserved
- **Cloud-init protected**: manage_resolv_conf: false added to prevent /etc/resolv.conf overwrites on reboot
- **Cloudflare investigated**: 66 hostnames catalogued, API credentials status documented, update script template created
- **Phase 1 validated**: All 8 success criteria checks PASS — host is ready for FreeIPA

## Task Commits

System configuration changes (outside git repo) — tracked via operational artifacts:

1. **Task 1: Disable systemd-resolved stub on port 53** — /etc/systemd/resolved.conf, /etc/resolv.conf, /etc/cloud/cloud.cfg modified
2. **Task 2: Investigate Cloudflare Origin Rules API** — /tmp/03-cloudflare-api-report.txt (174 lines), /tmp/03-cloudflare-update.sh (template), /tmp/03-all-hostnames.txt (66 hostnames)
3. **Task 3: Final Phase 1 validation** — /tmp/03-phase-validation-report.txt (all 8 checks PASS)

## Files Created/Modified

- `/etc/systemd/resolved.conf` — DNSStubListener=no, DNS=10.1.1.2 169.254.169.254
- `/etc/resolv.conf` — Automatically updated by resolvconf: 127.0.0.53 removed, 169.254.169.254 added
- `/etc/cloud/cloud.cfg` — manage_resolv_conf: false added after preserve_hostname
- `/tmp/03-cloudflare-api-report.txt` — Cloudflare investigation (174 lines)
- `/tmp/03-cloudflare-update.sh` — Template API update script (requires CF_API_TOKEN, CF_ZONE_ID)
- `/tmp/03-all-hostnames.txt` — 66 hostnames from Apache2 vhosts
- `/tmp/03-phase-validation-report.txt` — Phase 1 validation (all PASS)

## Decisions Made

1. **Explicit cloud-init protection** — The `manage_resolv_conf` setting was absent from cloud.cfg (neither true nor false). Added explicit `false` to prevent cloud-init from overwriting /etc/resolv.conf on next boot/reboot.

2. **No resolv.conf symlink conversion** — Research (Pattern 3) suggested converting resolv.conf to a systemd symlink, but the current resolvconf-managed setup works correctly. After stub disable, resolvconf automatically updated the file to remove 127.0.0.53. No manual intervention needed.

## Deviations from Plan

None - plan executed exactly as written.

### Note on CHECK 4 verification

The plan's automated verification for CHECK 4 (`ss -tlnp | grep apache2`) didn't show process names without root privileges in the ss output. Confirmed via `lsof` that Apache2 IS listening on 9080/9444 (PID 1954). The validation report was corrected to reflect PASS status.

## Issues Encountered

1. **ss output missing process names** — `ss -tlnp` doesn't show process names in this execution context. Used `lsof` as alternative to confirm Apache2 is on the correct ports. This is an execution environment limitation, not a system issue.

## Known Stubs

None — no stub patterns in configuration files.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag:availability | /etc/systemd/resolved.conf | DNSStubListener disabled — mitigated by preserving upstream DNS (10.1.1.2, 169.254.169.254) and verifying resolution works post-restart |
| threat_flag:integrity | /etc/cloud/cloud.cfg | manage_resolv_conf set to false — prevents cloud-init from overwriting DNS config on reboot, protects against configuration drift |

## User Setup Required

- **Cloudflare Origin Rules update**: Requires Cloudflare API token with "Zone Rulesets: Edit" permission and Zone ID for atius.com.br. Template script at `/tmp/03-cloudflare-update.sh`. Until updated, Cloudflare proxies port 443 to origin 443 (nothing listening) — HTTPS traffic via Cloudflare returns 521.

## Next Phase Readiness

- **Port 53**: FREE — systemd-resolved stub disabled, ready for FreeIPA BIND
- **DNS resolution**: WORKING — upstream 10.1.1.2 reachable
- **Ports 80/443**: FREE from Apache2, ready for FreeIPA container
- **Apache2**: Serving on 9080/9444, all 60+ vhosts migrated
- **certbot**: Working (5.5.0), webroot authenticator configured
- **NTP**: chrony synced, Leap status Normal
- **FQDN**: ipa.atius.com.br resolves to 10.1.1.1
- **BLOCKER**: Cloudflare Origin Rules must be updated before FreeIPA container can receive HTTPS traffic (Cloudflare still proxies to old port 443)

## Phase 1 Complete Validation Summary

| Check | Status |
|-------|--------|
| CHECK 1: FQDN Resolution | PASS — ipa.atius.com.br → 10.1.1.1 |
| CHECK 2: NTP Synchronization | PASS — chrony active, Leap status Normal |
| CHECK 3: Ports 80/443 Free | PASS — Apache2 no longer on 80/443 |
| CHECK 4: Apache2 on 9080/9444 | PASS — confirmed via lsof |
| CHECK 5: Port 53 Free | PASS — systemd-resolved stub disabled |
| CHECK 6: DNS Resolution | PASS — dig returns results |
| CHECK 7: Certbot | PASS — certbot 5.5.0 |
| CHECK 8: Port Matrix | PASS — all ports in expected state |

## Self-Check: PASSED

All claims verified: SUMMARY.md exists, validation report at /tmp (all PASS), Cloudflare report at /tmp (174 lines), hostname list at /tmp (66 entries), update script template created, all system config changes applied and verified.

---
*Phase: 01-preparacao-do-host*
*Completed: 2026-04-19*
