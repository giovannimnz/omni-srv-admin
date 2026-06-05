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

- [ ] **COEX-01**: SSO existente no Apache2 (~/GitHub/atius) NÃO é afetado
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

**Coverage:**
- v1 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-06 after merge*
*Last updated: 2026-05-06 after merge*
