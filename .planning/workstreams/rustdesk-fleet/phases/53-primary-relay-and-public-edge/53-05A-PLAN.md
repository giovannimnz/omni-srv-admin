---
phase: 53-primary-relay-and-public-edge
plan: 05A
type: execute
wave: 4
depends_on: [53-04]
files_modified:
  - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  - modules/rustdesk-fleet/tools/phase53-live-adapters.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json
autonomous: true
requirements: [SCP-04, SRV-02, SRV-03, SRV-04, OPS-01]
must_haves:
  truths:
    - "The 1.1.16 candidate is provenance-bound and remains NOT_ADMITTED until compatibility, currentness and explicit owner approval pass."
    - "The live runner exposes one ordered, resumable, redacted transaction; missing adapters, stale preflight or drift fail closed before mutation."
    - "Any post-mutation adapter failure produces a containment/rollback receipt and blocks Phase 53 continuation."
  artifacts:
    - path: modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json
      provides: "Value-free upstream candidate provenance and admission blockers."
    - path: modules/rustdesk-fleet/tools/phase53-live-adapters.py
      provides: "Explicit adapter factory and journal-safe stage adapters."
  key_links:
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/phase53-live-adapters.py
      via: "live-only factory after current preflight authorization"
      pattern: "build_live_adapters"
    - from: modules/rustdesk-fleet/tools/phase53-live-adapters.py
      to: modules/rustdesk-fleet/tools/install-phase53-server.py
      via: "closed runtime transaction"
      pattern: "install_closed"
    - from: modules/rustdesk-fleet/tools/phase53-live-adapters.py
      to: modules/rustdesk-fleet/tools/apply-phase53-edge.py
      via: "CAS edge transaction and rollback"
      pattern: "EdgeTransaction"
  prohibitions:
    - "Do not admit 1.1.15 over a stale Phase 52 observation."
    - "Do not call DNS, OCI, firewall, Vault write, client installation or public mutation without a fresh owner-bound preflight."
    - "Do not write secrets, raw probe payloads or stored PASS verdicts into evidence."
---

<objective>Fechar o gap técnico do Plan 53-05 e preparar a admissão segura do candidato 1.1.16, sem executar a publicação live nesta unidade.</objective>

<execution_context>
@$HOME/.codex/gsd-core/workflows/execute-plan.md
@$HOME/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@53-05A-CONTEXT.md
@53-05A-RESEARCH.md
@53-05-PLAN.md
@modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
</context>

## Artifacts this phase produces

- `phase53-live-adapters.py` with a live-only factory and deterministic fake seams.
- Runner journal/evidence handling with strict stage order and containment-first failure.
- Hermetic tests for candidate currentness, adapter order, resume, redaction and fault paths.

<tasks>
<task type="auto">
  <name>Task 53-05A-01: Implementar factory e journal fail-closed</name>
  <files>modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/phase53-live-adapters.py</files>
  <action>Adicionar factory explícito que só é chamado depois da flag live, validação de preflight atual e digest do candidato. Encapsular os módulos existentes por adapters injetáveis, manter `edge-probes` como sequência sem duplicar receipts, persistir somente journal value-free e executar containment/rollback quando um estágio que já mutou falhar. Nenhum adapter deve imprimir argv, env, token ou payload.</action>
  <verify><automated>omni srv1-ops resources run builds -- python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'live_gate or adapter or journal or receipt or redaction' --disable-warnings</automated></verify>
</task>
<task type="auto">
  <name>Task 53-05A-02: Validar candidato e supply currentness</name>
  <files>modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>Testar commit/digest/checksum do 1.1.16 contra fontes oficiais e client 1.4.9, marcar explicitamente NOT_ADMITTED e bloquear observações Phase 52 fora do TTL ou com source drift. Não alterar os contratos pinned até a aprovação do owner.</action>
  <verify><automated>omni srv1-ops resources run builds -- python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'supply or currentness or candidate' --disable-warnings</automated></verify>
</task>
</tasks>

<threat_model>
| Threat | Severity | Mitigation |
|---|---|---|
| Stale pin or vulnerable 1.1.15 admitted | critical | 1.1.16 provenance, TTL and explicit approval gate |
| Partial edge mutation | critical | journal, CAS and containment-first rollback |
| Secret/payload leakage | high | strict receipt schema, redaction and scans |
</threat_model>

<verification>Esta unidade é hermética e não autoriza publicação live; o gate live só pode ser considerado depois de currentness, capacity, recovery e aprovação owner-bound.</verification>
