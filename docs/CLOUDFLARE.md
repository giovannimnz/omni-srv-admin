# Cloudflare Configuration — omni-srv-admin

## Overview

Cloudflare é usado como CDN, proxy reverso e DNS manager para os domínios `atius.com.br` e `zentrius.com.br`. Toda a infraestrutura web passa pelo Cloudflare antes de chegar ao servidor de origem (Apache2).

---

## Account

| Property | Value |
|----------|-------|
| **Email** | `giovannimunizds@gmail.com` |
| **Account ID** | `cd986c150252827c1df07dcceaa92b4b` |
| **Account Name** | Giovanni Account |
| **User ID** | `ad7349df756c5077ea311f63a3e76700` |
| **Account Created** | 2025-05-18 |
| **Role** | Super Administrator — All Privileges |
| **Global API Key** | `cfk_Br...` (ver `~/.zshrc` em omni-srv-admin-1) |
| **Auth Method** | `X-Auth-Email` + `X-Auth-Key` headers (NÃO usar Bearer) |

### Credenciais no Ambiente

```bash
# .zshrc — variáveis de ambiente
export CF_AUTH_EMAIL="giovannimunizds@gmail.com"
export CF_GLOBAL_API_KEY="cfk_Br...REDACTED"
export CF_ACCOUNT_ID="cd986c150252827c1df07dcceaa92b4b"
export CF_ACCOUNT_NAME="Giovanni Account"
```

---

## Zones

| Domain | Zone ID | Status | Plan | DNS Records |
|--------|---------|--------|------|-------------|
| `atius.com.br` | `5b998a5d911f5a4102b6179df7f4518d` | active | Free Website | 60 (39 proxied, 21 DNS-only) |
| `zentrius.com.br` | `c07d652ec384c614418c28411ceed4ab` | active | Free Website | 3 (SPF/DMARC only) |

```bash
export CF_ZONE_ID_ATIUS="5b998a5d911f5a4102b6179df7f4518d"
export CF_ZONE_ID_ZENTRIUS="c07d652ec384c614418c28411ceed4ab"
```

---

## API Access

### Authentication — Critical Distinction

| Format | Type | Auth Method | Scope |
|--------|------|------------|-------|
| `cfk_...` | **Global API Key** | `X-Auth-Key` + `X-Auth-Email` headers | Full account |
| `cfut_...` | **Zone Token** | `Authorization: Bearer cfut_...` | Zone-scoped only |
| `cfur_...` | **User Token** | `Authorization: Bearer cfur_...` | User-scoped only |

**ATENÇÃO:** `cfk_...` NÃO usa Bearer header. Usa headers `X-Auth-Email` e `X-Auth-Key`.

### Endpoints Principais

```bash
# Verificar credencial
curl -s "https://api.cloudflare.com/client/v4/user" \
  -H "X-Auth-Email: $CF_AUTH_EMAIL" \
  -H "X-Auth-Key: $CF_GLOBAL_API_KEY"

# Listar zonas
curl -s "https://api.cloudflare.com/client/v4/zones" \
  -H "X-Auth-Email: $CF_AUTH_EMAIL" \
  -H "X-Auth-Key: $CF_GLOBAL_API_KEY"

# DNS records de atius.com.br
curl -s "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID_ATIUS/dns_records?per_page=100" \
  -H "X-Auth-Email: $CF_AUTH_EMAIL" \
  -H "X-Auth-Key: $CF_GLOBAL_API_KEY"

# Verificar token (para tokens, não global key)
curl -s "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer <token>"
```

### Aliases Úteis (disponíveis após carregar .zshrc)

```bash
cf-zones          # Lista todas as zonas
cf-dns-atius     # Lista DNS records de atius.com.br
cf-verify        # Verifica credencial global
cf-user-tokens    # Lista tokens da conta
```

---

## DNS Records — atius.com.br

60 DNS records gerenciados via Cloudflare. Principais:

