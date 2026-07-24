# Requirements: Horistic OCI/DRG and Edge Readdress

**Workstream:** `network-horistic-readdress`
**Phase:** 54
**Status:** Planned; review convergence pending; OCI writes blocked

- [ ] **NET-01**: Recoletar inventário live OCI/DRG/DNS/edge/hosts/serviços, backup timestampado e restore staging antes de qualquer mutação; receipts Phase 52 são apenas provenance até Wave 0 revalidá-los.
- [ ] **NET-02**: Entregar exatamente `10.31.0.0/16`, `10.31.1.0/24` e `10.31.1.31`, sem overlap e sem aceitar target `10.21.*` ou a proposta histórica rejeitada `10.71.*`.
- [ ] **NET-03**: Preservar `163.176.232.119` pelo `public_ip_ocid`, relendo binding/status até `RESERVED/ASSIGNED`; nunca release/delete/recreate, nunca retry cego em estado assíncrono desconhecido.
- [ ] **NET-04**: Migrar integralmente VCN/subnet/VNIC/private IP, host, K3s e serviços; decidir VCN atual versus VCN substituta por readback live e não concluir com qualquer residual `10.21.*`.
- [ ] **NET-05**: Provar DRG, route tables, security lists/NSGs e firewalls em ida e retorno entre os quatro servidores ATIUS e Horistic no novo CIDR.
- [ ] **NET-06**: Migrar Horistic WireGuard `10.100.100.4 -> 10.100.100.31`; preservar S23 em LAN `192.168.1.10` e WireGuard `10.100.100.10`; não usar `.9` como rollback do S23.
- [ ] **NET-07**: Migrar S20 MAC `30:AB:6A:3C:96:D1` de LAN/WireGuard `192.168.1.9` / `10.100.100.9` para `.11`; classificar lease antigo `192.168.1.62` e capturar readback/screenshot BE3.
- [ ] **NET-08**: Migrar DNS A/PTR/FQDN e resolvers preservando FreeIPA como autoridade e validar ICMP/TCP, SSH privado seguido obrigatoriamente pelo fallback público Horistic, K3s, Apache/HTTPS, TEI, reranker, PgBouncer, Vault, MCPs, Router e monitoring.
- [ ] **NET-09**: Convergir `omni-srv-admin`, `oci-admin`, `home-proxy`, inventários, AGENTS/runbooks, Obsidian, GBrain e Graphify sem segredos e sem editar backend externo no repo errado.
- [ ] **NET-10**: Retirement de VCN/subnet/VNIC/private IP/routes/DNS antigos é escalonado, destrutivo e exige duas leituras estáveis, OperationPlan hash-bound fresh, typed confirmation e rollback ensaiado.
- [ ] **NET-11**: Cada plano termina com gate automático machine-readable; `BLOCK`, `BLOCKED`, `UNKNOWN`, receipt ausente/stale/tampered ou evidence autoafirmado impede a wave seguinte.

## Traceability

Todos os requisitos NET-01..NET-11 pertencem exclusivamente à Phase 54 deste workstream. A Phase 54 do workstream `rustdesk-fleet` permanece fora de escopo.
