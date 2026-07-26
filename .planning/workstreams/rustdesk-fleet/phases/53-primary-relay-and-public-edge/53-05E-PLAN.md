---
phase: 53-primary-relay-and-public-edge
plan: 05E
type: execute
wave: 9
depends_on: [53-05D2]
gap_closure: true
execution_owner: 53-05E
files_modified:
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
    - "D-05D2-01: all authority artifacts bind the immutable 05D2 execution_source_commit, which includes 05D as an ancestor; the current authority tip must contain that source commit as ancestor and preserve every allowlisted blob."
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
    - from: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2-SUMMARY.md
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
Criar uma authority lane read-only e owner-bound sobre o source commit imutável do 05D2, que inclui 05D como ancestor, persistir um OperationPlan completo e parar em checkpoint explícito sem live mutation.

Purpose: tornar approval uma decisão humana atual e auditável, sem transformar ausência de approval em execução perdida ou em fallback inseguro.
Output: successor attestation, current admission/capacity/prestate, typed previews, OperationPlan e, somente após resposta explícita, owner approval hash-bound sobre o source final de 05D2.
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
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-UAT.md
@modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
@modules/rustdesk-fleet/tools/phase53-live-backend.py
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
</context>

## Artifacts

- `phase52-successor-attestation.json` records frozen Phase 52 input digests, `historical_replay=false`, `historical_rebaseline=false` and `authorizes_live=false`.
- `preflight.json` records the current descendant tip, immutable `execution_source_commit`, allowlisted `execution_source_tree_sha256`, clean source scope, exact selected host/public edge, value-free fingerprint, rollback readiness and provider prestates.
- `edge-forwarder-operation-plan.json` contains canonical input, exact port/DNS mapping, source binding, admission/capacity, typed OCI/Cloudflare/Apache previews, confirmations, risks, one apply transaction, immutable rollback seal and a distinct restore-production transaction.
- `edge-forwarder-owner-approval.json` does not exist while awaiting. After an explicit checkpoint response, it records owner identity, decision, current OperationPlan hash, expiry, risk/rollback acknowledgement and response digest without storing unrelated chat text.

<tasks>

<task type="auto">
  <name>Task 53-05E-01: Gerar successor attestation, prestate e OperationPlan somente read-only</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2-SUMMARY.md
    @.planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-UAT.md
    @modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/tools/phase53-live-backend.py
    @modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/phase52-successor-attestation.json, modules/rustdesk-fleet/evidence/phase53/candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/capacity-current.json, modules/rustdesk-fleet/evidence/phase53/preflight.json, modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json</files>
  <action>
Iniciar um processo novo. Ler `execution_source_commit` do 05D2 summary, provar que ele contém 05D como ancestor, que ele próprio é ancestor do tip e que todos os blobs allowlisted de code/contracts/Quadlet são idênticos; rejeitar source-scope dirt. Gravar commit e aggregate no successor/preflight/OperationPlan sem exigir tip equality. Verificar os bytes Phase 52 somente por leitura e gravar a nova attestation Phase 53; jamais executar generator Phase 52.

Executar o comando literal `--live-backend phase53-production --mode plan --stage full --operation-plan ...` sem live env e sem owner approval. O runner deve construir exclusivamente `ReadOnlyProviderBundle`, provar `capabilities={"read","preview"}` e zero apply/restore/containment callbacks, e coletar: supply/admission current, duas amostras por candidato na ordem srv2→srv3→Horistic, srv2/srv3 NO-GO zero-cleanup, Horistic capacity-finalize, backups/restore, Vault public fingerprint reference, host/OCI/Cloudflare/Apache prestates, ownership/revisions, typed previews/confirmations e rollback readiness.

Gerar novo canonical OperationPlan per D-05D-04/D-05D-05/D-05D-08/D-05D-10 com target `10.21.1.21`, IP `137.131.140.20`, mappings 34099-34101, A records DNS-only `rustdesk.atius.com.br`/`rustdesk-id.atius.com.br`/`rustdesk-relay.atius.com.br`, IP-before-DNS/two-origin probes, custom API boundary, three restarts/reboot, immutable rollback e distinct restore-production. Persistir status `AWAITING_OWNER_HASH_APPROVAL`, retornar exit 0, não criar owner approval/apply journal e provar zero provider mutations. Nenhum tip/evidence hash posterior entra no source tree.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode plan --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'successor_attestation or descendant_source_binding or read_only_backend or operation_plan or capacity_current or awaiting_owner' --disable-warnings</automated>
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
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'awaiting_owner or owner_approval_explicit_response' --disable-warnings</automated>
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
Executar somente após o checkpoint receber a resposta explícita exigida. Recalcular o OperationPlan hash, revalidar source ancestry/tree, typed confirmation expiry e prestate currentness; se qualquer campo mudou, descartar a resposta, permanecer AWAITING_OWNER_HASH_APPROVAL e voltar ao checkpoint. Se estiver current, criar atomicamente um record value-free com owner exato, decision, plan hash, source commit/tree, expiry, risk/rollback acknowledgement e digest da resposta estruturada; não copiar texto livre nem secrets.

Validar o record e escrever 53-05E-SUMMARY com `authority_status=OWNER_HASH_APPROVED`, ou escrever/atualizar summary com `authority_status=AWAITING_OWNER_HASH_APPROVAL` sem owner record quando não aprovado. Encerrar o processo. Não construir apply backend, não criar live journal e não despachar 05F; o orchestrator deve iniciar 05F em novo processo/execução.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'owner_approval_explicit_response or owner_approval_hash or owner_approval_expiry or no_auto_apply' --disable-warnings</automated>
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
