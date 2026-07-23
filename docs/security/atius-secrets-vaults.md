# Atius Secrets Vaults

**Status:** Live baseline deployed 2026-06-25
**Scope:** Human password vault plus machine/automation secrets vault.

## Architecture

| Layer | Product | Endpoint | Exposure | Purpose |
|---|---|---|---|---|
| Human password vault | Vaultwarden | `https://vault.atius.com.br` | Public HTTPS through SRV1 Apache | Human usernames/passwords and emergency access only |
| Machine secrets vault | HashiCorp Vault | `https://10.13.1.13:8202` | OCI private/DRG primary, `wg100` reserve | Primary backend for app tokens, automation credentials, AppRole and admin break-glass material |
| Landscape secrets UI | Landscape self-hosted + bridge to dedicated HashiCorp Vault | Public HTTPS via SRV1 -> SRV3 | Operator-visible control plane | View/edit administrative records backed by the dedicated HashiCorp Vault |

Landscape is the operational control plane for the fleet. Use it to administer hosts, run controlled scripts, view package/security state, and manage selected secrets records. The dedicated private HashiCorp Vault is the primary machine/automation secrets engine. Vaultwarden remains for human credentials only.

Operational registry:

- [Atius Automation Secret Registry](atius-automation-secret-registry.md) is the canonical map of machine/automation profiles, KV paths, exported variable names, and non-exported break-glass exceptions.
- Before using any API, MCP, CLI smoke, router validation, Cloudflare operation, GitHub automation, Landscape call, or fleet script that needs a credential, load the matching profile through `atius-vault-env`.
- Do not use GBrain, Obsidian, `.zshrc`, `.env`, shell history, chat, or copied notes as the credential value source. They can point to the correct Vault profile only.

Update 2026-06-25: the Landscape UI OOPS was patched locally in the `landscape` LXD container. The broken template expression `context/url` was replaced with `view/account_url` for the "Create secret" link.

Patch details:

| Item | Path |
|---|---|
| Patched template | `/opt/canonical/landscape/canonical/landscape/ui/secrets/list-secrets.pt` inside LXD `landscape` |
| Patch backup | `/root/landscape-ui-secrets-patch-20260625T234654Z/` inside LXD `landscape` |
| Durable fix script | `/usr/local/sbin/atius-landscape-secrets-ui-fix.sh` inside LXD `landscape` |
| APT post-invoke hook | `/etc/apt/apt.conf.d/99atius-landscape-secrets-ui-fix` inside LXD `landscape` |

Landscape UI default and dark theme update:

| Item | Path |
|---|---|
| Edge vhost backup | `/root/landscape-edge-new-ui-20260626T021455Z/` on `atius-srv-1` |
| Runtime UI backup | `/root/landscape-modern-dark-20260626T021753Z/` inside LXD `landscape` |
| Modern dashboard shell | `/opt/canonical/landscape/canonical/landscape/static/dashboard/index.html` inside LXD `landscape` |
| Modern dashboard dark CSS | `/opt/canonical/landscape/canonical/landscape/static/dashboard/assets/atius-dark.css` inside LXD `landscape` |
| Classic UI template | `/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt` inside LXD `landscape` |
| Durable dark script | `/usr/local/sbin/atius-landscape-modern-dark.sh` inside LXD `landscape` |
| APT post-invoke hook | `/etc/apt/apt.conf.d/99atius-landscape-modern-dark` inside LXD `landscape` |

Current behavior:

- `https://landscape.atius.com.br/` returns `302` to `/account/standalone/secrets`.
- The classic UI is the default operator landing path because the Vault/secrets administrator lives there.
- `https://landscape.atius.com.br/new_dashboard/` remains available by direct URL, but is no longer the default operator UI.
- Classic routes and API routes remain available for features not yet migrated.
- Dark mode is forced for the modern dashboard and best-effort for classic Hokan pages.
- Visual smoke was captured with Playwright on 2026-06-26 and confirmed the new login shell is dark with the white Landscape logo.

Landscape internal secrets seeded after the UI fix:

| Landscape secret | Purpose |
|---|---|
| `atius-hashicorp-vault` | Reference to the dedicated private HashiCorp Vault and seeded KV paths |
| `atius-vaultwarden` | Reference to the human password vault |
| `landscape-oops` | Record of the UI fix applied for the OOPS |

Break-glass secrets imported into Landscape after operator approval on 2026-06-25:

| Landscape internal Vault path | Data ID | Purpose |
|---|---|---|
| `standalone/atius-hashicorp-vault/root_token` | `root_token` | Dedicated HashiCorp Vault emergency root access |
| `standalone/atius-hashicorp-vault/unseal_key` | `unseal_key` | Dedicated HashiCorp Vault emergency unseal |
| `standalone/atius-hashicorp-vault/omni_approle_role_id` | `role_id` | Omni automation AppRole role ID |
| `standalone/atius-hashicorp-vault/omni_approle_secret_id` | `secret_id` | Omni automation AppRole secret ID |
| `standalone/atius-vaultwarden/admin_token` | `admin_token` | Vaultwarden emergency admin token |

Landscape internal Vault snapshot after break-glass import:

- `/root/landscape-vault-breakglass-20260626T001545Z.snap` inside LXD `landscape`

Do not paste these values into chat, docs, command lines, issue trackers, or shell history. Retrieve them only through the Landscape secrets UI or root-only Vault access during a controlled recovery.

## Landscape -> HashiCorp Vault Bridge

Current bridge scope:

| Landscape secret name | Dedicated Vault logical path | Backend mode |
|---|---|---|
| `atius-hashicorp-vault` | `kv/atius/hashicorp-vault/landscape` | Read/write in Landscape UI; stored in dedicated HashiCorp Vault |

Bridge runtime on `landscape` LXD:

| Item | Path |
|---|---|
| Bridge config | `/etc/landscape/hashicorp-vault-bridge.json` |
| Bridge code | `/opt/canonical/landscape/canonical/landscape/ui/secrets/secrets.py` |
| Reapply script | `/usr/local/sbin/atius-landscape-secrets-vault-bridge.sh` |
| APT hook | `/etc/apt/apt.conf.d/99atius-landscape-secrets-zz-vault-bridge` |
| UI patch backup | `/root/landscape-secrets-vault-bridge-20260626T065149Z/` |
| Audit log | `/var/lib/landscape/landscape-hashicorp-vault-bridge.jsonl` |
| Record-summary UI backup | `/root/landscape-secrets-record-ui-20260626T074057Z/` on `atius-srv-3` |
| UI tuning backup | `/root/landscape-secrets-ui-tune-20260626T085003Z/` on `atius-srv-3` |
| UX polish backup | `/root/landscape-secrets-ux-polish-20260626T090349Z/` on `atius-srv-3` |
| UX flow backup | `/root/landscape-secrets-ux-flow-20260626T094119Z/` on `atius-srv-3` |

Bridge credential material on `atius-srv-3` host:

| Item | Path |
|---|---|
| Policy | `/root/hashicorp-vault-atius/landscape-secrets-bridge-policy.hcl` |
| AppRole role ID | `/root/hashicorp-vault-atius/landscape-secrets-bridge-role-id.json` |
| AppRole secret ID | `/root/hashicorp-vault-atius/landscape-secrets-bridge-secret-id.json` |

Notes:

- Landscape `view/edit` for `atius-hashicorp-vault` reads and writes the dedicated HashiCorp Vault path directly.
- Update 2026-07-05: Landscape `Secrets` also exposes the HashiCorp-backed automation profile records listed in [Atius Automation Secret Registry](atius-automation-secret-registry.md), including Cloudflare, browser-login access keys, Landscape SaaS API, router, Tailscale, GitHub, AI/tools, FreeIPA, Vaultwarden runtime/admin, GSD web login, Atius MCP, and AppRole records.
- Browser-login access keys live at `kv/atius/browser-login/access-keys` and appear in Landscape as `atius-browser-login-access-keys`. Vault stores material and metadata; native passkeys still require an OS/browser/hardware authenticator or a purpose-built CDP/Playwright virtual-authenticator loader.
- The full `kv/atius/hashicorp-vault/admin-breakglass` path is not exposed as a dedicated generic Landscape record because it contains list-shaped recovery/unseal fields. The generic editor stores submitted form values as strings.
- The Landscape internal Vault is kept as a mirrored administrative copy for this record, but it is no longer the primary backend for `atius-hashicorp-vault`.
- `Vaultwarden` is not part of this machine-secret bridge and remains dedicated to human credential storage.

Landscape secrets UI behavior after the 2026-06-26 record-summary update:

