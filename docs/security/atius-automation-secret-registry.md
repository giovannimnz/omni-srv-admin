# Atius Automation Secret Registry

**Status:** active baseline verified on 2026-07-05
**Authority:** HashiCorp Vault on `atius-srv-3`, not Vaultwarden

## Rule

Before any API, MCP, CLI smoke, router validation, Cloudflare operation, GitHub automation, Landscape call, or fleet script that needs a credential, load it from HashiCorp Vault.

Do not rely on `.zshrc`, `.env`, shell history, chat, copied notes, GBrain summaries, or Obsidian text as the credential source. GBrain and Obsidian are routing memory only; the credential value source is Vault.

## Runtime

| Item | Value |
|---|---|
| Vault endpoint | `https://10.13.1.13:8202` |
| Vault host | `atius-srv-3` |
| Access path from Windows Codex | `C:\Users\muniz\.local\bin\atius-vault-env.cmd` |
| Access path from SRV-1 shell | `/home/ubuntu/.local/bin/atius-vault-env` |
| Root helper | `/usr/local/sbin/atius-vault` on `atius-srv-3` |
| JSON write helper | `/usr/local/sbin/atius-vault-kv-put-json` on `atius-srv-3` |
| Export helper | `/usr/local/sbin/atius-vault-export-env` on `atius-srv-3` |

Normal shell usage:

```bash
source <(atius-vault-env cloudflare landscape router-ai-atius)
```

Windows/Codex usage:

```powershell
atius-vault-env cloudflare landscape router-ai-atius
codex-cloud-ops
```

`codex-cloud-ops` is the Cloudflare-specific launcher. For other profiles, call `atius-vault-env <profile>` in the process that will run the tool.

## Export Profiles

| Profile | Vault KV path | Exported names |
|---|---|---|
| `cloudflare` | `kv/atius/cloudflare/api` | `CF_ACCOUNT_ID`, `CF_ACCOUNT_NAME`, `CF_AUTH_EMAIL`, `CF_GLOBAL_API_KEY`, `CF_ZONE_ID_ATIUS`, `CF_ZONE_ID_ZENTRIUS` |
| `landscape` | `kv/atius/landscape/saas-api` | `LANDSCAPE_ACCESS_KEY`, `LANDSCAPE_SECRET_KEY`, `LANDSCAPE_API_KEY`, `LANDSCAPE_API_SECRET`, `LANDSCAPE_API_URI`, `LANDSCAPE_ACCOUNT_ID`, `LANDSCAPE_ACCOUNT_NAME`, `OMNI_LANDSCAPE_ENDPOINT`, `OMNI_LANDSCAPE_ACCESS_KEY`, `OMNI_LANDSCAPE_SECRET_KEY` |
| `router-ai-atius` | `kv/atius/router-ai-atius/api` | `ATIUS_ROUTER_API_KEY`, `ATIUS_ROUTER_TOKEN`, `ATIUS_ROUTER_BASE_URL`, `ATIUS_ROUTER_DEFAULT_MODEL` |
| `tailscale` | `kv/atius/tailscale/api` | `TAILSCALE_API_KEY`, `TAILSCALE_AUTH_TOKEN` |
| `github` | `kv/atius/github/automation` | `GITHUB_TOKEN`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `COPILOT_GITHUB_TOKEN` |
| `ai` | `kv/atius/ai/api-keys` | `DEEPSEEK_API_KEY_1`, `DEEPSEEK_API_KEY_2`, `DEEPSEEK_API_KEY_3`, `MINIMAX_API_KEY`, `MINIMAX_API_ANTHROPIC`, `MINIMAX_API_OPENAI`, `MINIMAX_BASE_URL`, `MINIMAX_DEFAULT_MODEL` |
| `tools` | `kv/atius/tools/api-keys` | `BRAVE_API_KEY`, `CONTEXT7_API_KEY` |
| `freeipa` | `kv/atius/freeipa/bootstrap` | `FREEIPA_FQDN`, `FREEIPA_DOMAIN`, `FREEIPA_REALM`, `FREEIPA_IP`, `IPA_ADMIN_PASSWORD`, `IPA_DS_PASSWORD` |
| `vaultwarden` | `kv/atius/vaultwarden/admin` | `VAULTWARDEN_ADMIN_TOKEN`, `VAULTWARDEN_ADMIN_URL` |
| `vaultwarden-runtime` | `kv/atius/vaultwarden/runtime` | `DOMAIN`, `SIGNUPS_ALLOWED`, `INVITATIONS_ALLOWED`, `ADMIN_TOKEN`, `ROCKET_ADDRESS`, `ROCKET_PORT`, `WEBSOCKET_ENABLED`, `LOG_LEVEL`, `EXTENDED_LOGGING` |
| `gsd-web-login` | `kv/atius/gsd/web-login` | `GSD_WEB_LOGIN_PASSWORD` |
| `atius-mcp` | `kv/atius/atius-mcp/api` | `ATIUS_MCP_TOKEN` |
| `vault-omni-approle` | `kv/atius/hashicorp-vault/approle/omni-automation` | `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID` |
| `vault-landscape-bridge` | `kv/atius/hashicorp-vault/approle/landscape-secrets-bridge` | `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID` |

