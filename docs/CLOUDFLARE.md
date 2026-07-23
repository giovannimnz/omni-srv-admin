# Cloudflare Configuration — omni-srv-admin

## Overview

Cloudflare é usado como CDN, proxy reverso e DNS manager para os domínios
`atius.com.br`, `horistic.com` e `zentrius.com.br`. Toda a infraestrutura web
passa pelo Cloudflare antes de chegar ao servidor de origem (Apache2 ou edge
equivalente).

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
| **Global API Key** | HashiCorp Vault profile `cloudflare`, path `kv/atius/cloudflare/api` |
| **Auth Method** | `X-Auth-Email` + `X-Auth-Key` headers (NÃO usar Bearer) |

### Credenciais e hidratação

```bash
# Fonte autoritativa; não gravar valores no repo, shell history ou docs.
~/.local/bin/atius-vault-env cloudflare
```

O profile hidrata `CF_ACCOUNT_ID`, `CF_ACCOUNT_NAME`, `CF_AUTH_EMAIL`,
`CF_GLOBAL_API_KEY`, `CF_ZONE_ID_ATIUS` e `CF_ZONE_ID_ZENTRIUS`. `.env`,
`.zshrc` e environment do processo são somente caches transitórios.

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

### Aliases úteis

São conveniências locais e só devem ser usados depois de hidratar o profile
Vault `cloudflare` no processo atual; a `.zshrc` não é fonte de credencial.

```bash
cf-zones          # Lista todas as zonas
cf-dns-atius     # Lista DNS records de atius.com.br
cf-verify        # Verifica credencial global
cf-user-tokens    # Lista tokens da conta
```

---

## DNS Records — atius.com.br

Nao hardcode contagens de DNS; validar via API antes de auditorias ou release.
Snapshot operacional principal:

| Hostname | Type | Content | Proxy |
|----------|------|---------|-------|
| `casa.atius.com.br` | A | origin público canônico do SRV-1; consultar API/inventory | proxied |
| `aion.atius.com.br` | A | `137.131.190.161` | proxied |
| `router.atius.com.br` | A | `137.131.190.161` | proxied |
| `wayland.atius.com.br` | A/CNAME | edge SRV-1 -> SRV-3 `25725` | proxied |
| `mcp.atius.com.br` | A/CNAME | edge SRV-1 -> MCPs: GBrain `127.0.0.1:3131` via `/gbrain`, Obsidian `10.11.1.11:27124` via `/obsidian`, OCI Admin `10.13.1.13:8090` via `/oci-admin` | proxied |
| `landscape.atius.com.br` | A/CNAME | edge SRV-1/SRV-3, validar vhost | proxied |
| `portainer.atius.com.br` | A/CNAME | K3s Portainer edge | proxied |
| `docker.atius.com.br` | A/CNAME | K3s Portainer edge | proxied |
| `cloudbeaver.atius.com.br` | A | `137.131.190.161` -> `8978` | proxied |
| `api.atius.com.br` | A | `137.131.190.161` | proxied |
| `app.atius.com.br` | A | `137.131.190.161` | proxied |
| `dashboard.atius.com.br` | A | `137.131.190.161` | proxied |
| `jenkins.atius.com.br` | A | `137.131.190.161` | proxied |
| `plane.atius.com.br` | A | `137.131.190.161` | proxied |
| `pm2.atius.com.br` | A | `137.131.190.161` | proxied |
| `trade.atius.com.br` | A | `137.131.190.161` | proxied |
| `n8n.atius.com.br` | A | `137.131.190.161` | proxied |
| `taiga.atius.com.br` | A | `137.131.190.161` | proxied |

### Casa Remote Gateway — snapshot RustGuac 2026-07-19

| Campo | Estado |
|---|---|
| Record | exatamente um `A`; `proxied=true`; `proxiable=true` |
| TTL | API `1`, isto é, `Automatic` |
| Zone SSL | `Full (strict)` |
| WebSockets / TLS 1.3 | habilitados |
| Minimum TLS | `1.0` no snapshot |
| Always Use HTTPS | `off`; Apache `*:80` responde `301` |
| Cloudflare Tunnel | zero ativos; nenhum associado a Casa |