- The secrets list remains the simpler record list (`Record Name` + `Actions`).
- The `view` page shows one summarized row per credential record, not one row per field.
- The summary row intentionally hides noisy/sensitive categories and shows only `Service / Credential`, `Endpoint`, and `Contents`.
- `Endpoint` shows only the masked value, without repeating backend key names.
- `Contents` is a count summary such as fields, IDs, protected values, and paths; full values remain available only in edit mode.
- The `edit` page shows the same compact summary row; clicking it or using `Open editor` opens a modal table with add/remove row controls, bounded height, vertical-only scroll, and `Save changes` inside the modal footer.
- Runtime templates are under `/opt/canonical/landscape/canonical/landscape/ui/secrets/` inside LXD `landscape`.
- Durable template copies were refreshed under `/root/landscape-secrets-admin-ui-20260626T063107Z/patched/` and `/root/landscape-secrets-vault-bridge-20260626T065149Z/patched/`.

## Vaultwarden

Host:

- Runtime host: `atius-srv-3`
- Edge host: `atius-srv-1`
- Container: `vaultwarden-atius`
- Service: `container-vaultwarden-atius.service`
- Public URL: `https://vault.atius.com.br`
- Private upstream: `http://10.100.100.3:8088`
- Data directory: `/srv/vaultwarden-atius/data`
- Backup directory: `/srv/vaultwarden-atius/backups`
- Secret env: `/root/vaultwarden-atius/vaultwarden.env`

Security baseline:

- `SIGNUPS_ALLOWED=false`
- `INVITATIONS_ALLOWED=true`
- `ADMIN_TOKEN` stored as Argon2 PHC string, not plain text
- HTTPS terminates on `atius-srv-1` with Let's Encrypt
- Cloudflare DNS record is DNS-only, not proxied

Admin:

- Admin panel: `https://vault.atius.com.br/admin`
- The admin password is the original random token used to generate the Argon2 PHC hash.
- Root-only admin token recovery file: `/root/vaultwarden-atius/admin-token.txt` on `atius-srv-3`.
- Root-only environment file: `/root/vaultwarden-atius/vaultwarden.env` on `atius-srv-3`.
- Do not copy the token into repo docs, tickets, chat, or shell history.

Backup:

- Script: `/usr/local/sbin/atius-vaultwarden-backup.sh`
- Timer: `atius-vaultwarden-backup.timer`
- Schedule: daily around `03:20` UTC with randomized delay
- First backup: `/srv/vaultwarden-atius/backups/vaultwarden-atius-20260625T212856Z.tgz`

Rollback:

```bash
sudo systemctl disable --now container-vaultwarden-atius.service
sudo a2dissite vault.atius.com.br.conf
sudo systemctl reload apache2
```

DNS rollback:

- Remove or repoint Cloudflare `A vault.atius.com.br`.

## HashiCorp Vault

Host:

- Runtime host: `atius-srv-3`
- Container: `hashicorp-vault-atius`
- Service: `container-hashicorp-vault-atius.service`
- Private URL: `https://10.13.1.13:8202`
- Cluster port: `10.100.100.3:8203`
- Storage: integrated raft
- Config directory: `/srv/hashicorp-vault-atius/config`
- Data directory: `/srv/hashicorp-vault-atius/data`
- TLS directory: `/srv/hashicorp-vault-atius/tls`
- Audit log directory: `/srv/hashicorp-vault-atius/logs`
- Backup directory: `/srv/hashicorp-vault-atius/backups`
- Root-only init material: `/root/hashicorp-vault-atius/init.json`
- Root-only AppRole material: `/root/hashicorp-vault-atius/omni-automation-role-id.json` and `/root/hashicorp-vault-atius/omni-automation-secret-id.json`

Security baseline:

- Bound only to WireGuard IP `10.100.100.3`
- TLS enabled with local certificate for `secrets.atius.internal`, `vault-internal.atius.internal`, `10.100.100.3`, and `127.0.0.1`
- Initialized and unsealed
- KV v2 enabled at `kv/`
- AppRole enabled
- Policy `omni-automation` created for `kv/omni/*` and `kv/atius/*`
- File audit enabled at `/vault/logs/audit.log`

Operational status after deployment:

```text
initialized=True sealed=False standby=False
```

Post-start recovery guard (2026-07-13):

- `container-hashicorp-vault-atius.service` has the drop-in
  `/etc/systemd/system/container-hashicorp-vault-atius.service.d/20-auto-unseal.conf`.
