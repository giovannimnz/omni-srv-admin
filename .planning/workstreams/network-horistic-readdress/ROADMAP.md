# Roadmap: Horistic OCI/DRG and Edge Readdress

**Workstream:** `network-horistic-readdress`
**Current phase:** 54
**Requirements:** `.planning/workstreams/network-horistic-readdress/REQUIREMENTS.md`
**State:** `.planning/workstreams/network-horistic-readdress/STATE.md`

## Phase 54: Migração integral de rede OCI/DRG do Horistic para 10.31 e renumeração edge

**Goal:** Migrar integralmente o `horistic-srv` de `10.21.0.0/16` / `10.21.1.0/24` / `10.21.1.21` para `10.31.0.0/16` / `10.31.1.0/24` / `10.31.1.31`, preservando por OCID a reserva pública `163.176.232.119`; convergir VCN/subnet/DRG/routes/VNIC/private IP, DNS A/PTR/FQDN/resolvers, host/K3s/serviços e documentação; migrar Horistic WireGuard `.4 -> .31`; preservar S23 em LAN `192.168.1.10` e WireGuard `10.100.100.10`; migrar S20 de LAN/WireGuard `.9 -> .11`.
**Requirements:** NET-01..NET-11
**Depends on:** Phase 45 como baseline DRG; Phase 47.1 como release gate DNS ou transação DNS autocontida que prove autoridade/rollback
**Status:** In Progress; 54-01 PASS/hash-valid; nenhum OCI write autorizado antes dos gates posteriores
**Risk:** VERY HIGH
**Plans:** 1/10 plans executed

- [x] 54-01-PLAN.md
- [ ] 54-02-PLAN.md
- [ ] 54-03-PLAN.md
- [ ] 54-04-PLAN.md
- [ ] 54-05-PLAN.md
- [ ] 54-06-PLAN.md
- [ ] 54-07-PLAN.md
- [ ] 54-08-PLAN.md
- [ ] 54-09-PLAN.md
- [ ] 54-10-PLAN.md

### Execution waves

Todas as waves são sequenciais. Cada plano termina com gate automático fail-closed; somente `PASS` hash-valid e fresh libera o próximo.

- [x] `54-01-PLAN.md` — Corrigir runtime do workstream e endurecer runner/testes fail-closed.
- [ ] `54-02-PLAN.md` — Recoletar inventário live, backups, rollback e baseline público/DNS/edge.
- [ ] `54-03-PLAN.md` — Bloquear writes até o builder `oci-admin` publicar address plan 10.31 e decidir VCN atual versus substituta.
- [ ] `54-04-PLAN.md` — Aplicar VCN/subnet/DRG/routes/security do target com ida/retorno comprovados.
- [ ] `54-05-PLAN.md` — Anexar VNIC/private IP, configurar dual-path host/K3s e reassociar a reserva pública sem release.
- [ ] `54-06-PLAN.md` — Migrar DNS A/PTR/FQDN/resolvers e serviços sob release gate ou transação autocontida.
- [ ] `54-07-PLAN.md` — Atualizar BE3 e peers hub para Horistic `.31` e S20 `.11`, preservando S23 `.10`.
- [ ] `54-08-PLAN.md` — Executar imports/receipts de dispositivo e provar handshakes/fallbacks dual-path.
- [ ] `54-09-PLAN.md` — Executar duas leituras estáveis e aprovar OperationPlan destrutivo de retirement por hash.
- [ ] `54-10-PLAN.md` — Aposentar todo 10.21, validar integralmente e fechar docs/Graphify/Obsidian/GBrain.

### Done condition

A fase só conclui quando não existe target ou caminho operacional `10.21.*`, a reserva `163.176.232.119` continua `RESERVED/ASSIGNED` no private-IP OCID correto, DRG ida/retorno e DNS A/PTR/FQDN/resolvers passam, Horistic `.31` e S20 `.11` passam, S23 permanece `.10`, rollback foi ensaiado e todos os gates `54-01..54-10` estão `PASS`. Se o VCN atual não permitir remover o CIDR primário `10.21.0.0/16`, a execução deve usar VCN substituta; residual 10.21 não é conclusão aceitável.

**Validation:** `phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-VALIDATION.md`
