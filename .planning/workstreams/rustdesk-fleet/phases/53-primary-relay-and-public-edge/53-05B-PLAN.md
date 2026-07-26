---
phase: 53-primary-relay-and-public-edge
plan: 05B
type: execute
wave: 5
depends_on: [53-05A]
gap_closure: true
supersedes: [53-05]
execution_owner: 53-05B
files_modified:
  - modules/rustdesk-fleet/tools/phase53-production-adapters.py
  - modules/rustdesk-fleet/tools/run-phase53-live-gate.py
  - modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - modules/rustdesk-fleet/contracts/phase53-candidate-admission.json
  - modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
  - modules/rustdesk-fleet/contracts/phase53-runtime-candidate.json
  - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
  - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container
  - modules/rustdesk-fleet/tools/install-phase53-server.py
  - modules/rustdesk-fleet/tools/rustdesk-ops-api.py
  - modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
  - modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json
  - modules/rustdesk-fleet/evidence/phase53/compatibility-pending.json
  - modules/rustdesk-fleet/evidence/phase53/capacity-current.json
  - modules/rustdesk-fleet/evidence/phase53/contract-parity.json
  - modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
  - modules/rustdesk-fleet/evidence/phase53/edge-probes.json
  - modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
autonomous: true
requirements: [SCP-04, SRV-02, SRV-03, SRV-04, OPS-01]
must_haves:
  truths:
    - "The candidate state machine makes unsigned provenance, owner exception or signed rebuild observable and cannot transition to ADMITTED_PHASE53 without every current supply, compatibility, parity, capacity, recovery and approval gate."
    - "The production adapter bundle is explicit, bounded and testable; it never infers SSH aliases, ambient credentials, provider commands or target hosts from PATH or shell state."
    - "The live runner executes one ordered transaction with pre-state, containment-first rollback, external IP proof before DNS-last, hostname proof after DNS, and separate authenticated ops API proof; any missing gate blocks before mutation."
    - "The current evidence set distinguishes historical Phase 52 1.1.15 facts from successor 1.1.16 observations and stores no secrets, raw probe payloads or stored PASS verdicts."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-candidate-admission.json
      provides: "Machine-readable provenance, compatibility, currentness and owner-admission contract."
    - path: modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
      provides: "Named host/provider routes and bounded command classes without credentials."
    - path: modules/rustdesk-fleet/tools/phase53-production-adapters.py
      provides: "Explicit production adapter bundle with injectable fakes and fail-closed construction."
    - path: modules/rustdesk-fleet/evidence/phase53/candidate-admission.json
      provides: "Current metadata-only admission state; NOT_ADMITTED until owner-bound gates pass."
    - path: modules/rustdesk-fleet/evidence/phase53/capacity-current.json
      provides: "Fresh serial capacity/finalize chain with predecessor NO-GO receipts."
    - path: modules/rustdesk-fleet/evidence/phase53/compatibility-pending.json
      provides: "Value-free client 1.4.9 Linux ARM64/Windows x86-64 compatibility matrix."
    - path: modules/rustdesk-fleet/evidence/phase53/contract-parity.json
      provides: "Current source/contract/consumer digest parity map."
    - path: modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
      provides: "One ordered runtime/edge transaction and terminal rollback receipt."
    - path: modules/rustdesk-fleet/evidence/phase53/edge-probes.json
      provides: "Two-origin IP/hostname TCP+UDP and negative listener proof."
    - path: modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
      provides: "Separate authenticated/redacted ops API and vhost regression proof."
    - path: modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
      provides: "Strict value-free validator for current Phase 53 evidence and terminal BLOCKED state."
    - path: modules/rustdesk-fleet/contracts/phase53-runtime-candidate.json
      provides: "Admission-bound 1.1.16 runtime/Quadlet/ops digest contract, distinct from frozen Phase 52 1.1.15 inputs."
  key_links:
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/tools/phase53-production-adapters.py
      via: "ADMITTED_PHASE53 and explicit provider manifest gate"
      pattern: "build_production_adapters"
    - from: modules/rustdesk-fleet/tools/phase53-production-adapters.py
      to: modules/rustdesk-fleet/tools/install-phase53-server.py
      via: "bounded closed-runtime transaction and rollback"
      pattern: "install_closed"
    - from: modules/rustdesk-fleet/tools/phase53-production-adapters.py
      to: modules/rustdesk-fleet/tools/apply-phase53-edge.py
      via: "CAS host/OCI/DNS-last transaction"
      pattern: "EdgeTransaction"
    - from: modules/rustdesk-fleet/tools/phase53-production-adapters.py
      to: modules/rustdesk-fleet/tools/probe-phase53-edge.py
      via: "W11 private-first and independent-origin metadata-only probes"
      pattern: "run_windows_private_first"
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json
      via: "value-free ordered receipt journal"
      pattern: "deploy-transaction"
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/evidence/phase53/edge-probes.json
      via: "IP-before-DNS edge proof"
      pattern: "edge-probes"
    - from: modules/rustdesk-fleet/tools/run-phase53-live-gate.py
      to: modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json
      via: "final authenticated ops API/report receipt"
      pattern: "ops-api"
    - from: modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
      to: modules/rustdesk-fleet/evidence/phase53
      via: "strict current evidence and no-secret/no-stored-verdict scan"
      pattern: "NOT_ADMITTED|BLOCKED"
  prohibitions:
    - "Do not rewrite Phase 52 contracts, manifests, evidence, summaries or validator baselines pinned to 1.1.15."
    - "Do not treat an unsigned 1.1.16 tag as admitted; require a signed rebuild or an expiring Giovanni owner exception with risk disposition."
    - "Do not perform cleanup on srv2/srv3, install clients, publish DNS, mutate OCI/firewall/Apache, hydrate Vault or start RustDesk without current ADMITTED_PHASE53 authority."
    - "Do not use a WAN retry to manufacture PASS after a functional probe failure; preserve the failure and containment state."

