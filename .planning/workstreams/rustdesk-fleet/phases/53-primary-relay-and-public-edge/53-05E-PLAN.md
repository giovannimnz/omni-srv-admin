---
phase: 53-primary-relay-and-public-edge
plan: 05E
type: execute
wave: 14
depends_on: [53-05D2H]
gap_closure: true
execution_owner: 53-05E
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
  - modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json
  - modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
  - modules/rustdesk-fleet/evidence/phase53/capacity-current.json
  - modules/rustdesk-fleet/evidence/phase53/preflight.json
  - modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
  - modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md
autonomous: false
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-17, authority is regenerated from the immutable 05D2D execution_source_commit; the stale OperationPlan and every old hash/confirmation are rejected."
    - "Per D-06, current readback and the OperationPlan bind the non-conflatable tuple: reserved public owner/VNIC atius-srv-1 137.131.140.20/10.0.0.238, DRG route/SNAT/backend-ingress source 10.11.1.11, and horistic-srv backend 10.21.1.21."
    - "D-05D-02: Phase 52 remains byte-frozen and a new Phase 53 successor attestation is read-only, non-authorizing and digest-bound."
    - "D-05D-03/D-05D-08: supply, admission, prestate and previews are collected only with ReadOnlyProviderBundle, which has zero provider write capabilities."
    - "Absence of owner approval ends normally at AWAITING_OWNER_HASH_APPROVAL with OperationPlan persisted, zero apply journal/provider calls/live mutations and an explicit blocking checkpoint."
    - "An owner record can be created only from a new explicit Giovanni Muniz response containing the current OperationPlan hash and an unexpired RFC3339 expiry."
    - "05E stops after the authority handoff and never dispatches or executes 05F."
  artifacts:
    - path: modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json
      provides: "Read-only descendant attestation over frozen Phase 52 inputs and immutable execution source binding."
    - path: modules/rustdesk-fleet/evidence/phase53/preflight.json
      provides: "Current read-only source, placement, capacity, Vault fingerprint, provider prestate and rollback-readiness observations."
    - path: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      provides: "Canonical hash-bound full transaction preview with exact source tree, prestates, typed confirmations, rollback and restore scope."
    - path: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
      provides: "Owner record created only after the explicit checkpoint response; absent while awaiting."
  key_links:
    - from: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
      to: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      via: "immutable execution_source_commit plus allowlisted code/contracts aggregate"
      pattern: "execution_source_commit|execution_source_tree_sha256"
    - from: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
      to: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
      via: "exact canonical_input_sha256 and expiry copied only from explicit owner response"
      pattern: "operation_plan_sha256|expires_at"
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/phase53-live-backend.py
      via: "plan mode constructs only build_phase53_read_only_backend"
      pattern: "mode plan|build_phase53_read_only_backend"
  prohibitions:
    - "Do not call build_phase53_apply_backend, create apply/rollback/restore journals or perform any host/provider mutation."
    - "Do not manufacture, infer, reuse or auto-approve an owner response from generic authorization, chat history, stored files or prior plans."
    - "Do not rewrite Phase 52, clean srv2/srv3, mutate 10.31.1.31 or persist secret values."
    - "Do not autoexecute or dispatch 53-05F after this plan."
---

<objective>
Criar uma authority lane read-only e owner-bound sobre o source commit imutável do 05D2D, que inclui 05D2C/05D como ancestors, persistir um OperationPlan completo e parar em checkpoint explícito sem live mutation.

Purpose: tornar approval uma decisão humana atual e auditável, sem transformar ausência de approval em execução perdida ou em fallback inseguro.
Output: successor attestation, current admission/capacity/prestate, typed previews, OperationPlan e, somente após resposta explícita, owner approval hash-bound sobre o source final de 05D2D.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/ROADMAP.md
@.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-topology.json
@modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json
@modules/rustdesk-fleet/contracts/phase52-post-live-successor.json
@modules/rustdesk-fleet/evidence/phase52/post-live/review-1.json
@modules/rustdesk-fleet/evidence/phase52/post-live/review-2.json
@.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-10-CLOSEOUT.json
@modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
@modules/rustdesk-fleet/tools/phase53-live-backend.py
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
</context>

