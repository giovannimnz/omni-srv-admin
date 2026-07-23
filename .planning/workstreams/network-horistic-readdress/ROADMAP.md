# Roadmap: Horistic OCI/DRG and Edge Readdress

**Workstream:** `network-horistic-readdress`
**Current phase:** 54
**Requirements:** `.planning/workstreams/network-horistic-readdress/REQUIREMENTS.md`
**State:** `.planning/workstreams/network-horistic-readdress/STATE.md`

## Phase 54: Migração integral de rede OCI/DRG do Horistic para 10.31 e renumeração BE3/WireGuard

**Goal:** Migrar integralmente o plano privado do `horistic-srv` de `10.21.0.0/16` / `10.21.1.0/24` / `10.21.1.21` para `10.31.0.0/16` / `10.31.1.0/24` / `10.31.1.31`, preservando a reserva pública `163.176.232.119`, e renumerar `GIOVANNI-S23` para `10.100.100.10` e `S20-de-Giovanni` para LAN `192.168.1.11` + WireGuard `10.100.100.11`.
**Requirements:** NET-01..NET-11
**Depends on:** Phase 45 e Phase 47.1 do workstream `runtime-trust-codex-delivery-convergence`
**Status:** Executing; Waves 0/1 possuem evidência histórica preservada, live apply continua fail-closed
**Risk:** VERY HIGH
**Plans:** 0/6 complete after reenumeration; preflight receipts imported as provenance, not counted as final Phase 54 execution

### Execution waves

- [ ] `54-01` — Freeze, inventário, backups, public-IP attachment proof e rollback manifest.
- [ ] `54-02` — Preview/apply aditivo de `10.31.0.0/16`, subnet `10.31.1.0/24`, controles e propagação DRG.
- [ ] `54-03` — Replacement VNIC/IP `10.31.1.31`, preservação de `163.176.232.119` e migração host/K3s com rollback dual-path.
- [ ] `54-04` — DNS, Apache, TEI/reranker, Router, monitoring, inventários e serviços de `.21` para `.31`.
- [ ] `54-05` — S23 WG `.9` -> `.10` e S20 BE3 `.10` -> `.11` + WG `.11`, com import no dispositivo e screenshot/readback DHCP.
- [ ] `54-06` — Remoção da `.21` apenas depois dos gates, seguida da validação integral e publicação de evidências.

### Done condition

O workstream só conclui quando o mapa completo `10.31` está ativo, a reserva pública foi preservada, os clientes edge foram renumerados, todos os serviços passaram, a faixa `.21` foi removida de caminhos ativos e documentação/knowledge/checkouts estão convergentes.

**Validation:** `.planning/workstreams/network-horistic-readdress/phases/54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re/54-VALIDATION-CONTRACT.md`
