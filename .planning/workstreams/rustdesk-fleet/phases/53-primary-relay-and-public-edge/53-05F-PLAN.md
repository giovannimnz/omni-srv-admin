---
phase: 53-primary-relay-and-public-edge
plan: 05F
type: execute
wave: 10
depends_on: [53-05E]
gap_closure: true
execution_owner: 53-05F
files_modified:
  - modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/edge-probes.json
  - modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
  - modules/rustdesk-fleet/evidence/phase53/lifecycle.json
  - modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
  - modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "05F starts in a new process and reconstructs no authority from memory; it revalidates owner identity/decision/hash/expiry, typed confirmations, prestates, source ancestry/tree and admission immediately before the first write."
    - "D-05D-04/D-05D-05: one approved full transaction deploys Horistic 10.21.1.21 behind 137.131.140.20 with exact 34099-34101 translation and DNS-only A records for rustdesk.atius.com.br, rustdesk-id.atius.com.br and rustdesk-relay.atius.com.br."
    - "D-05D-10: two external origins prove IP-before-DNS and hostname-after-DNS TCP+UDP, separate API auth/redaction, three restarts plus reboot, resource/log/identity invariants and metrics."
    - "Containment-first rollback is sealed immutable; restore-production is a new transaction with a distinct ID and journal after rollback, never an append/rewrite of the rollback proof."
    - "srv2/srv3, Phase 52, Phase 54, reserved IP ownership, legacy fallbacks and 10.31.1.31 remain unmodified."
    - "The live_executor_commit contains only the seven sealed 05F evidence manifests and no summary; no pre-commit evidence contains live_executor_commit or any verified executor SHA."
    - "A descendant summary-only commit changes exactly 53-05F-SUMMARY.md and records the exact live_executor_commit parent, execution source/tree, plan/transaction identifiers and whole-manifest digests computed from git show bytes at that parent, without requiring either commit to contain its own SHA."
    - "53-05F execution never writes its own verification; an independent verifier validates the live executor parent and summary-only descendant, then alone creates 53-05F-VERIFICATION.md in another descendant with status passed or gaps_found."
  artifacts:
    - path: modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
      provides: "Single approved apply transaction journal and provider receipts."
    - path: modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
      provides: "Sealed immutable containment-first rollback proof."
    - path: modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
      provides: "Distinct post-rollback desired-state transaction and journal."
    - path: modules/rustdesk-fleet/evidence/phase53/lifecycle.json
      provides: "Three restart and one reboot source/transaction-bound observations."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md
      provides: "Summary-only descendant binding exact live_executor_commit, execution source/tree, plan/transactions and git-show manifest digests without self-hash."
    - path: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-VERIFICATION.md
      provides: "Independent verifier verdict required by the structural 53-06 preflight gate."
  key_links:
    - from: modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
      to: modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
      via: "new-process preflight validates exact plan/source/prestate/confirmation hash and expiry before journal creation"
      pattern: "operation_plan_sha256|execution_source_commit|expires_at"
    - from: modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
      to: modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
      via: "sealed rollback digest is an immutable input to a distinct restore transaction"
      pattern: "rollback_receipt_sha256|restore_transaction_id"
    - from: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md
      to: .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-VERIFICATION.md
      via: "independent verifier checks the evidence-only live_executor_commit, proves the intervening summary-only diff, and writes verification in a later descendant"
      pattern: "live_executor_commit|05F_summary_commit|status"
  prohibitions:
    - "Do not continue in the 05E process, reuse in-memory approval, accept expired confirmations or create a journal before all gates are revalidated."
    - "Do not run more than one approved apply transaction or silently retry an alternate plan."
    - "Do not modify/reopen rollback-drill.json after its seal or use the apply transaction ID for restore-production."
    - "Do not include 53-05F-SUMMARY.md in live_executor_commit, include any non-evidence path in that commit, or put live_executor_commit/verified executor SHA into pre-commit evidence."
    - "Do not make live_executor_commit or the summary commit contain its own SHA; commit identity is recorded only by descendants."
    - "Do not release 137.131.140.20, clean srv2/srv3, modify Phase 52/54, install clients or execute the 10.31.1.31 migration."
    - "Do not write 53-05F-VERIFICATION.md from the executor."
