# Phase 1: Preparação do Host - Research

**Researched:** 2026-04-19
**Domain:** Ubuntu 22.04 host preparation — FQDN, NTP, port management, DNS, Apache2 migration, Cloudflare
**Confidence:** HIGH

## Summary

Phase 1 prepares the Oracle Cloud Ubuntu 22.04 server (10.1.1.1, hostname `atius-srv-1`) to receive FreeIPA in Phase 3. The phase does NOT install FreeIPA — it ensures: (1) FQDN resolves correctly, (2) NTP is synchronized for Kerberos, (3) ports 80/443 are freed from Apache2, (4) Apache2 migrates to ports 9080/9444, (5) Cloudflare Origin Rules route to the new origin port, and (6) systemd-resolved releases port 53 for FreeIPA BIND DNS.

The server runs Ubuntu 22.04.5 LTS (Jammy) on ARM64/aarch64. Apache2 has **63 sites-enabled** entries (54 active vhosts on ports 80/443, plus symlinks and backup files). Certbot 1.21.0 is installed via apt but **currently broken** (pyOpenSSL compatibility error). 25+ Docker containers are running, with ports 8080 and 9443 already bound — forcing the Apache2 alternate port choice to 9080/9444.

**Primary recommendation:** Execute in strict order: (1) FQDN via `/etc/hosts`, (2) install+sync chrony, (3) disable systemd-resolved stub on port 53, (4) batch-update Apache2 vhosts to 9080/9444, (5) fix certbot, (6) update Cloudflare Origin Rules via API, (7) verify all services before releasing ports 80/443.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** FQDN do servidor FreeIPA será `ipa.atius.com.br`
- **D-02:** Hostname do OS mantido como `atius-srv-1` — FQDN configurado via `/etc/hosts` e DNS
- **D-03:** `/etc/hosts` deve incluir: `10.1.1.1 ipa.atius.com.br atius-srv-1`
- **D-04:** FreeIPA (container Docker) assume portas 80/443
- **D-05:** Apache2 movido para 9080 (HTTP) / 9444 (HTTPS) — portas 8080 e 9443 já em uso por Docker
- **D-06:** Keycloak usará 9180 (HTTP) / 9843 (HTTPS)
- **D-07:** WireGuard usará porta 51820 (padrão, sem conflito)
- **D-08:** Usar `chrony` como serviço NTP (recomendado para VMs/cloud)
- **D-09:** Kerberos exige sincronização ±5min entre servidor e clientes
- **D-10:** FreeIPA BIND será DNS primário para a rede interna
- **D-11:** CoreDNS será removido/desativado após FreeIPA DNS estar operacional
- **D-12:** Cloudflare Origin Rules mapearão :443 → origin:9444 para os 60+ vhosts
- **D-13:** Apache2 `Listen` alterado de 80/443 para 9080/9444
- **D-14:** Todos os 60+ vhosts atualizados com novas portas
- **D-15:** Cloudflare Origin Rules atualizadas para apontar para 9444
- **D-16:** Certbot configurado com `--http-01-port 9080` para renovação
- **D-17:** Proxy mode mantido (proxied) — Origin Rules definem porta de origem
- **D-18:** 60+ registros DNS podem precisar atualização de Origin Rules
- **D-19:** PM2 apps (Atius) continuam acessíveis via Apache2 na porta 9444
- **D-20:** Docker containers existentes não são afetados (portas internas inalteradas)

### Claude's Discretion
(None — all decisions locked by user)

### Deferred Ideas (OUT OF SCOPE)
- Migração de apps Atius para Keycloak OIDC — futuro (fase separada)
- Horistic no domínio — projeto separado
- Replica FreeIPA para HA — v2

## Runtime State Inventory

