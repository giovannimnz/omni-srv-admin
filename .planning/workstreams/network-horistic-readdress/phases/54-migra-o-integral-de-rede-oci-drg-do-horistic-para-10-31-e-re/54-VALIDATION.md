---
phase: 54
slug: migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-24
---

# Phase 54 — Validation Strategy

## Test infrastructure

| Property | Value |
|---|---|
| Framework | Existing pytest + standard-library gate runner + live read-only adapters |
| Quick run | `TMPDIR=/var/tmp/phase54-pytest-codex python3 -m pytest -q modules/fleet-control-plane/tests/test_phase54_network_gate.py` |
| Adapter run | `TMPDIR=/var/tmp/phase54-pytest-codex python3 -m pytest -q modules/fleet-control-plane/tests/test_phase54_probe_adapters.py` |
| Syntax | `python3 -m py_compile modules/fleet-control-plane/scripts/phase54_network_gate.py modules/fleet-control-plane/scripts/phase54_probe_adapters.py` |
| Heavy suite | `omni srv1-ops resources run builds -- python3 -m pytest modules/fleet-control-plane/tests -q` |
| CPU limit | Existing `builds` profile, at most 20% total host CPU |

### Bounded local matrix

Every local Wave 0 subset uses
`TMPDIR=/var/tmp/phase54-pytest-codex python3 -m pytest -q modules/fleet-control-plane/tests/test_phase54_network_gate.py -k '<selector>'`.
The 2026-07-26 independent final planning-gate certification used `-s` after the
WSL pytest capture backend failed closed before collection. The combined current
runner and adapter suites completed as follows:

| Selector | Result | Elapsed |
|---|---:|---:|
| complete runner + adapter suites | 136 passed (107 + 29) | 30.62 s |
| `probe_registry or physical_owner_adapter or adapter_coverage or real_local_probe or run_fixed_argv or bootstrap_uses_content_pin or successors_require` | 12 passed | 2.67 s |
| `check_inputs or injection_payloads or manually_fabricated` | 14 passed | 0.58 s |
| `predecessor_wrong or predecessor_depth or assert_gate` | 10 passed | 20.12 s |
| `backup or builder` | 7 passed | 26.10 s |
| `expired_approval or strict_operation or tampered_operation or non_literal_approval or raw_operation or sync_requires_hash_bound` | 6 passed | 14.33 s |
| `public_ip and not exact_54_05_anchor` | 4 passed | 6.93 s |
| `exact_54_05_anchor` | 5 passed | 11.11 s |
| `legacy or stale_evidence or tampered_artifact or unredacted or wrong_evidence or unknown_stage or plan_contract` | 7 passed | 9.46 s |
| `review_gate or plan_contract or probe_registry or physical_owner_adapter_coverage` | 14 passed | 7.75 s |
| `stage_contracts_cover_backup_device_retirement_and_read_only_sync` | 1 passed | 91.21 s |
| `s23 or s20 or final_operational or production_write_signal` | 5 passed | 20.33 s |

## Per-plan Nyquist map

| Plan | Requirement focus | Automated proof |
|---|---|---|
| 54-01 | NET-11 | focused pytest rejects forged PASS, missing check, partial write, BLOCKED/UNKNOWN, stale approval and tampered hash |
| 54-02 | NET-01,03 | first command validates independent fresh zero-finding review of the exact current 14-file planning scope; then gate validates fresh commit-pinned 54-01, exact public binding `10.0.0.65` with OCID chain distinct from secondary `10.21.1.21`, required hash-bound DNS baseline gap, three exact individual backup receipts and pending-write lineage |
| 54-03 | NET-02,04,09 | gate validates external builder commit/receipt and deterministic VCN branch |
| 54-04 | NET-02,05 | gate validates target network plus route/security ida/retorno |
| 54-05 | NET-03,04 | gate validates target 10.31.1.31 and private-IP/VNIC/subnet/VCN OCIDs against approved OperationPlan/readback |
| 54-06 | NET-04,08,09 | gate validates DNS authority/resolvers/services/rollback |
| 54-07 | NET-06,07 | gate validates exact hub/BE3 map and S23 unchanged |
| 54-08 | NET-06,07,08 | gate validates staged approval, device receipts, `.9` peer+AllowedIP absence receipt, defer-block semantics and S23 invariants |
| 54-09 | NET-10 | gate validates two readings, interval, retirement approval lineage and same-plan apply receipt |
| 54-10 | NET-01..11 | read-only final execution gate aggregates predecessor hashes and proves zero operational 10.21; independent gsd-verifier creates VERIFICATION afterward |

## Fixture matrix required in Wave 0

