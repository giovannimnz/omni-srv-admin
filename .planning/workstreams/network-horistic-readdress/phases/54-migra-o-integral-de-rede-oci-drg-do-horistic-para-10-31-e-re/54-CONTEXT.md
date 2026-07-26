---
phase: 54
status: pending-independent-review
updated: 2026-07-26
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
Os builder receipts de produção `fa604ea`/`700947`, do owner `oci-admin`, já retornam literalmente `10.31.0.0/16`, `10.31.1.0/24`, `10.31.1.31` e zero target `10.21.*`. Plan 03 deve revalidá-los read-only por endpoint/commit/output hash. Esses receipts satisfazem a precondition de builder, mas não autorizam OCI write; não editar esse backend neste worktree.

### D-04 — Reserved public IP
Preservar `163.176.232.119` e o label `horistic-srv-1` por public-IP OCID. O baseline 54-02 pode registrar o private binding antigo read-only. Após cutover, 54-05 e 54-10 exigem private address `10.31.1.31` e private-IP/VNIC/subnet/VCN OCIDs ligados ao OperationPlan 54-05 e a um readback schema `phase54.public-ip-readback.v1` hash-bound. Nunca comparar o target private-IP OCID ao antigo, nem release/delete/recreate. Estado assíncrono deve chegar a `RESERVED/ASSIGNED`; timeout/UNKNOWN bloqueia.

### D-05 — DRG e security bidirecionais
VCN/subnet/DRG route tables, route rules, attachments, security lists/NSGs e host firewalls devem provar ida e retorno para os quatro servidores ATIUS e Horistic antes de cutover.

### D-06 — OperationPlans e approvals
Cada write OCI, DNS, BE3/WireGuard ou retirement usa OperationPlan distinto com input hashes, diff, owner, expiry, anti-drift, rollback e typed confirmation exata. Autonomous nunca autoaprova typed confirmation, auth, device action ou checkpoint humano.

### D-07 — Approvals históricos
Approvals/receipts da antiga Phase 52 não são reutilizáveis por padrão. Wave 0 pode apenas reconhecê-los como provenance depois de provar mesmo scope, hashes atuais, expiry válida e ausência de drift; qualquer diferença exige approval nova.

### D-08 — Gate por wave
Cada plano termina com gate machine-readable fail-closed. Evidence autoafirmado não libera gate: contém apenas `check_inputs` tipados/hash-bound. `ProbeContext` e registry imutável escolhem executable absoluto, argv/host/tool/operation Literals, env sanitizado, stdin fechado, timeout e output cap; o runner executa e cria `phase54.check-observation.v1`. Campo de controle ou resultado vindo do evidence bloqueia. Os seis probes locais 54-01 executam workstream init semântico, pytest adversarial, secret scan e Graphify status/query fresh. Os probes 54-02..10 usam o adapter físico owner-specific `modules/fleet-control-plane/scripts/phase54_probe_adapters.py`, com integration tests reais, coverage exata e `adapters-ready --plan 54-NN --smoke` antes do gate final. Contratos de stage são derivados pelo runner a partir de evidence/receipts canônicos e nunca autoafirmados pelo adapter. `shell=false`; timeout/non-zero/truncation/JSON inválido/host-key, request-id, hash observado ou flags read-only ausentes bloqueiam.

### D-09 — DNS e Phase 47.1
FreeIPA permanece autoridade de `atius.internal` e das reverse zones; CoreDNS/AdGuard são resolvers/forwarders. Consumir `47.1-RELEASE-GATE.json` fresh/hash-valid ou executar uma transação autocontida que prove backup, A/PTR/SOA/NS, FQDN, TTL/cache, forwards, NXDOMAIN fail-closed e rollback antes do write.

### D-10 — Baseline edge canônico
Horistic WireGuard migra `10.100.100.4 -> 10.100.100.31` com dual-path. S23 permanece estritamente read-only em LAN `192.168.1.10`, WireGuard `10.100.100.10`, MAC `64:1B:2F:C2:DC:A3`. S20 MAC `30:AB:6A:3C:96:D1` migra LAN/WG `.9` para `.11`; o sync 54-08 só conclui com receipt hash-bound provando ausência simultânea do peer e AllowedIP `10.100.100.9`. `decision=defer` permite manter `.9`, mas bloqueia completion/sync final do 54-08.

