---
phase: 53-primary-relay-and-public-edge
plan: 05D
type: execute
wave: 7
depends_on: [53-05C]
gap_closure: true
execution_owner: 53-05D
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-edge.json
  - modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
  - modules/rustdesk-fleet/tools/phase53-live-backend.py
  - modules/rustdesk-fleet/tools/apply-phase53-edge.py
  - modules/rustdesk-fleet/tools/probe-phase53-edge.py
  - modules/rustdesk-fleet/tools/install-phase53-server.py
  - modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  - .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-05/D-06, phase53-edge.json is the sole machine-readable authority for 137.131.140.20, the three DNS-only A hostnames, external 34099/34100/34101 translation and internal native 21115/21116/21117 listeners."
    - "The hbbs Quadlet announces exactly rustdesk-relay.atius.com.br:34101, derived and asserted against phase53-edge.json, and install-phase53-server.py validates and materializes that exact command in the runtime-installed unit while native internal listener ports remain unchanged."
    - "Read-only and apply backend types are capability-disjoint; a read-only caller cannot obtain RuntimeProvider, ProviderBundle, mutation, containment, rollback or restore callbacks."
    - "No authority, owner approval, OperationPlan, live evidence or infrastructure mutation occurs in this plan."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-edge.json
      provides: "Strict sole authority for translated edge, internal listeners, public negatives, reserved IP and three DNS-only A records."
    - path: modules/rustdesk-fleet/tools/phase53-live-backend.py
      provides: "Typed read-only/apply capability boundary consumed by the CLI plan in 53-05D2."
      exports: ["ExecutionMode", "Phase53Stage", "ExecutionSourceBinding", "ReadOnlyProviderBundle", "ApplyProviderBundle", "build_phase53_read_only_backend", "build_phase53_apply_backend"]
    - path: modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
      provides: "Rootless digest-pinned hbbs command that announces the translated public relay endpoint."
      contains: "rustdesk-relay.atius.com.br:34101"
    - path: modules/rustdesk-fleet/tools/install-phase53-server.py
      provides: "Canonical server installer that derives the public relay announcement from phase53-edge.json, validates the source Quadlet and installs an equivalent runtime unit."
      contains: "phase53-edge.json"
  key_links:
    - from: modules/rustdesk-fleet/contracts/phase53-edge.json
      to: modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
      via: "test derives relay hostname and external relay port from the contract and asserts the exact hbbs announcement"
      pattern: "rustdesk-relay\\.atius\\.com\\.br:34101"
    - from: modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
      to: modules/rustdesk-fleet/tools/install-phase53-server.py
      via: "installer validates the contract-derived hbbs command before materializing the runtime-installed Quadlet and rejects source/runtime tamper or endpoint mismatch"
      pattern: "install-phase53-server\\.py"
    - from: modules/rustdesk-fleet/contracts/phase53-edge.json
      to: modules/rustdesk-fleet/tools/apply-phase53-edge.py
      via: "apply and probe helpers load the same translations, records and public negatives"
      pattern: "phase53-edge\\.json"
    - from: modules/rustdesk-fleet/tools/phase53-live-backend.py
      to: modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
      via: "typed factories validate the provider manifest before exposing capabilities"
      pattern: "ReadOnlyProviderBundle|ApplyProviderBundle"
  prohibitions:
    - "Do not create phase53-execution-source-scope.json or capture execution_source_commit here; 53-05D2 owns the final source binding."
    - "Do not write authority, evidence or live receipts and do not contact hosts, OCI, Cloudflare, Apache, DNS or Vault."
    - "Do not expose native 21114-21119 directly on the public edge."
    - "Do not mutate Phase 52, srv2/srv3, Phase 54 or 10.31.1.31."
---

<objective>
Implementar a autoridade hermética de edge/backend per D-01..D-06 e D-09..D-12, mantendo a superfície pública traduzida e o runtime nativo interno sem executar authority ou live work.

Purpose: reduzir o antigo 05D a um slice de no máximo nove arquivos que estabiliza edge, Quadlet, instalação canônica e capability boundary antes do binding/CLI final.
Output: edge/provider contracts, backend types, edge consumers, Quadlet hbbs, installer canônico e testes herméticos.
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
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-RESEARCH.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05C-VERIFICATION.md
@modules/rustdesk-fleet/contracts/phase53-edge.json
@modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
@modules/rustdesk-fleet/tools/apply-phase53-edge.py
@modules/rustdesk-fleet/tools/probe-phase53-edge.py
@modules/rustdesk-fleet/tools/install-phase53-server.py
@modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container
@modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
</context>

