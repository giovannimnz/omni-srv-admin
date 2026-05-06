---
phase: 01-preparacao-do-host
verified: 2026-04-19T06:05:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: N/A
  previous_score: N/A
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 01: Preparação do Host Verification Report

**Phase Goal:** Prepare Ubuntu 22.04 host to receive FreeIPA in Phase 3 — FQDN resolution, NTP sync, free ports 80/443 from Apache2, migrate Apache2 to 9080/9444, disable systemd-resolved stub on port 53
**Verified:** 2026-04-19T06:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                    | Status     | Evidence                                                                                   |
| --- | -------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------ |
| 1   | `ipa.atius.com.br` resolves to 10.1.1.1                  | ✓ VERIFIED | `getent hosts ipa.atius.com.br` returns `10.1.1.1`; `/etc/hosts` line: `10.1.1.1  ipa.atius.com.br  atius-srv-1` |
| 2   | chrony is installed and synchronized                      | ✓ VERIFIED | `systemctl is-active chrony` = active; `chronyc tracking` Leap status: Normal, Stratum tracked, system time offset 0.000053s |
| 3   | certbot runs without crashing                             | ✓ VERIFIED | `certbot --version` → `certbot 5.5.0` (exit 0); installed via snap at `/usr/bin/certbot` → `/snap/bin/certbot` |
| 4   | Port inventory is documented                              | ✓ VERIFIED | `/tmp/01-prep-audit-report.txt` exists (188 lines) with ports, vhosts, certbot, chrony, systemd-resolved, Docker audit |
| 5   | Apache2 listens on 9080/9444 instead of 80/443           | ✓ VERIFIED | `ss -tlnp` shows `*:9080` and `*:9444` LISTEN; `ports.conf` has `Listen 9080` and `Listen 9444` |
| 6   | All 54+ vhosts updated with new ports                    | ✓ VERIFIED | 37 vhosts on `:9080`, 40 vhosts on `:9444`, 0 on `:80`, 0 on `:443` in sites-enabled; `apache2ctl configtest` = Syntax OK |
| 7   | Apache2 config syntax is valid after migration           | ✓ VERIFIED | `sudo apache2ctl configtest` returns "Syntax OK"                                           |
| 8   | Apache2 serves content on new ports                      | ✓ VERIFIED | `curl http://localhost:9080/` → HTTP 200; `curl -sk https://localhost:9444/` → HTTP 403 (expected, no default vhost) |
| 9   | systemd-resolved stub is disabled on port 53             | ✓ VERIFIED | `/etc/systemd/resolved.conf` has `DNSStubListener=no`; `ss -ulnp | grep ':53'` returns nothing |
| 10  | DNS resolution still works (upstream reachable)          | ✓ VERIFIED | `dig google.com +short` returns IP; `/etc/resolv.conf` has `nameserver 10.1.1.2` and `169.254.169.254`; systemd-resolved service is active |

**Score:** 10/10 truths verified

### Additional Verifications (ROADMAP Success Criteria)

| # | ROADMAP SC                                    | Status     | Evidence                                                                                   |
| - | --------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------ |
| 1 | `hostname -f` retorna FQDN                    | ✓ VERIFIED | `hostname -f` returns `ipa.atius.com.br` (not bare `atius-srv-1`)                          |
| 2 | NTP sincronizado                              | ✓ VERIFIED | chronyc tracking: Leap status Normal, offset <1ms                                          |
| 3 | Portas 80/443 livres (sem Apache2)            | ✓ VERIFIED | `ss -tlnp | grep ':(80|443)'` returns nothing listening                                   |
| 4 | Portas alternativas documentadas              | ✓ VERIFIED | Apache2: 9080/9444 (D-05, avoids Docker 8080/9443); Keycloak: 9180/9843 (D-06, free)       |
| 5 | `/etc/hosts` e DNS resolvem FQDN              | ✓ VERIFIED | `getent hosts ipa.atius.com.br` → 10.1.1.1; `dig google.com` works                         |