---

<objective>
Em nova execução/processo, revalidar a authority owner-bound e aplicar exatamente uma transação full, incluindo lifecycle, rollback imutável e restore-production separado, então entregar o parent evidence-only e o descendant summary-only a um verifier independente.

Purpose: produzir a prova live completa sem misturar read-only planning, owner approval, mutation e verification no mesmo authority context.
Output: apply/edge/API/lifecycle/rollback/restore/metrics evidence-only live commit, descendant summary-only commit e independent verification handoff.
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
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05E-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
@modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
@modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
@modules/rustdesk-fleet/tools/phase53-live-backend.py
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
</context>

## Artifacts

- `deploy-transaction.json` is the only apply journal for the approved OperationPlan.
- `edge-probes.json` and `ops-api-probes.json` contain value-free two-origin IP/hostname TCP+UDP and separate API auth/redaction observations.
- `lifecycle.json` contains three restart cycles plus one real reboot, each tied to source/tree/transaction and current observations.
- `rollback-drill.json` is sealed after containment-first rollback and is never appended or rewritten.
- `restore-production-transaction.json` is a new transaction/journal with a distinct ID, current preflight and desired-state proof.
- Every pre-commit evidence manifest binds `execution_source_commit`, `execution_source_tree_sha256`, OperationPlan and applicable transaction identifiers plus owned receipt/payload digests. It contains neither `live_executor_commit` nor a self-referential digest of its own complete bytes.
- `53-05F-VERIFICATION.md` is outside executor ownership and is written only by the independent verifier.

## Small commit protocol

1. Validate and seal all seven evidence manifests, then create `live_executor_commit` containing exactly those seven paths and no summary/planning/report file.
2. After Git assigns that SHA, compute each whole-manifest SHA-256 from `git show live_executor_commit:path`. Write `53-05F-SUMMARY.md` with the exact `live_executor_commit`, `execution_source_commit`, `execution_source_tree_sha256`, OperationPlan digest, transaction IDs and the complete path-to-digest manifest table.
3. Create one direct descendant whose diff from `live_executor_commit` is exactly `53-05F-SUMMARY.md`; this is the externally identified `05F_summary_commit`. The summary does not record its own commit SHA.
4. Stop and hand both SHAs to an independent verifier. The verifier rejects any extra live/summary diff, proves source→live→summary ancestry, verifies manifest bytes from the live parent, and creates verification only in another descendant.

<tasks>

<task type="auto">
  <name>Task 53-05F-01: Revalidar authority e executar uma única transação full</name>
  <read_first>
    @.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2-SUMMARY.md
    @modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json
    @modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
    @modules/rustdesk-fleet/evidence/phase53/preflight.json
    @modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json
    @modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json
    @modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  </read_first>
  <files>modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json, modules/rustdesk-fleet/evidence/phase53/edge-probes.json, modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json, modules/rustdesk-fleet/evidence/phase53/lifecycle.json, modules/rustdesk-fleet/evidence/phase53/rollback-drill.json, modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json, modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json</files>
  <action>
Iniciar um processo novo, sem objetos/callbacks herdados do 05E. Antes de journal/provider construction, revalidar: `execution_source_commit` ancestor do tip, todos os allowlisted code/contracts blobs idênticos e scope clean; OperationPlan canonical hash; owner exato Giovanni Muniz, decision approve e expiry futura; typed confirmation IDs/hashes/expiry; admission/capacity/current prestates/revisions; backup/rollback readiness; live flag; `ADMITTED_PHASE53=1`. Qualquer falha retorna exit 3/BLOCKED com zero journals/provider calls/actions.