- Its `ExecStartPost` runs `/usr/local/sbin/atius-hashicorp-vault-after-start.sh`.
- The helper waits for the local Vault API, exits without mutation when already
  unsealed, and otherwise invokes the root-only backup/unseal helper before
  verifying `sealed=false`. It never writes recovery material to service logs.
- A controlled restart on 2026-07-13 returned the API to HTTP 200 with
  `initialized=true` and `sealed=false`.

Seeded KV paths:

| Path | Purpose |
|---|---|
| `kv/atius/cloudflare/api` | Source of truth for Cloudflare automation variables: `CF_ACCOUNT_ID`, `CF_ACCOUNT_NAME`, `CF_AUTH_EMAIL`, `CF_GLOBAL_API_KEY`, `CF_ZONE_ID_ATIUS`, and `CF_ZONE_ID_ZENTRIUS`; old shell files are migration evidence only |
| `kv/atius/landscape/saas-api` | Landscape SaaS API variables plus `OMNI_LANDSCAPE_*` aliases |
| `kv/atius/router-ai-atius/api` | Router/New API automation key and client aliases |
| `kv/atius/tailscale/api` | Tailscale API and auth tokens |
| `kv/atius/github/automation` | GitHub automation tokens imported from SRV-1 shell files |
| `kv/atius/ai/api-keys` | Active AI provider keys and MiniMax defaults |
| `kv/atius/tools/api-keys` | Tool API keys such as Brave and Context7 |
| `kv/atius/freeipa/bootstrap` | FreeIPA bootstrap material mirrored from `/root/freeipa-atius/bootstrap.env` |
| `kv/atius/vaultwarden/admin` | Vaultwarden admin recovery token mirrored from `/root/vaultwarden-atius/admin-token.txt` |
| `kv/atius/srv1/shell-exports/home-ubuntu-env` | SRV-1 `/home/ubuntu/.env` exports imported on 2026-07-04; values live under `values` |
| `kv/atius/srv1/shell-exports/home-ubuntu-zshrc` | SRV-1 `/home/ubuntu/.zshrc` exports imported on 2026-07-04; values live under `values` |
| `kv/atius/srv1/shell-exports/home-ubuntu-merged` | Merged SRV-1 shell exports, `.env` then `.zshrc` precedence, imported on 2026-07-04 |
| `kv/atius/vaultwarden/runtime` | Vaultwarden runtime env mirrored from `/root/vaultwarden-atius/vaultwarden.env` |
| `kv/atius/atius-mcp/api` | Source of truth for `ATIUS_MCP_TOKEN` used by `https://mcp.atius.com.br/gbrain`, `https://mcp.atius.com.br/obsidian`, and `https://mcp.atius.com.br/oci-admin`; runtime env files are hydration caches only |
| `kv/atius/gsd/web-login` | GSD web login password |
| `kv/atius/hashicorp-vault/approle/omni-automation` | Omni automation AppRole |
| `kv/atius/hashicorp-vault/approle/landscape-secrets-bridge` | Landscape bridge AppRole |
| `kv/atius/hashicorp-vault/admin-breakglass` | Vault root/unseal/recovery material; break-glass only |

Root-only helpers:

| Helper | Host | Purpose |
|---|---|---|
| `/usr/local/sbin/atius-vault` | `atius-srv-3` | Runs the Vault CLI against the dedicated HashiCorp Vault using root-only init material |
| `/usr/local/sbin/atius-vault-kv-put-json` | `atius-srv-3` | Stores stdin JSON into a KV path without exposing values in argv |
| `/usr/local/sbin/atius-vault-export-env` | `atius-srv-3` | Emits shell `export` lines for selected profiles |
| `/home/ubuntu/.local/bin/atius-vault-env` | Linux Codex hosts | SSH-safe wrapper for exporting selected profiles; wrappers that SSH to `atius-srv-3` use `ssh -n` |
| `/home/horistic/.local/bin/atius-vault-env` | `horistic-srv` | Uses a restricted SSH key forced to `/home/ubuntu/.local/bin/atius-vault-export-ssh` on `atius-srv-3` |

Load environment variables on demand:

```bash
source <(atius-vault-env cloudflare landscape)
```

Windows Codex helper added on 2026-07-05:

```powershell
atius-vault-env cloudflare
codex-cloud-ops
```

`atius-vault-env` calls the authoritative wrapper on `atius-srv-1` and emits
shell exports. `codex-cloud-ops` loads the Cloudflare profile into the child
Codex process and injects the Cloudflare MCP via `-c` without persisting the
secret in the Windows user environment.