- valid complete evidence -> PASS; fabricated receipt plus real adapter BLOCK -> BLOCK;
- exact fresh `phase54.review-evidence.v1` plus bound `phase54.review-gate.v1` over all 14 current planning files -> PASS;
- review scope drift/missing/extra/unknown, malformed or extra fields, stale/expired timestamps, self-review, non-empty blockers/warnings, non-`PASS` status or evidence path/hash drift -> BLOCK;
- registry coverage exact; local probe integration real; physical owner adapters cover 54-02..10 and must pass `adapters-ready --plan 54-NN --smoke`;
- live read-only capability smoke for 54-02 covers OCI MCP, strict srv1/srv3 SSH with fixed fallback, DNS via owners and BE3 owner commit/CLI pin;
- extra adapter/argv/command/host/tool/result fields and injection payloads -> BLOCK;
- fixed subprocess proves absolute argv, `shell=false`, sanitized secret env while preserving HOME/CODEX_HOME, closed stdin and capped output;
- normalized adapter semantics must match runner-owned tuple predicates and exact canonical evidence SHA-256; semantic tamper, hash drift or secret material -> BLOCK;
- Graphify `stale=true`, `commit_stale=true` or a query without Phase 54/gate/adapter/workstream relevance -> BLOCK;
- evidence claims PASS but omits required probe -> BLOCK;
- claimed PASS with empty artifact hashes, missing provenance receipt, unknown producer/adapter or receipt/output hash drift -> BLOCK;
- required probe UNKNOWN, timeout or non-zero -> BLOCK;
- input says BLOCKED -> canonical BLOCK;
- wrong plan ID, unknown/disallowed stage, stale timestamp, expired approval or changed input hash -> BLOCK;
- any `final` call using raw OperationPlan/approval/stability/device receipt instead of `54-NN-EVIDENCE.json` -> BLOCK;
- any token other than literal `APPROVE <plan> <sha256-completo>` -> BLOCK;
- 54-02 baseline old private binding -> allowed; 54-05/10 old private binding, missing target IDs or OperationPlan/readback mismatch -> BLOCK;
- 54-02 public baseline must bind `163.176.232.119` to primary `10.0.0.65` plus exact public/private/VNIC/subnet OCIDs; wrong public OCID, wrong binding or reuse of the secondary `10.21.1.21` identity -> BLOCK;
- 54-02 DNS baseline must include `phase54.dns-baseline-gap.v1` with authority SOA/NS/NX, absent authority A/PTR, intact resolver A/PTR `10.21.1.21` and explicit partial resolver matrix; silent/missing gap, digest drift or tampered A/PTR -> BLOCK;
- 54-06+ authority/resolver probes remain strict and reject the 54-02 baseline gap;
- builder includes any target `10.21.*`, misses a 10.31 literal or lacks validated commit -> BLOCK;
- any S23 write/import/activation, S23 address other than LAN `192.168.1.10` / WG `10.100.100.10`, S23 MAC other than `64:1B:2F:C2:DC:A3`, or S20 old target after approved retirement -> BLOCK;
- missing/stale/hash-drifted predecessor commit pin, any bootstrap/null-source lineage, backup-only approval, per-plan anti-drift/rollback/apply receipt, exact 54-09 stability evidence/gate hash, 54-08 retirement approval, or 54-08 sync without hash-bound apply receipt -> BLOCK;
- SRV1/SRV3/BE3 pre-existing backup reclassified as pending write or claimed as retroactively approved -> BLOCK;
- missing/wrong-name/wrong-schema or external receipt drift in SRV1/SRV3/BE3 local receipt -> BLOCK;
- predecessor wrong stage/name/dir/hash/cycle/depth -> BLOCK; immediate stale -> BLOCK; stale commit-pinned ancestor remains valid until hash mutation;
- 54-10 arbitrary self-consistent cutover/readback or drift in any five-artifact 54-05 anchor member -> BLOCK;
- S20 `.9` peer or AllowedIP present, or `decision=defer`, at 54-08 sync -> BLOCK;
- 54-09 approval without same-plan apply receipt, or any 54-10 apply stage/write attempt -> BLOCK;
- 54-10 knowledge write after the preflight freeze, drift in the exact five-artifact semantic manifest/receipt hashes, Graphify stale/irrelevant, or sync with `mutations_attempted`, `production_mutations_attempted`, operation/apply/write receipt, apply flag or write operation -> BLOCK;
- `full_matrix` missing live normalized `operational_10_21` plus consistent `residual_live` digest, or retaining any active 10.21 route/DNS/VNIC/private/subnet/VCN -> BLOCK; an evidence-authored empty list never authorizes PASS.

## Sign-off

- [ ] All task verifications are automated and complete in under 60 seconds unless they are bounded live probes.
- [ ] No wave advances on WARN/BLOCK/UNKNOWN.
- [ ] Heavy suite uses the CPU guard wrapper.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after Plan 01 tests pass.
- [ ] `54-VERIFICATION.md` is created only by an independent gsd-verifier after `54-10-GATE.json` PASS.
