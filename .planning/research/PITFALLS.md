# Domain Pitfalls: FreeIPA + Keycloak + Samba on Ubuntu

**Domain:** Linux domain infrastructure (FreeIPA + Keycloak + Samba)
**Researched:** 2026-04-19
**Server:** atius-srv-1, Ubuntu 22.04.5 LTS, aarch64 (ARM64)

---

## Critical Pitfalls

Mistakes that cause full reinstallation, data loss, or total authentication outage.

### Pitfall 1: FreeIPA on Ubuntu — Unsupported Platform

**What goes wrong:** FreeIPA is designed, tested, and shipped for RHEL/CentOS/Fedora. Ubuntu is a second-class citizen. The installer fails during the Certificate Authority (Dogtag) setup phase because `pkihelper.py` calls `sysctl crypto.fips_enabled`, which returns exit status 255 on Ubuntu — the `/proc/sys/crypto` sysctl path doesn't exist on Ubuntu kernels. The CA configuration fails with `"server did not start after 60s"` and the entire `ipa-server-install` aborts, leaving a half-configured system.

**Why it happens:** FreeIPA's platform abstraction layer (`ipaplatform`) has RHEL-specific assumptions baked in. Ubuntu packages are community-maintained, lag behind upstream versions, and receive less testing. The GitHub issue `freeipa/ansible-freeipa#509` remains **open with no resolution** — the bug has existed since at least Ubuntu 18.04 and persists through 22.04.

**Consequences:**
- `ipa-server-install` fails mid-way, leaving Apache, 389-ds, Kerberos, and Dogtag in inconsistent state
- Must run `ipa-server-install --uninstall` to clean up, but this often leaves residual config
- Even if installation succeeds, updates and upgrades may break components unpredictably
- ARM64 (aarch64) adds another layer of risk — fewer people test this combination
- No official Red Hat support; community fixes are slow

**Warning signs:**
- `ipa-server-install` output shows `CA configuration failed` or `server did not start after 60s`
- Error log contains `sysctl: cannot stat /proc/sys/crypto/fips_enabled`
- `ipactl status` shows some services running and others stopped

**Prevention strategy:**
- **STRONGLY CONSIDER:** Use a RHEL 9 or Rocky Linux 9 VM/container for FreeIPA instead of native Ubuntu install
- If committed to Ubuntu: file the `crypto.fips_enabled` bug workaround — patch `pkihelper.py` to use `ipaplatform` FIPS detection instead of raw sysctl
- Test installation in a disposable VM first, never on the production server
- Document every manual workaround; package updates WILL overwrite patched files

**Phase mapping:** FreeIPA Installation phase — this is the FIRST risk to address. If FreeIPA won't install cleanly on Ubuntu ARM64, the entire project architecture needs rethinking.

**Confidence:** HIGH — verified via FreeIPA mailing lists (freeipa-users@lists.fedorahosted.org), GitHub issue #509 (open, no fix), and Red Hat documentation (RHEL-only target platform).

---

### Pitfall 2: Hostname Is Not a FQDN — Current Server Fails This Requirement

**What goes wrong:** The current hostname is `atius-srv-1` (bare short name), NOT `atius-srv-1.atius.com.br` (FQDN). FreeIPA **refuses to install** without a fully qualified domain name. The Kerberos principal system, TLS certificate generation, and keytab lookups all depend on the FQDN being stable and resolvable.

**Why it happens:** Kerberos service principals encode the hostname (e.g., `HTTP/atius-srv-1.atius.com.br@ATIUS.COM.BR`). TLS certificates are issued with the FQDN as the Subject CN. If the local hostname (`hostname` command) doesn't match the FQDN used in principals and certificates, GSSAPI authentication fails with `"Server not found in Kerberos database"`.

**Consequences:**
- `ipa-server-install` will reject the current hostname outright
- `ipa-client-install` on client machines will fail with `"The hostname must be fully-qualified"`
- Even if forced through, changing the hostname post-installation **breaks Kerberos** — keytabs contain the original FQDN principal, and any hostname change causes silent auth failures
- Changing hostname after FreeIPA install is **unsupported** and requires full re-enrollment

**Warning signs:**
- `hostname -f` returns just `atius-srv-1` (not `atius-srv-1.atius.com.br`)
- `hostname` and `hostname -f` return different values
- `/etc/hostname` contains a short name

**Prevention strategy:**
1. Set FQDN BEFORE any FreeIPA installation:
   ```bash
   hostnamectl set-hostname atius-srv-1.atius.com.br
   ```
2. Ensure `/etc/hosts` has the FQDN first:
   ```
   10.1.1.1  atius-srv-1.atius.com.br atius-srv-1
   ```
