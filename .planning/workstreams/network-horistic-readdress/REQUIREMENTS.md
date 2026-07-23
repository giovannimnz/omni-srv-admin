# Requirements: Horistic OCI/DRG and Edge Readdress

**Workstream:** `network-horistic-readdress`
**Phase:** 54
**Status:** Executing from approved preflight; live migration remains gated

- [ ] **NET-01**: A fase captura inventário OCI/DRG, WireGuard, BE3, hosts, K3s, serviços, rotas e anexos públicos antes de qualquer mutação, com backup timestampado e rollback verificável.
- [ ] **NET-02**: A rede do Horistic recebe de forma controlada `10.31.0.0/16` + `10.31.1.0/24` sem sobreposição com OCI, DRG, WireGuard, K3s, LXD, Podman, Tailscale ou LAN residencial.
- [ ] **NET-03**: A reserva pública `163.176.232.119` permanece `RESERVED/ASSIGNED` durante a transição e é preservada/religada ao endpoint correto sem perda de Apache, SSH ou Cloudflare origin.
- [ ] **NET-04**: `horistic-srv`, K3s, DNS, Apache, TEI, reranker, Router, monitoring e inventários passam de `10.21.1.21` para `10.31.1.31`, mantendo `.21` somente até o gate final e removendo-a depois.
- [ ] **NET-05**: Rotas DRG, route tables, security lists/NSGs e firewalls permitem os quatro servidores ATIUS e o Horistic na nova faixa, com prova bidirecional.
- [ ] **NET-06**: O fallback WireGuard do `horistic-srv` migra de `10.100.100.4` para `10.100.100.31` e o S23 migra de `10.100.100.9` para `10.100.100.10`; ambos permanecem autenticáveis, sem `AllowedIPs` duplicados, mantendo os peers antigos somente até handshakes/device receipts e gate final.
- [ ] **NET-07**: O BE3 move `S20-de-Giovanni` de `192.168.1.10` para `192.168.1.11`, e o WireGuard correspondente usa `10.100.100.11`; a reserva DHCP ativa recebe screenshot/readback.
- [ ] **NET-08**: A validação final cobre DNS A/PTR/SOA, rotas, ICMP/TCP, SSH, K3s, Apache/HTTPS, TEI, reranker, PgBouncer, Vault, Obsidian/GBrain, Router, public IP, WireGuard e o mapa de portas.
- [ ] **NET-09**: `omni-srv-admin`, `oci-admin`, `home-proxy`, todos os `AGENTS.md`, inventários, runbooks, Obsidian e GBrain convergem para o novo mapa sem segredos.
- [ ] **NET-10**: O plano só remove `.21` depois de duas leituras consecutivas estáveis, backup/rollback testado e janela de observação.
- [ ] **NET-11**: Cada plano termina com validação automática machine-readable, receipt redigido/hashado e gate PASS; BLOCK/UNKNOWN impede a próxima wave.

## Traceability

Todos os requisitos NET-01..NET-11 pertencem exclusivamente à Phase 54 deste workstream. A Phase 54 do workstream `rustdesk-fleet` é independente e permanece inalterada.