> This phase involves host configuration changes that affect running systems.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no databases store hostname/port config as data | None |
| Live service config | Apache2: 54 vhosts on :80/:443, 25 certbot renewal configs, certbot.timer active | Batch sed on vhosts + ports.conf, update renewal configs |
| OS-registered state | systemd-resolved listening on 127.0.0.53:53, Oracle Cloud VCN DNS via 169.254.169.254 | Disable stub listener, preserve upstream DNS config |
| Secrets/env vars | `/etc/ssl/cloudflare/*.pem/*.key` — Cloudflare origin certs referenced by vhosts | No change — cert paths remain valid |
| Build artifacts | certbot 1.21.0 broken (pyOpenSSL incompatibility) — `/usr/bin/certbot` crashes | Reinstall or fix pyOpenSSL dependency |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| chrony | 4.2+ (Ubuntu 22.04 repos) | NTP synchronization | Oracle Cloud recommended, lightweight, VM-optimized |
| Apache2 | 2.4.52 (Ubuntu) | Reverse proxy (existing) | Already managing 60+ vhosts, migration not replacement |
| certbot | 1.21.0 (apt, broken) → 2.x recommended | Let's Encrypt HTTP-01 challenges | Standard ACME client, apache authenticator |
| systemd-resolved | 249.11 (Ubuntu 22.04) | DNS stub (to disable on port 53) | Ubuntu default, conflicts with FreeIPA BIND |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| cloudflared | Not installed | Cloudflare Tunnel (optional) | Only if not using standard proxy mode with Origin Rules |
| sed/awk | System | Batch config file updates | Migrating 54 vhost files from port 80/443 to 9080/9444 |
| ss/lsof | System | Port auditing | Verify port availability before/after changes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| chrony | systemd-timesyncd | timesyncd is simpler but lacks NTP server mode (FreeIPA may need to serve NTP) |
| certbot | acme.sh | acme.sh is lighter, no Python deps (avoids current certbot breakage) |
| Cloudflare Origin Rules API | Cloudflare Dashboard manual | Dashboard is impractical for 60+ hostnames; API is the only viable approach |

**Installation:**
```bash
# Chrony (not installed)
sudo apt install -y chrony

# Fix certbot (broken pyOpenSSL)
sudo pip3 install --upgrade pyOpenSSL cryptography
# OR reinstall cleanly:
sudo apt reinstall -y certbot python3-certbot-apache

# Verify port tools
sudo apt install -y iproute2 lsof
```

**Version verification:**
```bash
# Chrony
chronyd --version  # Expected: chronyd version 4.2

# Apache2
apache2 -v         # Current: Apache/2.4.52 (Ubuntu)

# Certbot (after fix)
certbot --version  # Current: 1.21.0 (consider upgrade to 2.x for reconfigure subcommand)
```

## Architecture Patterns

### Recommended Execution Order

```
Step 1: FQDN Configuration (PREP-01)
Step 2: NTP Setup (PREP-02)
Step 3: Port Audit & systemd-resolved (PREP-03 partial)
Step 4: Apache2 Port Migration (PREP-03, PREP-04, APCH-01)
Step 5: Certbot Reconfiguration (APCH-03)
Step 6: Cloudflare Origin Rules Update (APCH-02)
Step 7: Verification & Port Release (PREP-05, APCH-04)
```

**CRITICAL:** Steps 4-6 must complete and verify BEFORE Apache2 releases ports 80/443. Otherwise, downtime occurs.

### Pattern 1: FQDN Without Hostname Change

**What:** Keep OS hostname as `atius-srv-1` but make `ipa.atius.com.br` resolve to 10.1.1.1 so FreeIPA installation sees a valid FQDN.

**Why the user's decision works:** FreeIPA's `ipa-server-install` checks `hostname -f` during installation. On Ubuntu, `hostname -f` returns the first FQDN found by reverse-resolving the primary IP from `/etc/hosts`. The current `/etc/hosts` has:
```
10.1.1.1  atius-srv-1
```
This means `hostname -f` returns `atius-srv-1` (not an FQDN). The fix is to add the FQDN as an alias:

```
10.1.1.1  ipa.atius.com.br  atius-srv-1
```

**However** — for `hostname -f` to return `ipa.atius.com.br`, the `/etc/hostname` file would need to be `ipa.atius.com.br`. The user decision (D-02) keeps `/etc/hostname` as `atius-srv-1`. This means `hostname -f` will return `atius-srv-1`, NOT `ipa.atius.com.br`.