---

<objective>Fechar o gap do Plan 53-05 com adapters production-bound, admissão successor 1.1.16 e uma transação live auditável, sem transformar evidência histórica em autorização.</objective>

<scope_note>O plano mantém quatro tasks porque o quarto é um checkpoint serial obrigatório de supply/capacity/evidence/verification após os três blocos de implementação; ele não inicia mutação independente e permanece bloqueado sem autoridade atual.</scope_note>

<execution_context>
@$HOME/.codex/gsd-core/workflows/execute-plan.md
@$HOME/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@53-05B-CONTEXT.md
@53-05B-RESEARCH.md
@53-05A-SUMMARY.md
@53-05-PLAN.md
@modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json
@modules/rustdesk-fleet/tools/run-phase53-live-gate.py
@modules/rustdesk-fleet/tools/install-phase53-server.py
@modules/rustdesk-fleet/tools/apply-phase53-edge.py
@modules/rustdesk-fleet/tools/probe-phase53-edge.py
@modules/rustdesk-fleet/tools/rustdesk-ops-api.py
@modules/rustdesk-fleet/AGENTS.md
</context>

## Tasks

<task type="auto">
  <name>Task 53-05B-01: Implementar contrato de candidate admission e parity</name>
  <files>modules/rustdesk-fleet/contracts/phase53-candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/candidate-admission.json, modules/rustdesk-fleet/evidence/phase53/server-1.1.16-evaluation.json, modules/rustdesk-fleet/evidence/phase53/compatibility-pending.json, modules/rustdesk-fleet/evidence/phase53/contract-parity.json, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>Adicionar schema strict para `UNSIGNED -> OWNER_EXCEPTION_PENDING -> OWNER_EXCEPTION_APPROVED` ou `UNSIGNED -> SIGNED_REBUILD_PENDING -> SIGNED_REBUILD_VERIFIED`, seguido de supply fresh, compatibilidade client 1.4.9, parity e pre-state/rollback. Registrar no estado atual `NOT_ADMITTED`/`PROVENANCE_BLOCKED` com assinatura false, hashes exatos do candidato, `owner=Giovanni Muniz`, `approval_ref`, `expires_at`, vulnerability disposition e aprovação ausente. Re-resolver official release/tag/OCI/ZIP, baixar/verificar bytes somente no fluxo live autorizado e registrar path/size/arch/checksum/digest em receipt value-free; sem tocar nos freezes Phase 52. A compatibilidade deve cobrir explicitamente Linux ARM64 e Windows x86-64 (versão 1.4.9, hashes DEB/MSI), direct-first, forced-relay, reconnect, mesma public key/db, UDP 21116/reflection-negative, portas negativas e proibição de Client API Server; permanecer PENDING sem client install até gate live autorizado.</action>
  <verify><automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'candidate or provenance or compatibility or parity or supply' --disable-warnings</automated></verify>
  <done>Candidate state remains `NOT_ADMITTED` unless provenance, fresh supply, compatibility, parity, pre-state and owner-bound approval are all current; every mismatch has a deterministic BLOCKED test and no Phase 52 file changes.</done>