### Required Artifacts

| Artifact                                  | Expected                             | Status     | Details                                                                                      |
| ----------------------------------------- | ------------------------------------ | ---------- | -------------------------------------------------------------------------------------------- |
| `/etc/hosts`                              | FQDN for ipa.atius.com.br            | ✓ VERIFIED | Contains `10.1.1.1  ipa.atius.com.br  atius-srv-1`                                           |
| `/etc/chrony/chrony.conf`                 | NTP with Oracle Cloud source         | ✓ VERIFIED | Contains `server 169.254.169.254 iburst prefer` + public pool fallback, 14 lines substantive  |
| `/etc/apache2/ports.conf`                 | Listen 9080/9444                     | ✓ VERIFIED | Contains `Listen 9080` and `Listen 9444` (in ssl_module and mod_gnutls blocks), 15 lines      |
| `/etc/apache2/sites-enabled/*.conf`       | VirtualHost on new ports             | ✓ VERIFIED | 37 on :9080, 40 on :9444, 0 on old ports — all migrated                                       |
| `/etc/systemd/resolved.conf`              | DNSStubListener=no                   | ✓ VERIFIED | Contains `DNSStubListener=no` and `DNS=10.1.1.2 169.254.169.254`                             |
| `/etc/resolv.conf`                        | Working nameservers                  | ✓ VERIFIED | Contains `nameserver 10.1.1.2` and `nameserver 169.254.169.254`                              |
| `/etc/cloud/cloud.cfg`                    | manage_resolv_conf: false            | ✓ VERIFIED | Contains `manage_resolv_conf: false`                                                         |
| `/usr/bin/certbot`                        | Symlink to snap certbot              | ✓ VERIFIED | Symlink to `/snap/bin/certbot`, version 5.5.0                                                 |
| `/tmp/01-prep-audit-report.txt`           | Audit report (>50 lines)             | ✓ VERIFIED | 188 lines — comprehensive port/vhost/certbot/chrony/systemd-resolved/Docker inventory         |
| `/tmp/02-migration-dryrun.txt`            | Dry-run report                       | ✓ VERIFIED | 210 lines — vhost counts, sed diffs, hardcoded port check                                     |
| `/tmp/02-rollback-ports.sh`               | Rollback script (executable)         | ✓ VERIFIED | Exists, executable (-rwxrwxr-x), contains sed reversal patterns                               |
| `/tmp/03-cloudflare-api-report.txt`       | Cloudflare investigation (>10 lines) | ✓ VERIFIED | 174 lines — hostname list, credential status, update strategy                                 |
| `/tmp/03-phase-validation-report.txt`     | Phase 1 validation                   | ✓ VERIFIED | 62 lines — all 8 checks PASS                                                                  |
| `/tmp/03-all-hostnames.txt`               | Hostname list from vhosts            | ✓ VERIFIED | 66 hostnames extracted from Apache2 vhosts                                                    |
| `/tmp/03-cloudflare-update.sh`            | API update script template           | ✓ VERIFIED | Exists, template with $CF_API_TOKEN/$CF_ZONE_ID variables                                     |
| `/var/www/certbot/`                       | Webroot directory                    | ✓ VERIFIED | Created for certbot webroot authenticator                                                     |
| `/etc/apache2/conf-available/certbot.conf` | Webroot Alias directive             | ✓ VERIFIED | Created with `Alias /.well-known/acme-challenge/ /var/www/certbot/...`                        |
| `/etc/letsencrypt/renewal/*.conf`         | 24 configs: webroot authenticator    | ✓ VERIFIED | All 24 renewal configs have `authenticator = webroot` and `webroot_path = /var/www/certbot`    |

### Key Link Verification

