# Requirements: Omni Srv Admin (omni-srv-admin)

**Defined:** 2026-05-06 (merged from atius-srv + domain-infrastructure)
**Core Value:** Servidor Atius sempre provisionado e operante com identidade centralizada

## v1 Requirements

### Server Setup (Base)

- [ ] **SET-01**: `setup.sh` documentado e idempotente — todos os passos explicados
- [ ] **SET-02**: Rollback procedure documentada para alterações de rede (Apache2, iptables, WireGuard)

### Preparação do Host

- [ ] **PREP-01**: Hostname configurado como FQDN (`atius-srv-1.atius.com.br`)
- [ ] **PREP-02**: NTP configurado e sincronizado (requerido pelo Kerberos)
- [ ] **PREP-03**: Portas 80/443 liberadas (Apache2 movido para portas alternativas)
- [ ] **PREP-04**: Portas alternativas para Apache2 definidas (9080/9444 — 8080 já em uso pelo Docker)
- [ ] **PREP-05**: Portas alternativas para Keycloak definidas

### Migração Apache2

- [ ] **APCH-01**: Apache2 configurado para escutar em portas alternativas (9080/9444)
- [ ] **APCH-02**: 60+ vhosts atualizados com novas portas no Cloudflare Origin Rules
- [ ] **APCH-03**: Certbot reconfigurado para HTTP-01 challenge na nova porta HTTP
- [ ] **APCH-04**: Todos os vhosts funcionam nas novas portas (testes de conectividade)

### FreeIPA Server

- [ ] **FIPA-01**: Container FreeIPA (AlmaLinux 9) construído e rodando em ARM64
- [ ] **FIPA-02**: FreeIPA acessível via web UI e CLI (`ipa` command)
- [ ] **FIPA-03**: Domínio FreeIPA configurado (realm ATIUS.COM.BR)
- [ ] **FIPA-04**: DNS interno do FreeIPA integrado com rede WireGuard
- [ ] **FIPA-05**: CA do FreeIPA operacional (emissão de certificados)
- [ ] **FIPA-06**: Backup do FreeIPA configurado e testado

### Samba Domain Member

- [ ] **SAM-01**: `ipa-adtrust-install` executado no container FreeIPA
- [ ] **SAM-02**: Samba nativo instalado e configurado no host com `ipa-client-samba`
- [ ] **SAM-03**: Autenticação via Kerberos/keytab funcionando (sem NTLM)
- [ ] **SAM-04**: Compartilhamentos de arquivos criados e acessíveis
- [ ] **SAM-05**: Permissões UID/GID mapeadas corretamente (dados do 10.1.1.2 migrados)

### Migração WireGuard

- [ ] **MIG-01**: WireGuard configurado no 10.1.1.1 (servidor VPN principal)
- [ ] **MIG-02**: Peers conectados ao novo servidor (10.1.1.1)
- [ ] **MIG-03**: CoreDNS funcionando no novo servidor
- [ ] **MIG-04**: Servidor 10.1.1.2 descomissionado ou repurposado

### Keycloak SSO

- [ ] **KEY-01**: Keycloak instalado nativamente (Java 21) e rodando via systemd
- [ ] **KEY-02**: Keycloak acessível via subdomínio (ex: `auth.atius.com.br`)
- [ ] **KEY-03**: User federation configurado com FreeIPA via LDAP
- [ ] **KEY-04**: Login SSO funcional via OIDC
- [ ] **KEY-05**: Conta admin local mantida (prevenção de lockout)

### Coexistência e Integração

- [ ] **COEX-01**: SSO existente no Apache2 (~/GitHub/Atius-Capital/ats) NÃO é afetado
- [ ] **COEX-02**: Apache2 e FreeIPA coexistem sem conflito de portas
- [ ] **COEX-03**: CoreDNS encaminha queries para FreeIPA DNS
- [ ] **COEX-04**: Todas as máquinas na rede WireGuard resolvem nomes internos

### Client Enrollment

- [ ] **CLNT-01**: Máquina de teste ingressa no domínio (`ipa-client-install`)
- [ ] **CLNT-02**: Login via usuário FreeIPA funciona na máquina cliente
- [ ] **CLNT-03**: Sudo rules do FreeIPA aplicadas na máquina cliente