| Hostname | Type | Content | Proxy |
|----------|------|---------|-------|
| `aion.atius.com.br` | A | `137.131.190.161` | proxied |
| `router.atius.com.br` | A | `137.131.190.161` | proxied |
| `api.atius.com.br` | A | `137.131.190.161` | proxied |
| `app.atius.com.br` | A | `137.131.190.161` | proxied |
| `dashboard.atius.com.br` | A | `137.131.190.161` | proxied |
| `jenkins.atius.com.br` | A | `137.131.190.161` | proxied |
| `plane.atius.com.br` | A | `137.131.190.161` | proxied |
| `pm2.atius.com.br` | A | `137.131.190.161` | proxied |
| `trade.atius.com.br` | A | `137.131.190.161` | proxied |
| `n8n.atius.com.br` | A | `137.131.190.161` | proxied |
| `taiga.atius.com.br` | A | `137.131.190.161` | proxied |

---

## SSL / Origin Certificates

Certificados de origem Cloudflare em `/etc/ssl/cloudflare/`:

```
/etc/ssl/cloudflare/
├── atius.com.br.pem      # Origin certificate for *.atius.com.br
└── (outros certificados)
```

Cloudflare faz terminação SSL. O servidor de origem usa certificados de_origin_request.

---

## Cloudflare Origin Rules (Phase 02)

**Status:** Implementado conforme ROADMAP Phase 02.

Phase 02 planejou que Apache2 seria migrado para portas 9080/9444 e Cloudflare Origin Rules roteariam porta 443 → origin port 9444 para todos os 66 hostnames.

**Nota:** Audit de 2026-05-06 identificou que Apache2 ainda está nas portas originais 80/443. A migração de portas pode ter sido revertida ou nunca ter sido concluída. Verificar estado real antes de prosseguir.

---

## Anti-Bot / Turnstile

Cloudflare usa **Turnstile CAPTCHA** que bloqueia TODAS tentativas de automação headless:
- browser_navigate tool → timeout
- Playwright + Xvfb → challenge page
- Selenium + Chrome headless → crash

**Solução:** Usar API diretamente — `api.cloudflare.com/client/v4/` não é afetado pelo anti-bot.

---

## Permissões (Super Administrator)

90+ scopes habilitados incluindo:

| Categoria | Permissões |
|-----------|-----------|
| **Zone** | zone:edit, zone:read, zone_settings:edit, zone_settings:read, zone_versioning:* |
| **DNS** | dns_records:edit, dns_records:read |
| **SSL** | ssl:edit, ssl:read |
| **WAF** | waf:edit, waf:read |
| **Cache** | cache_purge:edit, query_cache:* |
| **Workers** | worker:edit, worker:read |
| **Billing** | billing:edit, billing:read |
| **Account** | organization:*, member:*, subscription:* |
| **R2** | r2_bucket:*, r2_bucket_item:*, r2_bucket_warehouse:* |
| **AI** | vectorize:*, dex:*, cds:* |
| **Access** | access:*, dash_sso:* |
| **Teams** | teams:*, teams_device:* |
| **Logs** | logs:edit, logs:read |
| **integrations** | integration:*, cf1_integration:* |

---

## Limitações Conhecidas

- **Browser automation:** Bloqueada por Turnstile — usar API exclusivamente
- **Zone Token (cfut_):** Não tem acesso a endpoints account-level → erro 9109
- **Dashboard manual:** Requer login em https://dash.cloudflare.com/profile/api-tokens
- **Global API Key:** Diferente do token criado na aba API Tokens — é o "Global API Key" em profile

---

## Referências

- Skill: `cloudflare-api-operations` (hermes skills)
- Dashboard: https://dash.cloudflare.com/
- API Docs: https://developers.cloudflare.com/api/
- Permissão IDs: `GET /user/tokens/permission_groups`

---

*Última validação: 2026-05-07 — Global API Key válido, Super Administrator*