3. Verify `hostname` and `hostname -f` both return the FQDN
4. Ensure DNS has both forward (A) and reverse (PTR) records for `10.1.1.1` → `atius-srv-1.atius.com.br`
5. **Never change the hostname after FreeIPA is installed**

**Phase mapping:** Prerequisite/Preparation phase — hostname must be fixed BEFORE FreeIPA installation begins.

**Confidence:** HIGH — verified via Red Hat Solution 7029959, FreeIPA mailing list discussions, and MIT Kerberos documentation.

---

### Pitfall 3: Kerberos Requires Perfect Forward + Reverse DNS

**What goes wrong:** If the forward DNS lookup (hostname → IP) and reverse DNS lookup (IP → hostname) don't return matching results, Kerberos authentication fails with `"Server not found in Kerberos database"` or `"Client not found in Kerberos database"`. This affects EVERY authentication attempt — `ipa-client-install`, SSSD logins, Samba Kerberos auth, and Keycloak LDAP binds.

**Why it happens:** Kerberos encodes the server hostname in service principals. When a client requests a ticket, the KDC validates that the hostname in the request matches the principal name. The validation chain is: client DNS lookup → hostname → KDC principal lookup. If reverse DNS returns a different name than what the forward lookup used, the principal won't match and authentication is rejected.

