# Codebase Concerns

**Analysis Date:** 2026-04-19

## Security Concerns

### UFW Firewall Not Active

- **Risk:** No firewall rules detected. `ufw status` returns empty. All listening ports are directly exposed.
- **Exposed ports:** 3000 (pm2web), 3015 (atius-web), 8015 (atius-api), 8080 (plane-web), 8085 (jenkins), 8090 (plane-proxy), 8745 (PostgreSQL), 8746 (new-api Postgres), 8747 (plane Postgres), 9001 (Portainer), 9090 (Cockpit), 9443 (Portainer HTTPS)
- **Impact:** Database ports (8745, 8746, 8747), Jenkins (8085), and Portainer (9001/9443) are potentially accessible from the internet
- **Fix approach:** Enable `ufw` with allow rules only for HTTP/HTTPS (80/443) and SSH. Block all other external access. Use WireGuard for admin access.

### PostgreSQL Listening on All Interfaces

- **Issue:** `listen_addresses = '*'` in `/etc/postgresql/17/main/postgresql.conf`
- **Files:** `/etc/postgresql/17/main/postgresql.conf`
- **Impact:** PostgreSQL port 8745 accepts connections from any network interface, not just localhost
- **Fix approach:** Change to `listen_addresses = 'localhost'` unless remote database access is explicitly required

### Docker Database Ports Externally Accessible

- **Issue:** Multiple containerized databases bound to `0.0.0.0` instead of `127.0.0.1`
- **Files:** Docker container port mappings
  - `db-newapi`: `0.0.0.0:8746->5432/tcp` (PostgreSQL)
  - `plane-app-plane-db-1`: `0.0.0.0:8747->5432/tcp` (PostgreSQL)
  - `cloudbeaver-cloudbeaver-1`: `0.0.0.0:8000->8978/tcp` (CloudBeaver DB admin)
- **Impact:** Database admin interfaces and raw database ports accessible from external networks
- **Fix approach:** Change port bindings to `127.0.0.1:PORT:5432` in docker-compose files

### Remote Access Services Running

- **Services:** AnyDesk and NoMachine both running and enabled
- **Impact:** Two independent remote desktop solutions create a larger attack surface. AnyDesk uses proprietary protocol that's hard to audit.
- **Files:** `/etc/systemd/system/anydesk.service`, `/etc/anydesk/system.conf`
- **Fix approach:** Disable one (prefer NoMachine if local, or AnyDesk if remote access needed). Consider SSH + VNC over WireGuard instead.

### Cockpit Exposed Without SSO

- **Issue:** `cockpit.atius.com.br` proxies to `127.0.0.1:9090` with no authentication layer in Apache
- **Files:** `/etc/apache2/sites-available/cockpit.atius.com.br.conf`
- **Impact:** Cockpit provides system administration (shell access, service management, user accounts). Anyone who reaches the endpoint can attempt to log in with system credentials.
- **Fix approach:** Add Apache `Require` directives or integrate with the existing SSO middleware.

### SSL Protocol Configuration Too Permissive

- **Issue:** `SSLProtocol all -SSLv2 -SSLv3` in `/etc/apache2/sites-available/vpn.atius.com.br.conf` — still allows TLSv1.0 and TLSv1.1
- **Files:** `/etc/apache2/sites-available/vpn.atius.com.br.conf` (only site with explicit SSLProtocol; others inherit default)
- **Fix approach:** Use `SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1` to enforce TLS 1.2+
- **Note:** No `SSLCipherSuite` configured anywhere — using Apache defaults

### n8n Apache Config Without Backend Service

- **Issue:** `/etc/apache2/sites-available/n8n.atius.com.br.conf` proxies to `127.0.0.1:5678` but no n8n container or process is running on that port
- **Files:** `/etc/apache2/sites-available/n8n.atius.com.br.conf`, `/etc/apache2/sites-available/n8n.atius.com.br-le-ssl.conf`
- **Impact:** Domain returns 502 errors. Dead configuration should be removed or the service should be started.

### Cloudflare SSL Cert Permissions

- **Issue:** SSL certificate file `/etc/ssl/cloudflare/atius.com.br.pem` has permissions `0644` (world-readable)
- **Files:** `/etc/ssl/cloudflare/atius.com.br.pem` (readable by all), `/etc/ssl/cloudflare/atius.com.br.key` (`0600` — correct)
- **Impact:** The origin certificate (not private) is readable, which is acceptable, but the directory should be restricted to `0750`
- **Fix approach:** `chmod 750 /etc/ssl/cloudflare && chown root:www-data /etc/ssl/cloudflare`