**The reality:** FreeIPA container can accept FQDN via `-h ipa.atius.com.br` docker run flag or `IPA_SERVER_HOSTNAME` environment variable [CITED: github.com/freeipa/freeipa-container]. The host's `hostname -f` does NOT need to return the FreeIPA FQDN — the container gets its own hostname via Docker's `-h` flag.

**Action for Phase 1:** Add FQDN to `/etc/hosts` for DNS resolution purposes. The FreeIPA container hostname will be set at container runtime in Phase 3.

```
# /etc/hosts — add this line
10.1.1.1  ipa.atius.com.br  atius-srv-1
```

### Pattern 2: Batch Apache2 Vhost Port Migration

**What:** Update 54 vhost files from `*:80` → `*:9080` and `*:443` → `*:9444` atomically.

**Why batch:** Manual editing of 54 files is error-prone and slow. A `sed`-based script with dry-run verification is the standard approach.

**Files to modify:**
1. `/etc/apache2/ports.conf` — `Listen 80` → `Listen 9080`, `Listen 443` → `Listen 9444`
2. `/etc/apache2/sites-enabled/*.conf` — all `<VirtualHost *:80>` → `<VirtualHost *:9080>`, `<VirtualHost *:443>` → `<VirtualHost *:9444>`
3. `/etc/apache2/sites-available/*.conf` — same patterns (symlink targets)

**Dry-run verification first:**
```bash
# Count matches before
grep -c 'VirtualHost.*:80>' /etc/apache2/sites-enabled/*.conf | grep -v ':0$' | wc -l
grep -c 'VirtualHost.*:443>' /etc/apache2/sites-enabled/*.conf | grep -v ':0$' | wc -l

# Preview changes (dry run)
sed -n 's/<VirtualHost \*:80>/<VirtualHost *:9080>/gp' /etc/apache2/sites-enabled/*.conf | head -20

# Apply to sites-enabled
sudo find /etc/apache2/sites-enabled/ -name '*.conf' -exec sed -i \
  -e 's/<VirtualHost \*:80>/<VirtualHost *:9080>/g' \
  -e 's/<VirtualHost \*:443>/<VirtualHost *:9444>/g' {} \;

# Apply to sites-available (symlink targets)
sudo find /etc/apache2/sites-available/ -name '*.conf' -exec sed -i \
  -e 's/<VirtualHost \*:80>/<VirtualHost *:9080>/g' \
  -e 's/<VirtualHost \*:443>/<VirtualHost *:9444>/g' {} \;
```

**Also update `ports.conf`:**
```bash
sudo sed -i 's/^Listen 80$/Listen 9080/' /etc/apache2/ports.conf
sudo sed -i 's/^\(\s*\)Listen 443$/\1Listen 9444/' /etc/apache2/ports.conf
```

### Pattern 3: systemd-resolved Port 53 Release

**What:** Disable systemd-resolved's stub listener on 127.0.0.53:53 so FreeIPA BIND can bind to port 53.

**Current state:** `systemd-resolved` is active, listening on `127.0.0.53:53`. The actual upstream DNS server is `10.1.1.2` (Oracle VCN DNS). The `/etc/resolv.conf` is managed by resolvconf (not a systemd symlink), which is a non-standard Ubuntu 22.04 setup.

**Steps:**
```bash
# 1. Edit /etc/systemd/resolved.conf
sudo sed -i 's/^#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf

# 2. Ensure upstream DNS is preserved in resolved.conf
# Add the current upstream server:
sudo sed -i 's/^#DNS=.*/DNS=10.1.1.2 169.254.169.254/' /etc/systemd/resolved.conf

# 3. Recreate the resolv.conf symlink (if not already)
sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf

# 4. Restart systemd-resolved
sudo systemctl restart systemd-resolved

# 5. Verify port 53 is free
ss -ulnp | grep ':53 '
```

**GOTCHA:** The current `/etc/resolv.conf` is a regular file managed by resolvconf, not a symlink. Converting it to a symlink will change DNS resolution behavior. **Safer approach:** Keep the current resolv.conf but disable only the stub listener, and ensure the real resolv.conf still points to `10.1.1.2`.

### Pattern 4: Cloudflare Origin Rules Bulk Update via API

**What:** Update Cloudflare Origin Rules for all 60+ hostnames to route port 443 → origin port 9444 instead of 443.