</task>

<task type="auto">
  <name>Task 53-05B-02: Construir provider manifest e adapters explícitos</name>
  <files>modules/rustdesk-fleet/contracts/phase53-provider-manifest.json, modules/rustdesk-fleet/tools/phase53-production-adapters.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>Implementar bundle typed/injetável para SSH privado→fallback público, dispatcher Vault já aprovado, OCI read/write CAS, Cloudflare DNS snapshot/apply/restore, Apache/ops API transaction, Phase53ServerTransaction, EdgeTransaction e probes W11/independent origin. Cada provider recebe alvo e argv allowlisted do manifest, limites de tempo/output e redaction; não lê PATH/SSH config/segredos ambient. Incluir `phase53-candidate-admission.json`, `phase53-provider-manifest.json` e `phase53-runtime-candidate.json` nos digests de `load_current_contracts`/preflight; exigir clean-tree ou digest explícito de todos os arquivos fonte relevantes. A construção exige `ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1`, `ADMITTED_PHASE53=1`, candidate admission PASS, source/contract/provider/runtime digests atuais, pre-state e rollback readiness. Fakes exercitam cada fronteira e fault path sem rede.</action>
  <verify><automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'adapter or provider or ssh or vault or oci or dns or apache or containment' --disable-warnings</automated></verify>
  <done>Provider construction succeeds only with named manifest routes, current candidate/provider/runtime digests and both live/admission flags; fake fault matrix proves no ambient command or secret crosses the adapter boundary.</done>
</task>

<task type="auto">
  <name>Task 53-05B-03: Integrar transação ordenada e evidence journal</name>
  <files>modules/rustdesk-fleet/tools/run-phase53-live-gate.py, modules/rustdesk-fleet/tools/phase53-production-adapters.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <action>Integrar adapters nas etapas `deploy_closed`, `edge-probes`, `ops-api`, `publish_dns`, `hostname_probes`, `report` e `contain_on_failure`. Reforçar uma única sequência admission/pre-state/closed runtime+ops/host+OCI/IP probes/DNS-last/hostname/final authenticated ops API/report, sem executar etapa posterior ou uma segunda CLI para fabricar PASS. Mover a abertura do journal para depois de ambos flags, admission e provider/runtime contract checks; o CLI sem esses gates deve retornar BLOCKED sem criar journal/provider. Atualizar o installer/Quadlets/ops API para consumir `phase53-runtime-candidate.json` quando ADMITTED, sem reescrever os contratos históricos Phase 52; o runtime efetivo deve provar digest 1.1.16 (ou a exceção owner-bound) antes do primeiro write. Após qualquer mutação, executar containment e rollback sem sobrescrever drift concorrente; persistir deploy/edge/ops receipts somente como digests e metadados.</action>
  <verify><automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'live_gate or edge_probes or ops_api or dns or hostname or report or rollback or fault' --disable-warnings</automated></verify>
  <done>One transaction has ordered receipts through final report; any fault reaches containment/rollback or explicit terminal blocked state, and no DNS/API/public mutation occurs before the preceding proof. Missing admission/provider/runtime gates produce no journal and no provider call.</done>
</task>

