---
phase: 54
status: ready-for-planning
updated: 2026-07-24
---

# Phase 54 Context — Migração integral Horistic 10.21 para 10.31

<domain>
## Phase Boundary

Substituir integralmente o plano privado OCI/DRG do Horistic, migrar identidade, rotas, DNS, serviços e edge, preservar o public IP reservado e retirar todo caminho operacional `10.21.*` somente após gates e rollback. O backend `oci-admin` é externo a este repo/worktree: a fase consome receipts/commits validados, mas não o edita aqui.
</domain>

<decisions>
## Decisions

### D-01 — Target OCI exato
O único target aceito é VCN `10.31.0.0/16`, subnet `10.31.1.0/24` e private IP `10.31.1.31`. A proposta histórica `10.71.*` é rejeitada. Nenhum target `10.21.*` pode constar no builder final.

### D-02 — Migração integral e arquitetura VCN
Readbacks live decidem entre transformar a VCN atual e criar VCN substituta. Se `10.21.0.0/16` for CIDR primário não removível ou qualquer dependência impedir eliminação integral, usar VCN substituta. A fase não conclui com residual `10.21.*`.

### D-03 — Builder externo como hard gate
Nenhum OCI write é autorizado até `peering.address_plan`, do owner `oci-admin`, emitir receipt ligado a commit validado contendo literalmente `10.31.0.0/16`, `10.31.1.0/24`, `10.31.1.31` e zero target `10.21.*`. Não editar esse backend neste worktree.

### D-04 — Reserved public IP
Preservar `163.176.232.119` e o label `horistic-srv-1` por OCID. Sempre reler o binding por `public_ip_ocid`; nunca release/delete/recreate. Estado assíncrono deve chegar a `RESERVED/ASSIGNED` dentro de timeout único; timeout/UNKNOWN bloqueia sem retry cego.

### D-05 — DRG e security bidirecionais
VCN/subnet/DRG route tables, route rules, attachments, security lists/NSGs e host firewalls devem provar ida e retorno para os quatro servidores ATIUS e Horistic antes de cutover.

### D-06 — OperationPlans e approvals
Cada write OCI, DNS, BE3/WireGuard ou retirement usa OperationPlan distinto com input hashes, diff, owner, expiry, anti-drift, rollback e typed confirmation exata. Autonomous nunca autoaprova typed confirmation, auth, device action ou checkpoint humano.

### D-07 — Approvals históricos
Approvals/receipts da antiga Phase 52 não são reutilizáveis por padrão. Wave 0 pode apenas reconhecê-los como provenance depois de provar mesmo scope, hashes atuais, expiry válida e ausência de drift; qualquer diferença exige approval nova.

### D-08 — Gate por wave
Cada plano termina automaticamente com gate machine-readable fail-closed. `BLOCK`, `BLOCKED`, `UNKNOWN`, malformed, missing, stale, tampered ou evidence autoafirmado impede a wave seguinte. O schema canônico usa `BLOCK`; o runner deve normalizar legado `BLOCKED` como falha, nunca como sucesso.

### D-09 — DNS e Phase 47.1
FreeIPA permanece autoridade de `atius.internal` e das reverse zones; CoreDNS/AdGuard são resolvers/forwarders. Consumir `47.1-RELEASE-GATE.json` fresh/hash-valid ou executar uma transação autocontida que prove backup, A/PTR/SOA/NS, FQDN, TTL/cache, forwards, NXDOMAIN fail-closed e rollback antes do write.

### D-10 — Baseline edge canônico
Horistic WireGuard migra `10.100.100.4 -> 10.100.100.31` com dual-path. S23 permanece LAN `192.168.1.10`, WireGuard `10.100.100.10`, MAC `64:1B:2F:C2:DC:A3`; não migrar S23 nem usar `.9` como rollback. S20 MAC `30:AB:6A:3C:96:D1` migra LAN/WG `192.168.1.9` / `10.100.100.9` para `.11`; classificar lease antigo `192.168.1.62`.

### D-11 — SSH Horistic
Após todo probe SSH privado, executar obrigatoriamente o fallback público nativo `ssh -p 22 horistic@ssh-horistic-srv.atius.com.br` e registrar ambos antes de declarar indisponibilidade.

### D-12 — Backups e rollback
Antes de writes: backups nativos OCI/host/DNS/WG/BE3/K3s/services, checksums, restore staging e rollback receipt. Public IP permanece reservado durante rollback.

### D-13 — Retirement escalonado
Retirement é plano separado e destrutivo. Exige duas matrizes estáveis separadas por pelo menos 15 minutos, OperationPlan hash-bound fresh, typed confirmation e reread imediato; remove rotas, VNIC/private IP, subnet/VCN antigos e identidade DNS/serviços sem residual `10.21.*`.

### D-14 — Segredos e evidence
Vault continua source of truth. Evidência guarda apenas nomes de profiles/vars/paths, comandos redigidos, exit codes, timestamps, hashes e OCIDs necessários; nunca tokens, chaves privadas ou credenciais.

### D-15 — Graphify e knowledge
Graphify status/query é obrigatório antes de escolher paths e freshness depois de código/docs/planning. Obsidian/GBrain recebem apenas estado live verificado e não secreto.

### D-16 — Review
`54-REVIEWS.md` registra o ciclo novo como pendente. Nenhuma alegação de zero findings é válida antes de nova revisão independente dos dez planos.

### the agent's Discretion
- Timeout assíncrono exato, entre 5 e 15 minutos, desde que não haja retry automático.
- Nome dos artifacts/transactions, preservando schemas, hashes e lineage exigidos.
- Ordem interna dos probes dentro de cada gate, sem alterar as dependências entre waves.

## Deferred Ideas

- Nenhuma. A proposta `10.71.*` é rejeitada, não deferred.
</decisions>

<evidence>
## Live Evidence 2026-07-24

- Horistic: VCN `10.21.0.0/16`, subnet `10.21.1.0/24`, host `10.21.1.21`.
- Reserved public IP `163.176.232.119`, label `horistic-srv-1`; binding deve ser relido por OCID.
- DRG central e attachment existem.
- `peering.address_plan` permanece `10.21.*` e bloqueia writes.
</evidence>