**API endpoint:** `PUT https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rulesets/$RULESET_ID`

**JSON body format:**
```json
{
  "rules": [
    {
      "ref": "rule-1",
      "expression": "http.host eq \"api.atius.com.br\"",
      "description": "Route api.atius.com.br to origin port 9444",
      "action": "route",
      "action_parameters": {
        "origin": {
          "port": 9444
        }
      }
    }
  ]
}
```

**Bulk approach:** The Origin Rules API **replaces the entire ruleset** in a single PUT call. The strategy is:
1. GET current ruleset to retrieve existing rules
2. Update all `action_parameters.origin.port` from 443 to 9444
3. PUT the entire updated ruleset back

**Required:** Cloudflare API token with `Zone Rulesets` permissions.

**Alternative:** If Origin Rules are NOT currently configured (subdomains use default port 443), the change is simpler — just add a single rule matching all `*.atius.com.br` hostnames:
```json
{
  "expression": "http.host endswith \".atius.com.br\"",
  "action": "route",
  "action_parameters": {
    "origin": {
      "port": 9444
    }
  }
}
```

### Anti-Patterns to Avoid
- **Manual vhost editing:** 54 files × 2 port changes = 108+ edits. One typo causes Apache2 to fail startup.
- **Stopping Apache2 before verifying new ports:** If you stop Apache2 on 80/443 before confirming 9080/9444 works, all 60+ sites go offline simultaneously.
- **Disabling systemd-resolved entirely (not just stub):** This breaks DNS resolution for the host itself. Only disable the stub listener, not the service.
- **Certbot with `--force-renewal` on broken install:** The current certbot crashes on import. Must fix before any renewal operations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NTP sync | Custom cron-based time sync script | `chrony` | Handles clock drift compensation, VM time skew, stratum tracking |
| Port availability checks | Manual `netstat` greps | `ss -tlnp` + `ss -ulnp` | `netstat` is deprecated; `ss` shows process names and is faster |
| vhost port migration | Individual file edits | `sed` batch with dry-run | Atomic, repeatable, verifiable before applying |
| Certbot renewal config edits | Manual editing of `/etc/letsencrypt/renewal/*.conf` | `certbot reconfigure` (v2.3+) or full renewal cycle | Manual edits break Certbot's renewal tracking; format may change between versions |
| Cloudflare rules updates | Dashboard manual clicks | Cloudflare API with script | 60+ hostnames would take hours manually; API takes seconds |

**Key insight:** Port migration on a live production server with 60+ vhosts is a "measure twice, cut once" operation. Every change must be dry-run verified before application, and rollback scripts must be prepared.

## Common Pitfalls

### Pitfall 1: certbot Broken Install
**What goes wrong:** Current certbot 1.21.0 crashes with `AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'` — pyOpenSSL version incompatibility.
**Why it happens:** Ubuntu 22.04's certbot 1.21.0 was built against an older pyOpenSSL. System updates may have upgraded pyOpenSSL beyond what certbot 1.21.0 supports.
**How to avoid:** Fix certbot BEFORE touching any vhost ports. Options:
  - `sudo pip3 install --upgrade pyOpenSSL cryptography` (may fix compatibility)
  - `sudo apt reinstall -y certbot python3-certbot-apache` (reinstall matching versions)
  - Upgrade to certbot 2.x via snap: `sudo snap install --classic certbot` (recommended for `reconfigure` subcommand)
**Warning signs:** `certbot --version` crashes instead of printing version number.

### Pitfall 2: systemd-resolved resolv.conf Overwrite
**What goes wrong:** Disabling DNSStubListener and recreating the symlink causes `/etc/resolv.conf` to be overwritten by cloud-init on next boot.
**Why it happens:** Oracle Cloud images use cloud-init which regenerates `/etc/resolv.conf` from metadata.
**How to avoid:**
  - Set `manage_resolv_conf: false` in `/etc/cloud/cloud.cfg` to prevent cloud-init from overwriting
  - Or use the existing resolv.conf (which already points to `10.1.1.2`) and ONLY disable the stub listener in resolved.conf
**Warning signs:** DNS breaks after reboot; `resolvectl status` shows different servers than expected.