Executar literalmente sob o governor: `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 ADMITTED_PHASE53=1 ... run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan ... --owner-approval ...`. `build_phase53_apply_backend(...)` deve ser o único factory apply. Executar exatamente uma vez e na ordem contratada: per D-01/D-02/D-03/D-04, deploy rootless digest-bound, isolado, bounded e Vault-hydrated em Horistic 10.21.1.21 com ingress fechado; per D-09/D-10/D-11/D-12, ops API separada/Apache configtest/auth/redaction/readiness/metrics; host+OCI CAS; public IP 137.131.140.20; per D-05/D-06/D-07/D-08, two-origin IP TCP 34099/34100/34101 e UDP 34100, negar diretamente public 21114-21119 e todo outro listener, manter native 21115-21117/UDP 21116 somente no target/internal path, depois DNS-last A DNS-only sem proxy/AAAA/CNAME para `rustdesk.atius.com.br`, `rustdesk-id.atius.com.br` e `rustdesk-relay.atius.com.br`, então hostname TCP+UDP. Per D-13, executar three restarts e real reboot; per D-14/D-15, preservar fallbacks/client domains e não reivindicar standby/DR.

Depois, executar containment-first rollback: fechar/restore host+OCI ingress, DNS CAS restore, remover somente runtime/API owned state, restore Apache/nft/linger if-current, provar public closed, fallbacks/backups/IP preserved e 10.31.1.31 untouched. Selar `rollback-drill.json` e seu digest antes de qualquer restore. Criar `restore-production-transaction.json` com novo transaction ID/journal, revalidar currentness, reaplicar desired state, repetir runtime/IP/DNS/hostname/API, um restart e regressions. Falha de restore preserva o rollback seal, contém ingress e termina exit 4/BLOCKED; nunca reescreve o rollback receipt.
  </action>
  <verify>
    <automated>ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 ADMITTED_PHASE53=1 omni srv1-ops resources run builds -- python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --repo . --live-backend phase53-production --mode apply --stage full --operation-plan modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json --owner-approval modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'new_process_revalidation or full_sequence or two_origin or lifecycle or immutable_rollback or restore_production_transaction or zero_cleanup or migration_handoff' --disable-warnings</automated>
  </verify>
  <acceptance_criteria>Uma única transaction current prova placement/edge/DNS/API/lifecycle; rollback é containment-first e imutável; restore-production tem novo ID/journal e desired-state proof; qualquer gate/failure bloqueia sem unsafe continuation; todos os exclusions permanecem intactos.</acceptance_criteria>
  <done>Live evidence completa ou um BLOCKED terminal value-free existe; nenhuma verification foi escrita pelo executor.</done>
</task>

<task type="auto">
  <name>Task 53-05F-02: Selar evidence-only live commit, criar summary-only descendant e entregar ao verifier</name>
  <read_first>
    @modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
    @modules/rustdesk-fleet/evidence/phase53/edge-probes.json
    @modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
    @modules/rustdesk-fleet/evidence/phase53/lifecycle.json
    @modules/rustdesk-fleet/evidence/phase53/rollback-drill.json
    @modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json
    @modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
  </read_first>
  <files>.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md</files>
  <action>
Executar validator strict e a suite governada contra raw evidence. Recalcular source ancestry/tree, plan/approval/prestate/confirmation bindings, transaction order/IDs, rollback seal, restore distinctness, secret hygiene, CPU/resource bounds, exact port/DNS surface, Phase 52 freeze, srv2/srv3 zero-cleanup, public-IP retention, Phase 54/client absence, fallback regressions e migration executable=false. Nenhum stored PASS substitui observações.

Antes do primeiro commit, exigir que cada manifest vincule `execution_source_commit`, `execution_source_tree_sha256`, OperationPlan e os transaction IDs aplicáveis, além de digests de receipts/payloads owned. Rejeitar qualquer `live_executor_commit`/verified executor SHA em evidence e qualquer campo que tente hashear os próprios bytes completos do manifest.