## Artifacts

- `phase52-successor-attestation.json` records frozen Phase 52 input digests, `historical_replay=false`, `historical_rebaseline=false` and `authorizes_live=false`.
- `preflight.json` records the current descendant tip, immutable `execution_source_commit`, allowlisted `execution_source_tree_sha256`, clean source scope, exact selected host/public edge, value-free fingerprint, rollback readiness and provider prestates.
- `edge-forwarder-operation-plan.json` is regenerated from scratch from current topology/source/prestate; the pre-existing file is forbidden input and no old hash is reused. It binds public-VNIC owner `10.0.0.238`, DRG/SNAT/backend source `10.11.1.11`, backend `10.21.1.21`, and the exact seven 05F evidence destinations with required prestate `absent`.
- `edge-forwarder-owner-approval.json` does not exist while awaiting. After an explicit checkpoint response, it records owner identity, decision, current OperationPlan hash, expiry, risk/rollback acknowledgement and response digest without storing unrelated chat text.

<tasks>

<task type="auto">
  <name>Task 53-05E-01: Gerar successor attestation, prestate e OperationPlan somente read-only</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md
    @.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/evidence/phase53/topology-discovery.json
    @modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json
    @modules/rustdesk-fleet/contracts/phase52-post-live-successor.json
    @modules/rustdesk-fleet/evidence/phase52/post-live/review-1.json
    @modules/rustdesk-fleet/evidence/phase52/post-live/review-2.json
    @.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-10-CLOSEOUT.json
    @modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/tools/phase53-live-backend.py
    @modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/topology-discovery.json, modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json, modules/rustdesk-fleet/evidence/phase53/candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/capacity-current.json, modules/rustdesk-fleet/evidence/phase53/preflight.json, modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json</files>
  <action>
Iniciar um processo novo. Ler `execution_source_commit` do 05D2D summary, provar ancestry e igualdade dos 34 blobs allowlisted, rejeitar source-scope dirt e exigir o receipt 05D2H atual com manifest de quarantine completo e os sete destinos canonical ausentes. Produzir fora do repo uma observação explícita, value-free e current usando somente reads governados (topology D-06, supply, duas amostras por candidato, Vault public fingerprint metadata e provider prestates/previews); o producer não pode descobrir credenciais/rotas nem sintetizar observações. Reexecutar a discovery read-only de 05D2T e exigir a topologia D-06 idêntica; drift bloqueia sem novo checkpoint. Verificar Phase 52 somente por Git objects/readback e gravar a nova attestation Phase 53.

Executar `build-phase53-authority-plan.py collect-observation` com output exclusivo sob `/tmp`, seguido pelo runner literal com `--authority-observation "$AUTHORITY_OBSERVATION"`, `--housekeeping-receipt .../53-05D2H-SUMMARY.md`, `--quarantine-pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json` e `--live-backend phase53-production --mode plan --stage full --operation-plan ...`, sem live env e sem owner approval. O collector/runner deve construir exclusivamente `ReadOnlyProviderBundle`, provar `capabilities={"read","preview"}` e zero apply/restore/containment callbacks, e consumir: supply/admission current, duas amostras por candidato na ordem srv2→srv3→Horistic, srv2/srv3 NO-GO zero-cleanup, Horistic capacity-finalize, backups/restore, Vault public fingerprint reference, host/OCI/Cloudflare/Apache prestates, ownership/revisions, typed previews/confirmations e rollback readiness.

