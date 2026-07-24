---
phase: 54
slug: migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-24
---

# Phase 54 — Validation Strategy

## Test infrastructure

| Property | Value |
|---|---|
| Framework | Existing pytest + standard-library gate runner + live read-only adapters |
| Quick run | `python3 -m pytest modules/fleet-control-plane/tests/test_phase54_network_gate.py -q -x` |
| Syntax | `python3 -m py_compile modules/fleet-control-plane/scripts/phase54_network_gate.py` |
| Heavy suite | `omni srv1-ops resources run builds -- python3 -m pytest modules/fleet-control-plane/tests -q` |
| CPU limit | Existing `builds` profile, at most 20% total host CPU |

## Per-plan Nyquist map

| Plan | Requirement focus | Automated proof |
|---|---|---|
| 54-01 | NET-11 | focused pytest rejects forged PASS, missing check, partial write, BLOCKED/UNKNOWN, stale approval and tampered hash |
| 54-02 | NET-01,03 | gate validates live inventory, backup/restore, OCID binding and baseline |
| 54-03 | NET-02,04,09 | gate validates external builder commit/receipt and deterministic VCN branch |
| 54-04 | NET-02,05 | gate validates target network plus route/security ida/retorno |
| 54-05 | NET-03,04 | gate validates VNIC/host/K3s/public-IP async state and reverse transaction |
| 54-06 | NET-04,08,09 | gate validates DNS authority/resolvers/services/rollback |
| 54-07 | NET-06,07 | gate validates exact hub/BE3 map and S23 unchanged |
| 54-08 | NET-06,07,08 | gate validates device receipts, handshakes and dual SSH paths |
| 54-09 | NET-10 | gate validates two readings, interval and retirement approval lineage |
| 54-10 | NET-01..11 | final gate aggregates predecessor hashes and proves zero operational 10.21 |

## Fixture matrix required in Wave 0

- valid complete evidence -> PASS;
- evidence claims PASS but omits required probe -> BLOCK;
- required probe UNKNOWN, timeout or non-zero -> BLOCK;
- input says BLOCKED -> canonical BLOCK;
- wrong plan ID, stale timestamp, expired approval or changed input hash -> BLOCK;
- public IP same address but different OCID/private binding -> BLOCK;
- builder includes any target `10.21.*`, misses a 10.31 literal or lacks validated commit -> BLOCK;
- S23 `.9` rollback/migration, wrong MAC or S20 old target -> BLOCK;
- final evidence retains active 10.21 route/DNS/VNIC/private/subnet/VCN -> BLOCK.

## Sign-off

- [ ] All task verifications are automated and complete in under 60 seconds unless they are bounded live probes.
- [ ] No wave advances on WARN/BLOCK/UNKNOWN.
- [ ] Heavy suite uses the CPU guard wrapper.
- [ ] `nyquist_compliant: true` and `wave_0_complete: true` are set only after Plan 01 tests pass.