## v2 Requirements

### Alta Disponibilidade

- **HA-01**: Replica FreeIPA em segundo servidor
- **HA-02**: Backup automático e DR plan testado

### App Migration para Keycloak

- **APP-01**: Apps Atius migrados do SSO Apache2 para Keycloak OIDC
- **APP-02**: Plane integrado com Keycloak
- **APP-03**: n8n integrado com Keycloak
- **APP-04**: Open WebUI integrado com Keycloak

## v3 Requirements

Milestone ownership and branch mapping live in `.planning/MILESTONES.md`.
This branch owns the M005/K3s requirements below; M004/Fleet requirements live
in `codex/omni-fleet-control-plane-m004`.

### K3s HA Cluster

- [ ] **K3S-01**: Cluster K3s HA criado nos 3 servidores `ATIUS-SRV-1`, `ATIUS-SRV-2`, `ATIUS-SRV-3` como `server` + `worker`.
- [ ] **K3S-02**: Embedded etcd funcional com quorum 2/3 e snapshots configurados.
- [ ] **K3S-03**: K3s usa apenas WireGuard `wg0` / `10.1.1.0/24` para API, etcd, kubelet e Flannel.
- [ ] **K3S-04**: SRV-1/SRV-2/SRV-3 atualizados para Ubuntu 24.04 antes da instalacao real do cluster.
- [ ] **K3S-05**: Traefik e ServiceLB padrao do K3s desabilitados no v1 para evitar conflito com Apache/portas atuais.
- [ ] **K3S-06**: Plano de fallback PTP full-mesh entre SRV-1/SRV-2/SRV-3 definido antes de declarar o cluster production-ready.

### Portainer on Kubernetes

- [ ] **PRT-01**: Portainer CE LTS instalado no namespace `portainer` via Helm, com persistencia e `nodeSelector` adequado ao storage local.
- [ ] **PRT-02**: Portainer do cluster acessivel em `https://portainer.atius.com.br`; legado `docker.atius.com.br` documentado, mas nao usado como dependencia do M005.

### Cloudflare + Security

- [ ] **CFL-01**: Cloudflare Tunnel remoto publica `portainer.atius.com.br` via replicas `cloudflared` no cluster, token em Kubernetes Secret e fora do git.
- [ ] **SEC-01**: Cada conta OCI/OC1 dos 3 servidores bloqueia acesso publico a 6443, 2379-2380, 8472, 10250 e Portainer NodePort/LoadBalancer; host firewall permite K3s apenas em `wg0`/`10.1.1.0/24`.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Integração Windows/Mac | Ambiente 100% Linux |
| NTLM para Samba | FreeIPA Samba só suporta Kerberos |
| Certificados de usuário via FreeIPA | FreeIPA delega certificação para hosts/serviços apenas |
| Migração de apps para Keycloak | Foco na infra primeiro |
| Horistic | Domínio próprio, projeto separado |
| FreeIPA nativo no Ubuntu | Bug #1875114 — container é a solução |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SET-01, SET-02 | Base | Pending |
| PREP-01 → PREP-05 | Phase 1 | Pending |
| APCH-01 → APCH-04 | Phase 2 | Pending |
| FIPA-01 → FIPA-06 | Phase 3 | Pending |
| SAM-01 → SAM-05 | Phase 4 | Pending |
| MIG-01 → MIG-04 | Phase 5 | Pending |
| KEY-01 → KEY-05 | Phase 6 | Pending |
| COEX-01 → COEX-04 | Phase 7 | Pending |
| CLNT-01 → CLNT-03 | Phase 7 | Pending |
| K3S-01 → K3S-06 | Phase 13 | Planned |
| PRT-01 → PRT-02 | Phase 13 | Planned |
| CFL-01, SEC-01 | Phase 13 | Planned |

**Coverage:**
- v1 requirements: 39 total
- v3 requirements: 10 total
- Mapped to phases: 49
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-06 after merge*
*Last updated: 2026-06-13 after M005 Phase 13 K3s HA Portainer planning*
