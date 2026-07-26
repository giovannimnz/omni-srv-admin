---
phase: 53-primary-relay-and-public-edge
plan: 05D2A
type: execute
wave: 9
depends_on: [53-05D2T]
gap_closure: true
execution_owner: 53-05D2A
files_modified:
  - modules/rustdesk-fleet/contracts/phase53-edge.json
  - modules/rustdesk-fleet/contracts/phase53-provider-manifest.json
  - modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
  - modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service
  - modules/rustdesk-fleet/tools/apply-phase53-edge.py
  - modules/rustdesk-fleet/tools/probe-phase53-edge.py
  - modules/rustdesk-fleet/tools/rustdesk-ops-api.py
  - modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
  - modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
autonomous: true
requirements: [SRV-02, SRV-03, SRV-04, SRV-06, OPS-01]
must_haves:
  truths:
    - "Per D-06, nftables uses prerouting DNAT/forward/return-path policy on atius-srv-1, never local redirect on Horistic."
    - "ct status dnat plus ct original proto-dst separate translated flows from direct-native public attempts."
    - "Backend native listeners accept only the proved edge return-path identity; direct public 21114-21119 remain closed."
    - "DNS snapshot, CAS apply, readback and rollback cover all three A records as one exact record set."
    - "Two origins probe the public IP plus all three hostnames; UDP 34100 reaches backend 21116; native negatives remain negative."
    - "Ops API and strict validator consume current translated-edge semantics rather than native-public constants."
    - "The complete governed RustDesk test file exits zero; fixtures are not the sole change."
  artifacts:
    - path: modules/rustdesk-fleet/contracts/phase53-edge.json
      provides: "Sole cross-host edge/backend/DNS/probe authority."
    - path: modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
      provides: "Owned DNAT/forward/return-path and direct-native deny policy."
    - path: modules/rustdesk-fleet/tools/apply-phase53-edge.py
      provides: "CAS transaction/readback/rollback for host, OCI and all DNS records."
    - path: modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
      provides: "Strict current translated-edge evidence validator."
  key_links:
    - from: modules/rustdesk-fleet/contracts/phase53-edge.json
      to: modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
      via: "rendered exact translations, backend restriction and native negatives"
      pattern: "34099|34100|34101"
    - from: modules/rustdesk-fleet/tools/probe-phase53-edge.py
      to: modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
      via: "shared two-origin x four-target receipt semantics"
      pattern: "udp.*34100|21116"
---

<objective>
Reconcile the 51 broad-suite failures at their semantic roots and implement D-06 cross-host forwarding without weakening historical safety gates.

Purpose: make contracts, nftables, transaction/probe code, ops API, validator and tests agree on the proved topology.
Output: production-bound DNAT/forward/backend/DNS semantics with a zero-exit governed broad test file.
</objective>

<execution_context>
@/home/ubuntu/.codex/gsd-core/workflows/execute-plan.md
@/home/ubuntu/.codex/gsd-core/templates/summary.md
</execution_context>

<context>
@AGENTS.md
@.planning/workstreams/rustdesk-fleet/REQUIREMENTS.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-CONTEXT.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D-SUMMARY.md
@.planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge/53-05D2T-SUMMARY.md
@modules/rustdesk-fleet/contracts/phase53-topology.json
@modules/rustdesk-fleet/contracts/phase53-ops-api.json
</context>

## Artifacts This Phase Produces

- Cross-host edge contract and owned nftables/systemd policy.
- Exact three-record DNS transaction and two-origin/four-target probes.
- Ops API/validator projections derived from the same authority.
- Updated production tests covering the 38 NFT/DNS, 8 ops API, 4 OCI and 1 validator failure clusters.

<tasks>

<task type="auto" tdd="true">
  <name>Task 53-05D2A-01: Replace local filter semantics with cross-host DNAT and exact DNS/probes</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-topology.json
    @modules/rustdesk-fleet/contracts/phase53-edge.json
    @modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft
    @modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service
    @modules/rustdesk-fleet/tools/apply-phase53-edge.py
    @modules/rustdesk-fleet/tools/probe-phase53-edge.py
    @modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-edge.json, modules/rustdesk-fleet/contracts/phase53-provider-manifest.json, modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft, modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service, modules/rustdesk-fleet/tools/apply-phase53-edge.py, modules/rustdesk-fleet/tools/probe-phase53-edge.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <behavior>
    - "Render exact prerouting DNAT mappings and forward only conntrack-confirmed translations to 10.21.1.21."
    - "Reject direct-native packets using original destination and retain IPv6 deny."
    - "Prove backend restriction/readback and deterministic return via 10.0.0.238."
    - "Apply/read back/rollback exactly three DNS-only A records under one CAS generation."
    - "Require two distinct origins against public IP and each of three names for positives/native negatives, including UDP 34100->21116."
  </behavior>
  <action>