<interfaces>
- `ExecutionMode = Literal["plan", "apply"]`
- `Phase53Stage = Literal["full", "edge-probes", "ops-api", "lifecycle", "rollback", "restore-production"]`
- `ExecutionSourceBinding(commit: str, tree_sha256: str, blobs: Mapping[str, str])`
- `ReadOnlyProviderBundle(read_prestate, preview_oci, preview_cloudflare, preview_apache, capabilities=frozenset({"read", "preview"}))`
- `ApplyProviderBundle(runtime: RuntimeProvider, providers: ProviderBundle, operation_plan_sha256: str, approval_sha256: str)`
- `build_phase53_read_only_backend(*, repo: Path, manifest_path: Path, source_binding: ExecutionSourceBinding, clock: Callable[[], datetime]) -> ReadOnlyProviderBundle`
- `build_phase53_apply_backend(*, repo: Path, manifest_path: Path, operation_plan: Mapping[str, Any], owner_approval: Mapping[str, Any], live_enabled: bool, admitted: bool, clock: Callable[[], datetime]) -> ApplyProviderBundle`
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D-01: Fixar edge traduzido e anúncio público do hbbs</name>
  <files>modules/rustdesk-fleet/contracts/phase53-edge.json, modules/rustdesk-fleet/contracts/phase53-provider-manifest.json, modules/rustdesk-fleet/tools/apply-phase53-edge.py, modules/rustdesk-fleet/tools/probe-phase53-edge.py, modules/rustdesk-fleet/tools/install-phase53-server.py, modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <behavior>
    - "The contract accepts exactly public 34099/TCP, 34100/TCP+UDP and 34101/TCP translated to internal 21115/TCP, 21116/TCP+UDP and 21117/TCP."
    - "The contract accepts exactly rustdesk.atius.com.br, rustdesk-id.atius.com.br and rustdesk-relay.atius.com.br as DNS-only A records for 137.131.140.20 and rejects proxy, AAAA, CNAME, missing or extra records."
    - "Direct public 21114-21119 and every non-allowlisted listener are negative assertions, while the pinned upstream internal socket set remains unchanged."
    - "The hbbs command announces exactly rustdesk-relay.atius.com.br:34101; the test derives that value from the relay record and external relay translation in phase53-edge.json."
    - "install-phase53-server.py rejects a tampered source Quadlet, an endpoint mismatch and a runtime-installed command that is not byte-equivalent in effective hbbs arguments; the accepted installed form announces the contract-derived relay endpoint."
    - "Apply/probe helpers load phase53-edge.json and fail closed on a stale or duplicated edge mapping."
  </behavior>
  <action>
Escrever primeiro os testes do contrato e dos consumidores. Per D-05/D-06, tornar `phase53-edge.json` a única authority para target `10.21.1.21`, reserved public IP `137.131.140.20`, três records A DNS-only, tradução externa 34099/34100/34101 para listeners nativos 21115/21116/21117 e negativos públicos exaustivos. `apply-phase53-edge.py` e `probe-phase53-edge.py` devem carregar e validar esse arquivo; remover constantes editáveis equivalentes dentro desses dois consumers.

Per D-01/D-02/D-03, manter o Quadlet rootless, digest-pinned, isolado e dentro do budget existente. No comando hbbs, anunciar o relay público exatamente `rustdesk-relay.atius.com.br:34101`; não anunciar `rustdesk.atius.com.br:21117`. A asserção hermética deve derivar hostname e porta pública do schema e comparar com o argumento efetivo do Quadlet. Não alterar os listeners internos nativos do container. Atualizar `phase53-provider-manifest.json` para referenciar o edge contract sem copiar seu mapping.

Atualizar o installer canônico `install-phase53-server.py` para carregar `phase53-edge.json`, derivar o relay hostname/porta externa, validar que o source Quadlet contém o comando hbbs equivalente e materializar essa forma no destino de runtime. Os testes devem exercitar source Quadlet adulterado, mismatch entre contract/Quadlet, runtime-installed unit adulterada e a forma instalada aceita; nenhum path de teste pode instalar no host real.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'edge_contract or translated_edge or hbbs_relay_announcement or phase53_server_installer or installer_tamper or runtime_installed_hbbs or apply_edge_contract or probe_edge_contract' --disable-warnings</automated>
  </verify>
  <done>Edge, Quadlet, installer e helpers compartilham uma única authority; a forma runtime-installed anuncia o relay público 34101, tamper/mismatch falham fechados e os listeners nativos internos permanecem inalterados.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D-02: Implementar capability boundary do backend</name>
  <files>modules/rustdesk-fleet/contracts/phase53-provider-manifest.json, modules/rustdesk-fleet/tools/phase53-live-backend.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py, .planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md</files>
  <behavior>
    - "ReadOnlyProviderBundle exposes only read and preview capabilities and has no conversion path to RuntimeProvider or ProviderBundle."
    - "ApplyProviderBundle construction requires live_enabled, admitted, exact current OperationPlan and unexpired owner approval."
    - "The provider manifest rejects an unknown backend, mutable authority paths, unbounded commands and any execution target other than 10.21.1.21."
  </behavior>
  <action>