### PM2 Log Contains Sensitive Data

- **Issue:** PM2 logs are world-writable in the `.pm2` directory structure (`drwxrwxr-x`)
- **Files:** `/home/ubuntu/.pm2/` (mode `0775`)
- **Impact:** Other users on the system could read process environment variables, API keys, and connection strings from logs
- **Fix approach:** `chmod 750 /home/ubuntu/.pm2`

## Service Migration Concerns

### WireGuard VPN to 10.1.1.2

- **Status:** WireGuard is installed (`wg0` interface at `10.1.1.1/32`) but interface is DOWN (`wg show` fails)
- **Dependency:** VPN proxy to `10.1.1.2` is configured in:
  - `vpn.atius.com.br.conf` — proxies to `10.1.1.2:3000` (Next.js VPN Manager)
  - `pico.atius.com.br.conf` — proxies to `10.1.1.2:3045` (Pico service, **actively failing** — see below)
- **Route:** `10.1.1.0/24 dev wg0 scope link` configured but wg0 is down
- **Impact:** VPN-dependent services are unreachable. The Apache error log shows continuous connection refused errors for `pico.atius.com.br` → `127.0.0.1:19800`
- **Fix approach:** Restore WireGuard connectivity to `10.1.1.2` or migrate the services (VPN Manager on port 3000, Pico on port 3045/19800) to this server

### Samba Mount Dependency on 10.1.1.2

- **Issue:** `/home/ubuntu/Shared_smb` is a CIFS mount to `//10.1.1.2/Shared`
- **Files:** `/etc/fstab` — `//10.1.1.2/Shared /home/ubuntu/Shared_smb cifs credentials=/home/ubuntu/.smbcredentials,...`
- **Status:** Mount is currently active (autofs), but depends on WireGuard connectivity to `10.1.1.2`
- **Impact:** If WireGuard to `10.1.1.2` goes down, Shared_smb becomes inaccessible. Any code relying on this path will fail.
- **Samba services:** `smbd` and `nmbd` are **masked and inactive** — this server does not serve Samba shares, only mounts them
- **Fix approach:** When migrating Samba from `10.1.1.2`, update `/etc/fstab` to point to the new server IP. Consider replicating data locally to remove the dependency.

### Pico Service Completely Broken

- **Issue:** `pico.atius.com.br` Apache config has no SSL VirtualHost — only HTTP redirect, no HTTPS proxy
- **Files:** `/etc/apache2/sites-available/pico.atius.com.br.conf` (only has `*:80` VirtualHost)
- **Apache logs:** Continuous `Connection refused` to `127.0.0.1:19800` every 3 seconds (automated retries from Cloudflare)
- **Port 19800:** Nothing is listening
- **Impact:** Active 502 errors visible to the internet. `pico-ssl-error.log` is 9.8MB with repeated errors.
- **Fix approach:** Either start the Pico backend service or disable the Apache vhost entirely

## Technical Debt

### Apache Configuration Clutter

- **Issue:** 34 backup/stale config files scattered across `/etc/apache2/sites-available/` and `/etc/apache2/sites-enabled/`
- **Examples:**
  - `api.atius.com.br.conf.bak.20260318132039`, `api.atius.com.br.conf.bak.20260411225939`
  - `api.atius.com.br.conf.bak.loopback.20260318132406`
  - `.backup-20260216-191543` through `.backup-20260305-fix` directories
  - `gsd.atius.com.br.conf.bak.20260410171641`, `gsd.atius.com.br.conf.bak.20260412032826`
- **Impact:** Confusing file landscape, risk of accidentally enabling stale configs
- **Fix approach:** Consolidate backups to `/etc/apache2/.config-backups/` or remove if git-tracked elsewhere

### PM2 Log Files Growing Unbounded

- **Issue:** No log rotation configured for PM2. Multiple logs exceeding 100MB:
  - `atius-web-error.log`: 214MB
  - `horistic-web-error.log`: 185MB
  - `bybit-account-60-error.log`: 176MB
  - `bybit-account-60-out.log`: 147MB
  - `unified-bot-launcher-out.log`: 109MB (two copies)
  - `pm2.log`: 184MB (main PM2 log)
