# Phase 54 Research — Implementation-ready findings

## Resolved architecture

1. The live source topology is `10.21.0.0/16` / `10.21.1.0/24` / `10.21.1.21`; the requested result is an integral replacement by `10.31.0.0/16` / `10.31.1.0/24` / `10.31.1.31`.
2. OCI permits additive VCN CIDRs, but a phase that must remove the old primary block cannot accept a permanent primary-CIDR residual. Wave 3 must inspect the live VCN CIDR properties and dependencies. If the old block cannot be removed, create a replacement VCN and migrate subnet/VNIC/DRG/routes before retirement. This resolves the current-VCN versus replacement-VCN question without weakening the goal.
3. `peering.address_plan` is a supply-chain boundary owned by external `oci-admin`. Its current 10.21 output is a terminal precondition failure. A validated commit/receipt with the three literal 10.31 targets and no 10.21 target is required before any write.
4. Reserved public IP reassociation is asynchronous. Poll by the same `public_ip_ocid` until `lifetime=RESERVED`, `ip_address=163.176.232.119`, `lifecycle_state=ASSIGNED` and `private_ip_id` equals the new private-IP OCID. One bounded timeout is allowed; timeout/UNKNOWN blocks and the executor must not retry the mutation.
5. DRG correctness is two-sided: routes/security from ATIUS to 10.31 and explicit return routes/security from Horistic to `10.11.0.0/16`, `10.12.0.0/16`, `10.13.0.0/16` (or the exact live canonical source CIDRs) must be recorded per attachment/route-table OCID.

## Runtime and validator gap

The existing `modules/fleet-control-plane/scripts/phase54_network_gate.py` trusts `evidence.status == PASS`, validates only a target map for 54-05/54-06, and can emit PASS without executing or verifying plan-specific probes. It does not verify previous-gate lineage, approval hashes/expiry/anti-drift, OperationPlan receipts, public-IP OCID/state, builder commit, stable-read timestamps, or 10.21 absence. Its tests cover only three target-map cases.

Plan 01 therefore hardens the runner before live work:

- schema separates observed probe results from asserted summary;
- required checks are selected from a per-plan allowlist and each has command/adapter, timeout, exit code, observed value, timestamp and redaction result;
- only the runner derives `status`;
- `BLOCKED` input normalizes to canonical failure `BLOCK`;
- previous gate/evidence/OperationPlan hashes and expiry are recomputed;
- fixtures prove missing, forged, stale, tampered, partial and UNKNOWN states block.

## DNS dependency

Phase 47.1 is not currently proven complete. Phase 54 may consume its fresh `47.1-RELEASE-GATE.json`; otherwise it must create a self-contained DNS transaction against FreeIPA authority with exact forward and reverse objects, resolver/forwarder readbacks, backup and rollback. CoreDNS/AdGuard must not become a second authority. A/PTR/SOA/NS, FQDN, TTL/cache and NXDOMAIN behavior are release checks.

## Edge resolution

- S23 is already canonical at LAN `192.168.1.10`, WG `10.100.100.10`, MAC `64:1B:2F:C2:DC:A3`; preserve it and prove no mutation.
- S20 is LAN/WG `.9` with MAC `30:AB:6A:3C:96:D1`; target both to `.11`, classifying old lease `192.168.1.62`.
- Horistic WG target is `.31`; retain `.4` until both private and public SSH probes plus current handshake pass.
- Historical `10.71.*` has no current requirement or live evidence and is rejected.

## Official OCI references

- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/add_cidr_to_vcn.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingvnics_tasks-attach.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/reserved-public-ip-reassign.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/remove_cidr_block_vcn.htm

## Package Legitimacy Audit

No npm, pip or cargo package install is planned. Python changes use the standard library and existing pytest infrastructure.

## Validation Architecture

Nyquist mapping is defined in `54-VALIDATION.md`; execution semantics and gate schema are defined in `54-VALIDATION-CONTRACT.md`. Every plan owns a focused automated gate and each subsequent plan recomputes the previous receipt lineage before doing work.