## Landscape Editable Records

The Landscape `Organisation -> Secrets` page is the operator UI for editing the HashiCorp-backed automation records. It uses `/etc/landscape/hashicorp-vault-bridge.json` inside the `landscape` LXD container and the `landscape-secrets-bridge` AppRole policy.

| Landscape record | Vault KV path |
|---|---|
| `atius-hashicorp-vault` | `kv/atius/hashicorp-vault/landscape` |
| `atius-cloudflare-api` | `kv/atius/cloudflare/api` |
| `atius-browser-login-access-keys` | `kv/atius/browser-login/access-keys` |
| `atius-landscape-saas-api` | `kv/atius/landscape/saas-api` |
| `atius-router-ai-atius-api` | `kv/atius/router-ai-atius/api` |
| `atius-tailscale-api` | `kv/atius/tailscale/api` |
| `atius-github-automation` | `kv/atius/github/automation` |
| `atius-ai-api-keys` | `kv/atius/ai/api-keys` |
| `atius-tools-api-keys` | `kv/atius/tools/api-keys` |
| `atius-freeipa-bootstrap` | `kv/atius/freeipa/bootstrap` |
| `atius-vaultwarden-admin` | `kv/atius/vaultwarden/admin` |
| `atius-vaultwarden-runtime` | `kv/atius/vaultwarden/runtime` |
| `atius-gsd-web-login` | `kv/atius/gsd/web-login` |
| `atius-mcp-api` | `kv/atius/atius-mcp/api` |
| `atius-hashicorp-vault-omni-approle` | `kv/atius/hashicorp-vault/approle/omni-automation` |
| `atius-hashicorp-vault-landscape-bridge` | `kv/atius/hashicorp-vault/approle/landscape-secrets-bridge` |

`kv/atius/hashicorp-vault/admin-breakglass` is intentionally not exposed as a dedicated generic Landscape record because it contains list-shaped recovery/unseal fields. The generic editor stores submitted form values as strings; exposing that full path could corrupt list fields on save. Use the existing `atius-hashicorp-vault` compatibility record for the simple emergency fields already approved for the UI.

## Browser Login Access Keys

`kv/atius/browser-login/access-keys` is the editable landing record for browser-login credentials that may be used by automation. It is visible in Landscape as `atius-browser-login-access-keys`.

Supported schema fields:

| Field | Purpose |
|---|---|
| `credential_kind` | One of `webauthn_virtual`, `browser_profile_passkey`, `password_totp`, or `client_certificate`. |
| `browser_integration_mode` | One of `manual_profile`, `cdp_virtual_authenticator`, `extension_provider`, or `password_totp_fill`. |
| `login_url`, `origin`, `rp_id`, `account_label`, `username` | Browser-login routing and account metadata. |
| `browser_profile_path` | Native browser profile that already contains a non-exportable OS/browser passkey. |
| `webauthn_credential_id_base64url`, `webauthn_user_handle_base64url`, `webauthn_private_key_pem`, `webauthn_sign_count`, `webauthn_transport` | Material for a WebAuthn virtual authenticator flow. |
| `password`, `totp_secret` | Fallback for password plus TOTP automation when the site allows it. |
| `client_certificate_pem`, `client_private_key_pem` | Material for mTLS/client-certificate login flows. |