**Consequences:**
- `ipa-client-install` fails during CA certificate download (can't reach the server)
- SSSD shows `"No domain configured"` or `"Authentication failed"` for all domain users
- Samba returns `NT_STATUS_LOGON_FAILURE` for Kerberos-authenticated connections
- Keycloak LDAP bind fails silently or with `Invalid credentials`
- Errors are cryptic and hard to diagnose — they look like password/credential issues, not DNS issues

**Warning signs:**
- `dig atius-srv-1.atius.com.br` returns `10.1.1.1` but `dig -x 10.1.1.1` returns something else (or NXDOMAIN)
- `hostname -f` doesn't match the PTR record for the server's IP
- CoreDNS forwarders aren't configured for the FreeIPA domain zone

**Prevention strategy:**
1. Before FreeIPA install, verify both directions resolve correctly:
   ```bash
   dig atius-srv-1.atius.com.br    # Must return 10.1.1.1
   dig -x 10.1.1.1                 # Must return atius-srv-1.atius.com.br
   ```
2. Configure FreeIPA DNS as authoritative for the `atius.com.br` zone (or a subdomain like `ipa.atius.com.br`)
3. Set up DNS forwarding in FreeIPA: forward `atius.com.br` queries to Cloudflare, forward everything else to public DNS
4. On client machines, point `/etc/resolv.conf` to the FreeIPA DNS server FIRST
5. Integrate CoreDNS with FreeIPA DNS (either replace CoreDNS with FreeIPA's BIND, or configure CoreDNS to forward the FreeIPA zone to the FreeIPA server)

**Phase mapping:** Prerequisite/Preparation phase (DNS) and FreeIPA Installation phase. Must be validated BEFORE `ipa-server-install` runs.

**Confidence:** HIGH — verified via RFC 4120 (Kerberos spec), MIT Kerberos docs, OneUptime Kerberos guide, and multiple community reports.

---

### Pitfall 4: Single Point of Failure — No Replica, No Recovery

**What goes wrong:** This project plans a **single FreeIPA server** at `10.1.1.1`. If that server crashes, is rebooted and fails to start services, or has disk corruption, the entire identity infrastructure goes down: no logins, no Samba access, no Keycloak SSO, no domain authentication for any client machine.

**Why it happens:** Red Hat's disaster recovery documentation explicitly states: *"An IdM deployment is unrecoverable if the CA renewal server has been lost"* without a replica or external CA backup. FreeIPA's recovery procedures assume at least one surviving replica exists. With a single server:
- The CA renewal master holds the only copy of the Dogtag CA signing key
- The 389 Directory Server holds the only copy of all user accounts, groups, HBAC rules, and sudo rules
- The Kerberos KDC holds the only copy of all keytabs and principal passwords

**Consequences:**
- Server hardware failure = total identity infrastructure loss
- Accidental `ipa-server-install --uninstall` = unrecoverable
- Disk corruption on `/var/lib/dirsrv` or `/etc/pki/pki-tomcat` = all user data and CA lost
- Certificate expiry on the CA (see Pitfall 7) with a dead server = no renewal possible
- All client machines lose authentication — domain users can't log in anywhere

**Warning signs:**
- `ipa server-find` shows only one server
- No backup strategy for `/etc/dirsrv`, `/var/lib/dirsrv`, `/etc/pki/pki-tomcat`, `/var/kerberos/krb5kdc`
- No documented recovery procedure
- No VM snapshot or LVM snapshot schedule

**Prevention strategy:**
1. **Minimum:** Implement automated daily backups of critical directories:
   - `/etc/dirsrv/slapd-ATIUS-COM-BR/`
   - `/var/lib/dirsrv/slapd-ATIUS-COM-BR/`
   - `/etc/pki/pki-tomcat/`
   - `/var/kerberos/krb5kdc/`
   - `/etc/ipa/`
   - Use `ipa-backup` (creates LDIF + config backup)
2. **Recommended:** Add a second FreeIPA replica on another machine (even a low-spec VM)
3. **If single server is unavoidable:**
   - Store backups off-server (different machine, different disk)
   - Test restore procedure at least once
   - Document the exact recovery steps for `ipa-restore`
   - Consider LVM snapshots before any `ipa-*` commands

**Phase mapping:** FreeIPA Installation phase (configure backup immediately after install) and ongoing Operations.

**Confidence:** HIGH — verified via Red Hat RHEL 9 disaster recovery documentation and FreeIPA community discussions.

---

### Pitfall 5: Apache Port Conflict — Moving Existing Apache Breaks 60+ Vhosts

**What goes wrong:** The plan is to move the existing Apache2 from ports 80/443 to 8080/8443 to free them for FreeIPA. FreeIPA's `ipa-server-install` takes exclusive control of ports 80, 443, 389, 636, 88, and 464. When Apache is moved to alternate ports:

1. **SSL termination changes:** All 60+ vhosts currently served on 443 must now be served on 8443. Every client, bookmark, API endpoint, and reverse proxy reference that uses `https://domain.atius.com.br` (implicit port 443) breaks.
2. **Let's Encrypt / Certbot renewal** may fail — Certbot uses port 80 for HTTP-01 challenges. If Apache isn't on 80, Certbot's `--webroot` or `--standalone` modes need reconfiguration.
3. **FreeIPA's Apache takes over ports 80/443** and uses its own SSL certificates (signed by the FreeIPA CA). The existing Cloudflare Origin CA certificates won't be used by FreeIPA's Apache.
4. **FreeIPA on alternate ports** (using `--http-port` / `--https-port` flags) is documented as **not using SSL** — running IPA without HTTPS is a security risk and breaks many Kerberos flows.

**Why it happens:** FreeIPA embeds Apache (httpd) as a core component. It's not a standard Apache config — it uses mod_nss for TLS, has specific module ordering, and manages its own virtual host configuration. FreeIPA's Apache handles the IPA Web UI, the Kerberos KDC proxy, and the Certificate Authority web interface.

**Consequences:**
- All 60+ existing vhosts become inaccessible on standard HTTPS ports
- Cloudflare proxy needs to be reconfigured to proxy to 8443 instead of 443 for every vhost
- Any internal services that connect to `https://hostname/` (implicit 443) will hit FreeIPA's Apache instead of the expected vhost
- FreeIPA's Apache may proxy requests to the wrong backend if vhost configs aren't carefully migrated
- **The FreeIPA Web UI and Keycloak would both want port 443** — Keycloak typically runs on 8080/8443, creating another conflict

**Warning signs:**
- Apache Listen directives still include `:80` or `:443` after migration to alternate ports
- FreeIPA install shows `Address already in use` for port 80 or 443
- `ss -tlnp | grep -E ':80|:443|:8080|:8443'` shows both Apache and FreeIPA trying to bind
- Certbot renewals start failing silently

**Prevention strategy:**
1. **Before FreeIPA install:** Migrate all Apache vhosts to 8080/8443 and verify EVERYTHING works:
   - Update all `Listen` directives in Apache
   - Update all Cloudflare origin rules to point to 8443
   - Test all 60+ vhosts on the new ports
   - Reconfigure Certbot for `--webroot` mode with the alternate port
2. **FreeIPA port strategy:**
   - Let FreeIPA use ports 80/443 (standard) — this is the only supported configuration
   - Put a reverse proxy (nginx) in front of both FreeIPA and Keycloak if needed, but this adds complexity
3. **Alternative architecture:** Keep Apache on 80/443, run FreeIPA on a separate machine/container
4. **Document every port dependency** before changing anything — audit `ss -tlnp` and all Docker container port mappings

**Phase mapping:** Apache Migration phase — MUST be completed and fully tested BEFORE FreeIPA installation.

**Confidence:** HIGH — verified via FreeIPA InstallAndDeploy documentation, Apache port binding behavior, and standard HTTPS/TLS architecture.

---

## Moderate Pitfalls

### Pitfall 6: FreeIPA CA Certificate Expiry — Silent Catastrophe

**What goes wrong:** FreeIPA's internal CA (Dogtag) issues certificates for all internal services (HTTP, LDAP, Kerberos). The CA certificate itself has a finite validity period (default 20 years for Dogtag system certs, but individual service certs have shorter lifetimes). When the CA certificate expires:
- All service certificates signed by the CA become untrusted
- Inter-service communication (FreeIPA → Dogtag, FreeIPA → 389-ds) breaks with TLS errors
- `ipactl status` shows services failing to start
- Client machines can't enroll because the CA cert is expired
- **Renewal becomes extremely difficult** when the CA cert has already expired — the renewal process itself requires a working CA

**Why it happens:** FreeIPA has automatic certificate renewal for service certs, but the CA certificate renewal is a manual process. If the server sits unattended for years, the CA cert expires and the entire PKI chain becomes invalid. Red Hat KB 7128558 notes that security policies may prevent renewal with extended validity, making the CA cert expire again immediately.

**Consequences:**
- Complete authentication outage — no new enrollments, no existing service renewals
- All domain clients lose trust in the server
- Recovery requires complex manual Dogtag CA certificate regeneration
- In worst case: full FreeIPA reinstallation required

**Warning signs:**
- `certutil -L -d /etc/pki/pki-tomcat/alias/` shows CA cert expiry within 6 months
- `ipa cert-find` returns expired certificate warnings
- Service logs show `SSL_ERROR_EXPIRED_CERT_ALERT` or `certificate has expired`
- FreeIPA health check: `ipa-healthcheck --failures-only` shows cert-related failures

**Prevention strategy:**
1. Immediately after install, check CA cert expiry:
   ```bash
   certutil -L -d /etc/pki/pki-tomcat/alias/ -n "CA Certificate" | grep -A2 "Validity"
   ```
2. Set up calendar reminders at 2-year, 1-year, and 6-month before expiry
3. Add a monitoring check (cron job or monitoring system) that alerts when CA cert is <90 days from expiry
4. Document the CA renewal procedure BEFORE it's needed:
   - Follow FreeIPA's `CA_Certificate_Renewal` howto
   - Test renewal in a disposable environment first
5. If CA cert has ALREADY expired: follow the Red Hat KB 7128558 procedure to bypass expiration validation

**Phase mapping:** FreeIPA Installation phase (check expiry immediately) and ongoing Operations (monitoring).

**Confidence:** HIGH — verified via FreeIPA CA Certificate Renewal docs, Red Hat KB 7128558, ServerFault 1161935, and Dogtag certificate lifetime documentation.

---

### Pitfall 7: Samba AD Trust — ipa-adtrust-install Breaks Existing Samba

**What goes wrong:** Running `ipa-adtrust-install` on a server that already has Samba packages/configurations can cause:
- **Samba service fails to start** after adtrust configuration (port conflicts between standalone Samba and FreeIPA-managed Samba)
- **Existing Samba shares become inaccessible** because the idmap configuration changes
- **File permissions break** because the SID-to-UID mapping changes — files owned by UID 1000 may no longer map to the correct user
- **Trust establishment fails silently** if DNS doesn't have the required `_ldap._tcp.dc._msdcs` SRV records

**Why it happens:** `ipa-adtrust-install` configures Samba as an AD Domain Controller component, which is fundamentally different from a standalone Samba file server. It installs a separate Samba instance (`smb` service managed by FreeIPA, not the standard `smbd`), changes idmap backends to `idmap_ad`, and creates AD trust keys. If the existing Samba at `10.1.1.2` has its own `smb.conf`, user mappings, or share definitions, they conflict with the FreeIPA-managed configuration.

**Consequences:**
- Existing `Shared` share from `10.1.1.2` becomes inaccessible during migration
- File ownership/permissions appear wrong after migration (all files show as owned by `nobody` or numeric IDs)
- Kerberos authentication to Samba fails with `NT_STATUS_LOGON_FAILURE`
- Windows clients (if any) can't browse shares without Global Catalog access

**Warning signs:**
- `ipa-adtrust-install` shows warnings about existing Samba configuration
- `smbd` is already running when adtrust installer tries to start its own Samba
- `testparm` shows conflicting idmap settings
- `wbinfo -u` or `wbinfo -g` fails after adtrust install

**Prevention strategy:**
1. **Before running `ipa-adtrust-install`:**
   - Stop and disable the existing Samba service: `systemctl stop smbd nmbd && systemctl disable smbd nmbd`
   - Back up the existing `/etc/samba/smb.conf` and all share data
   - Document existing UID/GID mappings and share permissions
2. **Migration plan for existing shares:**
   - Copy data from `//10.1.1.2/Shared` to local storage on `10.1.1.1` BEFORE changing idmap
   - Verify file ownership with `ls -ln` (numeric IDs) before and after migration
   - If existing files use POSIX ACLs, preserve them with `cp -a` or `rsync -aX`
3. **After `ipa-adtrust-install`:**
   - Verify DNS SRV records exist: `dig SRV _ldap._tcp.dc._msdcs.atius.com.br`
   - Test Samba share access with `smbclient //localhost/Share -k`
   - Check idmap consistency: `wbinfo -i username` should return correct UID

**Phase mapping:** Samba Migration phase — document existing share state BEFORE running `ipa-adtrust-install`.

**Confidence:** HIGH — verified via FreeIPA mailing lists (ipa-adtrust-install failures), FreeIPA Samba integration howto, and community reports of "Unable to find PAC" errors.

---

### Pitfall 8: Keycloak LDAP Federation — Wrong Object Classes and Attributes

**What goes wrong:** When configuring Keycloak to federate with FreeIPA's LDAP (389-ds), the most common misconfiguration is using the wrong LDAP object classes and attribute names. FreeIPA uses `posixAccount`, `inetOrgPerson`, and `ipaUser` object classes, but Keycloak's default LDAP provider templates assume Active Directory or OpenLDAP schemas.

Specific mistakes:
- Setting `userObjectClasses` to `inetOrgPerson, organizationalPerson` (missing `posixAccount`) — users are found but lack POSIX attributes (UID, GID, home directory)
- Using `sAMAccountName` as the username attribute (AD convention) instead of `uid` (FreeIPA convention)
- Using `entryUUID` as the UUID attribute — FreeIPA uses `nsUniqueID`
- Setting the wrong Users DN — FreeIPA uses `cn=users,cn=accounts,dc=atius,dc=com,dc=br`, not `ou=People,dc=...`
- Not configuring the Group DN correctly — FreeIPA groups are at `cn=groups,cn=accounts,dc=atius,dc=com,dc=br`
- Forgetting to enable "Trust Email" — FreeIPA stores email in `mail` attribute, Keycloak needs explicit mapping

**Why it happens:** Keycloak's LDAP federation UI presents many options with AD-centric defaults. FreeIPA's LDAP schema is 389-ds specific and differs from both AD and generic OpenLDAP.

**Consequences:**
- Keycloak can't find any users — login via FreeIPA credentials fails silently
- Users are imported but with empty email/name fields
- Group membership isn't synced — RBAC in Keycloak-relying apps doesn't work
- Password authentication falls back to Keycloak's internal store (users can't log in with FreeIPA passwords)

**Warning signs:**
- Keycloak server log shows `Creating new LDAP Store` with wrong base DN
- `kcadm.sh get users` returns empty list after federation setup
- Keycloak admin console shows users but with `Email: null`, `First Name: null`
- LDAP search from Keycloak server returns results but federation doesn't import them

**Prevention strategy:**
1. Test LDAP connectivity from Keycloak server before configuring federation:
   ```bash
   ldapsearch -x -H ldap://atius-srv-1.atius.com.br:389 \
     -D "uid=admin,cn=users,cn=accounts,dc=atius,dc=com,dc=br" \
     -W -b "cn=users,cn=accounts,dc=atius,dc=com,dc=br" "(uid=*)"
   ```
2. Use these specific Keycloak LDAP provider settings for FreeIPA:
   - `Vendor`: Red Hat Directory Server (or "Other")
   - `Username LDAP attribute`: `uid`
   - `RDN LDAP attribute`: `uid`
   - `UUID LDAP attribute`: `nsUniqueID` (NOT `entryUUID`)
   - `User Object Classes`: `inetOrgPerson, organizationalPerson` (FreeIPA users have these)
   - `Connection URL`: `ldaps://atius-srv-1.atius.com.br:636`
   - `Users DN`: `cn=users,cn=accounts,dc=atius,dc=com,dc=br`
   - `Auth Type`: `simple`
   - `Bind DN`: service account with read access to user subtree
   - `Edit Mode`: `READ_ONLY` (don't let Keycloak modify FreeIPA users)
3. Add explicit mappers for: `mail` → Email, `cn` → First Name, `sn` → Last Name, `memberOf` → Group membership
4. Test with a single user before enabling federation for all users

**Phase mapping:** Keycloak Installation phase — verify LDAP connectivity and schema BEFORE creating the User Federation provider.

**Confidence:** HIGH — verified via Keycloak server admin documentation (LDAP provider APIDOC), Keycloak GitHub issue #13492 (cn vs uid mapper bug), and Red Hat Customer Portal solution 3010401.

---

### Pitfall 9: SSSD Client Join — DNS Resolution Breaks Enrollment

**What goes wrong:** When running `ipa-client-install` on a client machine, the installer needs to resolve the FreeIPA server's hostname to download the CA certificate and establish the Kerberos connection. If DNS isn't properly configured on the client, enrollment fails with:
- `"Cannot contact any KDC for realm ATIUS.COM.BR"`
- `"Cannot find KDC for realm"`
- `"Cannot obtain CA certificate from 'https://atius-srv-1.atius.com.br/ipa/config/ca.crt'"`

**Why it happens:** `ipa-client-install` discovers the FreeIPA server via DNS. It needs the client's `/etc/resolv.conf` to point to a DNS server that can resolve the FreeIPA server's FQDN. If the client uses a different DNS (like public DNS or CoreDNS without FreeIPA zone forwarding), the hostname won't resolve.

**Consequences:**
- Client machines can't join the domain
- SSSD service fails to start on the client
- Domain users can't log in on client machines
- Error messages are cryptic and point to DNS as a red herring

**Warning signs:**
- `nslookup atius-srv-1.atius.com.br` fails from the client machine
- `dig SRV _kerberos._tcp.ATIUS.COM.BR` returns no results
- `/etc/resolv.conf` doesn't include the FreeIPA server as a nameserver
- `ipa-client-install` hangs for 30+ seconds before failing (DNS timeout)

**Prevention strategy:**
1. **Before `ipa-client-install` on each client:**
   - Ensure `/etc/resolv.conf` has the FreeIPA DNS server as the FIRST nameserver
   - Verify DNS resolution: `dig atius-srv-1.atius.com.br` and `dig -x 10.1.1.1`
   - Verify Kerberos SRV records: `dig SRV _kerberos._udp.ATIUS.COM.BR`
2. **Set hostname to FQDN on each client before enrollment:**
   ```bash
   hostnamectl set-hostname client-1.atius.com.br
   ```
3. **After enrollment, verify:**
   - `id admin@atius.com.br` returns user info
   - `kinit admin@ATIUS.COM.BR` obtains a Kerberos ticket
   - `sssctl domain-status atius.com.br` shows "Active: true"
4. **For CoreDNS integration:** Configure CoreDNS to forward `atius.com.br` zone queries to the FreeIPA DNS server, so all WireGuard clients can resolve FreeIPA hostnames

**Phase mapping:** Client Enrollment phase — validate DNS from each client BEFORE running `ipa-client-install`.

**Confidence:** HIGH — verified via FreeIPA mailing lists, ServerFault 1016915, Red Hat RHEL 7 troubleshooting docs, and SSSD community reports.

---

### Pitfall 10: Migration from Existing Samba — POSIX UID/GID Mapping Breaks File Permissions

**What goes wrong:** The existing Samba on `10.1.1.2` uses local Linux users (e.g., `ubuntu` with UID 1000). After migrating to FreeIPA-integrated Samba, users authenticate via FreeIPA/Kerberos, and their UIDs are managed by FreeIPA's ID ranges (typically starting at 10001+ for POSIX accounts). Files that were owned by UID 1000 now appear to be owned by an unknown user, and the FreeIPA user with the same username has a completely different UID.

**Why it happens:** FreeIPA assigns POSIX UIDs from its configured ID range (`ipa idrange-find` shows the range). The local `ubuntu` user (UID 1000) and the FreeIPA `ubuntu` user (UID 10001+) are different identities from the filesystem's perspective. When Samba uses `idmap_sss` (recommended for FreeIPA), file ownership is determined by the FreeIPA UID, not the local UID.

**Consequences:**
- After migration, ALL existing files show as owned by numeric UIDs that don't map to any FreeIPA user
- File permissions (`chmod`, `chown`) may fail because the new users don't own the files
- Samba shares reject access because POSIX permissions don't match FreeIPA identities
- Shared folders become inaccessible to users who should have access
- ACLs stored as extended attributes may reference old UIDs

**Warning signs:**
- `ls -ln /path/to/shared/` shows numeric UIDs (e.g., `1000`) that don't match `id username` output
- `getfacl` shows `user:1000:rwx` but `id ubuntu` returns `uid=10001(ubuntu)`
- Samba logs show `NT_STATUS_ACCESS_DENIED` for users who should have access

**Prevention strategy:**
1. **Before migration, audit existing file ownership:**
   ```bash
   find /path/to/shared -printf '%U %p\n' | sort -u
   ```
2. **Check FreeIPA ID ranges BEFORE creating users:**
   ```bash
   ipa idrange-find
   ```
   Ensure the range doesn't conflict with existing local UIDs.
3. **If possible, pre-assign UIDs in FreeIPA to match existing local UIDs** (requires careful ID range planning)
4. **Alternative:** Use `chown -R` to reassign file ownership after migration (time-consuming but reliable):
   ```bash
   find /path/to/shared -user 1000 -exec chown ubuntu '{}' +
   ```
5. **Use `cp -a` or `rsync -aX` to preserve POSIX ACLs** during data migration
6. **Test with a small subset of files first** before migrating the entire share

**Phase mapping:** Samba Migration phase — audit existing UIDs/GIDs and file ownership BEFORE migrating data.

**Confidence:** HIGH — verified via FreeIPA migration documentation, Samba idmap documentation, ServerFault 1030125 (consistent POSIX UID generation), and standard POSIX file permission behavior.

---

## Minor Pitfalls

### Pitfall 11: SELinux Denials on Ubuntu

**What goes wrong:** Ubuntu uses AppArmor, not SELinux. FreeIPA installation scripts assume SELinux is present and may attempt to set SELinux booleans (`setsebool`) or file contexts (`semanage fcontext`). On Ubuntu, these commands fail silently or cause the installer to abort with cryptic errors.

**Prevention:** Verify which MAC system is active. On Ubuntu, ensure AppArmor profiles don't interfere with FreeIPA services. The `freeipa-server` package on Ubuntu should handle this, but it's a known source of installation failures.

**Confidence:** MEDIUM — inferred from FreeIPA's RHEL-centric design and Ubuntu's AppArmor default.

### Pitfall 12: CoreDNS vs FreeIPA DNS Coexistence

**What goes wrong:** The existing setup uses CoreDNS for DNS resolution. FreeIPA installs BIND (named) as its DNS server. Both can't authoritatively serve the same zone. If CoreDNS continues serving `atius.com.br` records while FreeIPA's BIND also serves them, clients get inconsistent results depending on which DNS they query.

**Prevention:** Choose ONE authoritative DNS source for `atius.com.br`. Either:
- Migrate all DNS to FreeIPA's BIND and disable CoreDNS
- Keep CoreDNS as the primary DNS and configure it to forward the FreeIPA zone to FreeIPA's BIND
- Use FreeIPA DNS as primary and configure it to forward non-domain queries to CoreDNS/upstream

**Phase mapping:** Prerequisite/DNS phase — resolve before FreeIPA install.

**Confidence:** HIGH — DNS authority is a fundamental networking concept; verified via FreeIPA InstallAndDeploy docs.

### Pitfall 13: NTP Time Synchronization Breaks Kerberos

**What goes wrong:** Kerberos requires all machines in the realm to have synchronized clocks (within 5 minutes by default). If the FreeIPA server's clock drifts, or client machines aren't synced, authentication fails with `"Clock skew too great"`.

**Prevention:**
- Configure NTP on the FreeIPA server: `chronyd` or `ntpd` pointing to reliable upstream sources
- Configure all client machines to sync time (SSSD can handle this, or use `chronyd`)
- Monitor clock drift as part of infrastructure monitoring

**Phase mapping:** Prerequisite phase (NTP setup) and ongoing Operations.

**Confidence:** HIGH — Kerberos spec (RFC 4120) requirement, well-documented in all Kerberos guides.

### Pitfall 14: ARM64 (aarch64) Architecture Compatibility

**What goes wrong:** This server runs `aarch64` (ARM64). Some packages in the FreeIPA ecosystem may have limited ARM64 support or may not be available in Ubuntu's repositories at all. Dogtag (the PKI system), 389-ds (the directory server), and SSSD all need ARM64 builds.

**Prevention:**
- Verify ALL required packages are available for `arm64` before starting:
  ```bash
  apt-cache policy freeipa-server sssd 389-ds-base dogtag-pki
  ```
- If packages are missing or have version mismatches, consider using a RHEL/Rocky Linux container or VM instead
- Test the entire stack in an ARM64 VM before production deployment

**Confidence:** MEDIUM — ARM64 support has improved significantly in recent Ubuntu releases, but FreeIPA's Ubuntu packages are community-maintained and may lag.

### Pitfall 15: Docker Containers and Domain Integration

**What goes wrong:** The server runs ~25 Docker containers (Portainer, Plane, n8n, Open WebUI, Paperclip, Jenkins). After FreeIPA installation:
- Containers using host networking may conflict with FreeIPA's port requirements
- Containers that need LDAP authentication need their own SSSD/PAM configuration inside the container (complex)
- Docker's default bridge network bypasses the host's DNS, so containers may not resolve FreeIPA hostnames

**Prevention:**
- Audit all Docker container port mappings BEFORE FreeIPA install
- For containers that need LDAP auth, consider using Keycloak OIDC instead of direct LDAP
- Configure Docker daemon to use FreeIPA DNS: add `"dns": ["10.1.1.1"]` to `/etc/docker/daemon.json`

**Phase mapping:** Coexistence phase — audit Docker port usage before FreeIPA installation.

**Confidence:** HIGH — standard Docker networking behavior; verified via CONCERNS.md analysis.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| FreeIPA Installation on Ubuntu ARM64 | `crypto.fips_enabled` sysctl failure (Pitfall 1) | Patch `pkihelper.py` or use RHEL/Rocky VM |
| FreeIPA Installation | Hostname not FQDN (Pitfall 2) | Set FQDN before install; verify `hostname -f` |
| DNS Configuration | Forward/reverse DNS mismatch (Pitfall 3) | Test both directions before install |
| Apache Migration | Port conflicts with FreeIPA (Pitfall 5) | Migrate ALL vhosts to alt ports and verify before FreeIPA install |
| Samba AD Trust Setup | `ipa-adtrust-install` breaks existing Samba (Pitfall 7) | Stop existing Samba, backup config/data, document UIDs |
| Samba Migration | POSIX UID/GID mismatch breaks permissions (Pitfall 10) | Audit file ownership, plan UID migration strategy |
| Keycloak LDAP Federation | Wrong LDAP schema/attributes (Pitfall 8) | Test LDAP connectivity, use FreeIPA-specific attributes |
| Client Enrollment | SSSD can't resolve FreeIPA DNS (Pitfall 9) | Configure DNS on client before `ipa-client-install` |
| Certificate Management | CA cert expiry causes total outage (Pitfall 6) | Check expiry immediately, set up monitoring |
| Single Server Architecture | No recovery if server fails (Pitfall 4) | Implement backup strategy; document restore procedure |
| CoreDNS Integration | DNS authority conflict (Pitfall 12) | Choose single authoritative DNS source |
| NTP Configuration | Clock skew breaks Kerberos (Pitfall 13) | Configure chrony on server and all clients |
| Docker Coexistence | Port conflicts and DNS resolution (Pitfall 15) | Audit container ports, configure Docker DNS |

---

## Sources

| Source | URL | Confidence |
|--------|-----|------------|
| FreeIPA Install & Deploy | https://www.freeipa.org/page/InstallAndDeploy | HIGH |
| FreeIPA Ubuntu crypto.fips_enabled bug | https://lists.fedorahosted.org/archives/list/freeipa-users@lists.fedorahosted.org/thread/ZDKZJCAQUXSI4IBZBCAEKQXVZFBTDMMB/ | HIGH |
| FreeIPA Ubuntu install GitHub issue #509 | https://github.com/freeipa/ansible-freeipa/issues/509 | HIGH |
| FreeIPA FQDN requirements | https://freeipa-users.redhat.narkive.com/Kk4S9nbk/freeipa-and-fqdn-requirements | HIGH |
| Red Hat hostname error 7029959 | https://access.redhat.com/solutions/7029959 | HIGH |
| FreeIPA Samba integration howto | https://www.freeipa.org/page/Howto/Integrating_a_Samba_File_Server_With_IPA | HIGH |
| FreeIPA AD trust migration | https://www.freeipa.org/page/V4/Migrating_existing_environments_to_Trust | HIGH |
| FreeIPA CA certificate renewal | https://www.freeipa.org/page/Howto/CA_Certificate_Renewal | HIGH |
| Red Hat CA expiry KB 7128558 | https://access.redhat.com/solutions/7128558 | HIGH |
| FreeIPA disaster recovery RHEL 9 | https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/performing_disaster_recovery_with_identity_management/recovering-a-single-server-with-replication_performing-disaster-recovery | HIGH |
| FreeIPA Samba file server auth issues | https://lists.fedorahosted.org/archives/list/freeipa-users@lists.fedorahosted.org/thread/ZLAEUG2OTYM3D2VOCJXBOAGLZFKZDM2F/ | HIGH |
| Keycloak LDAP federation config | Context7 /keycloak/keycloak (server_admin topics) | HIGH |
| Keycloak cn vs uid mapper bug #13492 | https://github.com/keycloak/keycloak/issues/13492 | HIGH |
| Red Hat Keycloak-IPA federation 3010401 | https://access.redhat.com/solutions/3010401 | HIGH |
| Kerberos DNS requirement RFC 4120 | https://datatracker.ietf.org/doc/html/rfc4120 | HIGH |
| Kerberos setup on Ubuntu guide | https://oneuptime.com/blog/post/2026-03-02-how-to-install-and-configure-kerberos-kdc-on-ubuntu/view | MEDIUM |
| FreeIPA Samba domain controller design | https://freeipa.readthedocs.io/en/ipa-4-11/designs/adtrust/samba-domain-controller.html | HIGH |
| Dogtag certificate lifetimes | https://frasertweedale.github.io/blog-redhat/posts/2019-03-04-dogtag-system-cert-lifetime.html | HIGH |
| Project CONCERNS.md | /home/ubuntu/.planning/codebase/CONCERNS.md | HIGH |
| Project PROJECT.md | /home/ubuntu/.planning/PROJECT.md | HIGH |