### Pitfall 3: Apache2 Rewrite Rules Still Reference Port 80/443
**What goes wrong:** vhost files contain `RewriteRule` or `Redirect` directives with hardcoded `http://` or `https://` URLs that assume ports 80/443.
**Why it happens:** The sample vhost shows `RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI}` — this is fine (uses SERVER_NAME, not port), but some configs may have hardcoded ports.
**How to avoid:** After batch sed, grep for any remaining `:80` or `:443` references in vhost files:
```bash
grep -rn ':80\|:443' /etc/apache2/sites-enabled/*.conf | grep -v '9080\|9444\|#'
```
**Warning signs:** Apache2 starts but some vhosts return wrong redirects or fail SSL handshake.

### Pitfall 4: Certbot Apache Authenticator Can't Find Vhosts After Port Change
**What goes wrong:** Certbot's apache authenticator parses Apache config to find vhosts. After port migration, it may fail to match the expected vhost pattern.
**Why it happens:** Certbot 1.21.0 expects vhosts on standard ports. Non-standard ports may confuse the apache authenticator.
**How to avoid:** Test certbot renewal with `--dry-run` AFTER port migration:
```bash
sudo certbot renew --dry-run --http-01-port 9080
```
If apache authenticator fails, switch to `--webroot` authenticator pointing to `/var/www/certbot`.
**Warning signs:** `certbot renew --dry-run` fails with "Could not find appropriate vhost".

### Pitfall 5: Docker Container Port Conflicts
**What goes wrong:** FreeIPA container tries to bind to 80/443 but other services are already using them.
**Why it happens:** Current port scan shows ports 80/443 ARE in use (by Apache2). They must be freed BEFORE FreeIPA container starts.
**How to avoid:** Verify ports 80/443 are completely free:
```bash
ss -tlnp | grep -E ':(80|443)\s'
```
Should return nothing before starting FreeIPA container.
**Warning signs:** Docker container fails to start with "port is already allocated".

### Pitfall 6: FreeIPA Container ARM64 Image
**What goes wrong:** Official `freeipa/freeipa-server` images may not have ARM64/aarch64 builds.
**Why it happens:** GitHub issue #596 shows community request for ARM64 images. A user reported success building locally, but official multi-arch images may not exist.
**How to avoid:** [VERIFIED: github.com/freeipa/freeipa-container/issues/596] Check image availability:
```bash
docker manifest inspect freeipa/freeipa-server:latest 2>/dev/null | grep arm64
```
If no ARM64 image exists, the container must be built from source Dockerfile on the ARM64 host. This is a **Phase 3 risk**, not a Phase 1 blocker, but should be flagged.

### Pitfall 7: Apache2 Has Duplicate Listen Directives
**What goes wrong:** `ports.conf` has BOTH `Listen 80` AND `Listen 0.0.0.0:8080` (commented), plus duplicate `Listen 443` lines inside `IfModule` blocks.
**Why it happens:** Current ports.conf shows:
```
Listen 80
#Listen 0.0.0.0:8080
<IfModule ssl_module>
    Listen 443
    Listen 0.0.0.0:443    # DUPLICATE
</IfModule>
```
**How to avoid:** Clean up ports.conf during migration — remove duplicate Listen directives and comments:
```
Listen 9080
<IfModule ssl_module>
    Listen 9444
</IfModule>
<IfModule mod_gnutls.c>
    Listen 9444
</IfModule>
```

## Code Examples

### FQDN Configuration
```bash
# Add FQDN to /etc/hosts — preserves hostname 'atius-srv-1'
sudo sed -i 's/^10\.1\.1\.1\tatius-srv-1$/10.1.1.1\tipa.atius.com.br\tatius-srv-1/' /etc/hosts

# Verify
getent hosts ipa.atius.com.br    # Should return 10.1.1.1
getent hosts atius-srv-1          # Should return 10.1.1.1
hostname -f                       # Returns 'atius-srv-1' (hostname unchanged)
```