| From                              | To                                | Via                          | Status   | Details                                                                                      |
| --------------------------------- | --------------------------------- | ---------------------------- | -------- | -------------------------------------------------------------------------------------------- |
| `/etc/hosts`                      | FreeIPA container (Phase 3)       | DNS resolution               | ✓ WIRED  | `getent hosts ipa.atius.com.br` → 10.1.1.1                                                  |
| `/etc/chrony/chrony.conf`         | Kerberos (FreeIPA)                | Time synchronization         | ✓ WIRED  | `chronyc tracking` shows Normal leap status, <1ms offset                                     |
| `/etc/apache2/ports.conf`         | `/etc/apache2/sites-enabled/*.conf` | Listen + VirtualHost match | ✓ WIRED  | ports.conf: Listen 9080/9444; vhosts: VirtualHost *:9080/*:9444 — ports match exactly       |
| Apache2 :9444                     | Cloudflare proxy                  | Origin Rules (Plan 03)       | ⚠ PARTIAL | Apache2 listens on 9444; Cloudflare Origin Rules NOT yet updated (documented in Plan 03)     |
| `/etc/systemd/resolved.conf`      | FreeIPA BIND DNS (Phase 3)        | Port 53 availability         | ✓ WIRED  | DNSStubListener=no; `ss -ulnp | grep ':53'` returns empty                                  |
| `/etc/resolv.conf`                | 10.1.1.2 (Oracle VCN DNS)         | Nameserver directive         | ✓ WIRED  | `nameserver 10.1.1.2` present; `dig google.com` returns results                              |
| certbot renewal configs           | `/var/www/certbot` webroot        | authenticator = webroot      | ✓ WIRED  | All 24 configs point to webroot_path; webroot directory exists with www-data ownership        |

### Data-Flow Trace (Level 4)

Not applicable — this phase produces system configuration changes, not application code with data flows. Configuration values are statically written to files and verified by service responses.

### Behavioral Spot-Checks

| Behavior                                      | Command                                              | Result    | Status  |
| --------------------------------------------- | ---------------------------------------------------- | --------- | ------- |
| Apache2 serves HTTP on port 9080              | `curl -s -o /dev/null -w "%{http_code}" http://localhost:9080/` | `200`     | ✓ PASS  |
| Apache2 serves HTTPS on port 9444             | `curl -sk -o /dev/null -w "%{http_code}" https://localhost:9444/` | `403`     | ✓ PASS  |
| Ports 80/443 have no listeners                | `ss -tlnp \| grep -E ':(80\|443)\s'`                 | (empty)   | ✓ PASS  |
| FQDN resolves correctly                       | `getent hosts ipa.atius.com.br`                       | `10.1.1.1` | ✓ PASS  |
| NTP synchronized                              | `chronyc tracking \| grep "Leap status"`              | `Normal`  | ✓ PASS  |
| certbot runs without crash                    | `certbot --version`                                   | `certbot 5.5.0` | ✓ PASS |
| Apache2 config syntax valid                   | `sudo apache2ctl configtest`                          | `Syntax OK` | ✓ PASS |
| DNS resolution works                          | `dig google.com +short`                               | IP returned | ✓ PASS |
| Port 53 free (no stub listener)               | `ss -ulnp \| grep ':53 '`                            | (empty)   | ✓ PASS  |
| `hostname -f` returns FQDN                    | `hostname -f`                                         | `ipa.atius.com.br` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan    | Description                                        | Status     | Evidence                                                                                       |
| ----------- | -------------- | -------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------- |
| PREP-01     | 01-01-PLAN.md  | Hostname configurado como FQDN                     | ✓ SATISFIED | `/etc/hosts` has `ipa.atius.com.br`; `getent hosts` returns 10.1.1.1; `hostname -f` returns `ipa.atius.com.br` |
| PREP-02     | 01-01-PLAN.md  | NTP configurado e sincronizado                     | ✓ SATISFIED | chrony installed, active, Leap status Normal, Oracle Cloud NTP primary source                  |
| PREP-03     | 01-02, 01-03   | Portas 80/443 liberadas (Apache2 movido)           | ✓ SATISFIED | `ss -tlnp` shows nothing on 80/443; Apache2 listens only on 9080/9444; systemd-resolved stub disabled on port 53 |
| PREP-04     | 01-01, 01-02   | Portas alternativas para Apache2 definidas         | ✓ SATISFIED | Apache2 on 9080/9444 (not 8080 — Docker conflict avoided); `ports.conf` has Listen 9080/9444; all 54+ vhosts migrated |
| PREP-05     | 01-01-PLAN.md  | Portas alternativas para Keycloak definidas        | ✓ SATISFIED | Keycloak ports 9180/9843 documented in port matrix (D-06); ports verified free via `ss -tlnp` (not in use by any process) |

**All 5 Phase 1 requirements accounted for: PREP-01, PREP-02, PREP-03, PREP-04, PREP-05 — all SATISFIED.**

### Anti-Patterns Found

| File                                   | Line | Pattern                                          | Severity | Impact                                                                                        |
| -------------------------------------- | ---- | ------------------------------------------------ | -------- | --------------------------------------------------------------------------------------------- |
| `/etc/apache2/ports.conf`              | ~5   | Duplicate `Listen 0.0.0.0:9444` in ssl_module   | ℹ️ Info   | Functional (both match same port), but redundant — inherited from original duplicate cleanup   |
| `/etc/letsencrypt/renewal/*.conf`      | N/A  | `authenticator = webroot` in all 24 configs      | ℹ️ Info   | Not a stub — intentional fallback per Plan 01-02 Task 4; webroot is permanent strategy        |

**No blocker or warning anti-patterns found.**

### Human Verification Required

None. All truths verified programmatically against system state.

## Summary

Phase 01 goal **fully achieved**:

1. **FQDN resolution** ✓ — `ipa.atius.com.br` resolves to 10.1.1.1 via `/etc/hosts`; `hostname -f` returns FQDN
2. **NTP sync** ✓ — chrony installed, active, synchronized (Leap status: Normal, offset <1ms)
3. **Apache2 port migration** ✓ — All 54+ vhosts migrated from 80/443 to 9080/9444; config syntax valid; content served
4. **Ports 80/443 free** ✓ — Nothing listening on 80/443; systemd-resolved stub disabled on port 53
5. **certbot working** ✓ — snap certbot 5.5.0 installed, webroot authenticator configured for 24 renewal configs
6. **Cloudflare investigation** ✓ — 66 hostnames catalogued, API report created, update script template ready
7. **DNS preserved** ✓ — Upstream DNS (10.1.1.2, 169.254.169.254) working after stub disable
8. **Cloud-init protected** ✓ — `manage_resolv_conf: false` prevents `/etc/resolv.conf` overwrite on reboot

### Known Blockers for Next Phases

1. **Cloudflare Origin Rules NOT updated** — Documented in Plan 01-03 report. Cloudflare still proxies port 443 to origin 443 (not 9444). This is expected — requires Cloudflare API token (user action). Template script ready at `/tmp/03-cloudflare-update.sh`.
2. **Pre-existing certbot issue** — `vnc.atius-srv-1.atius.com.br` renewal config has broken symlink ("expected cert.pem to be a symlink"). Not caused by this phase.

### Git Commits

All claimed commits verified in repository:
- `609727d` — feat(01-preparacao-do-host-01-01): install and configure chrony for NTP sync
- `875be3f` — feat(01-preparacao-do-host-01-01): configure FQDN resolution in /etc/hosts
- `96913f8` — fix(01-preparacao-do-host-01-01): reinstall certbot v5.5.0 via snap
- `2d56646` — docs(01-preparacao-do-host-01-02): complete Apache2 port migration plan
- `d495151` — docs(01-preparacao-do-host-01-01): complete host preparation foundation plan

---

_Verified: 2026-04-19T06:05:00Z_
_Verifier: Claude (gsd-verifier)_
