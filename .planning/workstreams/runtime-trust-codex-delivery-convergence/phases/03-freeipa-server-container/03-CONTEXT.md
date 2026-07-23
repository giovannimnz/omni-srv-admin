# Phase 3: FreeIPA Server Container - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning (auto mode)

<domain>
## Phase Boundary

FreeIPA rodando em container Docker AlmaLinux 9 no servidor 10.1.1.1 (ARM64/aarch64), acessivel via web UI e CLI. Inclui realm ATIUS.COM.BR, DNS interno integrado com WireGuard, CA operacional, e backup configurado. Keycloak fica fora deste phase (Phase 6).

FreeIPA container MUST coexist with 25+ existing Docker containers without disrupting Apache2 (portas 9080/9444), PM2 apps, PostgreSQL, MongoDB, or any running services.

</domain>

<decisions>
## Implementation Decisions

### Container Base Image
- **D-01:** Usar `freeipa/freeipa-server:alma-9` ou `freeipa/freeipa-server:latest` (AlmaLinux 9 base) — compativel com ARM64/aarch64 confirmado no Docker Hub
- **D-02:** Container run privileged mode com `--systemd=true` — FreeIPA requer systemd dentro do container (multi-service: Directory Server, Kerberos, CA, DNS, HTTP)

### Container Networking
- **D-03:** Usar Docker bridge network customizado com IP fixo (sugerido `172.20.0.2`) — FreeIPA precisa de IP estavel para DNS e referencias internas
- **D-04:** Ports to expose on host:
  - `80` → container `80` (HTTP para certbot/ACME challenge)
  - `443` → container `443` (HTTPS Web UI + API)
  - `389` → container `389` (LDAP)
  - `636` → container `636` (LDAPS)
  - `88` → container `88` (Kerberos TCP+UDP)
  - `464` → container `464` (Kerberos password change TCP+UDP)
  - `53` → container `53` (DNS TCP+UDP) — CONFLITO POTENCIAL: port 53 was freed in Phase 1 (systemd-resolved stub disabled), mas CoreDNS externo pode precisar ser reconfigurado
- **D-05:** Hostname do container: `ipa.atius.com.br` — ja configurado em `/etc/hosts` apontando para `10.1.1.1`

### FreeIPA Domain Configuration
- **D-06:** Realm: `ATIUS.COM.BR` (uppercase, conforme PROJECT.md)
- **D-07:** Domain: `atius.com.br` (mesmo dominio do Cloudflare)
- **D-08:** Directory Manager password: generated secure, stored in `.env` ou Docker secret
- **D-09:** Admin user: `admin` com password generated, stored same location

### DNS Integration
- **D-10:** FreeIPA DNS (BIND) sera o authoritative DNS interno — encaminhar queries externas para `10.1.1.2` (atual nameserver) ou Cloudflare `1.1.1.1`
- **D-11:** Client machines na WireGuard devem usar `10.1.1.1` (FreeIPA) como DNS primario — requer atualizacao de `/etc/resolv.conf` nas maquinas clientes
- **D-12:** CoreDNS existente (se ainda ativo) deve encaminhar para FreeIPA DNS ou ser desativado

### Volume Persistence
- **D-13:** Bind mount para dados persistentes:
  - `/var/lib/freeipa/data` → `/data` (backup volume)
  - Docker named volumes para `/etc/ipa`, `/var/lib/ipa`, `/var/lib/dirsrv`, `/var/kerberos`
- **D-14:** Backup volume mount para exportar backups: `/var/lib/freeipa/backups` no host

### CA Configuration
- **D-15:** FreeIPA embedded CA (Dogtag) — auto-signed, nao usar CA externa
- **D-16:** Known ARM64 bug: `crypto.fips_enabled` pode causar falha no CA setup no Ubuntu host — workaround: set `FIPS_MODE=0` no container ou editar `/etc/crypto-policies/config` antes do setup

### Security
- **D-17:** Container run as root (required for FreeIPA) — privilege escalation necessario
- **D-18:** Firewall rules na OCI: liberar portas 80, 443, 389, 636, 88, 464, 53 para rede WireGuard `10.1.1.0/24`

### Backup Strategy
- **D-19:** Usar `ipa-backup` dentro do container via `docker exec` — gera arquivos em volume montado no host
- **D-20:** Backup schedule via cron no host ou systemd timer — diario, retention 7 dias

