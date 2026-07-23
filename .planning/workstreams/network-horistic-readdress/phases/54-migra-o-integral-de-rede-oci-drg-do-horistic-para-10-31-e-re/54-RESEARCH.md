# Phase 54 Research — OCI/DRG and edge renumbering

## Findings

- Live Horistic inventory has a secondary VNIC on `10.21.1.21` in VCN
  `10.21.0.0/16`, subnet `10.21.1.0/24`; the reserved public address
  `163.176.232.119` is currently attached to the older primary private IP
  `10.0.0.65`. Reuse therefore requires explicit reassignment to the new
  private-IP object after validation, not a text-only address edit.
- The safest transition is additive: add `10.31.0.0/16`, create
  `10.31.1.0/24`, attach a replacement VNIC/private IP `10.31.1.31`, run a
  dual-path window, then retire `.21`. The existing `oci-admin` OperationPlan
  supports CIDR/subnet/route/private/public-IP operations but does not expose a
  compute VNIC-attachment action; that step needs a gated OCI CLI/SDK/console
  operation or a separately reviewed extension.
- Existing address-plan readiness is blocked by overlapping `10.0.0.0/16`
  VCNs in other ATIUS profiles. The plan must not claim DRG readiness merely
  because a new Horistic subnet exists; every route preview must re-check
  overlap and `lpg_ready`.
- The active S23 WireGuard peer is `.9`; `.10` must be added and handshaken
  before `.9` is removed. S20's current BE3 static binding is `192.168.1.10`
  for MAC `72:EE:E2:ED:7B:8C`; `.11` needs collision/lease validation and a
  device-side profile import. WireGuard tunnel addresses are not BE3 LAN DHCP
  addresses.

## Official OCI constraints

Oracle documents that a VCN can receive an additional non-overlapping CIDR and
that a subnet CIDR must be contained by the VCN; VCN updates temporarily block
some subnet/route changes. Secondary VNICs are attached separately and require
OS configuration. A reserved public IP can be reassigned to a different
private-IP object only when the target has no public address. Removing a CIDR
is dependency-sensitive and may leave a required primary IPv4 block.

Sources:

- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/add_cidr_to_vcn.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/edit_vcn_cidr.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/add-ipv4-cidr.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingvnics_tasks-attach.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/reserved-public-ip-reassign.htm
- https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/remove_cidr_block_vcn.htm

## Implications

Plan execution must be explicitly gated, preserve the old path until two stable
validation passes, and classify inability to remove the old primary CIDR as a
documented OCI residual rather than a false complete migration.

## Validation architecture

The evidence artifact is append-only per wave: OCI readbacks and route matrices
are captured before/after each write; host/service probes are timestamped; DNS
checks record resolver, A/PTR/SOA and TTL; edge checks include direct origin and
Cloudflare; device changes require a device-side receipt. Two green passes are
required at least 15 minutes apart before retirement.

The execution contract is centralized in `54-VALIDATION-CONTRACT.md`: each
plan invokes the shared gate runner, emits a redacted/hashable receipt and the
next plan asserts the previous receipt before any mutation. Required
`UNKNOWN`/`BLOCK` results stop the wave; only the final phase aggregator may
advance STATE/ROADMAP completion.

## Open questions / execution gates

- The exact OCI OCID/profile and permission path for the replacement VNIC must be
  resolved in Wave 1; no plan may infer attachment from a preview-only result.
- The owner/public key of historical `peer11` must be resolved before `.11` can
  be assigned to S20.
- S20/S23 device-side import may require a human action; absence of a device
  receipt blocks retirement but does not justify removing encrypted fallback.