Cloudflare direct REST access uses the Vault `cloudflare` profile and the
Cloudflare global-key header pair `X-Auth-Email` + `X-Auth-Key`. Do not pass
Cloudflare keys in argv, commit them, paste them into chat, or record them in
Obsidian/GBrain/logs. Validation should report only HTTP status, `success`, and
zone names/ids that are not secret.

Available profiles:

- `cloudflare`
- `landscape`
- `router-ai-atius`
- `tailscale`
- `github`
- `ai`
- `tools`
- `freeipa`
- `vaultwarden`
- `vaultwarden-runtime`
- `gsd-web-login`
- `atius-mcp`
- `vault-omni-approle`
- `vault-landscape-bridge`

The SRV-1 shell export snapshots are intentionally not added as always-on
profiles yet. Read them directly from Vault or add a narrower profile per
consumer. Do not source the merged snapshot blindly because it includes runtime
environment entries such as `PATH`, `DISPLAY`, and `XAUTHORITY` in addition to
API credentials.

Do not add this command unconditionally to shell startup until the consumers have been migrated away from direct `.zshrc` exports.

## Recovery 2026-07-13

- Recovered a sealed Vault after a container restart by creating a fresh Raft
  snapshot through the existing root-only helper.
- Corrected the Landscape bridge from retired `https://10.1.1.3:8202` to
  `https://10.13.1.13:8202`; the bridge config backup is kept inside the
  `landscape` LXD container.
- AppRole smoke read all 16 allowlisted records. A no-op read/write round-trip
  of `atius-browser-login-access-keys` returned HTTP 200 with data preserved.

## Landscape Secrets UI Fix Rollback

Inside the `landscape` LXD container:

```bash
sudo lxc exec landscape -- bash
cp /root/landscape-ui-secrets-patch-20260625T234654Z/list-secrets.pt.orig /opt/canonical/landscape/canonical/landscape/ui/secrets/list-secrets.pt
rm -f /var/lib/landscape/landscape-chameleon-cache/list_secrets*
rm -f /etc/apt/apt.conf.d/99atius-landscape-secrets-ui-fix
systemctl restart landscape-appserver.service
```

## Landscape UI Default/Dark Rollback

On `atius-srv-1`:

```bash
sudo cp /root/landscape-edge-new-ui-20260626T021455Z/landscape.atius.com.br.conf.orig /etc/apache2/sites-available/landscape.atius.com.br.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Inside the `landscape` LXD container:

```bash
cp /root/landscape-modern-dark-20260626T021753Z/dashboard-index.html.orig /opt/canonical/landscape/canonical/landscape/static/dashboard/index.html
cp /root/landscape-modern-dark-20260626T021753Z/hokan-page.pt.orig /opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt
rm -f /opt/canonical/landscape/canonical/landscape/static/dashboard/assets/atius-dark.css
rm -f /etc/apt/apt.conf.d/99atius-landscape-modern-dark
rm -f /var/lib/landscape/landscape-chameleon-cache/*
systemctl restart landscape-appserver.service
```

Backup:

- Script: `/usr/local/sbin/atius-hashicorp-vault-backup.sh`
- Timer: `atius-hashicorp-vault-backup.timer`
- Schedule: daily around `03:35` UTC with randomized delay
- First snapshot: `/srv/hashicorp-vault-atius/backups/hashicorp-vault-atius-20260625T212933Z.snap`

Unseal:

Use only root shell on `atius-srv-3`. Do not print keys:

```bash
sudo /usr/local/sbin/atius-hashicorp-vault-backup.sh
```

The backup script reads `/root/hashicorp-vault-atius/init.json`, unseals if needed, and writes a raft snapshot.

Rollback:

```bash
sudo systemctl disable --now container-hashicorp-vault-atius.service
```

Do not delete `/srv/hashicorp-vault-atius` or `/root/hashicorp-vault-atius` unless a verified off-host backup exists.

## Immediate Follow-ups

1. Create the first Vaultwarden admin/user account through `/admin`.
2. Decide SMTP settings for Vaultwarden invitations and emergency recovery.
3. Migrate consumers from shell-file secrets to `atius-vault-env` or direct Vault AppRole reads.
4. Add internal DNS alias `secrets.atius.internal` after Phase 34/FreeIPA DNS forwarding is production-ready.
5. Run a restore drill for both backup formats before relying on either vault as sole source of truth.