<task type="auto">
  <name>Task 53-05B-04: Revalidar supply/capacity, executar gate e fechar evidência</name>
  <files>modules/rustdesk-fleet/evidence/phase53/capacity-current.json, modules/rustdesk-fleet/evidence/phase53/contract-parity.json, modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json, modules/rustdesk-fleet/evidence/phase53/edge-probes.json, modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json, modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05B-SUMMARY.md, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05B-VERIFICATION.md</files>
  <action>Executar somente após os testes herméticos: re-resolver official release/OCI/ZIP bytes e signature status, verificar cache path/size/arch/checksum e input digests; depois rodar duas amostras read-only na cadeia srv2→srv3→Horistic, `capacity_finalize` atual, security/recovery/backups e pre-state. Persistir cada predecessor NO-GO antes de tentar o próximo; preservar srv2/srv3 zero-cleanup. Client matrix deve incluir explicitamente Linux ARM64 e Windows x86-64 com os hashes 1.4.9 e no-install invariant. Sem signed rebuild ou aprovação formal owner-bound contendo Giovanni, hashes exatos, risco, disposição de vulnerabilidade e expiração, manter `NOT_ADMITTED` e não executar o comando live. Se ADMITTED for criado com hashes, executar uma única transação sob `omni srv1-ops resources run builds`, registrar ambas as rotas SSH W11 antes de classificar indisponibilidade, e nunca tentar WAN para converter falha funcional em PASS. Ao final rodar `git diff --check`, secret scan, receipt validator, Graphify status/query e suíte completa; produzir summary/verification honesto e atualizar Obsidian/GBrain só com paths/status/digests.</action>
  <verify><automated>omni srv1-ops resources run builds -- bash -lc 'if [ "${ADMITTED_PHASE53:-0}" = 1 ]; then ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage edge-probes; else env ATIUS_RUN_RUSTDESK_PHASE53_LIVE=1 python3 modules/rustdesk-fleet/tools/run-phase53-live-gate.py --stage edge-probes | tee /tmp/phase53-05b-blocked.json; test "$(python3 -c "import json;print(json.load(open(\"/tmp/phase53-05b-blocked.json\"))[\"status\"])" )" = BLOCKED; fi; python3 modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py --repo . --json; bash scripts/gsd-wave-regression.sh'</automated></verify>
  <done>Fresh supply/capacity/pre-state/evidence are either all current and owner-admitted with one verified transaction, or the artifacts explicitly remain BLOCKED/NOT_ADMITTED; `validate_phase53_live_evidence.py` rejects stale, secret-bearing or stored-PASS evidence; summary, verification, Obsidian and GBrain never claim PASS from stale/metadata-only input.</done>
</task>

## Threat model

| Threat | Severity | Mitigation |
|---|---|---|
| Unsigned/vulnerable candidate promoted by digest-only evidence | critical | Explicit provenance state machine, owner exception or signed rebuild, fresh source/cache and compatibility gates |
| Ambient SSH/Vault/provider command reaches the wrong host | critical | Provider manifest with allowlisted targets/argv, bounded wrappers, private-first fallback evidence and no ambient inference |
| Partial runtime/edge/DNS/Apache mutation | critical | Exact pre-state, CAS, containment-first rollback, value-free journal and terminal blocked state |
| False external PASS or secret/payload leak | high | Two-origin probes, no WAN retry after functional failure, strict receipt/redaction scans |
| Capacity or rollback drift after historical PASS | high | Current two-sample capacity-finalize/security/recovery gate and zero-cleanup policy |

<verification>Every task runs its narrow test first under the builds governor; the full suite and Graphify freshness are required before any live command. A missing owner-bound admission or current capacity gate is a successful safety block, not a failed test to hide.</verification>

<success_criteria>Plan 53-05 is complete only when current live evidence proves SRV-02/03/04 and OPS-01 or the transaction reaches explicit terminal containment with no unverified PASS; Phase 54 remains blocked until the independent verifier accepts all current evidence.</success_criteria>

<output>Create `53-05B-SUMMARY.md` and `53-05B-VERIFICATION.md`; do not mark Plan 53-05 or Phase 53 complete from metadata-only evidence.</output>
