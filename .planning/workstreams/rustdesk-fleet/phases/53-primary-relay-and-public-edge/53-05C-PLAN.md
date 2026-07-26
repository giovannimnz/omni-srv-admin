---
phase: 53-primary-relay-and-public-edge
plan: 05C
type: execute
wave: 6
depends_on: [53-05B]
gap_closure: true
execution_owner: 53-05C
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
  - modules/rustdesk-fleet/evidence/phase53/capacity-current.json
  - modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/edge-probes.json
  - modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
  - modules/rustdesk-fleet/tools/phase53-production-adapters.py
  - modules/rustdesk-fleet/tools/phase53_production_adapters.py
  - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05C-SUMMARY.md
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05C-VERIFICATION.md
autonomous: true
requirements: [SCP-04, SRV-02, SRV-03, SRV-04, OPS-01]
must_haves:
  truths:
    - "No 1.1.16 candidate becomes ADMITTED_PHASE53 without exact owner-bound provenance, fresh supply, compatibility, parity, capacity-finalize, pre-state and rollback gates."
    - "The serial capacity decision records srv2/srv3 NO-GO before any Horistic consideration and never performs zero-cleanup."
    - "A live transaction, if and only if every gate is current, uses the explicit typed provider bundle and ordered containment-first sequence; otherwise it stops before journal/provider creation."
    - "Evidence, summary and verification distinguish a real current PASS from an honest BLOCKED/gaps_found result."
  artifacts:
    - path: modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
      provides: "Current owner-bound candidate admission state."
    - path: modules/rustdesk-fleet/evidence/phase53/capacity-current.json
      provides: "Current serial capacity samples and finalize decision."
    - path: modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
      provides: "Value-free ordered transaction or blocked-before-mutation receipt."
  key_links:
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/phase53_production_adapters.py
      via: "explicit provider bundle binding after authority gates"
      pattern: "bind_provider_bundle"
    - from: modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
      to: modules/rustdesk-fleet/evidence/phase53
      via: "strict current value-free evidence validation"
      pattern: "NOT_ADMITTED|BLOCKED"
  prohibitions:
    - "Do not regenerate or rewrite Phase 52 historical artifacts."
    - "Do not perform srv2/srv3 cleanup or install any client in this plan."
    - "Do not infer owner approval, supply freshness, capacity finalize or provider credentials from ambient state."
    - "Do not run Phase 06 or plan Phase 54 until an independent verifier accepts a current Phase 53 PASS."
---

<objective>Resolver o remainder live do 53-05B com autoridade atual, ou registrar um bloqueio terminal honesto sem qualquer mutação.</objective>

<context>
@53-05C-CONTEXT.md
@53-05C-RESEARCH.md
@53-05B-SUMMARY.md
@53-05B-VERIFICATION.md
@modules/rustdesk-fleet/contracts/phase53-candidate-admission.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
@modules/rustdesk-fleet/tools/phase53_production_adapters.py
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
</context>

## Tasks

<task type="auto">
  <name>Task 53-05C-01: Provar autoridade e capacidade atuais</name>
  <files>modules/rustdesk-fleet/evidence/phase53/candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/capacity-current.json</files>
  <action>Em uma janela autorizada, resolver supply/provenance do 1.1.16 sem sobrescrever Phase 52, registrar a aprovação owner-bound de Giovanni somente se fornecida com hashes exatos, risco e expiração, coletar duas amostras value-free por candidato em ordem srv2→srv3→Horistic, preservar NO-GO e finalizar Horistic apenas com recovery/rollback/pre-state atuais. Sem aprovação ou capacidade final, permanecer BLOCKED e não criar preflight.</action>
  <verify><automated>python3 modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py --repo . --json</automated></verify>
  <done>Admission e capacity-finalize são atuais e vinculados aos digests, ou os artifacts continuam explicitamente NOT_ADMITTED/BLOCKED sem placement.</done>
</task>

<task type="auto">
  <name>Task 53-05C-02: Vincular provider bundle e rodar transação única</name>
  <files>modules/rustdesk-fleet/tools/phase53-production-adapters.py, modules/rustdesk-fleet/tools/phase53_production_adapters.py, modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>Construir o ProviderBundle somente com callbacks declarados e, apenas após os gates de 05C-01, executar uma única sequência runtime→ops→host/OCI→IP→DNS-last→hostname→report sob o governor. Qualquer falha chama containment-first e registra somente digests. Sem gates atuais, provar zero provider calls/journal e parar.</action>
  <verify><automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</automated></verify>
  <done>Transação atual PASS com evidências value-free e rollback pronto, ou bloqueio determinístico sem side effect.</done>
</task>

<task type="auto">
  <name>Task 53-05C-03: Validar e liberar somente com verifier independente</name>
  <files>modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json, modules/rustdesk-fleet/evidence/phase53/edge-probes.json, modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05C-SUMMARY.md, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05C-VERIFICATION.md</files>
  <action>Executar validator, suite governada, diff/secret scan, Graphify status e verifier independente. Produzir summary/verification como PASS somente com evidência current; caso contrário usar gaps_found/BLOCKED e manter Plan 06 e Phase 54 bloqueados.</action>
  <verify><automated>python3 modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py --repo . --json</automated></verify>
  <done>Existe uma decisão auditável current que libera 53-06 ou mantém bloqueio honesto; nunca há avanço summary-only.</done>
</task>

<verification>O plano não autoriza qualquer mutação quando os gates atuais estão ausentes; um bloqueio value-free é resultado válido e obrigatório.</verification>