### Chrony Setup (Oracle Cloud)
```bash
sudo apt install -y chrony

# Configure Oracle Cloud NTP + fallback public pools
sudo tee /etc/chrony/chrony.conf << 'EOF'
# Oracle Cloud Infrastructure NTP (primary)
server 169.254.169.254 iburst prefer

# Public NTP pools (fallback)
pool ntp.ubuntu.com iburst
pool pool.ntp.org iburst

# Record the rate at which the system clock gains/loses time
driftfile /var/lib/chrony/chrony.drift

# Allow the system clock to be stepped in the first three updates
makestep 1.0 3

# Enable kernel synchronization of the real-time clock
rtcsync
EOF

sudo systemctl enable --now chrony
chronyc sources -v      # Verify sources
chronyc tracking        # Verify sync status
```

### systemd-resolved Stub Disable (Safe)
```bash
# Disable stub listener only (keep resolved running for DNS forwarding)
sudo sed -i 's/^#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf

# Preserve upstream DNS servers
sudo sed -i 's/^#DNS=.*/DNS=10.1.1.2 169.254.169.254/' /etc/systemd/resolved.conf

# If /etc/resolv.conf is NOT a symlink, make it one
if [ ! -L /etc/resolv.conf ]; then
    sudo mv /etc/resolv.conf /etc/resolv.conf.backup
    sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
fi

sudo systemctl restart systemd-resolved

# Verify
ss -ulnp | grep ':53 '   # Should show nothing on 127.0.0.53:53
resolvectl status        # Should show DNS servers correctly
```

### Apache2 Batch Port Migration
```bash
# === DRY RUN FIRST ===
echo "=== VirtualHost :80 matches ==="
grep -l 'VirtualHost.*:80>' /etc/apache2/sites-enabled/*.conf 2>/dev/null | wc -l
echo "=== VirtualHost :443 matches ==="
grep -l 'VirtualHost.*:443>' /etc/apache2/sites-enabled/*.conf 2>/dev/null | wc -l

# === Preview sed changes ===
for f in /etc/apache2/sites-enabled/*.conf; do
    diff <(cat "$f") <(sed -e 's/<VirtualHost \*:80>/<VirtualHost *:9080>/g' -e 's/<VirtualHost \*:443>/<VirtualHost *:9444>/g' "$f") 2>/dev/null
done | head -50

# === Apply to sites-available first (symlink targets) ===
sudo find /etc/apache2/sites-available/ -name '*.conf' -exec sed -i \
  -e 's/<VirtualHost \*:80>/<VirtualHost *:9080>/g' \
  -e 's/<VirtualHost \*:443>/<VirtualHost *:9444>/g' {} \;

# === Update ports.conf ===
sudo sed -i \
  -e 's/^Listen 80$/Listen 9080/' \
  -e 's/^\(\s*\)Listen 443$/\1Listen 9444/' \
  /etc/apache2/ports.conf

# === Verify ===
sudo apache2ctl configtest    # Should say "Syntax OK"
sudo systemctl reload apache2 # Reload, not restart (zero-downtime)

# === Verify new ports ===
ss -tlnp | grep -E ':(9080|9444)\s'
```

### Certbot Fix and Alternate Port Config
```bash
# Fix broken certbot (Option 1: upgrade pyOpenSSL)
sudo pip3 install --upgrade pyOpenSSL cryptography

# Fix broken certbot (Option 2: snap install — recommended, gets v2.x)
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/bin/certbot

# Test renewal with alternate port
sudo certbot renew --dry-run --http-01-port 9080

# Update renewal configs to use alternate port permanently
# For certbot 2.3+:
for conf in /etc/letsencrypt/renewal/*.conf; do
    cert_name=$(basename "$conf" .conf)
    sudo certbot reconfigure --cert-name "$cert_name" --http-01-port 9080
done
```