Per D-17, tratar o OperationPlan existente como input proibido e gerar bytes canônicos novos sem reutilizar hash, confirmation ou approval. Per D-06, bindar separadamente e sem coerção o owner/VNIC público `atius-srv-1`/`137.131.140.20`/`10.0.0.238`, o route/SNAT/backend-ingress source `10.11.1.11` e o backend `horistic-srv`/`10.21.1.21`; qualquer plan/prestate que use `10.0.0.238` como backend source é inválido. Incluir DNAT/forward/return path/backend restriction, mappings 34099-34101, três A records DNS-only, dois origins contra IP mais três hostnames, native negatives, API, lifecycle, rollback imutável e restore-production distinto. O preflight e OperationPlan também devem bindar `05D2H_summary_commit`, `quarantine_manifest_sha256`, generation ID, canonical-seven absent digest e os sete destinos 05F com expected prestate `absent`, para que receipt drift ou stale tracked/untracked bytes bloqueiem antes de journal/provider construction. Persistir `AWAITING_OWNER_HASH_APPROVAL`, exit 0 e zero provider mutations.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'AUTHORITY_OBSERVATION=$(mktemp /tmp/rustdesk-phase53-authority.XXXXXX.json); trap "rm -f -- \"$AUTHORITY_OBSERVATION\"" EXIT; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 modules/rustdesk-fleet/tools/build-phase53-authority-plan.py collect-observation --repo . --output "$AUTHORITY_OBSERVATION"; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --authority-observation "$AUTHORITY_OBSERVATION" --housekeeping-receipt .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md --quarantine-pointer /var/tmp/omni-rustdesk-phase53-quarantine/current-phase53.json --live-backend phase53-production --mode plan --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json'</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_successor_attestation_binds_frozen_phase52 modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_descendant_source_binding_rejects_drift modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_read_only_backend_has_no_write_capability modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_operation_plan_writes_exact_six_artifacts_and_rejects_public_vnic_backend_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_capacity_current_requires_six_ordered_samples modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_strict_validator_accepts_authority_and_live_set_with_immutable_source modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_housekeeping_receipt_is_explicit_current_and_symlink_safe --disable-warnings</automated>
  </verify>
  <acceptance_criteria>Authority artifacts bind the immutable source commit/tree under an ancestor rule; Phase 52 remains unchanged; current read-only observations/previews form one complete OperationPlan; status is AWAITING_OWNER_HASH_APPROVAL exit 0 with no owner record, apply journal, provider write or live mutation.</acceptance_criteria>
  <done>Um OperationPlan current e reviewable existe, e a execução está parada de forma segura no owner gate.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 53-05E-02: Obter decisão owner-bound explícita de Giovanni</name>
  <read_first>
    @modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
    @modules/rustdesk-fleet/evidence/phase53/preflight.json
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json</files>
  <action>Parar no checkpoint. Exibir a Giovanni Muniz o current `operation_plan_sha256`, `execution_source_commit`, `execution_source_tree_sha256`, expiry proposal, typed preview/confirmation digests, risk disposition e rollback/restore scope. Não criar owner record antes da resposta e não interpretar silêncio, aprovação genérica, approval anterior ou auto-advance como decisão.</action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_requires_explicit_response --disable-warnings</automated>
    <human-check>Giovanni confere o OperationPlan atual e responde explicitamente com owner `Giovanni Muniz`, decision `approve`, o `operation_plan_sha256` atual e um `expires_at` RFC3339 futuro; qualquer ausência/mismatch mantém AWAITING_OWNER_HASH_APPROVAL.</human-check>
  </verify>
  <what-built>Successor attestation, current read-only prestate/typed previews e um OperationPlan completo, sem mutation capability.</what-built>
  <how-to-verify>
    1. Compare o hash mostrado com `edge-forwarder-operation-plan.json`.
    2. Confira source commit/tree, target/IP/ports/DNS, risk, rollback e restore scope.
    3. Para aprovar, responda incluindo literalmente owner, decision, hash atual e expiry futuro. Para não aprovar, não forneça esses quatro campos.
  </how-to-verify>
  <resume-signal>Forneça a decisão explícita hash-bound ou mantenha o checkpoint em AWAITING_OWNER_HASH_APPROVAL.</resume-signal>
  <acceptance_criteria>Somente uma resposta explícita de Giovanni com o hash atual e expiry futuro pode liberar a criação do owner record; até lá, a execução permanece aguardando sem erro e sem mutation.</acceptance_criteria>
  <done>O checkpoint permanece bloqueante até existir uma decisão owner-bound válida.</done>
</task>

<task type="auto">
  <name>Task 53-05E-03: Persistir o owner record e encerrar o handoff</name>
  <read_first>
    @modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
    @modules/rustdesk-fleet/evidence/phase53/preflight.json
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md</files>
  <action>