Important constraints:

- HashiCorp Vault is not a native Windows Hello, Chrome, or hardware FIDO2 authenticator.
- Native passkeys/security keys are usually non-exportable; the browser recognizes them through the OS authenticator, browser profile, hardware key, or credential-provider extension, not by reading a Vault KV value directly.
- For automated browser flows, use one of these patterns: keep a dedicated browser profile with the passkey already enrolled and store the profile metadata in Vault; or register a software/virtual WebAuthn credential for a CDP/Playwright-controlled browser and store that virtual credential material in Vault; or use password plus TOTP where allowed.
- Do not add `browser-login` to `atius-vault-env` by default. This record can contain private keys or passkey material and must be loaded only by a purpose-built browser automation helper.

## Non-Exported Material

| Path or source | Status |
|---|---|
| `kv/atius/hashicorp-vault/admin-breakglass` | Root/unseal/recovery material. Break-glass only; intentionally not in `atius-vault-env --help`. |
| `kv/atius/hashicorp-vault/landscape` | Compatibility record for the Landscape secrets bridge. Prefer the canonical AppRole and admin-breakglass paths above. |
| `kv/atius/srv1/shell-exports/*` | Raw SRV-1 shell-file imports. Use only for audit or migration; do not wire new automations directly to these raw paths. |
| `C:\Users\muniz\.codex\auth.json` and `/home/ubuntu/.codex/auth.json` | Codex session auth. Mutable login/session state, not an automation profile. Do not export into generic agent shells. |
| Cloudflare Access service token file | Not found on Windows or SRV-1 during the 2026-07-05 inventory. Create `kv/atius/cloudflare/access-service-token` only when a real service token exists. |
| OpenAI/Anthropic API keys from shell import | Only placeholder-length values were detected in the raw import. They are not exported by the canonical `ai` profile. |

## Verification Evidence

Verified on 2026-07-05 without printing secret values:

```text
Vault status: initialized=true sealed=false version=2.0.3
Remote profile smoke: cloudflare, landscape, router-ai-atius, tailscale, github, ai, tools, freeipa, vaultwarden, vaultwarden-runtime, gsd-web-login, atius-mcp, vault-omni-approle, vault-landscape-bridge all exported expected variable names.
Windows wrapper smoke: atius-vault-env cloudflare landscape router-ai-atius atius-mcp exported 21 expected names.
Landscape bridge config: 16 managed records after adding `atius-browser-login-access-keys`.
Landscape bridge AppRole read smoke: authenticated and read all 16 configured records with errors=0.
```

Recovery verification on 2026-07-13, without printing values:

```text
Vault post-restart health: initialized=true sealed=false standby=false HTTP 200.
Cloudflare profile: six expected names, including CF_GLOBAL_API_KEY.
Landscape bridge: canonical vault_addr=https://10.13.1.13:8202; 16 records read successfully.
Landscape edit contract: no-op read/write of atius-browser-login-access-keys returned HTTP 200 and preserved data.
```

Backups created before normalization:

```text
/root/hashicorp-vault-atius/automation-secrets-normalize-20260705T134230Z
/root/atius-vault-export-env.automation-normalize-20260705T134358Z.bak
/root/atius-vault-export-env.add-atius-mcp-20260705T135107Z.bak
/root/landscape-hashicorp-records-20260705T1415Z/hashicorp-vault-bridge.json.before
/root/hashicorp-vault-atius/landscape-secrets-bridge-policy.20260705T140808Z.bak
/root/landscape-browser-login-access-keys-20260705T1430Z/hashicorp-vault-bridge.json.before
/root/hashicorp-vault-atius/landscape-secrets-bridge-policy.browser-login-20260705T143859Z.bak
```

## Operational Checklist

1. Identify the API or MCP profile required.
2. Run `atius-vault-env <profile>` or a profile-specific launcher.
3. Confirm the tool process receives the variable names it needs.
4. Never print or paste the values.
5. If a needed credential is only in `.env`, `.zshrc`, or a local app auth file, stop and migrate it to a canonical Vault path before using it in automation.