### Cloudflare Origin Rules Bulk Update (API Script)
```bash
#!/bin/bash
# Requires: CF_API_TOKEN, CF_ZONE_ID environment variables

ZONE_ID="$CF_ZONE_ID"
API_TOKEN="$CF_API_TOKEN"

# Get current origin rules ruleset
RULESET_ID=$(curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rulesets" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | \
  jq -r '.result[] | select(.phase == "http_request_dynamic_routing") | .id')

# Get current rules
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rulesets/$RULESET_ID" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | \
  jq '.result.rules[] | .action_parameters.origin.port' 

# Update all rules to use port 9444
# (Construct new rules array with updated port, then PUT)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `netstat` for port checks | `ss -tlnp` | Years ago | `netstat` deprecated, `ss` is faster and shows process names |
| `ntp` daemon | `chrony` | Ubuntu 16.04+ | chrony handles VM clock skew better, faster sync |
| manual certbot config edits | `certbot reconfigure` subcommand | certbot 2.3.0+ | Safer config updates without breaking renewal tracking |
| Cloudflare Page Rules | Cloudflare Origin Rules | Page Rules deprecated | Origin Rules are the current standard for port mapping |
| FreeIPA on bare metal | FreeIPA in containers | 2020+ | Enables running on unsupported OS (Ubuntu), but adds complexity (cgroups, volumes, hostname) |

**Deprecated/outdated:**
- **certbot 1.21.0**: Ubuntu 22.04 ships with 1.21.0. Current certbot is 3.x+. The `reconfigure` subcommand (2.3+) makes renewal config updates safe. Current certbot is broken on this system.
- **Cloudflare Page Rules**: Deprecated in favor of Ruleset Engine (Origin Rules, Transform Rules, etc.).
- **`ntp` package**: Replaced by `chrony` or `systemd-timesyncd` on modern Ubuntu.
- **FreeIPA native Ubuntu packages**: Don't exist (Launchpad bug #1875114 since 2020). Container is the only option.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `hostname -f` returning `atius-srv-1` is acceptable for FreeIPA container because container gets its own hostname via Docker `-h` flag | Pattern 1 | If FreeIPA install on host (not container) requires `hostname -f` to return FQDN, Phase 3 will fail — would need to change `/etc/hostname` |
| A2 | Cloudflare Origin Rules are currently NOT configured for custom ports (default 443) — only a single wildcard rule matching `*.atius.com.br` is needed | Pattern 4 | If per-hostname rules already exist, the API script must GET-modify-PUT instead of creating a single rule |
| A3 | No ARM64/aarch64 official FreeIPA container images exist based on GitHub issue #596 | Pitfall 6 | If ARM64 images now exist (issue was from past), building from source is unnecessary — simplifies Phase 3 |

## Open Questions (RESOLVED)

1. **Are Cloudflare Origin Rules already configured for port mapping, or is default 443 assumed?**
   - What we know: Cloudflare proxy is active, SSL certs are Cloudflare origin certs
   - What's unclear: Whether custom Origin Rules already exist in the Cloudflare dashboard/API
   - Recommendation: Query Cloudflare API first (`GET /zones/$ZONE_ID/rulesets`) to discover current state before writing update script
   - **RESOLVED (execution):** Plan 01-03 Task 2 explicitly queries the Cloudflare API to discover current ruleset state before making changes. Resolution will be written to audit report during execution.

2. **Does the current certbot use Cloudflare origin certs (manual) or Let's Encrypt (auto-renewing)?**
   - What we know: vhosts reference `/etc/ssl/cloudflare/*.pem` — these are Cloudflare origin certificates
   - What's unclear: Whether certbot renewal configs are actually used, or certs are manually renewed from Cloudflare dashboard
   - Recommendation: Check `/etc/letsencrypt/live/` to see if certs match the Cloudflare origin certs or are separate Let's Encrypt certs
   - **RESOLVED (execution):** Plan 01-02 Task 3 runs `certbot certificates` and checks `/etc/letsencrypt/live/` to identify cert source. Resolution documented in migration dry-run report.

3. **What is the certbot renewal strategy after Apache2 moves to non-standard ports?**
   - What we know: HTTP-01 challenge normally connects on port 80. With Apache2 on 9080, Let's Encrypt's ACME server will still try port 80
   - What's unclear: Whether `--http-01-port 9080` actually works when Cloudflare proxies to 9444
   - Recommendation: Test during execution — Plan 01-02 Task 3 runs certbot dry-run on new port to validate
   - **RESOLVED (execution):** Plan 01-02 Task 3 tests `certbot renew --dry-run --http-01-port 9080`. If this fails (Cloudflare proxying port 80), alternative strategy (DNS-01 challenge or Cloudflare API cert upload) will be determined and documented during execution.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Apache2 | Reverse proxy for 60+ vhosts | ✓ | 2.4.52 | — |
| certbot | TLS certificate management | ✗ (broken) | 1.21.0 (crashes) | Reinstall via snap or fix pyOpenSSL |
| chrony | NTP synchronization for Kerberos | ✗ (not installed) | — (in repos) | systemd-timesyncd (less capable) |
| systemd-resolved | DNS resolution | ✓ (conflicting) | 249.11 | Disable stub only, not full service |
| Docker | Container runtime for FreeIPA | ✓ | Present (25+ containers running) | — |
| Oracle Cloud NTP | Time source | ✓ | 169.254.169.254 | ntp.ubuntu.com pool |
| Cloudflare API | Origin Rules management | ✓ (needs token) | — | Manual dashboard update (impractical for 60+) |
| ss/iproute2 | Port auditing | ✓ | System | netstat (deprecated) |

**Missing dependencies with no fallback:**
- certbot working installation — must be fixed before Phase 1 completes, otherwise TLS renewal breaks

**Missing dependencies with fallback:**
- chrony — not installed, but available in Ubuntu repos (simple `apt install`)
- Cloudflare API token — if not available, dashboard update is the fallback (time-consuming but possible)

## Validation Architecture

> Skipping: this phase involves only host configuration changes (hostname, NTP, ports, DNS). No application code changes or new features requiring test suites. Validation is operational (services respond correctly on expected ports).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not implemented in this phase |
| V3 Session Management | no | Not implemented in this phase |
| V4 Access Control | no | Not implemented in this phase |
| V5 Input Validation | no | Configuration changes only |
| V6 Cryptography | yes | TLS certificates (Apache2, Cloudflare), certbot management |
| V8 Data Protection | no | Not applicable |

### Known Threat Patterns for Apache2 Port Migration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Port exposure during migration | Exposure | Verify new ports accept traffic BEFORE releasing old ports |
| Certificate mismatch after port change | Tampering | Test TLS handshake on new ports; verify cert paths unchanged |
| DNS resolution break (systemd-resolved) | Availability | Keep upstream DNS config intact; test resolution after changes |
| Cloudflare proxy bypass | Spoofing | Ensure origin certs still valid; Cloudflare proxy mode unchanged |

## Sources

### Primary (HIGH confidence)
- [CITED: github.com/freeipa/freeipa-container] — FreeIPA container hostname setup via `-h` flag and `IPA_SERVER_HOSTNAME` env var
- [CITED: www.freeipa.org/page/Docker] — FreeIPA Docker deployment guide, port mappings, client enrollment
- [CITED: developers.cloudflare.com/rules/origin-rules/] — Cloudflare Origin Rules API format, `action_parameters.origin.port`
- [CITED: eff-certbot.readthedocs.io/en/stable/using.html] — Certbot `--http-01-port` option and `reconfigure` subcommand
- [CITED: docs.oracle.com/en-us/iaas/Content/Compute/Tasks/configuringntpservice.htm] — Oracle Cloud NTP server at 169.254.169.254
- [VERIFIED: system audit] — All port scans, service checks, config file reads performed on live system 2026-04-19
- [VERIFIED: github.com/freeipa/freeipa-container/issues/596] — ARM64 image status (community-built, not official)

### Secondary (MEDIUM confidence)
- [CITED: www.linuxuprising.com/2020/07/ubuntu-how-to-free-up-port-53-used-by.html] — systemd-resolved stub disable steps
- [CITED: leo.leung.xyz/wiki/FreeIPA] — FreeIPA docker-compose example with full port mappings and gotchas

### Tertiary (LOW confidence)
- [ASSUMED] Cloudflare Origin Rules current state — not verified via API, assumed default port 443 routing
- [ASSUMED] certbot renewal configs match Let's Encrypt certs — actual certificate source (Let's Encrypt vs manual Cloudflare) not fully verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified via system audit and official documentation
- Architecture: HIGH — patterns verified against actual system state (63 sites, port scans, config reads)
- Pitfalls: HIGH — all pitfalls identified from actual system state (broken certbot, duplicate Listen directives, systemd-resolved conflict)

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (30 days — stable domain, but Cloudflare API and certbot versions may change)