Fluxo confirmado por edge, probe de origin com SNI e access log:

```text
ssh.atius.com.br DNS-only HTTPS/WSS -> Apache atius-srv-1:443
  /ssh-* -> ATS gateway 127.0.0.1:8196 -> RustGuac 127.0.0.1:8089 (4/4)
rdp.atius.com.br proxied HTTPS/WSS -> gateway 127.0.0.1:8197 -> RustGuac
casa.atius.com.br proxied -> redirects remotos + router origin dinâmico:8888
```

O quarto endpoint nativo é
`A ssh-horistic-srv.atius.com.br -> 163.176.232.119`, DNS-only, TTL 300,
record `4f737eea28e12c5eefc0eb736dfde98e`. O browser Horistic não volta pela
internet: RustGuac usa relay loopback `8922` e OCI/DRG até `10.21.1.21:22`.
O RDP já usa RustGuac/guacd e alcança NLA; o desktop aguarda a senha Microsoft
correta da conta `muniz`, não disponível no Vault.

Não há Spectrum/raw SSH/RDP. O Cloudflare protege somente a superfície web;
RustGuac converte browser HTTPS/WSS em SSH/RDP no backend. O DNS Casa não
aponta ao WAN residencial.

Certificado edge: GTS `WE1`, `CN=atius.com.br`, SAN wildcard, válido até
`2026-10-05`, fingerprint SHA-256
`56:AD:03:F7:38:CC:F5:78:CF:C9:D9:C3:AF:70:EC:0C:90:FA:C5:69:78:94:1F:89:38:71:3A:C6:6C:3A:D3:E5`.
O hop origin usa Cloudflare Origin CA wildcard válido até 2041.

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

Validação 2026-07-12:

- `router.atius.com.br/` e `/api/status` retornam `200` via SRV-1 Podman
  `0.0.0.0:3000`.
- `router.atius.com.br/docs/` retorna `503`; vhost aponta para
  `127.0.0.1:3003`, mas nao ha listener em `3003`.
- `wayland.atius.com.br/api/auth/status` retorna `200`; runtime live no
  SRV-3 com `PORT=25725`.
- `mcp.atius.com.br/gbrain` aceita MCP `initialize` com `200`; backend GBrain
  escuta local-only em `127.0.0.1:3131`.
- `mcp.atius.com.br/gbrain/health` pode nao estar exposto no edge atual; nao
  usar esse path como gate principal quando `initialize` ja estiver verde.
- `mcp.atius.com.br/obsidian` e MCP `initialize` passam quando o bearer
  `ATIUS_MCP_TOKEN` e a sessao MCP estao corretos.
- `mcp.atius.com.br/oci-admin` usa o backend DRG `10.13.1.13:8090`; GET/HEAD
  retornam `405`, POST sem bearer retorna `401`, e `initialize` autenticado
  retorna `200` com `serverInfo.name=oci-admin` e nove tools.
- `landscape.atius.com.br/` retorna `302`; reconciliar vhost/porta live antes
  de declarar porta `6554` como ativa.

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
- **Casa redirect:** `Always Use HTTPS` está off; o `301` depende do Apache
- **Casa origin:** responde diretamente em `443`; manter Origin CA/ACLs e
  avaliar Authenticated Origin Pulls
- **Credencial ampla:** migrar de Global API Key para API Token de escopo
  mínimo quando o fluxo de automação estiver pronto
- **Docs do router:** `/docs/` esta degradado ate o target `3003` voltar a
  ouvir ou o vhost apontar para a rota atual.

---

## Referências

- Skill: `cloudflare-api-operations` (hermes skills)
- Dashboard: https://dash.cloudflare.com/
- API Docs: https://developers.cloudflare.com/api/
- Permissão IDs: `GET /user/tokens/permission_groups`

---

*Última validação: 2026-07-19 — Casa auditado read-only via API, edge e origin;
API key não foi reexposta nem registrada em logs/docs.*
