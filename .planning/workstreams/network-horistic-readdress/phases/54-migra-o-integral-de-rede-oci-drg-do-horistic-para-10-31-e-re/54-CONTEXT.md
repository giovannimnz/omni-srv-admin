# Phase 54 Context — Migração integral OCI/DRG e edge

**Source:** operator clarification in Codex session, 2026-07-23

## Objective

Executar um plano reversível para substituir o plano privado do Horistic por
`10.31.0.0/16` / `10.31.1.0/24` / `10.31.1.31`, preservar a reserva pública
`163.176.232.119`, migrar os serviços e somente depois retirar a identidade
antiga `.21`. Em paralelo, renumerar S23 e S20 nos planos WireGuard/BE3 sem
confundir IP de túnel com reserva LAN.

## Locked decisions

- O alvo OCI/DRG do Horistic é exatamente `10.31.1.31` dentro de
  `10.31.0.0/16` e `10.31.1.0/24`; não substituir por `10.21.1.31`.
- A rede antiga `10.21.0.0/16`, a subnet `10.21.1.0/24` e o IP `.21` devem
  permanecer durante a janela de dual-path e ser removidos apenas após a
  verificação final e a janela de observação.
- A reserva pública `163.176.232.119` deve ser preservada, com prova de
  associação antes/depois; nenhum plano pode liberá-la ou trocá-la por IP
  efêmero.
- O fallback WireGuard do Horistic passa de `10.100.100.4` para
  `10.100.100.31`, alinhado ao novo sufixo `.31`; o peer `.4` permanece
  disponível somente até o handshake do `.31`, os probes SSH/TCP/DNS e o gate
  final.
- O S23 passa de WireGuard `10.100.100.9` para `10.100.100.10`. A reserva
  residencial do S23 continua sendo LAN BE3 `192.168.1.9` até existir uma
  decisão explícita diferente.
- `S20-de-Giovanni` passa da reserva DHCP BE3 `192.168.1.10` para
  `192.168.1.11` e recebe o peer WireGuard `10.100.100.11`. O plano deve
  validar que `.11` não está em uso e capturar a tela/readback da reserva.
- A autenticação WireGuard continua criptografada e o fallback público do
  S23/S20 deve permanecer disponível durante a janela; não usar plaintext.
- Nenhuma exclusão de VCN/subnet/private IP antiga ocorre na mesma operação que
  a criação sem readback, rollback e gate humano documentados.
- Obsidian e GBrain são atualizados somente com valores não secretos e após o
  estado live ser verificado.

## Required evidence

- OCI inventory/OperationPlan para VCN, subnet, route tables, security lists,
  VNIC/private IP, reserved public IP e DRG routes em todos os profiles.
- Backups dos hosts, WireGuard, K3s, CoreDNS/FreeIPA/AdGuard, Apache e
  manifests de serviço antes da janela.
- Before/after de `ip -br -4`, rotas, `wg show`, K3s nodes, listeners e
  resoluções A/PTR.
- Screenshot headless e readback final da lista de reservas estáticas do BE3,
  mostrando `S20-de-Giovanni -> 192.168.1.11` e preservando as demais reservas.
- Matriz pós-cutover para SSH, DNS, K3s, Apache/HTTPS, TEI, reranker, Router,
  PgBouncer, Vault, Obsidian/GBrain, WireGuard handshakes e public edge.
- Cada plano termina automaticamente com um gate machine-readable `PASS`,
  `WARN`, `BLOCK` ou `UNKNOWN`; qualquer `BLOCK`/`UNKNOWN` obrigatório impede o
  próximo plano. O gate registra comandos, exit codes, timestamps, hashes,
  redaction e receipt de rollback conforme `54-VALIDATION-CONTRACT.md`.

## Scope fence

Inclui OCI/DRG, Horistic host/K3s/services, WireGuard S23/S20, DHCP static
binding BE3, inventories, `oci-admin`, `home-proxy`, AGENTS.md, runbooks,
Obsidian e GBrain. Não inclui remover a faixa WireGuard inteira, mudar a LAN do
roteador, trocar a autoridade FreeIPA/CoreDNS ou reabrir a implementação
Wayland; essas superfícies só recebem updates de endpoint necessários.

## Stop conditions

- VCNs/rotas com sobreposição, DRG `lpg_ready=false` sem plano de correção,
  ausência de backup, public IP não reassociável, K3s degraded, falha de SSH
  fallback, S23/S20 sem importação do perfil ou BE3 sem readback.
- Qualquer serviço crítico sem duas leituras estáveis após o cutover.

## Rollback contract

Manter `.21` e `.9/.10` anteriores durante a transição. Em falha, restaurar
rotas/DNS/K3s/host e peers para o snapshot anterior, preservar a reserva pública
e só então investigar. A deleção da identidade antiga é uma etapa separada e
irreversível, liberada somente pelo gate final.