Executar somente após o checkpoint receber a resposta explícita exigida. O orchestrator traduz somente os campos estruturados aprovados para um arquivo temporário `OWNER_RESPONSE` fora do repo, sem texto livre. Recalcular o OperationPlan hash, revalidar source ancestry/tree, typed confirmation expiry e prestate currentness; se qualquer campo mudou, descartar a resposta, permanecer AWAITING_OWNER_HASH_APPROVAL e voltar ao checkpoint. Se estiver current, chamar o subcomando sealed `build-phase53-authority-plan.py record-owner`, que cria atomicamente apenas um record value-free com owner exato, decision, plan hash, source commit/tree, expiry, risk/rollback acknowledgement e digest da resposta estruturada; o subcomando não expõe apply/runtime providers e não copia texto livre nem secrets.

Validar o record e escrever 53-05E-SUMMARY com `authority_status=OWNER_HASH_APPROVED`, ou escrever/atualizar summary com `authority_status=AWAITING_OWNER_HASH_APPROVAL` sem owner record quando não aprovado. Encerrar o processo. Não construir apply backend, não criar live journal e não despachar 05F; o orchestrator deve iniciar 05F em novo processo/execução.
  </action>
  <verify>
    <automated>bash -euo pipefail -c 'test -n "${OWNER_RESPONSE:-}"; test -f "$OWNER_RESPONSE"; omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 modules/rustdesk-fleet/tools/build-phase53-authority-plan.py record-owner --repo . --response "$OWNER_RESPONSE" --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json --output modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json'</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_requires_explicit_response modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_owner_approval_hash_and_expiry_are_current modules/rustdesk-fleet/tests/test_phase53_primary_edge.py::test_05e_no_auto_apply_after_owner_record --disable-warnings</automated>
  </verify>
  <acceptance_criteria>Owner record exists only after an exact current Giovanni response; mismatch/expiry returns to the checkpoint; 05E ends with zero apply capability/provider mutation and 05F was not dispatched.</acceptance_criteria>
  <done>A authority handoff está current e owner-bound, ou permanece honestamente aguardando sem live mutation.</done>
</task>

</tasks>

<threat_model>
**Security enforcement:** OWASP ASVS L1. Qualquer threat high/critical não mitigada mantém o checkpoint e bloqueia 05F.

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53E-SOURCE | Spoofing/Tampering | authority source binding | critical | mitigate | Ancestor plus exact allowlisted code/contracts blob equality; evidence/planning tips are excluded from the tree. |
| T53E-READONLY | Elevation of Privilege | plan backend | critical | mitigate | Capability inspection and tests prove no apply/restore/containment callback or ProviderBundle conversion. |
| T53E-APPROVAL | Spoofing/Repudiation | owner decision | critical | mitigate | Blocking checkpoint; exact Giovanni identity, current plan hash, explicit decision and future expiry are mandatory. |
| T53E-TOCTOU | Tampering | previews/prestate | high | mitigate | Recalculate plan/source/prestate/confirmation currentness before recording approval; drift returns to checkpoint. |
| T53E-SECRET | Information Disclosure | authority artifacts | high | mitigate | Value-free schemas, response digest only, Vault path/fingerprint only and strict scanner. |
</threat_model>

<verification>
- Plan mode uses the literal full command and returns exit 0 with `PLAN_READY`/`AWAITING_OWNER_HASH_APPROVAL`; this is a valid checkpoint state, not lost failure.
- Tests prove zero write capabilities/provider calls and reject generic, stale, mismatched or expired approvals.
- No task in 05E can start 05F; the output explicitly returns control to the orchestrator.
</verification>

<success_criteria>
1. All current authority artifacts bind 05D source commit/tree through ancestry plus exact code/contracts equality.
2. A complete current OperationPlan exists from read-only supply/prestate/preview calls.
3. Missing approval leaves a durable AWAITING checkpoint with no live mutation.
4. Owner approval, if created, derives only from a new explicit Giovanni response with exact current hash and expiry.
5. 05E stops after handoff and requires a new process for 05F.
</success_criteria>

<output>Create `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md`, stop at or after the explicit owner checkpoint, and return control. Never auto-dispatch 53-05F.</output>
