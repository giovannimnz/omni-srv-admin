# Phase 1: Preparação do Host - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Configurar o servidor 10.1.1.1 com as configurações de base necessárias para receber o FreeIPA: hostname FQDN, NTP sincronizado, portas 80/443 liberadas (Apache2 migrado), mapeamento de portas documentado, e DNS resolvido.

Esta fase NÃO instala o FreeIPA — apenas prepara o terreno.
</domain>

<decisions>
## Implementation Decisions

### Hostname e FQDN
- **D-01:** FQDN do servidor FreeIPA será `ipa.atius.com.br`
- **D-02:** Hostname do OS mantido como `atius-srv-1` — FQDN configurado via `/etc/hosts` e DNS
- **D-03:** `/etc/hosts` deve incluir: `10.1.1.1 ipa.atius.com.br atius-srv-1`

### Port Mapping
- **D-04:** FreeIPA (container Docker) assume portas 80/443
- **D-05:** Apache2 movido para 9080 (HTTP) / 9444 (HTTPS) — portas 8080 e 9443 já em uso por Docker
- **D-06:** Keycloak usará 9180 (HTTP) / 9843 (HTTPS)
- **D-07:** WireGuard usará porta 51820 (padrão, sem conflito)

### NTP
- **D-08:** Usar `chrony` como serviço NTP (recomendado para VMs/cloud)
- **D-09:** Kerberos exige sincronização ±5min entre servidor e clientes

### DNS
- **D-10:** FreeIPA BIND será DNS primário para a rede interna
- **D-11:** CoreDNS será removido/desativado após FreeIPA DNS estar operacional
- **D-12:** Cloudflare Origin Rules mapearão :443 → origin:9444 para os 60+ vhosts

### Apache2 Migration
- **D-13:** Apache2 `Listen` alterado de 80/443 para 9080/9444
- **D-14:** Todos os 60+ vhosts atualizados com novas portas
- **D-15:** Cloudflare Origin Rules atualizadas para apontar para 9444
- **D-16:** Certbot configurado com `--http-01-port 9080` para renovação

### Cloudflare
- **D-17:** Proxy mode mantido (proxied) — Origin Rules definem porta de origem
- **D-18:** 60+ registros DNS podem precisar atualização de Origin Rules

### Services Coexistence
- **D-19:** PM2 apps (Atius) continuam acessíveis via Apache2 na porta 9444
- **D-20:** Docker containers existentes não são afetados (portas internas inalteradas)

### Folded Todos

Nenhum todo folded nesta fase.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Network and DNS
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` §Phase 1 — Phase goal and success criteria
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` — Requirements PREP-01 through PREP-05, APCH-01 through APCH-04
- `.planning/codebase/INTEGRATIONS.md` — Existing Apache2 vhosts, Cloudflare setup, Docker containers

### Apache2 Configuration
- `/etc/apache2/ports.conf` — Current Listen directives
- `/etc/apache2/sites-enabled/` — Current vhost configurations (60+)
- `~/GitHub/Atius-Capital/ats/` — Apache2 vhost configs managed by Atius app

### Infrastructure
- `/etc/hosts` — Current hostname and FQDN resolution
- `/etc/cloudflared/` — Cloudflare tunnel config (if applicable)
- `.planning/codebase/STACK.md` — Apache2 version, Certbot setup

### Port Matrix (Final)

| Service | HTTP | HTTPS | Notes |
|---------|------|-------|-------|
| FreeIPA | 80 | 443 | Container Docker |
| Apache2 | 9080 | 9444 | 60+ vhosts |
| Keycloak | 9180 | 9843 | Native (Java 21) |
| WireGuard | — | 51820 | UDP |
| FreeIPA LDAP | 389 | 636 | Container Docker |
| FreeIPA Kerberos | 88 | 464 | Container Docker |

### Docker Conflicts (to avoid)
- Port 8080: Docker proxy (existing container)
- Port 9443: Docker proxy (existing container)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Apache2 vhost configs** (`/etc/apache2/sites-enabled/`) — Padrão de configuração existente para 60+ vhosts; migração pode ser automatizada via script batch
- **Cloudflare Origin Rules** — Já configuradas para portas 80/443;只需 update port numbers
- **Certbot configs** — Já funcionando;只需 add `--http-01-port` flag

### Established Patterns
- **Apache2 + PM2** — PM2 apps expostos via Apache2 reverse proxy; padrão já estabelecido
- **Docker containers** — Muitos containers rodando; evitar conflito de portas é crítico
- **Portainer** — Gerencia containers; útil para verificar portas em uso

### Integration Points
- Apache2 reverse proxy → PM2 apps (API, web, webhooks)
- Apache2 → Cloudflare (proxy mode)
- Cloudflare → origin server (10.1.1.1)
- Certbot → Apache2 (HTTP-01 challenge)

### Critical Constraint
- **25+ containers Docker** rodando — muitas portas já alocadas
- Port scan necessário antes de definir qualquer porta nova
</code_context>

<specifics>
## Specific Ideas

- Usuário prefere manter hostname `atius-srv-1` em vez de alterar — FQDN via /etc/hosts é suficiente
- 60+ vhosts no Apache2 — migração deve ser automatizada (script batch), não manual
- CoreDNS será substituído pelo FreeIPA BIND — migração de DNS deve ser planejada com cuidado para não quebrar resolução interna
</specifics>

<deferred>
## Deferred Ideas

- Migração de apps Atius para Keycloak OIDC — futuro (fase separada)
- Horistic no domínio — projeto separado
- Replica FreeIPA para HA — v2
- None — discussão permaneceu dentro do escopo da fase

### Reviewed Todos (not folded)

Nenhum todo revisado nesta fase.
</deferred>

---

*Phase: 01-preparacao-do-host*
*Context gathered: 2026-04-19*