- **Total PM2 disk usage:** ~1.5GB+ in logs
- **Fix approach:** Configure `pm2-logrotate` plugin or add logrotate rules. Set `max_size` in ecosystem.config.js

### Unified Bot Launcher Excessive Restarts

- **Issue:** `atius-unified-bot-launcher` has **2185 restarts**, `horistic-unified-bot-launcher` has **2507 restarts**
- **Pattern:** One-shot architecture — runs one cycle, exits, PM2 restarts after 60s delay. This is by design but generates excessive restart counts that mask real crash signals.
- **Files:** `/home/ubuntu/GitHub/Atius-Capital/ats/backend/services/unified-bot-launcher.js`
- **Secondary issue:** Launcher repeatedly warns about accounts in wrong namespace (`⚠️ Conta 44 ... em namespace "default". Normalizando para "atius"`) — namespace correction happens every cycle
- **Fix approach:** Fix the namespace assignments so accounts are created in the correct namespace initially. Consider a long-running daemon pattern instead of one-shot.

### MEXC Session Healer Processes Stopped

- **Issue:** Multiple MEXC-related PM2 processes are in `stopped` state:
  - `atius-mexc-bridged-api-session-healer-prd`: stopped
  - `atius-mexc-bridged-api-worker-prd`: stopped
  - `atius-mexc-fee-sync`: stopped
  - `atius-mexc-token-cookie-monitor`: stopped
- **Impact:** MEXC exchange integration is non-functional. Session healing, fee sync, and token recovery are not running.
- **Fix approach:** Investigate why they stopped and restart if needed, or remove from ecosystem.config.js if deprecated

### gsd-ac-web Stopped

- **Issue:** `gsd-ac-web` PM2 process is stopped
- **Files:** `/etc/apache2/sites-available/gsd-ac.atius.com.br.conf` proxies to port 1132
- **Impact:** `gsd-ac.atius.com.br` returns 502 errors
- **Fix approach:** Start the process or disable the Apache vhost

### PHP 8.1 Still Loaded in Apache

- **Issue:** `php8.1.conf` and `php8.1.load` are enabled Apache modules
- **Impact:** PHP module loaded for all requests even though the primary stack is Node.js/Next.js. Adds overhead to every Apache process (mpm_prefork).
- **Fix approach:** Disable PHP module if not needed: `a2dismod php8.1`

## Performance & Reliability Concerns

### Apache mpm_prefork with Reverse Proxy

- **Issue:** Apache uses `mpm_prefork` (not `mpm_event`) which is memory-inefficient for reverse proxy workloads
- **Files:** `/etc/apache2/mods-enabled/mpm_prefork.conf`
- **Impact:** Each Apache child process carries full memory footprint. With many virtual hosts and proxy connections, memory pressure increases.
- **Fix approach:** Switch to `mpm_event` for better proxy performance and lower memory usage

### Disk Usage at 72%

- **Issue:** Root filesystem at 138GB/194GB (72%)
- **Contributing factors:** Snap packages (30+ loop devices, ~2GB+), PM2 logs (~1.5GB+), Apache logs, Docker images
- **Impact:** Approaching capacity limits. Docker images and logs will continue to grow.
- **Fix approach:** Clean old Docker images (`docker system prune`), implement log rotation, remove unused snaps

### MongoDB Bound to WireGuard IP

- **Issue:** MongoDB `bindIp` includes `10.1.1.1` (WireGuard interface): `bindIp: 127.0.0.1,172.17.0.1,10.1.1.1`
- **Files:** `/etc/mongod.conf`
- **Impact:** If WireGuard interface goes down, MongoDB may fail to bind on restart. Also exposes MongoDB to the VPN network.
- **Authorization:** Enabled (good). But verify password strength and user permissions.

### CUPS and Printing Services Running

- **Issue:** CUPS, cups-browsed, and snap.cups services are all running on a server infrastructure host
- **Services:** `cups.service`, `cups-browsed.service`, `snap.cups.cupsd.service`, `snap.cups.cups-browsed.service`
- **Impact:** Wastes RAM and CPU. Unnecessary attack surface.
- **Fix approach:** `systemctl disable --now cups cups-browsed` and remove snap cups packages

### Libvirt/KVM Running Unnecessarily