Write failing tests first, then reshape D-06 authority around separate `public_edge` and `backend` objects. Replace the filter-input-only nft template with owned NAT prerouting, filter forward and return-path postrouting chains; validate exact hook priorities, ownership marker, contract digest, ct translation/original-destination predicates, backend address/source restriction and zero foreign-chain mutation. Update the systemd transaction to syntax-check, atomically apply, independently read back all owned chains and contain/restore on drift. Update OCI auditing for the edge VNIC rather than backend VNIC. Rewrite DNS and probe state machines so all three records form one CAS unit and every origin proves the IP and three hostnames, with TCP positives, UDP 34100 correlation to 21116 and direct-native negatives. Do not merely rewrite fixture expectations.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py -k 'nft or oci or dns or external_probe or hostname or udp or translated_edge' --disable-warnings</automated>
  </verify>
  <acceptance_criteria>NFT/OCI/DNS/probe behavior is production code backed, exact, rollback-safe and topology-bound; all four target forms and UDP translation are tested.</acceptance_criteria>
  <done>The 38 NFT/transaction/DNS and 4 OCI root failures are semantically closed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 53-05D2A-02: Reconcile ops API, validator and complete broad tests</name>
  <read_first>
    @modules/rustdesk-fleet/contracts/phase53-ops-api.json
    @modules/rustdesk-fleet/contracts/phase53-edge.json
    @modules/rustdesk-fleet/tools/rustdesk-ops-api.py
    @modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py
    @modules/rustdesk-fleet/tests/test_phase53_primary_edge.py
  </read_first>
  <files>modules/rustdesk-fleet/contracts/phase53-provider-manifest.json, modules/rustdesk-fleet/tools/rustdesk-ops-api.py, modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py, modules/rustdesk-fleet/tests/test_phase53_primary_edge.py</files>
  <behavior>
    - "Readiness reports external 34099/34100/34101 and backend native listeners as separate fields."
    - "Validator rejects one-of-three DNS proof, missing target/origin, native-public positive, or UDP mapped to the wrong backend."
    - "All 197 current test outcomes complete with pytest exit 0; expected xfail may remain only if already unrelated and explicit."
  </behavior>
  <action>
Make `rustdesk-ops-api.py` load the strict edge and ops contracts and report edge-forwarder semantics separately from backend listener ownership; retain authentication/redaction and no Pro/API Server claim per D-09..D-12. Make the validator require the topology receipt, exact edge/backend separation, three-record CAS/rollback parity, two origins multiplied by public IP plus three names, UDP 34100→21116 and native negatives. Update the provider manifest to expose disjoint atius-srv-1 edge and Horistic backend routes/capabilities. Reconcile genuine obsolete assertions in the broad test file without deleting adversarial coverage or converting failures to stored PASS.
  </action>
  <verify>
    <automated>omni srv1-ops resources run builds -- env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q modules/rustdesk-fleet/tests/test_phase53_primary_edge.py --disable-warnings</automated>
    <automated>git diff --check</automated>
  </verify>
  <acceptance_criteria>The exact broad test file exits 0, and production consumers—not only fixtures—encode the current topology and edge semantics.</acceptance_criteria>
  <done>The 8 ops API and 1 validator failures are closed and the broad Phase 53 test file is green.</done>
</task>

</tasks>

<threat_model>
| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|---|---|---|---|---|---|
| T53A-DIRECT | Elevation of Privilege | native public ports | critical | mitigate | ct original-destination/direct-native denies plus external negative probes. |
| T53A-NAT | Tampering/DoS | DNAT/forward/return | critical | mitigate | Exact owned chains, independent readback, backend source restriction and containment rollback. |
| T53A-DNS | Tampering | three Cloudflare records | critical | mitigate | One exact CAS snapshot/apply/readback/rollback unit. |
| T53A-PROBE | Spoofing | external proof | high | mitigate | Two origins x four target forms with UDP counter/socket correlation. |
| T53A-API | Information Disclosure | ops API | high | mitigate | Existing auth/redaction plus contract-derived separate edge/backend status. |
</threat_model>

## Multi-Source Coverage Audit

| Source | ID | Feature / requirement | Plan | Status |
|---|---|---|---|---|
| GOAL | Phase 53 | Stable hardened public primary | 05D2T-06 | COVERED |
| REQ | SRV-02 | Runtime/resources | 05D/05D2A/05F | COVERED |
| REQ | SRV-03 | Cross-host translation and native negatives | 05D2A/05F | COVERED |
| REQ | SRV-04 | Three DNS records and external proof | 05D2A/05E/05F | COVERED |
| REQ | SRV-06 | Restarts/boot | 05D2B/05F/06 | COVERED |
| REQ | OPS-01 | Authenticated/redacted ops API | 05D2A/05F/06 | COVERED |
| RESEARCH | nftables/OCI | DNAT/forward and conntrack original destination | 05D2A | COVERED |
| CONTEXT | D-01..D-15 | Runtime through rollback | 05D-06 | COVERED |
| CONTEXT | D-16, D-17 | Migration/stale authority | 05D2T/05D2B/05E | COVERED |
| CONTEXT | Deferred | Client/fleet/DR | excluded | EXCLUDED |

No source item is missing.

<verification>Both focused selectors and the exact complete Phase 53 test file run through the 20% builds governor; no live/provider mutation occurs.</verification>

<success_criteria>
1. The plan owns exactly nine files.
2. All 51 observed compatibility failures are closed at production semantics.
3. Broad test file exits zero before 05D2B.
</success_criteria>

<output>Create `53-05D2A-SUMMARY.md` and stop; do not dispatch 05D2B automatically.</output>
