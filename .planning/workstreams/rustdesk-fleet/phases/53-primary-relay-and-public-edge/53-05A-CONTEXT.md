# Phase 53: Candidate Pin and Live Adapter Closure - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Avaliar e admitir, de forma explícita e reproduzível, o candidato RustDesk Server
1.1.16 antes da primeira mutação da Phase 53; fechar o contrato do runner e dos
adapters fail-closed sem repetir Gate B da Phase 52 nem alterar a Phase 48.

</domain>

<decisions>
## Implementation Decisions

### Supply chain e segurança
- 1.1.16 é o candidato preferencial porque corrige o abuso de UDP PunchHoleRequest, o update de `mio` e o overflow de timeout.
- 1.1.15 permanece somente como fallback de staging até compatibilidade, aprovação e rollback serem comprovados.
- O candidato deve ser ligado a commit, digest multiarch/ARM64, checksum do ZIP, source HEAD e digests dos contratos atuais.

### Runner e evidência
- O runner mantém `edge-probes` como alias ordenado e suporta execução de uma transação com journal persistente value-free.
- Adapters concretos são injetáveis nos testes e só são construídos pela CLI com flag live explícita e preflight fresco.
- Qualquer falha após mutação chama containment/rollback e impede Plan 53-06/Phase 54.

### Placement e autoridade
- Horistic continua primary histórico até capacity/security/recovery fresco; srv-2 é preferência de relay somente se passar o gate, srv-3 é fallback serial.
- Nenhum cleanup, segredo, DNS, OCI, firewall ou listener será alterado durante avaliação.
- Aprovação humana nova deve referenciar os hashes do candidato, pre-state, rollback e disposição de vulnerabilidade.

### the agent's Discretion
- Nomes internos de adapters, formato do journal value-free e fixtures herméticos, desde que preservem as chaves de receipt e os contratos existentes.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Phase53ServerTransaction.install_closed()` e `rollback_server()` fornecem a transação rootless local.
- `EdgeTransaction` fornece CAS, DNS-last e rollback sem conhecer o backend.
- `probe-phase53-edge.py` valida duas origens, fallback W11, TCP/UDP e hostname sem guardar payload.
- `ApacheVhostTransaction` e `rustdesk-ops-api.py` fornecem auth/redaction e rollback de vhost.

### Established Patterns
- Contracts são JSON strict, digests são calculados em runtime e evidência durável é redacted.
- Testes usam adapters/fakes injetados e resource governor para qualquer suite.
- Phase 48/52 são source/evidence freezes e não devem ser regeneradas.

### Integration Points
- `run-phase53-live-gate.py` é o dispatcher único.
- `modules/rustdesk-fleet/evidence/phase53/` guarda somente receipts value-free.
- `.planning/workstreams/rustdesk-fleet/STATE.md` e `ROADMAP.md` recebem o checkpoint após os gates.

</code_context>

<specifics>
## Specific Ideas

Não publicar DNS nem promover o candidato antes de provar os negativos UDP/TCP,
identidade, rollback e compatibilidade com client 1.4.9.
</specifics>

<deferred>
## Deferred Ideas

Instalação de clients, canário Windows/Horistic e rollout dos servidores permanecem nas Phases 54/55.
</deferred>
