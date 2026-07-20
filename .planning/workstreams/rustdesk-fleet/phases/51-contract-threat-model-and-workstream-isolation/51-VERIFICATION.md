---
phase: 51-contract-threat-model-and-workstream-isolation
verified: 2026-07-20T08:27:04Z
status: passed
score: 15/15 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 13/15
  gaps_closed:
    - "P51-LEDGER-001 agora exige evidence file existente e confere sha256/input_digest contra os bytes reais."
    - "51-SECURITY.md agora projeta o sign-off final aprovado e sanitizado."
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "Instalar o cliente RustDesk no GIOVANNI-W11-PC para acessar os servidores Atius."
    addressed_in: "Phase 54"
    evidence: "ROADMAP Phase 54, dependente da Phase 53 e indiretamente da Phase 52, exige MSI x86-64 1.4.9 verificado, serviço/config/ID estáveis e provas Windows de logon, UAC e reboot. O cliente permanece não instalado e não é achievement da Phase 51."
---

# Phase 51: Contract, Threat Model and Workstream Isolation — Re-verification

**Phase Goal:** O operador possui um contrato testável e sem ambiguidade para escopo, edição GSD, OSS/Pro, direct/relay, secrets, permissions e preservação dos acessos existentes.

**Status:** `passed`

**Re-verification:** Sim — os dois gaps da verificação inicial foram reabertos, corrigidos e testados; itens anteriormente aprovados receberam regression check.

## Resultado executivo

Os dois blockers fecharam. O ledger agora rejeita evidência ausente e digest incorreto mesmo quando o valor possui formato SHA-256 válido. A projeção `51-SECURITY.md` agora concorda com a operational review e registra o sign-off accountable sem valores secretos. A suíte passou com 78 testes, a execução atual do validator retornou exatamente 11/11 checks `PASS`, e source pin, report currentness, Markdown parity, Phase 48 e secret hygiene permaneceram verdes.

O refresh governado do Graphify foi executado no HEAD `b11b32b6a474cda445a0518378465e542a951f75` sob `omni-builds.slice` com `CPUQuota=80%` no host de quatro vCPUs. A extração terminou 774/774, `structural_ok=true`, `last_build_auto_update.status=ok` e `head_at_build` igual ao HEAD. Como não houve mudança topológica, o Graphify deixou os outputs intactos e preservou o `built_at_commit` embutido anterior; isso é um refresh válido no HEAD, não drift pendente.

## Gap Closure

### 1. Ledger evidence currentness — CLOSED

`validate_ledger` agora:

- resolve somente paths repo-relative permitidos;
- exige que o evidence target seja arquivo regular existente;
- calcula o SHA-256 dos bytes reais;
- exige que `sha256` e `input_digest` sejam iguais ao digest real;
- retorna `evidence-file-missing` ou `evidence-digest-mismatch` em vez de PASS.

Os dois casos adversariais da verificação inicial agora são negative tests explícitos: missing in-scope path e valid-shaped wrong digest. Ambos bloqueiam.

### 2. Security projection final sign-off — CLOSED

`51-SECURITY.md` agora registra:

- `status: approved`;
- aceitação accountable das seis ausências OSS;
- aprovação dos seis Vault paths sem valores;
- três checkboxes de sign-off marcados;
- aprovação por Giovanni Muniz nos timestamps já atestados.

O arquivo pertence ao signing domain atualizado; a operational review foi repinada e os reports foram regenerados sem quebrar source ancestry/currentness.

## Goal Achievement

### Observable Truths

| # | Truth consolidada | Status | Evidência atual |
|---|---|---|---|
| 1 | Cinco hosts exatos, WSL/S23 excluídos, cinco fallbacks preservados e direct-first | VERIFIED | Scope/legacy/transport contracts e negatives; checks PASS. |
| 2 | GO/OSS somente no boundary single-operator aceito; controles centralizados obrigatórios promovem Pro | VERIFIED | Product truth table e operational review accountable. Atius ops API continua separada para Phase 53. |
| 3 | Permission profiles são desired local policy e não alegam RBAC central | VERIFIED | Matrizes exatas e negative capability test. |
| 4 | Identity/recovery e cinco password refs são distintos, aprovados e não contêm valores | VERIFIED | Seis paths exatos; value distinctness permanece Phase 52. |
| 5 | T-01..T-12, ASVS L1/V16 L2 e zero high unresolved são fail-closed | VERIFIED | Threat contract, security projection e unresolved-high negative. |
| 6 | Ledger 36/36 rejeita missing/stale/wrong-digest evidence | VERIFIED | Real file/digest enforcement e novos negative tests. |
| 7 | Cada comando GSD mutante exige `--ws rustdesk-fleet` individualmente | VERIFIED | Parser, mixed-command fixture e wrong-scope negatives. |
| 8 | Shared planning/Graphify usa writer serializado | VERIFIED | `serialized-single-writer` e cinco paths exatos. |
| 9 | Phase 48 preserva nove blobs/arquivos sem auto-rebaseline | VERIFIED | P51-P48 PASS e disposable-copy drift BLOCKED. |
| 10 | Checks são leves e não instalam/mutam runtime nem leem Vault values | VERIFIED | 78 testes em 1,05 s; hygiene scan sanitizado passou em 21 arquivos. |
| 11 | Operator/Vault owner registram decisões, timestamps, seis paths e zero high | VERIFIED | Operational review APPROVED por Giovanni Muniz. |
| 12 | Source pin é ancestral, manifest é acíclico e post-review drift é restrito | VERIFIED | Review source PASS; pin ancestral do HEAD. |
| 13 | Report contém 11 IDs únicos PASS, inputs atuais, parity e nenhum secret | VERIFIED | Validator live 11/11; stored currentness PASS; Markdown parity true; `secret_material_present=false`. |
| 14 | Transições usam scope explícito e bracket P51-WS/P51-P48 | VERIFIED | Transition contract e ambos checks PASS. |
| 15 | Security projection reflete o review/sign-off concluído | VERIFIED | `status: approved`, audit notes atuais e sign-off completo. |