Criar `live_executor_commit` contendo exatamente `deploy-transaction.json`, `edge-probes.json`, `ops-api-probes.json`, `lifecycle.json`, `rollback-drill.json`, `restore-production-transaction.json` e `direct-relay-metrics.json`; confirmar por `git diff-tree --no-commit-id --name-only -r` que não há summary nem path extra. Depois que o SHA existir, obter os bytes de cada manifest com `git show live_executor_commit:path`, calcular SHA-256 e escrever `53-05F-SUMMARY.md` com outcomes reais, o SHA exato do parent live, execution_source commit/tree, OperationPlan/approval hashes, apply/rollback/restore IDs, tabela completa path→digest e `verification_status=pending_independent`. Não escrever o SHA do próprio summary commit no arquivo.

Criar um direct descendant cuja única diferença para `live_executor_commit` seja `53-05F-SUMMARY.md`; identificar externamente esse tip como `05F_summary_commit` e parar. O executor não cria 53-05F-VERIFICATION.md, não altera ROADMAP/ledger e não inicia 53-06.
  </action>
  <verify>
    <automated>python3 modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py --repo . --json</automated>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py --disable-warnings</automated>
    <automated>SUMMARY_COMMIT=$(git rev-parse HEAD) &amp;&amp; LIVE_EXECUTOR_COMMIT=$(git rev-parse "${SUMMARY_COMMIT}^") &amp;&amp; test "$(git diff-tree --no-commit-id --name-only -r "$LIVE_EXECUTOR_COMMIT" | LC_ALL=C sort | paste -sd, -)" = "modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json,modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json,modules/rustdesk-fleet/evidence/phase53/edge-probes.json,modules/rustdesk-fleet/evidence/phase53/lifecycle.json,modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json,modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json,modules/rustdesk-fleet/evidence/phase53/rollback-drill.json" &amp;&amp; test "$(git diff-tree --no-commit-id --name-only -r "$LIVE_EXECUTOR_COMMIT" "$SUMMARY_COMMIT")" = ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md"</automated>
    <automated>git diff --check</automated>
  </verify>
  <acceptance_criteria>Validator/tests derive current evidence only; live_executor_commit is evidence-only; its direct summary descendant changes one file and records the parent/source/tree/manifest digests without self-hash; no self-verification, ledger/ROADMAP promotion or 53-06 execution occurred.</acceptance_criteria>
  <done>Os commits evidence-only e summary-only estão prontos para um verifier independente e 53-06 permanece bloqueado.</done>
</task>

</tasks>

<post_execution_orchestrator_contract>
1. Encerrar o processo executor e iniciar um agente/verifier independente com os SHAs exatos de `live_executor_commit` e `05F_summary_commit`.
2. O verifier executa `validate_phase53_binding_chain(...)`, confirma source→live→summary ancestry, tree allowlisted idêntica/clean, commit live com exatamente sete evidence paths, diff summary com exatamente `53-05F-SUMMARY.md`, manifest digests contra bytes do parent via `git show`, e OperationPlan/approval/prestate/apply/rollback/restore evidence current/value-free. O SHA live pode ocorrer somente no summary e na verification, nunca na evidence selada.
3. Somente o verifier escreve `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-VERIFICATION.md`, em outro descendant, com frontmatter `status: passed` ou `status: gaps_found`, `live_executor_commit`, `05F_summary_commit`, `execution_source_commit` e `execution_source_tree_sha256`.
4. `status: gaps_found`, arquivo ausente, hash mismatch ou verifier não independente mantém 53-06 BLOCKED. `status: passed` apenas torna o preflight de 53-06 elegível; não executa 53-06 automaticamente.
</post_execution_orchestrator_contract>