### D-11 — SSH Horistic
Após todo probe SSH privado, executar obrigatoriamente o fallback público nativo `ssh -p 22 horistic@ssh-horistic-srv.atius.com.br` e registrar ambos antes de declarar indisponibilidade.

### D-12 — Backups e rollback
Antes de writes: backups nativos OCI/host/DNS/WG/BE3/K3s/services, checksums, restore staging e rollback receipt. SRV1/SRV3 e o BE3 final-v13/final-v11 são evidence preexistente nos receipts locais exatos `54-02-SRV1-BACKUP-RECEIPT.json`, `54-02-SRV3-BACKUP-RECEIPT.json` e `54-02-BE3-BACKUP-RECEIPT.json`, schema `phase54.backup-receipt.v1`, `approval_claimed=false`. O BE3 é ligado ao commit `24f2562af086625b0678c4573f1c03a77270fc22`, source/metadata hashes e backup SHA/size/mode canônicos. Não é pending write; somente OCI boot backup ou refresh explicitamente aprovado podem entrar no OperationPlan 54-02.

### D-13 — Retirement escalonado
Retirement é plano separado e destrutivo no 54-09. Exige duas matrizes estáveis separadas por pelo menos 15 minutos, OperationPlan hash-bound fresh, typed confirmation literal `APPROVE 54-09 <sha256-completo>`, reread imediato e apply receipt no mesmo plan; remove rotas, VNIC/private IP, subnet/VCN antigos e identidade DNS/serviços sem residual `10.21.*`. O 54-10 é somente read-only validation/sync e não recebe autoridade de write.

### D-14 — Segredos e evidence
Vault continua source of truth. Evidência guarda apenas nomes de profiles/vars/paths, comandos redigidos, exit codes, timestamps, hashes e OCIDs necessários; nunca tokens, chaves privadas ou credenciais.

### D-15 — Graphify e knowledge
Graphify status/query é obrigatório antes de escolher paths e freshness depois de código/docs/planning, sempre por `scripts/graphify-sync.sh`, que seleciona node Linux ou node.exe+wslpath e aplica guardrail no update de servidores. Obsidian/GBrain recebem apenas estado live verificado e não secreto. No 54-10, toda convergência writeful termina no preflight; depois do freeze, o sync final é fresh/read-only.

### D-18 — Trust boundary e lineage
Integridade por SHA-256 não prova autoria contra writer local malicioso; assinatura/ledger externo fica fora desta fase. Dentro do boundary aceito, Plan 54-01 deve ser reexecutado fresh e encerrado em commit atômico antes de 54-02. Todo predecessor e ancestral, inclusive 54-01→54-02, exige `assert-gate`, source commit/blob pin verificável e `chain_sha256` com exact plan/stage/path/required IDs. O 54-02 apenas consome/asserta 54-01 e nunca modifica seus artifacts. OperationPlan/approval/anti-drift/apply/rollback usam schemas, owners e filenames exatos. O 54-09 preview ancora `54-09-STABILITY-EVIDENCE.json` e `54-09-STABILITY-GATE.json` por hashes exatos. O 54-10 preflight congela semantic artifacts, receipts e Graphify fresh/relevante em `54-10-KNOWLEDGE-FREEZE.json`; o sync somente relê esse manifest. O 54-10 também ancora diretamente `54-05-EVIDENCE/GATE/OPERATION-PLAN/APPROVAL/APPLY-RECEIPT` por path/hash e exige apply terminal PASS mais readback live com mesmo binding digest.

### D-16 — Review
`54-REVIEWS.md` é audit trail humano e não constitui runtime authorization artifact. O Revision Gate termina na validação dos PLANs; antes de retomar 54-02, o executor reexecuta 54-01 fresh, emite evidence/gate finais e cria um commit atômico. O 54-02 apenas verifica esse commit/blob pin e o predecessor fresh; qualquer mudança posterior exige nova execução/commit de 54-01, nunca rewrite dentro de 54-02.

### D-17 — Verifier independente
O executor produz evidence, gates e SUMMARY; nunca cria nem marca como passed `54-VERIFICATION.md`. Após `54-10-GATE.json` PASS, um `gsd-verifier` independente do executor cria `54-VERIFICATION.md`, verifica o goal da Phase 54 contra estado live e é o único agente autorizado a declarar a fase verificada/complete.

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
- Builder receipts de produção `fa604ea`/`700947` retornam targets 10.31 e zero target 10.21; são evidence read-only e não autorizam write.
</evidence>