Implementar em `phase53-live-backend.py` os exports e signatures do bloco `interfaces`. Per D-04/D-09/D-10/D-11/D-12, usar resultados tipados, bounded e value-free; manter Vault somente como reference/fingerprint e a ATIUS ops API separada do RustDesk Pro/API Server. A factory read-only não deve conter callbacks de mutation, containment, rollback ou restore. A factory apply valida os gates mas não é construída/executada neste plano.

Registrar em `53-05D-SUMMARY.md` somente os artifacts/test selectors, incluindo a cadeia edge contract → hbbs Quadlet → installer/runtime-installed unit, e o handoff de execução para 05D2; não registrar `execution_source_commit`, pois o próximo plano ainda modifica code/contracts/tests.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'read_only_backend or apply_backend or provider_manifest' --disable-warnings</automated>
    <automated>git diff --check</automated>
  </verify>
  <done>Backend factories estão hermeticamente definidos, sem authority/evidence/live writes e sem source commit prematuro.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53D-EDGE | Tampering | translated edge contract | critical | mitigate | Sole strict schema plus consumer tests reject a second authority, stale mapping, extra records and public native-port exposure per D-05/D-06. |
| T53D-RELAY | Spoofing/Tampering | hbbs relay announcement | critical | mitigate | Test derives `rustdesk-relay.atius.com.br:34101` from the edge contract and compares it with the Quadlet command. |
| T53D-CAPABILITY | Elevation of Privilege | backend factories | critical | mitigate | Separate exported types; read-only bundle has no apply/rollback/restore members or conversion path. |
| T53D-SECRET | Information Disclosure | provider results | high | mitigate | Value-free typed results, Vault reference/fingerprint only and bounded output. |
| T53D-INSTALL | Tampering | canonical server installer and runtime-installed Quadlet | critical | mitigate | Contract-derived command validation plus hermetic source/runtime tamper and endpoint-mismatch tests. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status | Notes |
|---|---|---|---|---|---|
| GOAL | Phase 53 | Hardened recoverable observable primary on the approved translated edge | 05D/05D2/05E/05F/06 | COVERED | 05D owns edge/backend; serial successors own binding, authority, live proof and closeout. |
| REQ | SRV-02 | Rootless hardened runtime and aggregate limits | 05D | COVERED | Quadlet/installer/provider boundary preserves digest, isolation, command and resource contracts. |
| REQ | SRV-03 | External 34099-34101 translation and direct-public negatives | 05D | COVERED | Sole edge schema and scoped consumers enforce the mapping. |
| REQ | SRV-04 | Three DNS-only A records and external proof | 05D/05F | COVERED | Contract here; live proof in 05F. |
| REQ | SRV-06 | Restart/boot persistence | 05D2/05F | COVERED | State machine and live execution are downstream. |
| REQ | OPS-01 | Separate authenticated/redacted ops API | 05D/05D2/05F | COVERED | Backend boundary preserves the separate API contract. |
| RESEARCH | Runtime/edge/API/rollback | Current authority plus historical upstream constraints | 05D/05D2/05F | COVERED | D-05/D-06 and the sole edge contract supersede historical public values. |
| CONTEXT | D-01..D-06, D-09..D-12 | Runtime, identity, translated edge and ops API | 05D | COVERED | Edge contract, Quadlet, canonical installer and capability backend implement the decisions. |
| CONTEXT | D-07, D-08, D-13..D-15 | External proof, transaction, lifecycle and rollback | 05D2/05F/06 | COVERED | Serial downstream ownership. |
| CONTEXT | Deferred | Clients, fleet rollout and standby/DR | excluded | EXCLUDED | Assigned to Phases 54-57. |

No source item is missing.

<verification>
Only governed hermetic selectors and structural diff checks run. No Graphify, authority, approval, live, host or provider action is part of 05D.
</verification>

<success_criteria>
1. The plan modifies no more than nine declared files.
2. `phase53-edge.json` is the sole authority for external translation, internal listeners, records and negatives.
3. The hbbs Quadlet and the runtime-installed form produced by `install-phase53-server.py` announce exactly `rustdesk-relay.atius.com.br:34101`, derived and asserted from the edge contract, with tamper/mismatch rejected.
4. Read-only and apply capabilities are type- and behavior-separated.
5. The next plan, not 05D, captures the final execution source commit.
</success_criteria>

<output>Create `.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md` and stop. Do not dispatch 53-05D2 automatically.</output>