<threat_model>
**Security enforcement:** OWASP ASVS L1. Qualquer threat high/critical não mitigada produz BLOCKED/gaps_found e impede 53-06.

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53F-REPLAY | Spoofing/Repudiation | approval/confirmations | critical | mitigate | New-process revalidation of exact owner/plan/source/prestate hashes and future expiry before journal creation. |
| T53F-SOURCE | Tampering | live source and two-commit binding | critical | mitigate | Source ancestry, exact allowlisted blobs/clean scope, evidence-only live parent, summary-only descendant and git-show manifest digests; no commit self-hash. |
| T53F-EDGE | Tampering/DoS | host/OCI/DNS publication | critical | mitigate | Exact approved mapping, CAS/readback, DNS-last, two-origin proof and containment-first failure path. |
| T53F-SECRET | Information Disclosure | Vault/API/provider receipts | critical | mitigate | Runtime-only hydration, fingerprint/value-free receipts, redaction and strict secret scan. |
| T53F-ROLLBACK | Tampering/DoS | rollback/restore | critical | mitigate | Sealed immutable rollback receipt and distinct restore transaction ID/journal after rollback. |
| T53F-RESOURCE | Denial of Service | host/runtime/tests | high | mitigate | 20% host CPU governor, Phase 53 cgroup caps and bounded output/log/lifecycle checks. |
| T53F-VERIFIER | Spoofing/Repudiation | independent release gate | high | mitigate | Executor cannot write verification; verifier binds exact executor/source commits and writes explicit passed/gaps_found frontmatter. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Stable hardened recoverable observable primary on minimal translated edge | 05D/05D2/05E/05F/06 | COVERED | Edge/backend, binding/CLI, authority, live transaction, independent gate and closeout are serial. |
| REQ | SRV-02 | Rootless hardened runtime and aggregate limits | 05D/05D2/05F | COVERED | Contracts/factory/source scope plus live effective readback. |
| REQ | SRV-03 | Public 34099-34101 mapping, internal native listeners and exhaustive direct-public negatives | 05D/05D2/05F | COVERED | Exact translated allowset, bound consumers and live direct-public deny proof. |
| REQ | SRV-04 | Three DNS-only A hostnames with external IP/hostname TCP+UDP proof | 05D/05D2/05E/05F | COVERED | Read-only previews, IP-before-DNS, DNS-last and all-hostname proof for 137.131.140.20. |
| REQ | SRV-06 | Three restarts and one boot preserve invariants | 05D2/05F/06 | COVERED | Full state machine and current live cycles. |
| REQ | OPS-01 | Separate authenticated/redacted API and metrics | 05D/05D2/05F | COVERED | No Pro/API Server semantics or TCP 21114. |
| RESEARCH | Runtime/edge/API/rollback | Exact sockets, cgroups, DNS-last, two origins, rollback | 05D/05D2/05E/05F | COVERED | No researched in-scope feature omitted; current external mapping comes from D-05/D-06. |
| CONTEXT | D-01..D-15 | Rootless, isolation, edge, API, lifecycle and rollback decisions | 05D/05D2/05E/05F/06 | COVERED | Each locked decision is implemented without scope reduction. |
| CONTEXT | Deferred | Client install, standby/DR and fleet rollout | excluded | EXCLUDED | Explicitly assigned to later phases. |
| REVISION | D-05D/05D2 | Edge/backend split, source binding, authority/apply, placement, approval, proof | 05D/05D2/05E/05F | COVERED | Every checker blocker/warning has a serial owner. |

No source item is missing.

<verification>
- Apply uses the exact literal command and only a new process can construct the apply backend.
- The full evidence set proves source/authority/currentness, public edge/API/lifecycle, immutable rollback and distinct restore.
- Independent verifier ownership, evidence-only live commit, summary-only descendant and 53-06 hard gate prevent executor self-release or circular commit identity.
</verification>

<success_criteria>
1. New-process preflight rejects any approval/source/prestate/confirmation drift before side effects.
2. Exactly one full transaction produces current Phase 53 runtime/edge/API/lifecycle proof.
3. Rollback remains immutable and restore-production is a distinct transaction/journal.
4. All scope fences, secrets, CPU guardrails, fallbacks and reserved resources remain intact.
5. The evidence-only `live_executor_commit` and summary-only descendant contain no self-hash; an independent verifier, not the executor, validates both and creates 53-05F-VERIFICATION.md in a later descendant.
</success_criteria>

<output>Create an evidence-only `live_executor_commit`, then a direct summary-only descendant containing `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05F-SUMMARY.md`, and stop for independent verification. Do not create 53-05F-VERIFICATION.md or execute 53-06.</output>