### Claude's Discretion
- Exact Docker Compose vs docker run command structure
- Password generation approach
- Specific FreeIPA server-install options (DNS forwarder choice, NTP source)
- Container healthcheck implementation
- Exact backup script location and naming

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### FreeIPA Requirements
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` — FIPA-01 through FIPA-06 (phase 3 requirements)
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/ROADMAP.md` — Phase 3 goal, success criteria, risk notes

### FreeIPA Documentation
- FreeIPA Docker container: https://github.com/freeipa/freeipa-container — Dockerfile, run instructions, ARM64 notes
- FreeIPA Docker Hub: https://hub.docker.com/r/freeipa/freeipa-server/ — Image tags, ARM64 support confirmation
- FreeIPA install guide: https://www.freeipa.org/page/Quick_Start_Guide — Server setup steps, realm configuration

### Known Issues
- Ubuntu FreeIPA bug: https://bugs.launchpad.net/ubuntu/+source/freeipa/+bug/1875114 — `freeipa-server` nao existe nos repos Ubuntu (justifica abordagem Docker)
- ARM64 FIPS bug: FreeIPA CA pode falhar com `crypto.fips_enabled` em hosts Ubuntu ARM64 — requer workaround

### Project Context
- `/etc/hosts` — ja contem entry `10.1.1.1 ipa.atius.com.br atius-srv-1`
- `/etc/resolv.conf` — current nameserver `10.1.1.2` (WireGuard/CoreDNS)
- Oracle Cloud Infrastructure — ARM64/aarch64 instance, security groups need port opens

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Docker infrastructure**: 25+ containers ja rodando — seguir padroes existentes em `/home/ubuntu/docker/`
- **Portainer**: ja gerencia containers — FreeIPA pode ser adicionado via Portainer UI ou compose
- **Apache2**: reverse proxy nas portas 9080/9444 — NAO pode conflitar com FreeIPA em 80/443

### Established Patterns
- Containers usam Docker Compose (ver `docker/ai-apps/`, `docker/portainer/`)
- PM2 gerencia apps Node.js/Python — FreeIPA e independente (container systemd)
- PostgreSQL na porta 8745 — sem conflito com FreeIPA

### Integration Points
- `/etc/hosts` — ja tem entry para `ipa.atius.com.br` → `10.1.1.1`
- `/etc/resolv.conf` — precisara apontar para FreeIPA DNS (`10.1.1.1`) apos setup
- WireGuard network `10.1.1.0/24` — FreeIPA DNS deve resolver para todas as maquinas
- OCI Security Groups — liberar portas FreeIPA (80, 443, 389, 636, 88, 464, 53)
- Cloudflare Origin Rules — FREEIPA NAO passa por Cloudflare (acesso direto via WireGuard)

### Constraints
- **ARM64/aarch64**: FreeIPA image DEVE suportar ARM64 (confirmado: `freeipa/freeipa-server:alma-9` suporta)
- **Port 53**: Liberado no Phase 1 (systemd-resolved stub disabled), mas CoreDNS em 10.1.1.2 ainda pode estar ativo
- **Memory**: FreeIPA requer ~2GB RAM minimo — verificar se instancia Oracle tem capacity
- **Hostname**: FQDN `atius-srv-1.atius.com.br` configurado no Phase 1

</code_context>

<specifics>
## Specific Ideas

- "FreeIPA container precisa de IP fixo — nao pode mudar em restart porque DNS e Kerberos dependem disso"
- "Backup via ipa-backup monta volume no host para persistencia fora do container"
- "CA embedded (Dogtag) — sem CA externa, certificado auto-signed para uso interno"
- "Realm ATIUS.COM.BR deve usar uppercase conforme padrao Kerberos"
</specifics>

<deferred>
## Deferred Ideas

- Keycloak federation com FreeIPA LDAP — Phase 6
- Client machine enrollment (ipa-client-install) — Phase 7
- Samba AD Trust config — Phase 4
- FreeIPA replica para HA — v2 (HA-01)
- CoreDNS decommission ou reconfiguracao — Phase 5 (WireGuard migration)

### Reviewed Todos (not folded)
None — no todos matched this phase scope.

</deferred>

---

*Phase: 03-freeipa-server-container*
*Context gathered: 2026-04-19 (auto mode)*
