# Phase 52-01 preflight evidence

Status: `PASS` — host rollback artifacts and a fresh OCI volume snapshot pass.
The only authorized mutation was creation of the incremental boot-volume
backup; no network, DNS, WireGuard, BE3, host, service, VNIC, route, DRG, or
public-IP mutation was attempted.

Captured: `2026-07-23T08:20:00Z` (UTC)

## Human gate and access

The required signal `APROVADO: phase52-wave0` was received. SRV-1 access used
only `ubuntu@10.100.100.1` through WireGuard. Horistic authenticated readback
passed as the canonical user `horistic`, with `IdentitiesOnly=yes` and the
dedicated identity, on both `10.21.1.21` and fallback `10.100.100.4`. No public
IP path was used.

## OCI/DRG inventory

Read-only `inventory.get` loaded all four explicit profiles (`atius1`,
`atius2`, `atius3`, `horistic`) without partial results. Horistic remains on
VCN `10.21.0.0/16`, subnet `10.21.1.0/24`, with the secondary VNIC address
`10.21.1.21`. Reserved public IP `163.176.232.119` remains
`RESERVED`/`ASSIGNED` to the old primary private address `10.0.0.65`; the
machine-readable evidence records its public-IP and private-IP IDs.

The DRG readback reports a central DRG and attached states for all four
profiles, with no collection blocker. This is inventory only; no OperationPlan
was applied.

## Verified host backups

- Horistic:
  `/var/backups/omni-srv-admin/phase52/20260723T081521Z-horistic`
  contains `SHA256SUMS`, `checksum-verify.txt`, and `restore-staging`.
  Checksum-manifest SHA-256:
  `7fa4d4ab034309917081ea203b3d6ed17b39375644d62501e8d0c0470a5a70b1`.
  Two archives restored into staging with 228 entries.
- SRV-1:
  `/var/backups/omni-srv-admin/phase52/20260723T081521Z-srv1`
  contains `SHA256SUMS`, `checksum-verify.txt`, and `restore-staging`.
  Checksum-manifest SHA-256:
  `f24f8192637a95ce58ec1232fc8278284d26cfde479df6f30cd08a09038c48f8`.
  Five archives restored into staging with 582 entries.

These exports cover the present configuration/inventory files found for
routes, firewall, listeners, WireGuard, Apache, K3s and manifests on the two
rollback-critical hosts. They do not substitute for an OCI volume snapshot.

## Wave 0 release

The fresh OCI backup is `AVAILABLE` and associated with the applied
OperationPlan. The Wave 0 runner can therefore return `PASS` and release the
52-02 gate.