- **Issue:** `libvirtd.service` is running (Virtualization daemon)
- **Impact:** Consumes RAM (~100MB+) on a server that appears to use Docker containers, not VMs.
- **Fix approach:** Disable if not actively managing VMs: `systemctl disable --now libvirtd`

## Fragile Areas

### SSO Middleware Depends on Apache Forwarded Headers

- **Issue:** The SSO implementation in `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts` relies on `x-forwarded-host` header set by Apache reverse proxy
- **Files:** `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/src/middleware.ts`
- **Pattern:** `const forwardedHost = request.headers.get('x-forwarded-host')` — extracts hostname from Apache proxy to determine subdomain permissions
- **Risk:** If Apache proxy configuration changes or `RequestHeader set X-Forwarded-Host` is removed, SSO breaks silently (falls back to `host` header which may be wrong behind proxy)
- **Current SSO coverage:** Subdomain-to-permission mapping for backtest, dashboard, painel (admin), strategy, admin
- **Missing SSO:** Several domains in the system are not listed in `VALID_HOSTNAMES` or `SUBDOMAIN_PERMISSIONS` — they may fall through to default behavior

### SSL Certificate Single Point of Failure

- **Issue:** All virtual hosts use the same wildcard certificate: `/etc/ssl/cloudflare/atius.com.br.pem`
- **Certificate expiry:** Issued 2025-01-29, Cloudflare Origin CA certs have 15-year validity (low risk)
- **Risk:** If the certificate needs rotation, ~50+ Apache virtual hosts must be updated simultaneously
- **Fix approach:** Use Apache `Include` or variable for SSL paths to centralize certificate management

### Cockpit Not Enabled in Apache sites-enabled

- **Issue:** `cockpit.atius.com.br.conf` exists in `sites-available` but is NOT symlinked to `sites-enabled`
- **Impact:** Cockpit is accessible directly on port 9090 (bound to `::`) but NOT through Apache proxy. No HTTPS termination for Cockpit.
- **Fix approach:** Either enable the Apache vhost with `a2ensite` or disable direct port 9090 access

## Known Bugs

### Pico atius.com.br — Continuous Connection Refused Loop

- **Symptoms:** Every 3 seconds Apache attempts to connect to `127.0.0.1:19800` and fails. 9.8MB error log.
- **Files:** `/etc/apache2/sites-available/pico.atius.com.br.conf`, `/var/log/apache2/pico-ssl-error.log`
- **Root cause:** Apache vhost configured but backend service not running on port 19800. Cloudflare keeps sending requests.
- **Workaround:** Disable the vhost: `a2dissite pico.atius.com.br`

### Horistic Launcher Namespace Loop

- **Symptoms:** `horistic-unified-bot-launcher` (2507 restarts) repeatedly removes and recreates worker accounts for accounts 12 and 15
- **Files:** `/home/ubuntu/GitHub/Atius-Capital/ats/backend/services/unified-bot-launcher.js`
- **Trigger:** Accounts 12 (SemFiltro) and 15 (Copy7030) are being created in namespace `default` instead of `horistic`
- **Workaround:** Manually delete and recreate these PM2 processes in the correct namespace

## Dependencies at Risk

### Samba Mount Depends on Remote Server

- **Risk:** `/home/ubuntu/Shared_smb` depends on `//10.1.1.2/Shared` being available
- **Impact:** Any automation, backups, or shared files stored there become inaccessible if `10.1.1.2` goes offline
- **Migration plan:** Replicate shared files locally and update fstab path

### WireGuard Interface Down

- **Risk:** `wg0` interface exists but is not operational. No `wg show` output.
- **Impact:** All `10.1.1.0/24` traffic fails. Shared_smb mount may time out.
- **Migration plan:** Either restore WireGuard connectivity or migrate dependent services (VPN Manager, Samba share, Pico backend) to this server

## Test Coverage Gaps

- **What's not tested:** No test framework detected in the atius backend. `jest.config.js` exists but only for backend configuration — no test files found with `.test.ts` or `.spec.ts` patterns
- **PM2 ecosystem:** `ecosystem.testnet.config.js` exists but no automated deployment tests
- **Apache configs:** No syntax validation in CI. Changes are made directly on production server.
- **Risk:** Configuration drift and breaking changes go undetected until runtime
- **Priority:** High — especially for Apache virtual hosts and PM2 configurations

---

*Concerns audit: 2026-04-19*