**Score:** 15/15 truths verified; 0 behavior-dependent truths sem teste.

## Required Artifacts and Wiring

| Artifact group | Status | Wiring/evidência |
|---|---|---|
| Cinco contracts JSON | VERIFIED | Consumidos pelos validators e positive/negative tests. |
| `validate_phase51.py` | VERIFIED | Scope, product, permission, threat, secret, ledger, workstream, Phase 48 e report gates integrados. |
| `test_phase51_contracts.py` | VERIFIED | 78 testes PASS; inclui os três closure tests novos. |
| `phase48-baseline.json` | VERIFIED | Nove Git blobs ligados aos nove hashes atuais. |
| `ledger.json` | VERIFIED | 36/36 exact-set; quatro Phase 51 PASS com evidence files e digests reais; 32 later-phase pending. |
| Fixtures Plans 01-03 | VERIFIED | Materialization e negatives consumidos pela suíte. |
| `51-OPERATIONAL-REVIEW.md` | VERIFIED | Product/Vault/permission/threat/Phase 48 review e source manifest válidos. |
| `51-CONTRACT-VALIDATION.json` / `.md` | VERIFIED | 11/11 PASS, currentness PASS e renderer parity. |
| `51-SECURITY.md` | VERIFIED | Threat projection e sign-off final atuais. |
| `51-VALIDATION.md` | VERIFIED | Permanece separado e não foi usado como runtime report. |

## Behavioral Spot-Checks

| Check | Resultado | Status |
|---|---|---|
| `python3 -m pytest modules/rustdesk-fleet/tests/test_phase51_contracts.py -q` | 78 passed em 1,05 s | PASS |
| Validator live, sem persistir outputs | 11 checks únicos PASS, overall PASS | PASS |
| Stored report currentness | PASS | PASS |
| Stored Markdown parity | Igual ao renderer do JSON canônico | PASS |
| Review source/manifest | PASS; source pin ancestral | PASS |
| Secret hygiene | 21 arquivos, redacted reporting, PASS | PASS |
| Governed Graphify refresh | 774/774, structural_ok, status ok no HEAD; sem mudança topológica | PASS |

## Requirements Coverage

| Requirement | Status Phase 51 | Limite verificado |
|---|---|---|
| SCP-01 | SATISFIED como contrato de scope | Cinco hosts/exclusões exatos; não afirma instalação runtime. |
| SCP-02 | SATISFIED | GO/OSS accountable e Atius ops API separada. |
| SCP-03 | SATISFIED | Direct-first e forced-relay limitado. |
| SCP-05 | SATISFIED | Workstream explícito, writer serialization e Phase 48 íntegra. |

Não há requirement Phase 51 orphaned. Requirements de runtime permanecem pending em suas phases proprietárias.

## Deferred obrigatório — cliente Windows

O RustDesk **ainda não está instalado** no `GIOVANNI-W11-PC`. Isso não foi entregue nem reivindicado pela Phase 51. O ROADMAP atribui obrigatoriamente essa instalação à **Phase 54 — Heterogeneous Canary**, depois dos gates da Phase 52 e da Phase 53. A Phase 54 deve instalar o MSI x86-64 1.4.9 verificado e provar serviço, config, ID, rollback, logon screen, UAC secure desktop e reconnect após reboot.

Esse deferimento não reduz o PASS da Phase 51, cujo goal era o contrato/governance gate; também não autoriza pular a instalação ou antecipá-la antes dos prerequisites.

## Gaps Summary

Nenhum gap permanece. Nenhuma regressão foi encontrada nos 13 must-haves previamente aprovados.

---

_Re-verified: 2026-07-20T08:27:04Z_
_Verifier: Codex (gsd-verifier fallback)_
